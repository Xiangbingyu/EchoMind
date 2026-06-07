import unittest
import asyncio
from pathlib import Path
from unittest.mock import patch

from agentscope.message import SystemMsg, UserMsg
from fastapi.testclient import TestClient

from agent_service.main import app
from agent_service.runtime.event_mapper import build_chat_snapshot, build_workspace_snapshot
from agent_service.runtime.events import extract_text_delta
from agent_service.runtime.memory import build_agent_state, build_session_msgs, trim_history
from agent_service.runtime.models import build_chat_model
from agent_service.runtime.runner import load_session_history
from agent_service.runtime.runner import run_agent
from agent_service.runtime.runner import load_project_snapshot, load_session_snapshot
from agent_service.runtime.session_runtime import SessionRuntime
from agent_service.runtime.session_runtime_manager import SessionRuntimeManager


class AgentServiceMainTests(unittest.TestCase):
    def test_run_delegates_to_runtime_runner(self):
        client = TestClient(app)

        calls = []

        def fake_submit_run(*, session_id, content):
            calls.append({"session_id": session_id, "content": content})
            return None

        with patch("agent_service.main.submit_run", side_effect=fake_submit_run) as submit_run_mock:
            
            response = client.post(
                "/run",
                json={"session_id": "session-1", "content": "hello"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"accepted": True})
        submit_run_mock.assert_called_once()
        self.assertEqual(
            calls,
            [{"session_id": "session-1", "content": "hello"}],
        )
 
    def test_runner_streams_tokens_and_done_callback(self):
        callback_payloads = []
        history_calls = []
        message_build_calls = []

        class Event:
            def __init__(self, event_type, delta=""):
                self.type = event_type
                self.delta = delta

        class FakeCodeAgent:
            def reply_stream(self, message):
                self.message = message

                async def iterator():
                    for event in [
                        Event("TEXT_BLOCK_DELTA", "hel"),
                        Event("TEXT_BLOCK_DELTA", "lo"),
                    ]:
                        yield event

                return iterator()

        agent = FakeCodeAgent()

        class FakeClient:
            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, tb):
                return False

            async def post(self, url, json):
                callback_payloads.append({"url": url, "json": json})
                return None

        async def fake_load_session_history(*, session_id):
            history_calls.append(session_id)
            return [
                {"role": "system", "content": "system rules"},
                {"role": "user", "content": "old question"},
            ]

        def fake_build_agent_state(*, history):
            from agentscope.state._state import AgentState

            message_build_calls.append({"history": history})
            return AgentState(
                context=[
                    SystemMsg("system", "system rules"),
                    UserMsg("user", "old question"),
                ],
                summary="Authoritative session facts from prior conversation:\n- system: system rules\n- user: old question",
            )

        async def fake_build_runtime_agent(*, history):
            state = fake_build_agent_state(history=history)
            agent.state = state
            return agent

        async def fake_ensure_session_runtime(*, session_id):
            runtime = SessionRuntime(
                session_id=session_id,
                workspace_id='workspace-1',
                project_workspace_id='project-1',
                workspace_root='.',
            )
            return runtime

        with patch("agent_service.runtime.runner.build_runtime_agent", side_effect=fake_build_runtime_agent), patch(
            "agent_service.runtime.runner.httpx.AsyncClient",
            return_value=FakeClient(),
        ), patch(
            "agent_service.runtime.runner.load_session_history",
            side_effect=fake_load_session_history,
        ), patch(
            "agent_service.runtime.runner.ensure_session_runtime",
            side_effect=fake_ensure_session_runtime,
        ):
            result = asyncio.run(
                run_agent(session_id="session-2", content="hello")
            )

        self.assertEqual(result, {"ok": True})
        self.assertEqual(history_calls, ["session-2"])
        self.assertEqual(
            message_build_calls,
            [
                {
                    "history": [
                        {"role": "system", "content": "system rules"},
                        {"role": "user", "content": "old question"},
                    ]
                }
            ],
        )
        self.assertIsNotNone(agent.state)
        self.assertEqual(len(getattr(agent.state, "context")), 2)
        self.assertIn("system rules", getattr(agent.state, "summary"))
        self.assertIn("old question", getattr(agent.state, "summary"))
        blocks = getattr(agent.message, "content")
        self.assertEqual(len(blocks), 1)
        self.assertEqual(getattr(blocks[0], "text"), "hello")
        self.assertEqual(
            [payload["json"] for payload in callback_payloads],
            [
                {"session_id": "session-2", "type": "task.status", "data": "running"},
                {"session_id": "session-2", "type": "agent.status", "data": {"status": "running", "last_error": ""}},
                {"session_id": "session-2", "type": "sandbox.status", "data": {"status": "running"}},
                {"session_id": "session-2", "type": "workspace.tree.updated", "data": [{"path": ".", "type": "root"}, {"path": "conversation.txt", "type": "file"}]},
                {"session_id": "session-2", "type": "agent.token", "data": "hel"},
                {"session_id": "session-2", "type": "agent.token", "data": "lo"},
                {"session_id": "session-2", "type": "agent.done", "data": "hello"},
                {"session_id": "session-2", "type": "agent.status", "data": {"status": "idle", "last_error": ""}},
                {"session_id": "session-2", "type": "sandbox.status", "data": {"status": "ready"}},
                {"session_id": "session-2", "type": "task.status", "data": "completed"},
            ],
        )

    def test_extract_text_delta_returns_text_for_text_block_delta(self):
        class Event:
            type = "TEXT_BLOCK_DELTA"
            delta = "hello"

        self.assertEqual(extract_text_delta(Event()), "hello")

    def test_build_session_msgs_returns_agentscope_messages(self):
        history = [
            {"role": "system", "content": "system rules"},
            {"role": "user", "content": "old question"},
            {"role": "agent", "content": "old answer"},
        ]

        messages = build_session_msgs(history=history)

        self.assertEqual(type(messages[0]).__name__, "Msg")
        self.assertEqual(type(messages[1]).__name__, "Msg")
        self.assertEqual(type(messages[2]).__name__, "Msg")

    def test_build_agent_state_contains_context_and_authoritative_summary(self):
        history = [
            {"role": "system", "content": "system rules"},
            {"role": "user", "content": "first code name Alpha"},
            {"role": "agent", "content": "stored Alpha"},
        ]

        state = build_agent_state(history=history)

        self.assertEqual(len(state.context), 3)
        self.assertIn("authoritative", state.summary.lower())
        self.assertIn("Alpha", state.summary)

    def test_trim_history_keeps_all_system_and_latest_non_system_messages(self):
        history = [
            {"role": "system", "content": "system rules"},
            {"role": "user", "content": "u1"},
            {"role": "agent", "content": "a1"},
            {"role": "user", "content": "u2"},
            {"role": "agent", "content": "a2"},
        ]

        trimmed = trim_history(history=history, max_non_system_messages=2)

        self.assertEqual(
            trimmed,
            [
                {"role": "system", "content": "system rules"},
                {"role": "user", "content": "u2"},
                {"role": "agent", "content": "a2"},
            ],
        )

    def test_load_session_history_fetches_messages_over_http(self):
        calls = []

        class FakeResponse:
            def raise_for_status(self):
                return None

            def json(self):
                return [
                    {"role": "system", "content": "rules"},
                    {"role": "user", "content": "hello"},
                    {"role": "agent", "content": "world"},
                    {"role": "tool", "content": "skip me"},
                ]

        class FakeClient:
            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, tb):
                return False

            async def get(self, url):
                calls.append(url)
                return FakeResponse()

        with patch("agent_service.runtime.runner.httpx.AsyncClient", return_value=FakeClient()), patch(
            "agent_service.runtime.runner.GATEWAY_MESSAGES_URL_TEMPLATE",
            "http://localhost:8000/api/sessions/{session_id}/messages",
        ):
            history = asyncio.run(load_session_history(session_id="session-1"))

        self.assertEqual(
            history,
            [
                {"role": "system", "content": "rules"},
                {"role": "user", "content": "hello"},
                {"role": "agent", "content": "world"},
            ],
        )
        self.assertEqual(
            calls,
            ["http://localhost:8000/api/sessions/session-1/messages"],
        )

    def test_load_session_snapshot_fetches_session_metadata_over_http(self):
        calls = []

        class FakeResponse:
            def raise_for_status(self):
                return None

            def json(self):
                return {
                    "id": "session-1",
                    "workspace_id": "workspace-1",
                    "project_workspace_id": "project-1",
                    "type": "single",
                    "title": "Test Session",
                }

        class FakeClient:
            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, tb):
                return False

            async def get(self, url):
                calls.append(url)
                return FakeResponse()

        with patch("agent_service.runtime.runner.httpx.AsyncClient", return_value=FakeClient()), patch(
            "agent_service.runtime.runner.GATEWAY_SESSION_URL_TEMPLATE",
            "http://localhost:8000/api/sessions/{session_id}",
        ):
            snapshot = asyncio.run(load_session_snapshot(session_id="session-1"))

        self.assertEqual(snapshot["workspace_id"], "workspace-1")
        self.assertEqual(calls, ["http://localhost:8000/api/sessions/session-1"])

    def test_load_project_snapshot_fetches_project_metadata_over_http(self):
        calls = []

        class FakeResponse:
            def raise_for_status(self):
                return None

            def json(self):
                return {
                    "id": "project-1",
                    "workspace_id": "workspace-1",
                    "name": "Project One",
                    "local_path": "E:/repo/project-one",
                    "remote_path": None,
                }

        class FakeClient:
            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, tb):
                return False

            async def get(self, url):
                calls.append(url)
                return FakeResponse()

        with patch("agent_service.runtime.runner.httpx.AsyncClient", return_value=FakeClient()), patch(
            "agent_service.runtime.runner.GATEWAY_PROJECT_URL_TEMPLATE",
            "http://localhost:8000/api/projects/{project_id}",
        ):
            snapshot = asyncio.run(load_project_snapshot(project_id="project-1"))

        self.assertEqual(snapshot["local_path"], "E:/repo/project-one")
        self.assertEqual(calls, ["http://localhost:8000/api/projects/project-1"])

    def test_runtime_manager_reuses_session_runtime(self):
        manager = SessionRuntimeManager()

        runtime1 = asyncio.run(
            manager.ensure_runtime(
                session_id="session-1",
                workspace_id="workspace-1",
                project_workspace_id="project-1",
                workspace_root="E:/repo/project-one",
            )
        )
        runtime2 = asyncio.run(
            manager.ensure_runtime(
                session_id="session-1",
                workspace_id="workspace-1",
                project_workspace_id="project-1",
                workspace_root="E:/repo/project-one",
            )
        )

        self.assertIs(runtime1, runtime2)
        self.assertEqual(runtime1.workspace_root, "E:/repo/project-one")

    def test_event_mapper_builds_workspace_snapshot_events(self):
        manager = SessionRuntimeManager()
        runtime = asyncio.run(
            manager.ensure_runtime(
                session_id="session-1",
                workspace_id="workspace-1",
                project_workspace_id="project-1",
                workspace_root="E:/repo/project-one",
            )
        )

        events = build_workspace_snapshot(runtime)

        self.assertEqual(events[0]["type"], "workspace.snapshot")
        self.assertEqual(events[0]["data"]["workspace_id"], "workspace-1")

    def test_event_mapper_builds_chat_snapshot_event(self):
        event = build_chat_snapshot(messages=[{"role": "user", "content": "hello"}])

        self.assertEqual(event["type"], "message.history.sync")
        self.assertEqual(event["data"][0]["content"], "hello")

    def test_runner_emits_failed_status_when_history_fetch_fails(self):
        callback_payloads = []

        class FakeClient:
            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, tb):
                return False

            async def post(self, url, json):
                callback_payloads.append({"url": url, "json": json})
                return None

        async def fake_load_session_history(*, session_id):
            raise RuntimeError("history unavailable")

        async def fake_ensure_session_runtime(*, session_id):
            runtime = SessionRuntime(
                session_id=session_id,
                workspace_id='workspace-1',
                project_workspace_id='project-1',
                workspace_root='.',
            )
            from agent_service.runtime.session_runtime_manager import runtime_manager

            runtime_manager._runtimes[session_id] = runtime
            return runtime

        with patch("agent_service.runtime.runner.httpx.AsyncClient", return_value=FakeClient()), patch(
            "agent_service.runtime.runner.ensure_session_runtime",
            side_effect=fake_ensure_session_runtime,
        ), patch(
            "agent_service.runtime.runner.load_session_history",
            side_effect=fake_load_session_history,
        ):
            result = asyncio.run(run_agent(session_id="session-3", content="hello"))

        self.assertEqual(result["ok"], False)
        self.assertIn("history unavailable", result["error"])
        self.assertEqual(
            [payload["json"] for payload in callback_payloads],
            [
                {"session_id": "session-3", "type": "task.status", "data": "running"},
                {"session_id": "session-3", "type": "agent.status", "data": {"status": "running", "last_error": ""}},
                {"session_id": "session-3", "type": "sandbox.status", "data": {"status": "running"}},
                {"session_id": "session-3", "type": "workspace.tree.updated", "data": [{"path": ".", "type": "root"}, {"path": "conversation.txt", "type": "file"}]},
                {"session_id": "session-3", "type": "agent.status", "data": {"status": "error", "last_error": "history unavailable"}},
                {"session_id": "session-3", "type": "task.status", "data": "failed: history unavailable"},
            ],
        )

    def test_legacy_provider_files_are_removed(self):
        self.assertFalse(Path("agent_service/agents/base_provider.py").exists())
        self.assertFalse(Path("agent_service/agents/openai_provider.py").exists())
        self.assertFalse(Path("agent_service/agents/factory.py").exists())

    def test_agent_service_requirements_do_not_pin_legacy_runtime_versions(self):
        requirements = Path("agent_service/requirements.txt").read_text(encoding="utf-8")

        self.assertIn("agentscope==2.0.1", requirements)
        self.assertIn("sqlalchemy", requirements)
        self.assertIn("aiosqlite", requirements)
        self.assertNotIn("starlette==0.38.6", requirements)
        self.assertNotIn("uvicorn==0.30.6", requirements)
        self.assertNotIn("openai==1.35.0", requirements)

    def test_build_openai_chat_model_requires_api_key(self):
        with patch("agent_service.runtime.models.MODEL_PROVIDER", "openai"), patch(
            "agent_service.runtime.models.OPENAI_API_KEY", ""
        ):
            with self.assertRaisesRegex(ValueError, "OPENAI_API_KEY"):
                build_chat_model()

    def test_build_chat_model_uses_openai_model_for_openai_provider(self):
        with patch("agent_service.runtime.models.MODEL_PROVIDER", "openai"), patch(
            "agent_service.runtime.models.OPENAI_API_KEY", "test-key"
        ), patch("agent_service.runtime.models.OPENAI_BASE_URL", "https://api.openai.local/v1"), patch(
            "agent_service.runtime.models.MODEL_NAME", "gpt-4o-mini"
        ):
            model = build_chat_model()

        self.assertEqual(type(model).__name__, "OpenAIChatModel")

    def test_build_chat_model_uses_deepseek_model_for_deepseek_provider(self):
        with patch("agent_service.runtime.models.MODEL_PROVIDER", "deepseek"), patch(
            "agent_service.runtime.models.DEEPSEEK_API_KEY", "test-key"
        ), patch("agent_service.runtime.models.DEEPSEEK_BASE_URL", "https://api.deepseek.local"), patch(
            "agent_service.runtime.models.MODEL_NAME", "deepseek-chat"
        ):
            model = build_chat_model()

        self.assertEqual(type(model).__name__, "DeepSeekChatModel")


if __name__ == "__main__":
    unittest.main()
