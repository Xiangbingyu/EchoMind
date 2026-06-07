from agent_service.runtime.session_runtime import SessionRuntime


class SessionRuntimeManager:
    def __init__(self):
        self._runtimes: dict[str, SessionRuntime] = {}

    async def ensure_runtime(
        self,
        session_id: str,
        *,
        workspace_id: str,
        project_workspace_id: str,
        workspace_root: str,
    ) -> SessionRuntime:
        runtime = self._runtimes.get(session_id)
        if runtime is not None:
            return runtime

        runtime = SessionRuntime(
            session_id=session_id,
            workspace_id=workspace_id,
            project_workspace_id=project_workspace_id,
            status='ready',
            sandbox_status='ready',
            workspace_root=workspace_root,
        )
        self._runtimes[session_id] = runtime
        return runtime

    def get_runtime(self, session_id: str) -> SessionRuntime | None:
        return self._runtimes.get(session_id)


runtime_manager = SessionRuntimeManager()
