from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from gateway.db.base import AsyncSessionLocal
from gateway.models.models import Message
from gateway.ws.manager import manager
import httpx
from gateway.config import AGENT_SERVICE_URL

router = APIRouter()


async def _dispatch_agent_run(*, session_id: str, text: str):
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


async def _send_chat_snapshot(*, session_id: str, ws: WebSocket):
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{AGENT_SERVICE_URL}/runtime/{session_id}/chat-snapshot",
            timeout=5,
        )
        response.raise_for_status()
        await ws.send_json(response.json())


async def _send_workspace_snapshot(*, session_id: str, ws: WebSocket):
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{AGENT_SERVICE_URL}/runtime/{session_id}/workspace-snapshot",
            timeout=5,
        )
        response.raise_for_status()
        for event in response.json():
            await ws.send_json(event)


@router.websocket("/ws/session/{session_id}")
async def session_ws(session_id: str, ws: WebSocket):
    try:
        await manager.connect(session_id, ws)
        await _send_chat_snapshot(session_id=session_id, ws=ws)
        await _send_workspace_snapshot(session_id=session_id, ws=ws)
        while True:
            text = await ws.receive_text()
            await _dispatch_agent_run(session_id=session_id, text=text)
    except WebSocketDisconnect:
        manager.disconnect(session_id, ws)
