"""
LoanFlow – Real-time Notification Service (FastAPI + WebSockets).
Features:
- Consumes domain events (state changes, repayments, overdue, KYC, fraud).
- Dispatches stub Email and SMS notifications (structured logs / delivery mock).
- Pushes real-time in-app alerts to connected clients over WebSockets.
- Exposes REST endpoints for querying notification history and ad-hoc notification dispatch.
"""
import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from shared.config import get_settings
from shared.redis_client import get_redis
from shared.event_bus import create_event_bus

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("notification_service")

settings = get_settings()

app = FastAPI(title="LoanFlow Notification Service", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ═══════════════════════ Schemas ═══════════════════════

class NotificationPayload(BaseModel):
    user_id: Optional[str] = "all"
    recipient_email: Optional[str] = None
    recipient_phone: Optional[str] = None
    title: str
    message: str
    category: str = "INFO"  # INFO, ALERT, SUCCESS, WARNING
    metadata: Optional[dict] = None


class NotificationItem(BaseModel):
    id: str
    user_id: str
    title: str
    message: str
    category: str
    timestamp: str
    channel: str  # WEBSOCKET, EMAIL, SMS
    delivered: bool = True


# In-memory history for quick UI feed
_notification_history: List[dict] = [
    {
        "id": "notif-001",
        "user_id": "all",
        "title": "Welcome to LoanFlow",
        "message": "LoanFlow enterprise lending platform initialized and online.",
        "category": "SUCCESS",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "channel": "SYSTEM",
        "delivered": True,
    }
]


# ═══════════════════════ Connection Manager ═══════════════════════

class ConnectionManager:
    """Manages active WebSocket connections for push notifications."""
    def __init__(self):
        self.active_connections: Dict[str, List[WebSocket]] = {}
        self.broadcast_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket, user_id: str = "broadcast"):
        await websocket.accept()
        if user_id == "broadcast" or not user_id:
            self.broadcast_connections.append(websocket)
        else:
            if user_id not in self.active_connections:
                self.active_connections[user_id] = []
            self.active_connections[user_id].append(websocket)
        logger.info(f"WebSocket client connected: user={user_id}")

    def disconnect(self, websocket: WebSocket, user_id: str = "broadcast"):
        if websocket in self.broadcast_connections:
            self.broadcast_connections.remove(websocket)
        if user_id in self.active_connections and websocket in self.active_connections[user_id]:
            self.active_connections[user_id].remove(websocket)
            if not self.active_connections[user_id]:
                del self.active_connections[user_id]
        logger.info(f"WebSocket client disconnected: user={user_id}")

    async def send_personal_message(self, message: dict, user_id: str):
        if user_id in self.active_connections:
            disconnected = []
            for connection in self.active_connections[user_id]:
                try:
                    await connection.send_json(message)
                except Exception:
                    disconnected.append(connection)
            for d in disconnected:
                self.disconnect(d, user_id)

    async def broadcast(self, message: dict):
        dead_broadcast = []
        for connection in self.broadcast_connections:
            try:
                await connection.send_json(message)
            except Exception:
                dead_broadcast.append(connection)
        for d in dead_broadcast:
            if d in self.broadcast_connections:
                self.broadcast_connections.remove(d)

        # Also send to all specific user channels
        for uid, conns in list(self.active_connections.items()):
            dead_user = []
            for c in conns:
                try:
                    await c.send_json(message)
                except Exception:
                    dead_user.append(c)
            for d in dead_user:
                self.disconnect(d, uid)


manager = ConnectionManager()


# ═══════════════════════ Stub Delivery Channels ═══════════════════════

def send_stub_email(recipient: str, subject: str, body: str):
    """Stub email delivery log."""
    logger.info(
        f"\n[EMAIL DISPATCH STUB]\n"
        f"  To: {recipient}\n"
        f"  Subject: [LoanFlow] {subject}\n"
        f"  Body: {body}\n"
        f"  Status: SENT (Mock Provider SMTP 250 OK)\n"
    )


def send_stub_sms(phone: str, message: str):
    """Stub SMS delivery log."""
    logger.info(
        f"\n[SMS DISPATCH STUB]\n"
        f"  To: {phone}\n"
        f"  Message: {message}\n"
        f"  Status: DELIVERED (Mock Gateway SID: {uuid.uuid4().hex[:12]})\n"
    )


# ═══════════════════════ Endpoints ═══════════════════════

@app.websocket("/ws/notifications/{user_id}")
async def websocket_user_notifications(websocket: WebSocket, user_id: str):
    await manager.connect(websocket, user_id)
    try:
        while True:
            # Keep-alive heartbeat & client ack
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        manager.disconnect(websocket, user_id)


@app.websocket("/ws/notifications")
async def websocket_broadcast_notifications(websocket: WebSocket):
    await manager.connect(websocket, "broadcast")
    try:
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        manager.disconnect(websocket, "broadcast")


@app.post("/notify", response_model=dict)
async def dispatch_notification(payload: NotificationPayload):
    """
    Dispatch a notification across channels:
    1. In-app WebSocket real-time push
    2. Stub Email dispatch (if recipient_email provided or customer alert)
    3. Stub SMS dispatch (if recipient_phone provided or urgent alert)
    """
    notif_id = f"notif-{uuid.uuid4().hex[:8]}"
    now_iso = datetime.now(timezone.utc).isoformat()

    record = {
        "id": notif_id,
        "user_id": payload.user_id or "all",
        "title": payload.title,
        "message": payload.message,
        "category": payload.category,
        "timestamp": now_iso,
        "metadata": payload.metadata or {},
        "channel": "WEBSOCKET",
        "delivered": True,
    }
    _notification_history.insert(0, record)
    if len(_notification_history) > 100:
        _notification_history.pop()

    # 1. Real-time WebSocket push
    if payload.user_id and payload.user_id != "all":
        await manager.send_personal_message(record, payload.user_id)
    else:
        await manager.broadcast(record)

    # 2. Stub Email
    email_dest = payload.recipient_email or (f"{payload.user_id}@loanflow.internal" if payload.user_id != "all" else "team@loanflow.internal")
    send_stub_email(email_dest, payload.title, payload.message)

    # 3. Stub SMS
    sms_dest = payload.recipient_phone or "+91-9876543210"
    send_stub_sms(sms_dest, f"{payload.title}: {payload.message}")

    return {
        "status": "dispatched",
        "notification_id": notif_id,
        "channels": ["WEBSOCKET", "STUB_EMAIL", "STUB_SMS"],
        "timestamp": now_iso,
    }


@app.get("/notifications/history", response_model=List[dict])
async def get_notification_history(user_id: Optional[str] = None):
    """Get recent notifications for client in-app notification center."""
    if user_id:
        return [n for n in _notification_history if n["user_id"] in (user_id, "all")]
    return _notification_history[:50]


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "service": "notification",
        "active_websockets": len(manager.broadcast_connections) + sum(len(c) for c in manager.active_connections.values()),
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8007)
