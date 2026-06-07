import unittest
from datetime import UTC, datetime
from unittest.mock import patch

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
        with self.client.websocket_connect('/ws/session/session-1/chat') as chat_ws:
            with self.client.websocket_connect('/ws/session/session-1/workspace') as workspace_ws:
                response = self.client.post(
                    '/internal/callback',
                    json={
                        'session_id': 'session-1',
                        'type': 'agent.token',
                        'data': 'hello',
                    },
                )

                self.assertEqual(response.status_code, 200)
                self.assertEqual(chat_ws.receive_json()['type'], 'agent.token')
                workspace_ws.send_text('noop')

    def test_workspace_callback_broadcasts_only_to_workspace_channel(self):
        with self.client.websocket_connect('/ws/session/session-1/chat') as chat_ws:
            with self.client.websocket_connect('/ws/session/session-1/workspace') as workspace_ws:
                response = self.client.post(
                    '/internal/callback',
                    json={
                        'session_id': 'session-1',
                        'type': 'workspace.snapshot',
                        'data': {'workspace_id': 'workspace-1'},
                    },
                )

                self.assertEqual(response.status_code, 200)
                self.assertEqual(workspace_ws.receive_json()['type'], 'workspace.snapshot')
                chat_ws.send_text('noop')

    def test_workspace_callback_accepts_list_payloads(self):
        with self.client.websocket_connect('/ws/session/session-1/workspace') as workspace_ws:
            response = self.client.post(
                '/internal/callback',
                json={
                    'session_id': 'session-1',
                    'type': 'workspace.tree.updated',
                    'data': [{'path': '.', 'type': 'root'}],
                },
            )

            self.assertEqual(response.status_code, 200)
            event = workspace_ws.receive_json()
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
            with self.client.websocket_connect('/ws/session/session-1/chat') as chat_ws:
                self.assertEqual(chat_ws.receive_json()['type'], 'message.history.sync')

    def test_workspace_websocket_sends_snapshot_on_connect(self):
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
                return FakeResponse([
                    {'type': 'workspace.snapshot', 'data': {'workspace_id': 'workspace-1'}},
                    {'type': 'workspace.tree.snapshot', 'data': []},
                ])

        with patch('gateway.ws.routes.httpx.AsyncClient', return_value=FakeClient()):
            with self.client.websocket_connect('/ws/session/session-1/workspace') as workspace_ws:
                self.assertEqual(workspace_ws.receive_json()['type'], 'workspace.snapshot')


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
                self.local_path = 'E:/repo/project-one'
                self.remote_path = None
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


if __name__ == '__main__':
    unittest.main()
