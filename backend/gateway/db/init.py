from sqlalchemy import text

from gateway.db.base import Base, engine
from gateway.models.models import Workspace, ProjectWorkspace, Session, Message, Agent, Proposal


async def _ensure_proposal_base_branch_column() -> None:
    async with engine.begin() as conn:
        result = await conn.execute(text("PRAGMA table_info(proposal)"))
        columns = {row[1] for row in result.fetchall()}
        if "base_branch" not in columns:
            await conn.execute(
                text("ALTER TABLE proposal ADD COLUMN base_branch VARCHAR DEFAULT 'master' NOT NULL")
            )


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await _ensure_proposal_base_branch_column()
