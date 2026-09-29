"""
LoanFlow – Upstash Redis client.
Uses the UPSTASH_REDIS_URL for connections (rediss:// for TLS).
"""
import redis.asyncio as aioredis
from .config import get_settings

settings = get_settings()

redis_client = aioredis.from_url(
    settings.upstash_redis_url,
    decode_responses=True,
    socket_timeout=5,
    retry_on_timeout=True,
)


async def get_redis() -> aioredis.Redis:
    """FastAPI dependency – returns the shared Redis client."""
    return redis_client
