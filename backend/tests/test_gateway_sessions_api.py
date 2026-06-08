import asyncio
import os
import tempfile
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
                self.workspace_id = 'workspace-1'
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

    def test_delete_session_removes_existing_session(self):
        client = TestClient(app)
        from gateway.db.base import get_db

        class FakeSession:
            def __init__(self):
                self.id = 'session-1'

        class FakeDb:
            def __init__(self):
                self.deleted = None

            async def get(self, model, key):
                if key == 'session-1':
                    return FakeSession()
                return None

            async def delete(self, value):
                self.deleted = value.id

            async def commit(self):
                return None

        db = FakeDb()

        async def fake_get_db():
            yield db

        app.dependency_overrides[get_db] = fake_get_db
        try:
            response = client.delete('/api/sessions/session-1')
        finally:
            app.dependency_overrides.clear()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'ok': True})
        self.assertEqual(db.deleted, 'session-1')

    def test_project_payload_uses_unified_path_field(self):
        client = TestClient(app)
        from gateway.db.base import get_db

        class FakeProject:
            def __init__(self):
                self.id = 'project-1'
                self.workspace_id = 'workspace-1'
                self.name = 'frontend'
                self.path = '/repo/frontend'
                self.created_at = '2026-06-08T00:00:00'

        class FakeDb:
            async def get(self, model, key):
                if key == 'project-1':
                    return FakeProject()
                return None

        async def fake_get_db():
            yield FakeDb()

        app.dependency_overrides[get_db] = fake_get_db
        try:
            response = client.get('/api/projects/project-1')
        finally:
            app.dependency_overrides.clear()

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload['path'], '/repo/frontend')
        self.assertNotIn('local_path', payload)
        self.assertNotIn('remote_path', payload)

    def test_delete_project_removes_related_sessions(self):
        client = TestClient(app)
        from gateway.db.base import get_db

        class FakeProject:
            def __init__(self):
                self.id = 'project-1'
                self.workspace_id = 'workspace-1'

        class FakeSessionRow:
            def __init__(self, session_id):
                self.id = session_id

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
            def __init__(self):
                self.deleted = []

            async def get(self, model, key):
                if key == 'project-1':
                    return FakeProject()
                return None

            async def execute(self, stmt):
                return FakeExecuteResult([FakeSessionRow('session-a'), FakeSessionRow('session-b')])

            async def delete(self, value):
                self.deleted.append(value.id)

            async def commit(self):
                return None

        db = FakeDb()

        async def fake_get_db():
            yield db

        app.dependency_overrides[get_db] = fake_get_db
        try:
            response = client.delete('/api/projects/project-1')
        finally:
            app.dependency_overrides.clear()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(db.deleted, ['session-a', 'session-b', 'project-1'])

    def test_delete_workspace_removes_projects_and_related_sessions(self):
        client = TestClient(app)
        from gateway.db.base import get_db

        class FakeWorkspace:
            def __init__(self):
                self.id = 'workspace-1'

        class FakeProject:
            def __init__(self, project_id):
                self.id = project_id

        class FakeSessionRow:
            def __init__(self, session_id):
                self.id = session_id

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
            def __init__(self):
                self.deleted = []
                self.execute_count = 0

            async def get(self, model, key):
                if key == 'workspace-1':
                    return FakeWorkspace()
                return None

            async def execute(self, stmt):
                self.execute_count += 1
                if self.execute_count == 1:
                    return FakeExecuteResult([FakeProject('project-1'), FakeProject('project-2')])
                return FakeExecuteResult([FakeSessionRow('session-a'), FakeSessionRow('session-b')])

            async def delete(self, value):
                self.deleted.append(value.id)

            async def commit(self):
                return None

        db = FakeDb()

        async def fake_get_db():
            yield db

        app.dependency_overrides[get_db] = fake_get_db
        try:
            response = client.delete('/api/workspaces/workspace-1')
        finally:
            app.dependency_overrides.clear()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(db.deleted, ['session-a', 'session-b', 'project-1', 'project-2', 'workspace-1'])

    def test_project_files_tree_lists_root_entries(self):
        client = TestClient(app)
        from gateway.db.base import get_db

        class FakeProject:
            def __init__(self, path):
                self.id = 'project-1'
                self.path = path

        class FakeDb:
            def __init__(self, path):
                self.path = path

            async def get(self, model, key):
                if key == 'project-1':
                    return FakeProject(self.path)
                return None

        with tempfile.TemporaryDirectory() as tmpdir:
            os.makedirs(os.path.join(tmpdir, 'src'))
            with open(os.path.join(tmpdir, 'README.md'), 'w', encoding='utf-8') as handle:
                handle.write('hello')

            async def fake_get_db():
                yield FakeDb(tmpdir)

            app.dependency_overrides[get_db] = fake_get_db
            try:
                response = client.get('/api/projects/project-1/files/tree')
            finally:
                app.dependency_overrides.clear()

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(any(item['path'] == 'src' and item['type'] == 'directory' for item in payload))
        self.assertTrue(any(item['path'] == 'README.md' and item['type'] == 'file' for item in payload))

    def test_project_file_content_returns_text(self):
        client = TestClient(app)
        from gateway.db.base import get_db

        class FakeProject:
            def __init__(self, path):
                self.id = 'project-1'
                self.path = path

        class FakeDb:
            def __init__(self, path):
                self.path = path

            async def get(self, model, key):
                if key == 'project-1':
                    return FakeProject(self.path)
                return None

        with tempfile.TemporaryDirectory() as tmpdir:
            with open(os.path.join(tmpdir, 'README.md'), 'w', encoding='utf-8') as handle:
                handle.write('workspace docs')

            async def fake_get_db():
                yield FakeDb(tmpdir)

            app.dependency_overrides[get_db] = fake_get_db
            try:
                response = client.get('/api/projects/project-1/files/content', params={'path': 'README.md'})
            finally:
                app.dependency_overrides.clear()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['content'], 'workspace docs')


if __name__ == '__main__':
    unittest.main()
