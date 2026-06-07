import asyncio
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from gateway.main import app


class GatewaySessionsApiTests(unittest.TestCase):
    def test_list_sessions_filters_by_type(self):
        client = TestClient(app)

        class FakeSessionRow:
            def __init__(self, id, type, title):
                self.id = id
                self.project_workspace_id = 'project-1'
                self.type = type
                self.title = title
                self.created_at = '2026-06-07T00:00:00'
                self.last_active_at = '2026-06-07T00:00:00'

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

        class FakeDb:
            async def execute(self, stmt):
                rows = [
                    FakeSessionRow('session-1', 'single', '单聊 A'),
                    FakeSessionRow('session-2', 'single', '单聊 B'),
                ]
                return FakeExecuteResult(rows)

        async def fake_get_db():
            yield FakeDb()

        app.dependency_overrides.clear()
        from gateway.db.base import get_db

        app.dependency_overrides[get_db] = fake_get_db
        try:
            response = client.get('/api/sessions', params={'type': 'single'})
        finally:
            app.dependency_overrides.clear()

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(len(payload), 2)
        self.assertTrue(all(item['type'] == 'single' for item in payload))

    def test_sessions_endpoint_allows_frontend_origin(self):
        client = TestClient(app)

        response = client.options(
            '/api/sessions',
            headers={
                'Origin': 'http://localhost:5173',
                'Access-Control-Request-Method': 'GET',
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers.get('access-control-allow-origin'), 'http://localhost:5173')


if __name__ == '__main__':
    unittest.main()
