from agent_service.runtime.session_runtime import SessionRuntime


def build_chat_snapshot(*, messages: list[dict]) -> dict:
    return {'type': 'message.history.sync', 'data': messages}


def build_workspace_snapshot(runtime: SessionRuntime) -> list[dict]:
    return [
        {
            'type': 'workspace.snapshot',
            'data': {
                'workspace_id': runtime.workspace_id,
                'project_workspace_id': runtime.project_workspace_id,
                'workspace_root': runtime.workspace_root,
            },
        },
        {'type': 'workspace.tree.snapshot', 'data': runtime.workspace_tree},
        {'type': 'plan.snapshot', 'data': runtime.plan_steps},
        {'type': 'sandbox.snapshot', 'data': {'status': runtime.sandbox_status}},
        {
            'type': 'agent.snapshot',
            'data': {'status': runtime.agent_status, 'last_error': runtime.last_error},
        },
    ]
