from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from gateway.db.base import get_db
from gateway.models.models import Workspace, ProjectWorkspace
from gateway.schemas import WorkspaceCreate, WorkspaceOut, ProjectCreate, ProjectOut

router = APIRouter(prefix="/api")


@router.post("/workspaces", response_model=WorkspaceOut)
async def create_workspace(body: WorkspaceCreate, db: AsyncSession = Depends(get_db)):
    ws = Workspace(**body.model_dump())
    db.add(ws)
    await db.commit()
    await db.refresh(ws)
    return ws


@router.get("/workspaces", response_model=list[WorkspaceOut])
async def list_workspaces(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Workspace))
    return result.scalars().all()


@router.post("/workspaces/{workspace_id}/projects", response_model=ProjectOut)
async def create_project(workspace_id: str, body: ProjectCreate, db: AsyncSession = Depends(get_db)):
    ws = await db.get(Workspace, workspace_id)
    if not ws:
        raise HTTPException(404, "Workspace not found")
    project = ProjectWorkspace(workspace_id=workspace_id, **body.model_dump())
    db.add(project)
    await db.commit()
    await db.refresh(project)
    return project


@router.get("/workspaces/{workspace_id}/projects", response_model=list[ProjectOut])
async def list_projects(workspace_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(ProjectWorkspace).where(ProjectWorkspace.workspace_id == workspace_id)
    )
    return result.scalars().all()
