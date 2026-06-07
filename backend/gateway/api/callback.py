from fastapi import APIRouter
from pydantic import BaseModel
from typing import Any
from gateway.ws.manager import manager
from gateway.db.base import AsyncSessionLocal
from gateway.models.models import Message

router = APIRouter(prefix="/internal")


class CallbackPayload(BaseModel):
    session_id: str
    type: str  # agent.token / agent.done / task.status / proposal.ready / sandbox.log
    data: Any


CHAT_EVENTS = {
    "message.history.sync",
    "message.created",
    "agent.token",
    "agent.done",
    "chat.status",
    "task.status",
    "error",
}

WORKSPACE_EVENTS = {
    "workspace.snapshot",
    "workspace.tree.snapshot",
    "plan.snapshot",
    "sandbox.snapshot",
    "agent.snapshot",
    "workspace.tree.updated",
    "plan.updated",
    "sandbox.status",
    "agent.status",
    "tool.status",
    "test.status",
    "task.status",
    "error",
}


@router.post("/callback")
async def agent_callback(payload: CallbackPayload):
    event = {"type": payload.type, "data": payload.data}
    if payload.type in CHAT_EVENTS:
        await manager.broadcast(payload.session_id, "chat", event)
    if payload.type in WORKSPACE_EVENTS:
        await manager.broadcast(payload.session_id, "workspace", event)

    if payload.type == "agent.done":
        async with AsyncSessionLocal() as db:
            msg = Message(
                session_id=payload.session_id,
                role="agent",
                content=payload.data,
                content_type="text",
            )
            db.add(msg)
            await db.commit()

    return {"ok": True}
