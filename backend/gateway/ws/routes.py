from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from gateway.db.base import AsyncSessionLocal
from gateway.models.models import Message
from gateway.ws.manager import manager
import httpx
from gateway.config import AGENT_SERVICE_URL

router = APIRouter()


@router.websocket("/ws/session/{session_id}")
async def session_ws(session_id: str, ws: WebSocket):
    await manager.connect(session_id, ws)
    try:
        while True:
            text = await ws.receive_text()
            async with AsyncSessionLocal() as db:
                msg = Message(session_id=session_id, role="user", content=text, content_type="text")
                db.add(msg)
                await db.commit()

            async with httpx.AsyncClient() as client:
                try:
                    await client.post(
                        f"{AGENT_SERVICE_URL}/run",
                        json={"session_id": session_id, "content": text},
                        timeout=5,
                    )
                except httpx.RequestError:
                    await manager.broadcast(session_id, {"type": "error", "data": "agent_service unavailable"})
    except WebSocketDisconnect:
        manager.disconnect(session_id, ws)
