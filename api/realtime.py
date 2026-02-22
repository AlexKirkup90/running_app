from __future__ import annotations

import json
from collections import defaultdict
from typing import Any

from fastapi import WebSocket


class ConnectionManager:
    def __init__(self) -> None:
        self.connections: dict[str, set[WebSocket]] = defaultdict(set)

    async def connect(self, channel: str, websocket: WebSocket) -> None:
        await websocket.accept()
        self.connections[channel].add(websocket)

    def disconnect(self, channel: str, websocket: WebSocket) -> None:
        if channel in self.connections:
            self.connections[channel].discard(websocket)
            if not self.connections[channel]:
                del self.connections[channel]

    async def broadcast(self, channel: str, event: str, payload: dict[str, Any]) -> None:
        if channel not in self.connections:
            return
        msg = json.dumps({"event": event, "payload": payload}, default=str)
        stale: list[WebSocket] = []
        for ws in self.connections[channel]:
            try:
                await ws.send_text(msg)
            except Exception:
                stale.append(ws)
        for ws in stale:
            self.disconnect(channel, ws)


manager = ConnectionManager()
