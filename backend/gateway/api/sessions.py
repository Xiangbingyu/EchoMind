from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from gateway.db.base import get_db
from gateway.models.models import Session, Message, ProjectWorkspace
from gateway.schemas import SessionCreate, SessionOut, MessageOut

router = APIRouter(prefix="/api")


@router.get("/sessions", response_model=list[SessionOut])
async def list_sessions(type: str | None = None, db: AsyncSession = Depends(get_db)):
    stmt = select(Session)
    if type:
        stmt = stmt.where(Session.type == type)
    stmt = stmt.order_by(Session.last_active_at.desc())
    result = await db.execute(stmt)
    return result.scalars().all()


@router.post("/sessions", response_model=SessionOut)
async def create_session(body: SessionCreate, db: AsyncSession = Depends(get_db)):
    project = await db.get(ProjectWorkspace, body.project_workspace_id)
    if not project:
        raise HTTPException(404, "ProjectWorkspace not found")
    session = Session(**body.model_dump())
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return session


@router.get("/sessions/{session_id}", response_model=SessionOut)
async def get_session(session_id: str, db: AsyncSession = Depends(get_db)):
    session = await db.get(Session, session_id)
    if not session:
        raise HTTPException(404, "Session not found")
    return session


@router.get("/sessions/{session_id}/messages", response_model=list[MessageOut])
async def list_messages(session_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Message).where(Message.session_id == session_id).order_by(Message.created_at)
    )
    return result.scalars().all()
