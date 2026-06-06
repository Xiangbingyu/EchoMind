from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from gateway.db.base import get_db
from gateway.models.models import ProjectWorkspace, Proposal
from gateway.schemas import ProposalCreate, ProposalOut, ProposalDiffOut
from gateway.git import repo as git

router = APIRouter(prefix="/api")


def _get_project_path(project: ProjectWorkspace) -> str:
    if not project.local_path:
        raise HTTPException(400, "Project has no local_path")
    return project.local_path


@router.post("/projects/{project_id}/repo/init")
async def init_repo(project_id: str, remote_url: str | None = None, db: AsyncSession = Depends(get_db)):
    project = await db.get(ProjectWorkspace, project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    git.init_repository(project.local_path, remote_url)
    return {"ok": True}


@router.post("/projects/{project_id}/proposals", response_model=ProposalOut)
async def create_proposal(project_id: str, db: AsyncSession = Depends(get_db)):
    project = await db.get(ProjectWorkspace, project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    proposal = Proposal(project_workspace_id=project_id, branch_name="")
    db.add(proposal)
    await db.flush()
    branch = git.create_proposal_branch(_get_project_path(project), proposal.id)
    proposal.branch_name = branch
    await db.commit()
    await db.refresh(proposal)
    return proposal


@router.get("/projects/{project_id}/proposals", response_model=list[ProposalOut])
async def list_proposals(project_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Proposal).where(Proposal.project_workspace_id == project_id)
    )
    return result.scalars().all()


@router.get("/proposals/{proposal_id}/diff", response_model=ProposalDiffOut)
async def get_diff(proposal_id: str, db: AsyncSession = Depends(get_db)):
    proposal = await db.get(Proposal, proposal_id)
    if not proposal:
        raise HTTPException(404, "Proposal not found")
    project = await db.get(ProjectWorkspace, proposal.project_workspace_id)
    diff = git.get_proposal_diff(_get_project_path(project), proposal_id)
    return diff


@router.post("/proposals/{proposal_id}/commit")
async def commit_proposal(proposal_id: str, message: str = "update", db: AsyncSession = Depends(get_db)):
    proposal = await db.get(Proposal, proposal_id)
    if not proposal:
        raise HTTPException(404, "Proposal not found")
    project = await db.get(ProjectWorkspace, proposal.project_workspace_id)
    hexsha = git.commit_to_proposal(_get_project_path(project), proposal_id, message)
    return {"hexsha": hexsha}


@router.post("/proposals/{proposal_id}/confirm")
async def confirm_proposal(proposal_id: str, db: AsyncSession = Depends(get_db)):
    proposal = await db.get(Proposal, proposal_id)
    if not proposal:
        raise HTTPException(404, "Proposal not found")
    project = await db.get(ProjectWorkspace, proposal.project_workspace_id)
    hexsha = git.confirm_proposal(_get_project_path(project), proposal_id)
    proposal.status = "confirmed"
    await db.commit()
    return {"hexsha": hexsha}


@router.post("/projects/{project_id}/push")
async def push_project(project_id: str, branch: str = "master", db: AsyncSession = Depends(get_db)):
    project = await db.get(ProjectWorkspace, project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    git.push_project(_get_project_path(project), branch)
    return {"ok": True}


@router.get("/projects/{project_id}/history")
async def get_history(project_id: str, limit: int = 20, db: AsyncSession = Depends(get_db)):
    project = await db.get(ProjectWorkspace, project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    return git.get_project_history(_get_project_path(project), limit)
