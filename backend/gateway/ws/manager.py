import json
from fastapi import WebSocket


class ConnectionManager:
    def __init__(self):
        self._connections: dict[tuple[str, str], list[WebSocket]] = {}

    async def connect(self, session_id: str, channel: str, ws: WebSocket):
        await ws.accept()
        self._connections.setdefault((session_id, channel), []).append(ws)

    def disconnect(self, session_id: str, channel: str, ws: WebSocket):
        key = (session_id, channel)
        conns = self._connections.get(key, [])
        if ws in conns:
            conns.remove(ws)
        if not conns and key in self._connections:
            self._connections.pop(key)

    async def broadcast(self, session_id: str, channel: str, event: dict):
        payload = json.dumps(event, ensure_ascii=False)
        for ws in list(self._connections.get((session_id, channel), [])):
            await ws.send_text(payload)


manager = ConnectionManager()
