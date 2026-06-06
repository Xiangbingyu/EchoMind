from contextlib import asynccontextmanager
from fastapi import FastAPI
from gateway.db.init import init_db
from gateway.api.workspaces import router as workspaces_router
from gateway.api.sessions import router as sessions_router
from gateway.api.agents import router as agents_router
from gateway.api.callback import router as callback_router
from gateway.ws.routes import router as ws_router
from gateway.git.api import router as git_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(lifespan=lifespan)
app.include_router(workspaces_router)
app.include_router(sessions_router)
app.include_router(agents_router)
app.include_router(callback_router)
app.include_router(ws_router)
app.include_router(git_router)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "gateway"}
