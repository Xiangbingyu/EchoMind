import json
from fastapi import WebSocket
from starlette.websockets import WebSocketDisconnect


class ConnectionManager:
    def __init__(self):
        self._connections: dict[str, list[WebSocket]] = {}

    async def connect(self, session_id: str, ws: WebSocket):
        await ws.accept()
        self._connections.setdefault(session_id, []).append(ws)

    def disconnect(self, session_id: str, ws: WebSocket):
        conns = self._connections.get(session_id, [])
        if ws in conns:
            conns.remove(ws)
        if not conns and session_id in self._connections:
            self._connections.pop(session_id)

    async def broadcast(self, session_id: str, event: dict):
        payload = json.dumps(event, ensure_ascii=False)
        for ws in list(self._connections.get(session_id, [])):
            try:
                await ws.send_text(payload)
            except WebSocketDisconnect:
                self.disconnect(session_id, ws)


manager = ConnectionManager()
