from fastapi import FastAPI
from pydantic import BaseModel
from agent_service.runtime.runner import run_agent

app = FastAPI()


class RunRequest(BaseModel):
    session_id: str
    content: str


@app.get("/health")
async def health():
    return {"status": "ok", "service": "agent_service"}


@app.post("/run")
async def run(req: RunRequest):
    return await run_agent(session_id=req.session_id, content=req.content)
