import httpx
from fastapi import FastAPI
from pydantic import BaseModel
from agent_service.config import GATEWAY_CALLBACK_URL

app = FastAPI()


class RunRequest(BaseModel):
    session_id: str
    content: str


@app.get("/health")
async def health():
    return {"status": "ok", "service": "agent_service"}


@app.post("/run")
async def run(req: RunRequest):
    # mock: echo 回复
    async with httpx.AsyncClient() as client:
        await client.post(GATEWAY_CALLBACK_URL, json={
            "session_id": req.session_id,
            "type": "agent.token",
            "data": f"[echo] {req.content}",
        })
        await client.post(GATEWAY_CALLBACK_URL, json={
            "session_id": req.session_id,
            "type": "agent.done",
            "data": f"[echo] {req.content}",
        })
    return {"ok": True}
