"""
EchoMind backend integration tests.
Run: python test_all.py
Requires: gateway on :8000, agent_service on :8001
Agent service now uses AgentScope. A valid model environment such as
OPENAI_API_KEY / OPENAI_MODEL is required for websocket message tests.
"""
import asyncio
import httpx
import json

BASE = "http://localhost:8000"
PASS = "\033[92mPASS\033[0m"
FAIL = "\033[91mFAIL\033[0m"


def check(label, condition, detail=""):
    status = PASS if condition else FAIL
    print(f"  [{status}] {label}" + (f" — {detail}" if detail else ""))
    return condition


async def wait_for_done(ws, timeout: int = 15) -> str:
    for _ in range(30):
        msg = await asyncio.wait_for(ws.receive_text(), timeout=timeout)
        event = json.loads(msg)
        if event["type"] == "agent.done":
            return event["data"]
    return ""


async def test_health():
    print("\n=== Health ===")
    async with httpx.AsyncClient() as c:
        r = await c.get(f"{BASE}/health")
        check("gateway /health 200", r.status_code == 200)
        check("service=gateway", r.json().get("service") == "gateway")

        r2 = await c.get("http://localhost:8001/health")
        check("agent_service /health 200", r2.status_code == 200)
        check("service=agent_service", r2.json().get("service") == "agent_service")


async def test_rest() -> tuple[str, str, str]:
    print("\n=== REST API ===")
    async with httpx.AsyncClient() as c:
        r = await c.post(f"{BASE}/api/workspaces", json={"name": "测试工作区"})
        check("POST /api/workspaces 200", r.status_code == 200)
        ws_id = r.json()["id"]
        check("workspace has id", bool(ws_id))

        r = await c.get(f"{BASE}/api/workspaces")
        check("GET /api/workspaces returns list", isinstance(r.json(), list))

        r = await c.post(f"{BASE}/api/workspaces/{ws_id}/projects", json={"name": "proj1"})
        check("POST /api/workspaces/{id}/projects 200", r.status_code == 200)
        proj_id = r.json()["id"]

        r = await c.get(f"{BASE}/api/workspaces/{ws_id}/projects")
        check("GET /api/workspaces/{id}/projects returns list", isinstance(r.json(), list))

        r = await c.post(f"{BASE}/api/sessions", json={
            "project_workspace_id": proj_id,
            "type": "group",
            "title": "测试会话",
        })
        check("POST /api/sessions 200", r.status_code == 200)
        sess_id = r.json()["id"]

        r = await c.get(f"{BASE}/api/sessions/{sess_id}")
        check("GET /api/sessions/{id} 200", r.status_code == 200)

        r = await c.post(f"{BASE}/api/agents", json={"name": "CodeAgent", "type": "code"})
        check("POST /api/agents 200", r.status_code == 200)

        r = await c.get(f"{BASE}/api/agents")
        check("GET /api/agents returns list", isinstance(r.json(), list))

    return ws_id, proj_id, sess_id


async def create_session(project_id: str, title: str) -> str:
    async with httpx.AsyncClient() as c:
        r = await c.post(f"{BASE}/api/sessions", json={
            "project_workspace_id": project_id,
            "type": "group",
            "title": title,
        })
        check("POST /api/sessions 200", r.status_code == 200)
        return r.json()["id"]


async def test_websocket(sess_id: str):
    print("\n=== WebSocket ===")
    uri = f"ws://localhost:8000/ws/session/{sess_id}"
    try:
        import httpx_ws
        async with httpx.AsyncClient() as client:
            async with httpx_ws.aconnect_ws(uri, client) as ws:
                check("WS handshake ok", True)
                await ws.send_text("ping")
                events = []
                for _ in range(20):
                    msg = await asyncio.wait_for(ws.receive_text(), timeout=10)
                    event = json.loads(msg)
                    events.append(event)
                    if event["type"] == "agent.done":
                        break
                types = [e["type"] for e in events]
                check("received agent.token", "agent.token" in types)
                check("received agent.done", "agent.done" in types)
                check("reply not empty", any(e["data"] for e in events if e["type"] == "agent.done"))
    except Exception as e:
        check("WS test", False, str(e))


async def test_messages(sess_id: str):
    print("\n=== Messages ===")
    async with httpx.AsyncClient() as c:
        r = await c.get(f"{BASE}/api/sessions/{sess_id}/messages")
        check("GET /api/sessions/{id}/messages 200", r.status_code == 200)
        msgs = r.json()
        roles = [m["role"] for m in msgs]
        check("user message persisted", "user" in roles)
        check("agent message persisted", "agent" in roles)


async def test_history_context(project_id: str):
    print("\n=== History Context ===")
    sess_id = await create_session(project_id, "历史上下文验证")
    uri = f"ws://localhost:8000/ws/session/{sess_id}"
    try:
        import httpx_ws

        async with httpx.AsyncClient() as client:
            async with httpx_ws.aconnect_ws(uri, client) as ws:
                history_turns = [
                    "Remember this exact fact for the rest of this session: the first code name is Alpha. Reply with exactly: STORED ALPHA.",
                    "Remember this exact fact for the rest of this session: the second keyword is Beta. Reply with exactly: STORED BETA.",
                ]

                for text in history_turns:
                    await ws.send_text(text)
                    turn_reply = await wait_for_done(ws)
                    check("history setup reply not empty", bool(turn_reply), turn_reply[:200])

                await ws.send_text(
                    "Based only on the earlier session facts, what is the first code name and what is the second keyword? Reply with both exact values."
                )
                final_reply = await wait_for_done(ws)
                check("history reply contains Alpha", "Alpha" in final_reply, final_reply[:200])
                check("history reply contains Beta", "Beta" in final_reply, final_reply[:200])
    except Exception as e:
        check("history context test", False, str(e))


async def main():
    await test_health()
    _, proj_id, sess_id = await test_rest()
    await test_websocket(sess_id)
    await test_messages(sess_id)
    await test_history_context(proj_id)
    print()


asyncio.run(main())
