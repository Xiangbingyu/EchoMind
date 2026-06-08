import httpx
from agentscope.message import UserMsg

from agent_service.config import (
    GATEWAY_CALLBACK_URL,
    GATEWAY_MESSAGES_URL_TEMPLATE,
    GATEWAY_PROJECT_URL_TEMPLATE,
    GATEWAY_SESSION_URL_TEMPLATE,
    SESSION_MAX_NON_SYSTEM_MESSAGES,
)
from agent_service.runtime.agentscope_runner import build_runtime_agent
from agent_service.config import (
    GATEWAY_CALLBACK_URL,
    GATEWAY_MESSAGES_URL_TEMPLATE,
    SESSION_MAX_NON_SYSTEM_MESSAGES,
)
from agent_service.runtime.events import build_status_callback, extract_text_delta
from agent_service.runtime.memory import build_agent_state, trim_history
from agent_service.runtime.session_runtime_manager import runtime_manager


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


async def load_session_snapshot(*, session_id: str) -> dict:
    url = GATEWAY_SESSION_URL_TEMPLATE.format(session_id=session_id)
    async with httpx.AsyncClient() as client:
        response = await client.get(url)
        response.raise_for_status()
        return response.json()


async def load_project_snapshot(*, project_id: str) -> dict:
    url = GATEWAY_PROJECT_URL_TEMPLATE.format(project_id=project_id)
    async with httpx.AsyncClient() as client:
        response = await client.get(url)
        response.raise_for_status()
        return response.json()


async def ensure_session_runtime(*, session_id: str):
    session_snapshot = await load_session_snapshot(session_id=session_id)
    project_snapshot = await load_project_snapshot(
        project_id=session_snapshot['project_workspace_id']
    )
    return await runtime_manager.ensure_runtime(
        session_id=session_id,
        workspace_id=session_snapshot['workspace_id'],
        project_workspace_id=session_snapshot['project_workspace_id'],
        workspace_root=project_snapshot.get('path') or '',
    )


async def run_agent(*, session_id: str, content: str) -> dict:
    async with httpx.AsyncClient() as client:
        await client.post(
            GATEWAY_CALLBACK_URL,
            json=build_status_callback(session_id=session_id, status="running"),
        )
        try:
            runtime = await ensure_session_runtime(session_id=session_id)
            runtime.status = 'running'
            runtime.agent_status = 'running'
            runtime.sandbox_status = 'running'
            runtime.workspace_tree = [
                {'path': runtime.workspace_root or '.', 'type': 'root'},
                {'path': 'conversation.txt', 'type': 'file'},
            ]
            await client.post(
                GATEWAY_CALLBACK_URL,
                json={
                    'session_id': session_id,
                    'type': 'agent.status',
                    'data': {'status': runtime.agent_status, 'last_error': runtime.last_error},
                },
            )
            await client.post(
                GATEWAY_CALLBACK_URL,
                json={
                    'session_id': session_id,
                    'type': 'sandbox.status',
                    'data': {'status': runtime.sandbox_status},
                },
            )
            await client.post(
                GATEWAY_CALLBACK_URL,
                json={
                    'session_id': session_id,
                    'type': 'workspace.tree.updated',
                    'data': runtime.workspace_tree,
                },
            )
            history = await load_session_history(session_id=session_id)
            trimmed_history = trim_history(
                history=history,
                max_non_system_messages=SESSION_MAX_NON_SYSTEM_MESSAGES,
            )
            agent = await build_runtime_agent(history=trimmed_history)
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
            runtime.status = 'ready'
            runtime.agent_status = 'idle'
            runtime.sandbox_status = 'ready'
            await client.post(
                GATEWAY_CALLBACK_URL,
                json={
                    'session_id': session_id,
                    'type': 'agent.status',
                    'data': {'status': runtime.agent_status, 'last_error': runtime.last_error},
                },
            )
            await client.post(
                GATEWAY_CALLBACK_URL,
                json={
                    'session_id': session_id,
                    'type': 'sandbox.status',
                    'data': {'status': runtime.sandbox_status},
                },
            )
            await client.post(
                GATEWAY_CALLBACK_URL,
                json=build_status_callback(session_id=session_id, status="completed"),
            )
            return {"ok": True}
        except Exception as exc:
            runtime = runtime_manager.get_runtime(session_id)
            if runtime is not None:
                runtime.status = 'error'
                runtime.agent_status = 'error'
                runtime.sandbox_status = 'error'
                runtime.last_error = str(exc)
                await client.post(
                    GATEWAY_CALLBACK_URL,
                    json={
                        'session_id': session_id,
                        'type': 'agent.status',
                        'data': {'status': runtime.agent_status, 'last_error': runtime.last_error},
                    },
                )
            await client.post(
                GATEWAY_CALLBACK_URL,
                json=build_status_callback(session_id=session_id, status=f"failed: {exc}"),
            )
            return {"ok": False, "error": str(exc)}
