import unittest
from datetime import UTC, datetime
from unittest.mock import patch
import asyncio

from fastapi.testclient import TestClient

from gateway.main import app


class SessionWorkspaceBindingTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def tearDown(self):
        app.dependency_overrides.clear()

    def test_create_session_requires_workspace_id(self):
        from gateway.db.base import get_db

        class FakeProject:
            def __init__(self):
                self.id = 'project-1'
                self.workspace_id = 'workspace-a'

        class FakeDb:
            async def get(self, model, key):
                if key == 'project-1':
                    return FakeProject()
                return None

            def add(self, value):
                self.added = value

            async def commit(self):
                return None

            async def refresh(self, value):
                if getattr(value, 'id', None) is None:
                    value.id = 'session-created'
                value.created_at = datetime.utcnow()
                value.last_active_at = datetime.utcnow()

        async def fake_get_db():
            yield FakeDb()

        app.dependency_overrides[get_db] = fake_get_db

        response = self.client.post(
            '/api/sessions',
            json={
                'type': 'single',
                'title': 'Missing workspace',
                'project_workspace_id': 'project-1',
            },
        )

        self.assertEqual(response.status_code, 422)

    def test_create_session_rejects_workspace_project_mismatch(self):
        from gateway.db.base import get_db

        class FakeProject:
            def __init__(self):
                self.id = 'project-b'
                self.workspace_id = 'workspace-b'

        class FakeDb:
            async def get(self, model, key):
                if key == 'project-b':
                    return FakeProject()
                return None

            def add(self, value):
                self.added = value

            async def commit(self):
                return None

            async def refresh(self, value):
                if getattr(value, 'id', None) is None:
                    value.id = 'session-created'
                value.created_at = datetime.utcnow()
                value.last_active_at = datetime.utcnow()

        async def fake_get_db():
            yield FakeDb()

        app.dependency_overrides[get_db] = fake_get_db

        response = self.client.post(
            '/api/sessions',
            json={
                'type': 'single',
                'title': 'Bad binding',
                'workspace_id': 'workspace-a',
                'project_workspace_id': 'project-b',
            },
        )

        self.assertEqual(response.status_code, 400)


class DualChannelWebsocketTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def tearDown(self):
        app.dependency_overrides.clear()

    def test_chat_callback_broadcasts_only_to_chat_channel(self):
        with self.client.websocket_connect('/ws/session/session-1') as ws:
            response = self.client.post(
                '/internal/callback',
                json={
                    'session_id': 'session-1',
                    'type': 'agent.token',
                    'data': 'hello',
                },
            )

            self.assertEqual(response.status_code, 200)
            self.assertEqual(ws.receive_json()['type'], 'agent.token')

    def test_workspace_callback_broadcasts_only_to_workspace_channel(self):
        with self.client.websocket_connect('/ws/session/session-1') as ws:
            response = self.client.post(
                '/internal/callback',
                json={
                    'session_id': 'session-1',
                    'type': 'workspace.snapshot',
                    'data': {'workspace_id': 'workspace-1'},
                },
            )

            self.assertEqual(response.status_code, 200)
            self.assertEqual(ws.receive_json()['type'], 'workspace.snapshot')

    def test_workspace_callback_accepts_list_payloads(self):
        with self.client.websocket_connect('/ws/session/session-1') as ws:
            response = self.client.post(
                '/internal/callback',
                json={
                    'session_id': 'session-1',
                    'type': 'workspace.tree.updated',
                    'data': [{'path': '.', 'type': 'root'}],
                },
            )

            self.assertEqual(response.status_code, 200)
            event = ws.receive_json()
            self.assertEqual(event['type'], 'workspace.tree.updated')
            self.assertEqual(event['data'][0]['path'], '.')

    def test_chat_websocket_sends_snapshot_on_connect(self):
        class FakeResponse:
            def __init__(self, payload):
                self._payload = payload

            def raise_for_status(self):
                return None

            def json(self):
                return self._payload

        class FakeClient:
            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, tb):
                return False

            async def get(self, url, timeout=5):
                return FakeResponse({'type': 'message.history.sync', 'data': []})

        with patch('gateway.ws.routes.httpx.AsyncClient', return_value=FakeClient()):
            with self.client.websocket_connect('/ws/session/session-1') as ws:
                self.assertEqual(ws.receive_json()['type'], 'message.history.sync')

    def test_workspace_websocket_sends_snapshot_on_connect(self):
        class FakeClient:
            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, tb):
                return False

            async def get(self, url, timeout=5):
                class FakeResponse:
                    def __init__(self, payload):
                        self._payload = payload

                    def raise_for_status(self):
                        return None

                    def json(self):
                        return self._payload

                if url.endswith('/chat-snapshot'):
                    return FakeResponse({'type': 'message.history.sync', 'data': []})

                return FakeResponse([
                    {'type': 'workspace.snapshot', 'data': {'workspace_id': 'workspace-1'}},
                    {'type': 'workspace.tree.snapshot', 'data': []},
                ])

        with patch('gateway.ws.routes.httpx.AsyncClient', return_value=FakeClient()):
            with self.client.websocket_connect('/ws/session/session-1') as ws:
                first_event = ws.receive_json()
                second_event = ws.receive_json()
                third_event = ws.receive_json()
                self.assertEqual(first_event['type'], 'message.history.sync')
                self.assertEqual(second_event['type'], 'workspace.snapshot')
                self.assertEqual(third_event['type'], 'workspace.tree.snapshot')


class ProjectLookupTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def tearDown(self):
        app.dependency_overrides.clear()

    def test_get_project_returns_project_workspace_snapshot(self):
        from gateway.db.base import get_db

        class FakeProject:
            def __init__(self):
                self.id = 'project-1'
                self.workspace_id = 'workspace-1'
                self.name = 'Project One'
                self.path = 'E:/repo/project-one'
                self.created_at = datetime.now(UTC)

        class FakeDb:
            async def get(self, model, key):
                if key == 'project-1':
                    return FakeProject()
                return None

        async def fake_get_db():
            yield FakeDb()

        app.dependency_overrides[get_db] = fake_get_db

        response = self.client.get('/api/projects/project-1')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['id'], 'project-1')


class SessionWorkspaceBackfillTests(unittest.TestCase):
    def test_backfill_updates_legacy_sessions_from_project_workspace(self):
        from gateway.db import init as init_module

        statements = []

        class FakeResult:
            def fetchall(self):
                return [(0, 'id'), (1, 'project_workspace_id'), (2, 'workspace_id')]

        class FakeConn:
            async def execute(self, stmt):
                statements.append(str(stmt))
                return FakeResult()

        class FakeBegin:
            async def __aenter__(self):
                return FakeConn()

            async def __aexit__(self, exc_type, exc, tb):
                return False

        class FakeEngine:
            def begin(self):
                return FakeBegin()

        with patch.object(init_module, 'engine', FakeEngine()):
            asyncio.run(init_module._backfill_session_workspace_ids())

        self.assertTrue(any('UPDATE session' in stmt for stmt in statements), statements)

    def test_cleanup_invalid_workspaces_removes_rows_without_endpoint(self):
        from gateway.db import init as init_module

        statements = []

        class FakeResult:
            def fetchall(self):
                return []

        class FakeConn:
            async def execute(self, stmt):
                statements.append(str(stmt))
                return FakeResult()

        class FakeBegin:
            async def __aenter__(self):
                return FakeConn()

            async def __aexit__(self, exc_type, exc, tb):
                return False

        class FakeEngine:
            def begin(self):
                return FakeBegin()

        with patch.object(init_module, 'engine', FakeEngine()):
            asyncio.run(init_module._cleanup_invalid_workspaces())

        self.assertTrue(any('DELETE FROM session' in stmt for stmt in statements), statements)
        self.assertTrue(any('DELETE FROM project_workspace' in stmt for stmt in statements), statements)
        self.assertTrue(any('DELETE FROM workspace' in stmt for stmt in statements), statements)
        self.assertTrue(any('endpoint IS NULL' in stmt for stmt in statements), statements)

    def test_ensure_project_path_column_backfills_from_legacy_fields(self):
        from gateway.db import init as init_module

        statements = []

        class FakeResult:
            def fetchall(self):
                return [(0, 'id'), (1, 'workspace_id'), (2, 'name'), (3, 'local_path'), (4, 'remote_path')]

        class FakeConn:
            async def execute(self, stmt):
                statements.append(str(stmt))
                return FakeResult()

        class FakeBegin:
            async def __aenter__(self):
                return FakeConn()

            async def __aexit__(self, exc_type, exc, tb):
                return False

        class FakeEngine:
            def begin(self):
                return FakeBegin()

        with patch.object(init_module, 'engine', FakeEngine()):
            asyncio.run(init_module._ensure_project_path_column())

        self.assertTrue(any('ALTER TABLE project_workspace ADD COLUMN path' in stmt for stmt in statements), statements)
        self.assertTrue(any('COALESCE(local_path, remote_path' in stmt for stmt in statements), statements)

    def test_ensure_workspace_is_remote_defaults_to_zero(self):
        from gateway.db import init as init_module

        statements = []

        class FakeResult:
            def fetchall(self):
                return [(0, 'id'), (1, 'name'), (2, 'endpoint'), (3, 'is_remote')]

        class FakeConn:
            async def execute(self, stmt):
                statements.append(str(stmt))
                return FakeResult()

        class FakeBegin:
            async def __aenter__(self):
                return FakeConn()

            async def __aexit__(self, exc_type, exc, tb):
                return False

        class FakeEngine:
            def begin(self):
                return FakeBegin()

        with patch.object(init_module, 'engine', FakeEngine()):
            asyncio.run(init_module._ensure_workspace_is_remote_column())

        self.assertTrue(any('UPDATE workspace' in stmt for stmt in statements), statements)
        self.assertTrue(any('SET is_remote = 0' in stmt for stmt in statements), statements)


class WebsocketDisconnectTests(unittest.TestCase):
    def test_session_ws_ignores_disconnect_during_snapshot(self):
        from gateway.ws import routes as routes_module

        class FakeResponse:
            def raise_for_status(self):
                return None

            def json(self):
                return {'type': 'message.history.sync', 'data': []}

        class FakeClient:
            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, tb):
                return False

            async def get(self, url, timeout=5):
                return FakeResponse()

        class ClosedWs:
            async def send_json(self, payload):
                raise RuntimeError('connection already closed')

        async def fake_connect(session_id, ws):
            return None

        with patch.object(routes_module, 'manager') as manager_mock, patch.object(
            routes_module.httpx, 'AsyncClient', return_value=FakeClient()
        ), patch.object(
            routes_module, '_send_workspace_snapshot', side_effect=RuntimeError('connection already closed')
        ):
            manager_mock.connect.side_effect = fake_connect

            # The coroutine should surface the disconnect as a normal exception path,
            # not as an unhandled ASGI crash.
            with self.assertRaises(RuntimeError):
                asyncio.run(routes_module.session_ws('session-1', ClosedWs()))


if __name__ == '__main__':
    unittest.main()
