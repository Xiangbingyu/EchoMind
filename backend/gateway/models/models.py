import uuid
from datetime import datetime
from sqlalchemy import String, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column
from gateway.db.base import Base


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.utcnow()


class Workspace(Base):
    __tablename__ = "workspace"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String, nullable=False)
    endpoint: Mapped[str | None] = mapped_column(String, nullable=True)
    is_remote: Mapped[bool] = mapped_column(Boolean, default=False)
    config_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class ProjectWorkspace(Base):
    __tablename__ = "project_workspace"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspace.id"), nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    local_path: Mapped[str | None] = mapped_column(String, nullable=True)
    remote_path: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class Session(Base):
    __tablename__ = "session"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    project_workspace_id: Mapped[str] = mapped_column(ForeignKey("project_workspace.id"), nullable=False)
    type: Mapped[str] = mapped_column(String, nullable=False)  # group / single / group_dm
    title: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    last_active_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class Message(Base):
    __tablename__ = "message"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    session_id: Mapped[str] = mapped_column(ForeignKey("session.id"), nullable=False)
    role: Mapped[str] = mapped_column(String, nullable=False)  # user / agent / system
    agent_id: Mapped[str | None] = mapped_column(String, nullable=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    content_type: Mapped[str] = mapped_column(String, default="text")  # text/diff/preview/deploy/log
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class Agent(Base):
    __tablename__ = "agent"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String, nullable=False)
    type: Mapped[str] = mapped_column(String, nullable=False)  # single/orchestrator/code/doc/test/review
    skills_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    tools_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    plugins_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class Proposal(Base):
    __tablename__ = "proposal"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    project_workspace_id: Mapped[str] = mapped_column(ForeignKey("project_workspace.id"), nullable=False)
    branch_name: Mapped[str] = mapped_column(String, nullable=False)
    base_branch: Mapped[str] = mapped_column(String, default="master")
    status: Mapped[str] = mapped_column(String, default="open")  # open / committed / confirmed / pushed
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
