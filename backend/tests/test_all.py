"""
EchoMind backend integration tests.
Run: python test_all.py
Requires: gateway on :8000, agent_service on :8001
"""
import asyncio
import httpx
import websockets
import json

BASE = "http://localhost:8000"
PASS = "\033[92mPASS\033[0m"
FAIL = "\033[91mFAIL\033[0m"


def check(label, condition, detail=""):
    status = PASS if condition else FAIL
    print(f"  [{status}] {label}" + (f" — {detail}" if detail else ""))
    return condition


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


async def test_websocket(sess_id: str):
    print("\n=== WebSocket ===")
    uri = f"ws://localhost:8000/ws/session/{sess_id}"
    try:
        async with websockets.connect(uri) as ws:
            check("WS handshake ok", True)
            await ws.send("ping")
            events = []
            for _ in range(2):
                raw = await asyncio.wait_for(ws.recv(), timeout=5)
                events.append(json.loads(raw))
            types = [e["type"] for e in events]
            check("received agent.token", "agent.token" in types)
            check("received agent.done", "agent.done" in types)
            check("echo content correct", any("[echo] ping" in e["data"] for e in events))
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


async def main():
    await test_health()
    _, _, sess_id = await test_rest()
    await test_websocket(sess_id)
    await test_messages(sess_id)
    print()


asyncio.run(main())
