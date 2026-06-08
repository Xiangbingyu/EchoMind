# Workspace Resource CRUD Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add workspace and project create/delete flows to the compiler-style `Workspace` page, unify the resource model to `workspace.endpoint` and `project.path`, and enforce backend cascade deletion for related sessions.

**Architecture:** Update backend schema and API contracts first so frontend stops depending on `is_remote`, `local_path`, and `remote_path`. Then extend the current `Workspace` page with focused create/delete controls for workspaces and projects while preserving the existing explorer layout and session-binding flow in `Messages`.

Current MVP boundary: treat `endpoint` as a local-environment marker only. Real remote endpoint execution and remote filesystem access are explicitly out of scope for this implementation.

**Tech Stack:** FastAPI, SQLAlchemy, Pydantic, React 19, Vite 8, Vitest, React Testing Library, ESLint

---

## File Map

### Existing backend files to modify

- `backend/gateway/models/models.py`
  - Replace `ProjectWorkspace.local_path` / `remote_path` usage with a unified `path` field and stop treating `Workspace.is_remote` as an active contract.
- `backend/gateway/schemas.py`
  - Update `WorkspaceCreate`, `WorkspaceOut`, `ProjectCreate`, and `ProjectOut` to the unified contract.
- `backend/gateway/api/workspaces.py`
  - Add `DELETE /api/workspaces/{workspace_id}` and `DELETE /api/projects/{project_id}` and update create/list endpoints to use `path`.
- `backend/gateway/api/sessions.py`
  - Keep session endpoints aligned with renamed project payloads and cascade deletion rules where needed.
- `backend/gateway/git/api.py`
  - Replace `local_path` reads with `path`.

### Existing backend tests to modify

- `backend/tests/test_gateway_sessions_api.py`
  - Add contract tests for project deletion and workspace deletion cascade behavior.
- `backend/tests/test_gateway_dual_ws_api.py`
  - Update fake project objects to use the unified `path` field if they assert project payloads.
- `backend/tests/test_all.py`
  - Update project creation payloads and any response assertions that currently expect `local_path`.
- `backend/tests/test_git.py`
  - Switch project creation payloads and git-path assertions from `local_path` to `path`.
- `backend/tests/test_agent_service_main.py`
  - Update project payload fixtures if they still assert `local_path`.

### Existing frontend files to modify

- `frontend/src/pages/Workspace/Workspace.jsx`
  - Add create/delete state, load refreshed resource data, and wire all CRUD actions to backend endpoints.
- `frontend/src/components/WorkspaceBrowser/WorkspaceBrowser.jsx`
  - Add create/delete action triggers while preserving the current compiler-style layout.
- `frontend/src/components/WorkspaceBrowser/WorkspaceBrowser.css`
  - Style action buttons, inline resource controls, and destructive confirmations.
- `frontend/src/components/WorkspaceBrowser/WorkspaceBrowser.test.jsx`
  - Update fixtures and tests from `local_path` to `path`, and add create/delete action coverage.
- `frontend/src/pages/Messages/Messages.jsx`
  - Keep session creation flow compatible with the updated project payload shape and optionally refresh sessions after resource deletion.
- `frontend/src/components/SessionCreateDialog/SessionCreateDialog.jsx`
  - Ensure the session creation form displays updated project labels and data.

### New frontend files to create

- `frontend/src/components/WorkspaceResourceDialog/WorkspaceResourceDialog.jsx`
  - Shared lightweight dialog for creating a workspace or a project.
- `frontend/src/components/WorkspaceResourceDialog/WorkspaceResourceDialog.css`
  - Styles for the new resource form dialog.
- `frontend/src/components/WorkspaceResourceDialog/WorkspaceResourceDialog.test.jsx`
  - Tests for workspace creation fields and project creation fields.

## Task 1: Unify backend resource contracts to `endpoint` and `path`

**Files:**
- Modify: `backend/gateway/models/models.py`
- Modify: `backend/gateway/schemas.py`
- Modify: `backend/gateway/api/workspaces.py`
- Modify: `backend/gateway/git/api.py`
- Test: `backend/tests/test_gateway_sessions_api.py`

- [ ] **Step 1: Write the failing backend contract test for project path output**

Add this test to `backend/tests/test_gateway_sessions_api.py`:

```python
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
```

- [ ] **Step 2: Run the backend test to verify it fails for the expected reason**

Run: `$env:PYTHONPATH="E:\Github\EchoMind\backend"; & "E:\Github\EchoMind\backend\gateway\.venv\Scripts\python.exe" -m tests.test_gateway_sessions_api`

Expected: FAIL because `ProjectOut` and route serialization still expect `local_path` / `remote_path` instead of `path`.

- [ ] **Step 3: Update backend model, schema, and workspace/project API to use `path`**

Apply these exact structural changes:

```python
# backend/gateway/models/models.py
class ProjectWorkspace(Base):
    __tablename__ = "project_workspace"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspace.id"), nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    path: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
```

```python
# backend/gateway/schemas.py
class WorkspaceCreate(BaseModel):
    name: str
    endpoint: str
    config_json: str | None = None


class ProjectCreate(BaseModel):
    name: str
    path: str
```

```python
# backend/gateway/api/workspaces.py
@router.post("/workspaces/{workspace_id}/projects", response_model=ProjectOut)
async def create_project(workspace_id: str, body: ProjectCreate, db: AsyncSession = Depends(get_db)):
    ws = await db.get(Workspace, workspace_id)
    if not ws:
        raise HTTPException(404, "Workspace not found")
    project = ProjectWorkspace(workspace_id=workspace_id, **body.model_dump())
    db.add(project)
    await db.commit()
    await db.refresh(project)
    return project
```

```python
# backend/gateway/git/api.py
def _get_project_path(project: ProjectWorkspace) -> str:
    if not project.path:
        raise HTTPException(400, "Project has no path")
    return project.path
```

- [ ] **Step 4: Run the backend contract test to verify it passes**

Run: `$env:PYTHONPATH="E:\Github\EchoMind\backend"; & "E:\Github\EchoMind\backend\gateway\.venv\Scripts\python.exe" -m tests.test_gateway_sessions_api`

Expected: PASS for the unified project payload test and previously passing file/session tests.

- [ ] **Step 5: Commit the resource model unification**

```bash
git add backend/gateway/models/models.py backend/gateway/schemas.py backend/gateway/api/workspaces.py backend/gateway/git/api.py backend/tests/test_gateway_sessions_api.py backend/tests/test_gateway_dual_ws_api.py backend/tests/test_all.py backend/tests/test_git.py backend/tests/test_agent_service_main.py
git commit -m "refactor(backend): unify workspace and project fields"
```

## Task 2: Add backend cascade deletion for projects and workspaces

**Files:**
- Modify: `backend/gateway/api/workspaces.py`
- Modify: `backend/tests/test_gateway_sessions_api.py`
- Test: `backend/tests/test_gateway_sessions_api.py`

- [ ] **Step 1: Write the failing delete-project and delete-workspace tests**

Add these tests to `backend/tests/test_gateway_sessions_api.py`:

```python
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
```

```python
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
```

- [ ] **Step 2: Run the backend tests to confirm both delete routes fail before implementation**

Run: `$env:PYTHONPATH="E:\Github\EchoMind\backend"; & "E:\Github\EchoMind\backend\gateway\.venv\Scripts\python.exe" -m tests.test_gateway_sessions_api`

Expected: FAIL with 404/405 because delete-project and delete-workspace routes are not implemented yet.

- [ ] **Step 3: Implement cascade deletion in `backend/gateway/api/workspaces.py`**

Use this structure:

```python
from sqlalchemy import select
from gateway.models.models import Workspace, ProjectWorkspace, Session


@router.delete('/projects/{project_id}')
async def delete_project(project_id: str, db: AsyncSession = Depends(get_db)):
    project = await db.get(ProjectWorkspace, project_id)
    if not project:
        raise HTTPException(404, 'Project not found')

    session_result = await db.execute(
        select(Session).where(Session.project_workspace_id == project_id)
    )
    for session in session_result.scalars().all():
        await db.delete(session)

    await db.delete(project)
    await db.commit()
    return {'ok': True}


@router.delete('/workspaces/{workspace_id}')
async def delete_workspace(workspace_id: str, db: AsyncSession = Depends(get_db)):
    workspace = await db.get(Workspace, workspace_id)
    if not workspace:
        raise HTTPException(404, 'Workspace not found')

    project_result = await db.execute(
        select(ProjectWorkspace).where(ProjectWorkspace.workspace_id == workspace_id)
    )
    projects = project_result.scalars().all()

    project_ids = [project.id for project in projects]
    if project_ids:
        session_result = await db.execute(
            select(Session).where(Session.project_workspace_id.in_(project_ids))
        )
        for session in session_result.scalars().all():
            await db.delete(session)

    for project in projects:
        await db.delete(project)

    await db.delete(workspace)
    await db.commit()
    return {'ok': True}
```

- [ ] **Step 4: Run the backend tests again to verify cascade behavior**

Run: `$env:PYTHONPATH="E:\Github\EchoMind\backend"; & "E:\Github\EchoMind\backend\gateway\.venv\Scripts\python.exe" -m tests.test_gateway_sessions_api`

Expected: PASS with delete-project and delete-workspace cascade tests green.

- [ ] **Step 5: Commit the cascade deletion endpoints**

```bash
git add backend/gateway/api/workspaces.py backend/tests/test_gateway_sessions_api.py
git commit -m "feat(backend): add workspace resource cascade deletion"
```

## Task 3: Add workspace and project creation dialogs to the Workspace page

**Files:**
- Create: `frontend/src/components/WorkspaceResourceDialog/WorkspaceResourceDialog.jsx`
- Create: `frontend/src/components/WorkspaceResourceDialog/WorkspaceResourceDialog.css`
- Create: `frontend/src/components/WorkspaceResourceDialog/WorkspaceResourceDialog.test.jsx`
- Modify: `frontend/src/pages/Workspace/Workspace.jsx`
- Modify: `frontend/src/components/WorkspaceBrowser/WorkspaceBrowser.jsx`
- Modify: `frontend/src/components/WorkspaceBrowser/WorkspaceBrowser.css`
- Test: `frontend/src/components/WorkspaceBrowser/WorkspaceBrowser.test.jsx`

- [ ] **Step 1: Write the failing dialog and explorer tests for resource creation**

Add this test file:

```jsx
import React from 'react';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import WorkspaceResourceDialog from './WorkspaceResourceDialog';

describe('WorkspaceResourceDialog', () => {
  it('renders workspace fields for workspace mode', () => {
    render(
      <WorkspaceResourceDialog
        mode="workspace"
        open
        loading={false}
        onClose={() => {}}
        onSubmit={() => {}}
      />,
    );

    expect(screen.getByLabelText('Workspace 名称')).toBeInTheDocument();
    expect(screen.getByLabelText('Endpoint')).toBeInTheDocument();
  });

  it('renders path field for project mode', () => {
    render(
      <WorkspaceResourceDialog
        mode="project"
        open
        loading={false}
        onClose={() => {}}
        onSubmit={() => {}}
      />,
    );

    expect(screen.getByLabelText('Project 名称')).toBeInTheDocument();
    expect(screen.getByLabelText('Path')).toBeInTheDocument();
  });
});
```

Extend `frontend/src/components/WorkspaceBrowser/WorkspaceBrowser.test.jsx` with:

```jsx
  it('shows create project and delete actions in the explorer', () => {
    render(
      <WorkspaceBrowser
        activeWorkspace={workspaces[0]}
        activeProject={projectsByWorkspace['ws-1'][0]}
        workspaces={workspaces}
        projectsByWorkspace={projectsByWorkspace}
        selectedWorkspaceId="ws-1"
        selectedProjectId="pw-1"
        selectedFilePath=""
        onWorkspaceSelect={() => {}}
        onProjectSelect={() => {}}
        onFileSelect={() => {}}
        onCreateWorkspace={() => {}}
        onCreateProject={() => {}}
        onDeleteWorkspace={() => {}}
        onDeleteProject={() => {}}
        fileTree={fileTree}
        fileTreeLoading={false}
        fileTreeError=""
        fileContent=""
        fileContentLoading={false}
        fileContentError=""
        loading={false}
        error=""
      />,
    );

    expect(screen.getByRole('button', { name: '新建' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '新建 Project' })).toBeInTheDocument();
    expect(screen.getAllByRole('button', { name: '删除 Workspace' }).length).toBeGreaterThan(0);
    expect(screen.getAllByRole('button', { name: '删除 Project' }).length).toBeGreaterThan(0);
  });
```

- [ ] **Step 2: Run frontend tests to verify they fail before implementation**

Run: `npm test -- WorkspaceResourceDialog.test.jsx WorkspaceBrowser.test.jsx`

Expected: FAIL because the dialog component and explorer action props do not exist yet.

- [ ] **Step 3: Implement the shared resource dialog**

Create `frontend/src/components/WorkspaceResourceDialog/WorkspaceResourceDialog.jsx` with this minimal structure:

```jsx
import React, { useState } from 'react';
import './WorkspaceResourceDialog.css';

export default function WorkspaceResourceDialog({ mode, open, loading, onClose, onSubmit }) {
  const [name, setName] = useState('');
  const [value, setValue] = useState('');

  if (!open) {
    return null;
  }

  const isWorkspace = mode === 'workspace';

  return (
    <div className="workspace-resource-overlay" role="dialog" aria-modal="true">
      <div className="workspace-resource-dialog">
        <h3>{isWorkspace ? '新建 Workspace' : '新建 Project'}</h3>
        <label>
          <span>{isWorkspace ? 'Workspace 名称' : 'Project 名称'}</span>
          <input value={name} onChange={(event) => setName(event.target.value)} />
        </label>
        <label>
          <span>{isWorkspace ? 'Endpoint' : 'Path'}</span>
          <input value={value} onChange={(event) => setValue(event.target.value)} />
        </label>
        <div className="workspace-resource-actions">
          <button type="button" onClick={onClose}>取消</button>
          <button
            type="button"
            disabled={!name.trim() || !value.trim() || loading}
            onClick={() =>
              onSubmit(isWorkspace ? { name: name.trim(), endpoint: value.trim() } : { name: name.trim(), path: value.trim() })
            }
          >
            {loading ? '处理中' : '确认'}
          </button>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Extend `WorkspaceBrowser` to expose create/delete action hooks**

Make these concrete changes in `frontend/src/components/WorkspaceBrowser/WorkspaceBrowser.jsx`:

- Add props:
  - `onCreateProject`
  - `onDeleteWorkspace`
  - `onDeleteProject`
- Add a `新建 Project` button in the project section header that calls `onCreateProject(activeWorkspace.id)`.
- Add a `删除 Workspace` button in the selected workspace row.
- Add a `删除 Project` button in the selected project row.
- Update the project summary line from `activeProject?.local_path` to `activeProject?.path`.

- [ ] **Step 5: Wire creation state into `Workspace.jsx` and verify tests pass**

In `frontend/src/pages/Workspace/Workspace.jsx`, add:

```jsx
const [resourceDialog, setResourceDialog] = useState({ open: false, mode: 'workspace' });
const [creatingWorkspace, setCreatingWorkspace] = useState(false);
const [creatingProject, setCreatingProject] = useState(false);
```

Add handlers:

```jsx
async function handleCreateWorkspace(payload) {
  setCreatingWorkspace(true);
  try {
    await fetchJson('/api/workspaces', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    await reloadResources();
  } finally {
    setCreatingWorkspace(false);
  }
}

async function handleCreateProject(workspaceId, payload) {
  setCreatingProject(true);
  try {
    await fetchJson(`/api/workspaces/${workspaceId}/projects`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    await reloadResources();
    setSelectedWorkspaceId(workspaceId);
  } finally {
    setCreatingProject(false);
  }
}
```

Run: `npm test -- WorkspaceResourceDialog.test.jsx WorkspaceBrowser.test.jsx`

Expected: PASS with creation dialog rendering and explorer action hooks covered.

- [ ] **Step 6: Commit the Workspace creation flows**

```bash
git add frontend/src/components/WorkspaceResourceDialog frontend/src/components/WorkspaceBrowser/WorkspaceBrowser.jsx frontend/src/components/WorkspaceBrowser/WorkspaceBrowser.css frontend/src/components/WorkspaceBrowser/WorkspaceBrowser.test.jsx frontend/src/pages/Workspace/Workspace.jsx
git commit -m "feat(frontend): add workspace resource creation flows"
```

## Task 4: Add project and workspace deletion flows to the frontend

**Files:**
- Modify: `frontend/src/pages/Workspace/Workspace.jsx`
- Modify: `frontend/src/components/WorkspaceBrowser/WorkspaceBrowser.jsx`
- Modify: `frontend/src/components/WorkspaceBrowser/WorkspaceBrowser.test.jsx`
- Modify: `frontend/src/pages/Messages/Messages.jsx`
- Test: `frontend/src/components/WorkspaceBrowser/WorkspaceBrowser.test.jsx`

- [ ] **Step 1: Write the failing delete-action test for the Workspace page state flow**

Extend `frontend/src/components/WorkspaceBrowser/WorkspaceBrowser.test.jsx` with:

```jsx
  it('calls delete handlers for workspace and project actions', async () => {
    const user = userEvent.setup();
    const onDeleteWorkspace = vi.fn();
    const onDeleteProject = vi.fn();

    render(
      <WorkspaceBrowser
        activeWorkspace={workspaces[0]}
        activeProject={projectsByWorkspace['ws-1'][0]}
        workspaces={workspaces}
        projectsByWorkspace={projectsByWorkspace}
        selectedWorkspaceId="ws-1"
        selectedProjectId="pw-1"
        selectedFilePath=""
        onWorkspaceSelect={() => {}}
        onProjectSelect={() => {}}
        onFileSelect={() => {}}
        onCreateWorkspace={() => {}}
        onCreateProject={() => {}}
        onDeleteWorkspace={onDeleteWorkspace}
        onDeleteProject={onDeleteProject}
        fileTree={fileTree}
        fileTreeLoading={false}
        fileTreeError=""
        fileContent=""
        fileContentLoading={false}
        fileContentError=""
        loading={false}
        error=""
      />,
    );

    await user.click(screen.getAllByRole('button', { name: '删除 Workspace' })[0]);
    await user.click(screen.getAllByRole('button', { name: '删除 Project' })[0]);

    expect(onDeleteWorkspace).toHaveBeenCalledWith('ws-1');
    expect(onDeleteProject).toHaveBeenCalledWith('pw-1');
  });
```

- [ ] **Step 2: Run the frontend tests to confirm delete hooks fail before implementation**

Run: `npm test -- WorkspaceBrowser.test.jsx`

Expected: FAIL because delete action buttons and callbacks are not wired yet.

- [ ] **Step 3: Implement frontend delete handlers in `Workspace.jsx`**

Use this structure:

```jsx
async function handleDeleteProject(projectId) {
  const confirmed = window.confirm('删除该 project 会同时删除所有相关 session，确认继续吗？');
  if (!confirmed) {
    return;
  }

  setDeletingProjectId(projectId);
  try {
    await fetchJson(`/api/projects/${projectId}`, { method: 'DELETE' });
    await reloadResources();
    if (selectedProjectId === projectId) {
      setSelectedProjectId('');
      setSelectedFilePath('');
    }
  } finally {
    setDeletingProjectId('');
  }
}

async function handleDeleteWorkspace(workspaceId) {
  const confirmed = window.confirm('删除该 workspace 会同时删除其下所有 project 和相关 session，确认继续吗？');
  if (!confirmed) {
    return;
  }

  setDeletingWorkspaceId(workspaceId);
  try {
    await fetchJson(`/api/workspaces/${workspaceId}`, { method: 'DELETE' });
    await reloadResources();
    if (selectedWorkspaceId === workspaceId) {
      setSelectedWorkspaceId('');
      setSelectedProjectId('');
      setSelectedFilePath('');
    }
  } finally {
    setDeletingWorkspaceId('');
  }
}
```

After each delete, clear relevant caches from `projectTrees` and `fileContents` using `setProjectTrees` and `setFileContents` so removed resources do not linger in memory.

- [ ] **Step 4: Refresh session options after resource deletion**

In `frontend/src/pages/Messages/Messages.jsx`, add a lightweight `reloadSessions` helper extracted from the existing initial load logic so future callers can refresh the session list after workspace/project deletion. If you do not directly call it from the workspace page in this task, keep the helper ready and ensure session creation still uses current project payloads.

- [ ] **Step 5: Re-run frontend tests, lint, and build**

Run: `npm test -- WorkspaceBrowser.test.jsx SessionCreateDialog.test.jsx ConversationList.test.jsx App.test.jsx`

Expected: PASS with creation and deletion flows covered.

Run: `npm run lint`

Expected: PASS with no new lint errors.

Run: `npm run build`

Expected: PASS with the production bundle emitted under `dist/`.

- [ ] **Step 6: Commit the frontend deletion flows**

```bash
git add frontend/src/pages/Workspace/Workspace.jsx frontend/src/components/WorkspaceBrowser/WorkspaceBrowser.jsx frontend/src/components/WorkspaceBrowser/WorkspaceBrowser.test.jsx frontend/src/pages/Messages/Messages.jsx
git commit -m "feat(frontend): add workspace resource deletion flows"
```

## Plan Self-Review

- Spec coverage: The plan covers the unified `endpoint/path` model, workspace and project create/delete flows, backend cascade deletion, session impact, and existing file-preview preservation. No spec section is left without a corresponding task.
- Placeholder scan: No `TODO`, `TBD`, or vague “handle appropriately” phrases remain. Each task has explicit files, commands, and implementation snippets.
- Type consistency: The plan consistently uses `workspace.endpoint`, `project.path`, `workspace_id`, `project_workspace_id`, `creatingWorkspace`, `creatingProject`, `deletingWorkspaceId`, and `deletingProjectId` across backend and frontend tasks.
