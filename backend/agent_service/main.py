import asyncio

from fastapi import FastAPI
from pydantic import BaseModel
from agent_service.runtime.event_mapper import build_chat_snapshot, build_workspace_snapshot
from agent_service.runtime.runner import ensure_session_runtime, load_session_history, run_agent

app = FastAPI()


class RunRequest(BaseModel):
    session_id: str
    content: str


def submit_run(*, session_id: str, content: str):
    asyncio.create_task(run_agent(session_id=session_id, content=content))


@app.get("/health")
async def health():
    return {"status": "ok", "service": "agent_service"}


@app.post("/run")
async def run(req: RunRequest):
    submit_run(session_id=req.session_id, content=req.content)
    return {"accepted": True}


@app.get("/runtime/{session_id}/chat-snapshot")
async def runtime_chat_snapshot(session_id: str):
    history = await load_session_history(session_id=session_id)
    return build_chat_snapshot(messages=history)


@app.get("/runtime/{session_id}/workspace-snapshot")
async def runtime_workspace_snapshot(session_id: str):
    runtime = await ensure_session_runtime(session_id=session_id)
    return build_workspace_snapshot(runtime)
