"""
LoanFlow – Event Bus Abstraction.
Default: Redis Streams (Upstash compatible).
Fallback: Postgres events table (set USE_PG_EVENTS=true).
Swappable for Kafka/MSK later.
"""
import json
import asyncio
import uuid
from datetime import datetime, timezone
from typing import Callable, Awaitable
from abc import ABC, abstractmethod


class Event:
    """Standard event envelope."""
    def __init__(self, event_type: str, payload: dict, source: str = ""):
        self.event_id = str(uuid.uuid4())
        self.event_type = event_type
        self.payload = payload
        self.source = source
        self.timestamp = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> dict:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "payload": json.dumps(self.payload),
            "source": self.source,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Event":
        evt = cls(
            event_type=data.get("event_type", ""),
            payload=json.loads(data.get("payload", "{}")),
            source=data.get("source", ""),
        )
        evt.event_id = data.get("event_id", evt.event_id)
        evt.timestamp = data.get("timestamp", evt.timestamp)
        return evt


EventHandler = Callable[[Event], Awaitable[None]]


class EventBus(ABC):
    """Abstract event bus interface."""

    @abstractmethod
    async def publish(self, event: Event) -> None:
        ...

    @abstractmethod
    async def subscribe(self, event_type: str, handler: EventHandler, group: str = "default") -> None:
        ...

    @abstractmethod
    async def start_consuming(self) -> None:
        ...

    @abstractmethod
    async def stop(self) -> None:
        ...


class RedisStreamEventBus(EventBus):
    """Event bus implemented with Redis Streams (Upstash compatible)."""

    def __init__(self, redis_client):
        self._redis = redis_client
        self._handlers: dict[str, list[tuple[EventHandler, str]]] = {}
        self._running = False
        self._stream_prefix = "loanflow:events:"

    async def publish(self, event: Event) -> None:
        stream_key = f"{self._stream_prefix}{event.event_type}"
        await self._redis.xadd(stream_key, event.to_dict())

    async def subscribe(self, event_type: str, handler: EventHandler, group: str = "default") -> None:
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        self._handlers[event_type].append((handler, group))

        # Create consumer group if not exists
        stream_key = f"{self._stream_prefix}{event_type}"
        try:
            await self._redis.xgroup_create(stream_key, group, id="0", mkstream=True)
        except Exception:
            pass  # Group already exists

    async def start_consuming(self) -> None:
        self._running = True
        consumer_name = f"consumer-{uuid.uuid4().hex[:8]}"

        while self._running:
            for event_type, handlers in self._handlers.items():
                stream_key = f"{self._stream_prefix}{event_type}"
                for handler, group in handlers:
                    try:
                        messages = await self._redis.xreadgroup(
                            group, consumer_name,
                            {stream_key: ">"},
                            count=10, block=100,
                        )
                        for _stream, entries in messages:
                            for msg_id, data in entries:
                                event = Event.from_dict(data)
                                await handler(event)
                                await self._redis.xack(stream_key, group, msg_id)
                    except Exception:
                        pass
            await asyncio.sleep(0.1)

    async def stop(self) -> None:
        self._running = False


class PostgresEventBus(EventBus):
    """Fallback event bus using a Postgres 'events' table (for local dev / testing)."""

    def __init__(self, session_factory):
        self._session_factory = session_factory
        self._handlers: dict[str, list[EventHandler]] = {}
        self._running = False
        self._last_id = 0

    async def publish(self, event: Event) -> None:
        from sqlalchemy import text
        async with self._session_factory() as session:
            await session.execute(
                text(
                    "INSERT INTO events (event_id, event_type, payload, source, created_at) "
                    "VALUES (:eid, :etype, :payload, :source, NOW())"
                ),
                {
                    "eid": event.event_id,
                    "etype": event.event_type,
                    "payload": json.dumps(event.payload),
                    "source": event.source,
                },
            )
            await session.commit()

    async def subscribe(self, event_type: str, handler: EventHandler, group: str = "default") -> None:
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        self._handlers[event_type].append(handler)

    async def start_consuming(self) -> None:
        from sqlalchemy import text
        self._running = True
        while self._running:
            async with self._session_factory() as session:
                for event_type, handlers in self._handlers.items():
                    result = await session.execute(
                        text(
                            "SELECT id, event_id, event_type, payload, source, created_at "
                            "FROM events WHERE id > :last_id AND event_type = :etype "
                            "ORDER BY id LIMIT 50"
                        ),
                        {"last_id": self._last_id, "etype": event_type},
                    )
                    for row in result.mappings():
                        event = Event(
                            event_type=row["event_type"],
                            payload=json.loads(row["payload"]),
                            source=row["source"],
                        )
                        event.event_id = row["event_id"]
                        for handler in handlers:
                            await handler(event)
                        self._last_id = max(self._last_id, row["id"])
            await asyncio.sleep(1)

    async def stop(self) -> None:
        self._running = False


def create_event_bus(use_postgres: bool = False, **kwargs) -> EventBus:
    """Factory: create the appropriate event bus implementation."""
    if use_postgres:
        return PostgresEventBus(session_factory=kwargs["session_factory"])
    return RedisStreamEventBus(redis_client=kwargs["redis_client"])
