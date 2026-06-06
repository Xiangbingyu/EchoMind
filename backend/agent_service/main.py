import httpx
from fastapi import FastAPI
from pydantic import BaseModel
from agent_service.config import GATEWAY_CALLBACK_URL
from agent_service.agents.factory import get_provider

app = FastAPI()
provider = get_provider()


class RunRequest(BaseModel):
    session_id: str
    content: str


@app.get("/health")
async def health():
    return {"status": "ok", "service": "agent_service"}


@app.post("/run")
async def run(req: RunRequest):
    messages = [{"role": "user", "content": req.content}]
    full_reply = []

    async with httpx.AsyncClient() as client:
        async for token in provider.stream(messages):
            full_reply.append(token)
            await client.post(GATEWAY_CALLBACK_URL, json={
                "session_id": req.session_id,
                "type": "agent.token",
                "data": token,
            })
        await client.post(GATEWAY_CALLBACK_URL, json={
            "session_id": req.session_id,
            "type": "agent.done",
            "data": "".join(full_reply),
        })

    return {"ok": True}
