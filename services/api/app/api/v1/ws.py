"""WebSocket endpoint for live events (inspection completed, agent status, ...).

In-memory connection manager for single-process deployments; a Redis pub/sub
adapter can replace notify_org without changing call sites (documented).
"""
from __future__ import annotations

import jwt
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.config import settings
from app.core.metrics import ACTIVE_WS_CONNECTIONS

ws_router = APIRouter()


class ConnectionManager:
    def __init__(self):
        self._by_org: dict[int, set[WebSocket]] = {}

    def connect(self, org_id: int, ws: WebSocket) -> None:
        self._by_org.setdefault(org_id, set()).add(ws)
        ACTIVE_WS_CONNECTIONS.inc()

    def disconnect(self, org_id: int, ws: WebSocket) -> None:
        self._by_org.get(org_id, set()).discard(ws)
        ACTIVE_WS_CONNECTIONS.dec()

    async def broadcast(self, org_id: int, payload: dict) -> None:
        dead: list[WebSocket] = []
        for ws in list(self._by_org.get(org_id, set())):
            try:
                await ws.send_json(payload)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(org_id, ws)


manager = ConnectionManager()


async def notify_org(org_id: int, payload: dict) -> None:
    """Fire-and-forget helper callable from background tasks."""
    await manager.broadcast(org_id, payload)


def _token_ok(token: str | None) -> bool:
    if not token:
        return False
    try:
        jwt.decode(token, settings.secret_key, algorithms=["HS256"])
        return True
    except jwt.PyJWTError:
        return False


@ws_router.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    token = ws.query_params.get("token")
    if not _token_ok(token):
        await ws.close(code=4401)
        return
    org_id = int(jwt.decode(token, settings.secret_key, algorithms=["HS256"])["org_id"])
    await ws.accept()
    manager.connect(org_id, ws)
    try:
        while True:
            msg = await ws.receive_json()
            if msg.get("type") == "ping":
                await ws.send_json({"type": "pong"})
    except WebSocketDisconnect:
        manager.disconnect(org_id, ws)
    except Exception:
        manager.disconnect(org_id, ws)
