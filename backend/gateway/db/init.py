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


async def _ensure_session_workspace_id_column() -> None:
    async with engine.begin() as conn:
        result = await conn.execute(text("PRAGMA table_info(session)"))
        columns = {row[1] for row in result.fetchall()}
        if "workspace_id" not in columns:
            await conn.execute(
                text("ALTER TABLE session ADD COLUMN workspace_id VARCHAR")
            )


async def _ensure_workspace_is_remote_column() -> None:
    async with engine.begin() as conn:
        result = await conn.execute(text("PRAGMA table_info(workspace)"))
        columns = {row[1] for row in result.fetchall()}
        if "is_remote" in columns:
            await conn.execute(
                text(
                    """
                    UPDATE workspace
                    SET is_remote = 0
                    WHERE is_remote IS NULL
                    """
                )
            )


async def _ensure_project_path_column() -> None:
    async with engine.begin() as conn:
        result = await conn.execute(text("PRAGMA table_info(project_workspace)"))
        columns = {row[1] for row in result.fetchall()}
        if "path" not in columns:
            await conn.execute(
                text("ALTER TABLE project_workspace ADD COLUMN path VARCHAR")
            )
            await conn.execute(
                text(
                    """
                    UPDATE project_workspace
                    SET path = COALESCE(local_path, remote_path)
                    WHERE path IS NULL OR TRIM(path) = ''
                    """
                )
            )


async def _backfill_session_workspace_ids() -> None:
    async with engine.begin() as conn:
        await conn.execute(
            text(
                """
                UPDATE session
                SET workspace_id = (
                    SELECT project_workspace.workspace_id
                    FROM project_workspace
                    WHERE project_workspace.id = session.project_workspace_id
                )
                WHERE workspace_id IS NULL
                """
            )
        )


async def _cleanup_invalid_workspaces() -> None:
    async with engine.begin() as conn:
        await conn.execute(
            text(
                """
                DELETE FROM session
                WHERE workspace_id IN (
                    SELECT id FROM workspace WHERE endpoint IS NULL OR TRIM(endpoint) = ''
                )
                OR project_workspace_id IN (
                    SELECT id FROM project_workspace
                    WHERE workspace_id IN (
                        SELECT id FROM workspace WHERE endpoint IS NULL OR TRIM(endpoint) = ''
                    )
                )
                """
            )
        )
        await conn.execute(
            text(
                """
                DELETE FROM project_workspace
                WHERE workspace_id IN (
                    SELECT id FROM workspace WHERE endpoint IS NULL OR TRIM(endpoint) = ''
                )
                """
            )
        )
        await conn.execute(
            text(
                """
                DELETE FROM workspace
                WHERE endpoint IS NULL OR TRIM(endpoint) = ''
                """
            )
        )


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await _ensure_proposal_base_branch_column()
    await _ensure_workspace_is_remote_column()
    await _ensure_session_workspace_id_column()
    await _ensure_project_path_column()
    await _backfill_session_workspace_ids()
    await _cleanup_invalid_workspaces()
