import httpx
from agentscope.message import UserMsg
from agentscope.state._state import AgentState
from sqlalchemy import select

from agent_service.agents.code_agent import build_code_agent
from agent_service.config import GATEWAY_CALLBACK_URL
from agent_service.runtime.events import extract_text_delta
from agent_service.runtime.memory import build_agent_state
from gateway.db.base import AsyncSessionLocal
from gateway.models.models import Message


async def load_session_history(*, session_id: str) -> list[dict]:
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Message)
            .where(Message.session_id == session_id)
            .order_by(Message.created_at)
        )
        messages = result.scalars().all()

    return [
        {"role": message.role, "content": message.content}
        for message in messages
        if message.role in {"system", "user", "agent"}
    ]


async def run_agent(*, session_id: str, content: str) -> dict:
    history = await load_session_history(session_id=session_id)
    agent_state = build_agent_state(history=history) if history else None
    agent = build_code_agent(state=agent_state)
    full_reply = []

    async with httpx.AsyncClient() as client:
        async for event in agent.reply_stream(UserMsg("user", content)):
            token = extract_text_delta(event)
            if not token:
                continue
            full_reply.append(token)
            await client.post(
                GATEWAY_CALLBACK_URL,
                json={
                    "session_id": session_id,
                    "type": "agent.token",
                    "data": token,
                },
            )
        await client.post(
            GATEWAY_CALLBACK_URL,
            json={
                "session_id": session_id,
                "type": "agent.done",
                "data": "".join(full_reply),
            },
        )

    return {"ok": True}
