from pydantic import BaseModel
from datetime import datetime


class WorkspaceCreate(BaseModel):
    name: str
    endpoint: str | None = None
    is_remote: bool = False
    config_json: str | None = None


class WorkspaceOut(WorkspaceCreate):
    id: str
    created_at: datetime
    model_config = {"from_attributes": True}


class ProjectCreate(BaseModel):
    name: str
    local_path: str | None = None
    remote_path: str | None = None


class ProjectOut(ProjectCreate):
    id: str
    workspace_id: str
    created_at: datetime
    model_config = {"from_attributes": True}


class SessionCreate(BaseModel):
    project_workspace_id: str
    type: str  # group / single / group_dm
    title: str | None = None


class SessionOut(SessionCreate):
    id: str
    created_at: datetime
    last_active_at: datetime
    model_config = {"from_attributes": True}


class MessageOut(BaseModel):
    id: str
    session_id: str
    role: str
    agent_id: str | None
    content: str
    content_type: str
    created_at: datetime
    model_config = {"from_attributes": True}


class AgentCreate(BaseModel):
    name: str
    type: str
    skills_json: str | None = None
    tools_json: str | None = None
    plugins_json: str | None = None


class AgentOut(AgentCreate):
    id: str
    created_at: datetime
    model_config = {"from_attributes": True}
