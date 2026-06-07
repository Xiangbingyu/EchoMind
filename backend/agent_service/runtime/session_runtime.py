from dataclasses import dataclass, field


@dataclass
class SessionRuntime:
    session_id: str
    workspace_id: str
    project_workspace_id: str
    status: str = 'initializing'
    sandbox_status: str = 'pending'
    agent_status: str = 'idle'
    workspace_root: str = ''
    workspace_tree: list[dict] = field(default_factory=list)
    plan_steps: list[dict] = field(default_factory=list)
    last_error: str = ''
