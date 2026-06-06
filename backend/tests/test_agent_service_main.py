import unittest
import asyncio
from pathlib import Path
from unittest.mock import patch

from agentscope.message import SystemMsg, UserMsg
from fastapi.testclient import TestClient

from agent_service.main import app
from agent_service.runtime.events import extract_text_delta
from agent_service.runtime.memory import build_agent_state, build_session_msgs
from agent_service.runtime.models import build_chat_model
from agent_service.runtime.runner import load_session_history
from agent_service.runtime.runner import run_agent


class AgentServiceMainTests(unittest.TestCase):
    def test_run_delegates_to_runtime_runner(self):
        client = TestClient(app)

        calls = []

        async def fake_run_agent(*, session_id, content):
            calls.append({"session_id": session_id, "content": content})
            return {"ok": True}

        with patch("agent_service.main.run_agent", side_effect=fake_run_agent):
            
            response = client.post(
                "/run",
                json={"session_id": "session-1", "content": "hello"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"ok": True})
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

        def fake_build_code_agent(*, state=None):
            agent.state = state
            return agent

        with patch("agent_service.runtime.runner.build_code_agent", side_effect=fake_build_code_agent), patch(
            "agent_service.runtime.runner.httpx.AsyncClient",
            return_value=FakeClient(),
        ), patch(
            "agent_service.runtime.runner.load_session_history",
            side_effect=fake_load_session_history,
        ), patch(
            "agent_service.runtime.runner.build_agent_state",
            side_effect=fake_build_agent_state,
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
                {"session_id": "session-2", "type": "agent.token", "data": "hel"},
                {"session_id": "session-2", "type": "agent.token", "data": "lo"},
                {"session_id": "session-2", "type": "agent.done", "data": "hello"},
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

    def test_load_session_history_returns_sorted_messages_for_session(self):
        class Message:
            def __init__(self, session_id, role, content, created_at):
                self.session_id = session_id
                self.role = role
                self.content = content
                self.created_at = created_at

        class FakeScalarResult:
            def __init__(self, items):
                self._items = items

            def all(self):
                return self._items

        class FakeExecuteResult:
            def __init__(self, items):
                self._items = items

            def scalars(self):
                return FakeScalarResult(self._items)

        class FakeSession:
            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, tb):
                return False

            async def execute(self, stmt):
                return FakeExecuteResult(
                    [
                        Message("session-1", "system", "rules", 1),
                        Message("session-1", "user", "hello", 2),
                        Message("session-1", "agent", "world", 3),
                    ]
                )

        with patch("agent_service.runtime.runner.AsyncSessionLocal", return_value=FakeSession()):
            history = asyncio.run(load_session_history(session_id="session-1"))

        self.assertEqual(
            history,
            [
                {"role": "system", "content": "rules"},
                {"role": "user", "content": "hello"},
                {"role": "agent", "content": "world"},
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
