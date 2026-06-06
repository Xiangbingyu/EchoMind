from fastapi import APIRouter
from pydantic import BaseModel
from gateway.ws.manager import manager
from gateway.db.base import AsyncSessionLocal
from gateway.models.models import Message

router = APIRouter(prefix="/internal")


class CallbackPayload(BaseModel):
    session_id: str
    type: str  # agent.token / agent.done / task.status / proposal.ready / sandbox.log
    data: str


@router.post("/callback")
async def agent_callback(payload: CallbackPayload):
    await manager.broadcast(payload.session_id, {"type": payload.type, "data": payload.data})

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
