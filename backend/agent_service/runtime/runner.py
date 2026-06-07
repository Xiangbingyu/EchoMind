import httpx
from agentscope.message import UserMsg

from agent_service.agents.code_agent import build_code_agent
from agent_service.config import (
    GATEWAY_CALLBACK_URL,
    GATEWAY_MESSAGES_URL_TEMPLATE,
    SESSION_MAX_NON_SYSTEM_MESSAGES,
)
from agent_service.runtime.events import build_status_callback, extract_text_delta
from agent_service.runtime.memory import build_agent_state, trim_history


async def load_session_history(*, session_id: str) -> list[dict]:
    url = GATEWAY_MESSAGES_URL_TEMPLATE.format(session_id=session_id)
    async with httpx.AsyncClient() as client:
        response = await client.get(url)
        response.raise_for_status()
        messages = response.json()

    return [
        {"role": message["role"], "content": message.get("content", "")}
        for message in messages
        if message.get("role") in {"system", "user", "agent"}
    ]


async def run_agent(*, session_id: str, content: str) -> dict:
    async with httpx.AsyncClient() as client:
        await client.post(
            GATEWAY_CALLBACK_URL,
            json=build_status_callback(session_id=session_id, status="running"),
        )
        try:
            history = await load_session_history(session_id=session_id)
            trimmed_history = trim_history(
                history=history,
                max_non_system_messages=SESSION_MAX_NON_SYSTEM_MESSAGES,
            )
            agent_state = build_agent_state(history=trimmed_history) if trimmed_history else None
            agent = build_code_agent(state=agent_state)
            full_reply = []

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
            await client.post(
                GATEWAY_CALLBACK_URL,
                json=build_status_callback(session_id=session_id, status="completed"),
            )
            return {"ok": True}
        except Exception as exc:
            await client.post(
                GATEWAY_CALLBACK_URL,
                json=build_status_callback(session_id=session_id, status=f"failed: {exc}"),
            )
            return {"ok": False, "error": str(exc)}
