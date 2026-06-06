import asyncio
import httpx
import websockets
import json


BASE = "http://localhost:8000"


async def main():
    async with httpx.AsyncClient() as client:
        ws = await client.post(f"{BASE}/api/workspaces", json={"name": "test-ws"})
        workspace_id = ws.json()["id"]

        proj = await client.post(f"{BASE}/api/workspaces/{workspace_id}/projects", json={"name": "proj1"})
        project_id = proj.json()["id"]

        sess = await client.post(f"{BASE}/api/sessions", json={
            "project_workspace_id": project_id,
            "type": "group",
        })
        session_id = sess.json()["id"]
        print(f"session_id: {session_id}")

    async with websockets.connect(f"ws://localhost:8000/ws/session/{session_id}") as ws:
        await ws.send("你好，这是测试消息")
        for _ in range(2):
            msg = await asyncio.wait_for(ws.recv(), timeout=5)
            print(f"收到: {json.loads(msg)}")


asyncio.run(main())
