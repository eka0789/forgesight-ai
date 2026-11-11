"""WebSocket endpoint: mounted + auth-gated (regression guard: the router was
once imported but never included — found by lint audit)."""
from __future__ import annotations

import jwt


def test_ws_rejects_missing_token(client):
    from starlette.testclient import WebSocketDisconnect

    try:
        with client.websocket_connect("/api/v1/ws") as ws:
            ws.receive_json()
        raise AssertionError("connection should have been rejected")
    except WebSocketDisconnect as e:
        assert e.code == 4401


def test_ws_rejects_tampered_token(client):
    from starlette.testclient import WebSocketDisconnect

    bad = jwt.encode({"sub": "1", "org_id": 1}, "not-the-secret", algorithm="HS256")
    try:
        with client.websocket_connect(f"/api/v1/ws?token={bad}") as ws:
            ws.receive_json()
        raise AssertionError("connection should have been rejected")
    except WebSocketDisconnect as e:
        assert e.code == 4401


def test_ws_ping_pong_with_valid_token(client, org1):
    token = org1["access_token"]
    with client.websocket_connect(f"/api/v1/ws?token={token}") as ws:
        ws.send_json({"type": "ping"})
        assert ws.receive_json() == {"type": "pong"}
