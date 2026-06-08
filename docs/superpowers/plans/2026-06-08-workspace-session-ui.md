# Workspace Session UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an independent `Workspace` management page, keep `Messages` focused on session workflows, and support creating and deleting sessions with explicit `workspace` and `project workspace` selection.

**Architecture:** Split the current mixed `Messages` page responsibilities into two route-level flows. `Messages` keeps chat and session runtime concerns, while a new `Workspace` page owns resource browsing and creation. Add a minimal frontend test harness first so routing, resource selection, and session actions can be verified as the UI grows.

**Tech Stack:** React 19, Vite 8, React Router 7, ESLint, Vitest, React Testing Library

---

## File Map

### Existing files to modify

- `frontend/package.json`
  - Add test dependencies and scripts.
- `frontend/src/App.jsx`
  - Register the new `Workspace` route.
- `frontend/src/components/Sidebar/Sidebar.jsx`
  - Add the `Workspace` navigation entry.
- `frontend/src/components/Sidebar/Sidebar.css`
  - Adjust sidebar spacing if the extra nav item needs it.
- `frontend/src/components/ConversationList/ConversationList.jsx`
  - Add session create and delete UI hooks.
- `frontend/src/components/ConversationList/ConversationList.css`
  - Style the new session actions.
- `frontend/src/components/WorkspacePanel/WorkspacePanel.jsx`
  - Rename user-facing copy from resource semantics to runtime semantics.
- `frontend/src/pages/Messages/Messages.jsx`
  - Move resource-fetching responsibilities out, add session create/delete flows, and keep only session runtime state.
- `frontend/src/pages/Messages/Messages.css`
  - Adjust layout if session creation UI changes list width or header behavior.

### New frontend files to create

- `frontend/vitest.config.js`
  - Vitest config for jsdom and React tests.
- `frontend/src/test/setup.js`
  - Global test setup for RTL matchers and fetch mocks.
- `frontend/src/pages/Workspace/Workspace.jsx`
  - New route-level page for workspace browsing.
- `frontend/src/pages/Workspace/Workspace.css`
  - Layout and card styles for workspace and project workspace views.
- `frontend/src/components/SessionCreateDialog/SessionCreateDialog.jsx`
  - Modal or drawer for creating sessions from existing resources.
- `frontend/src/components/SessionCreateDialog/SessionCreateDialog.css`
  - Styles for the create-session form.
- `frontend/src/components/WorkspaceBrowser/WorkspaceBrowser.jsx`
  - Focused component for workspace list, workspace detail, and file preview states.
- `frontend/src/components/WorkspaceBrowser/WorkspaceBrowser.css`
  - Styles for workspace cards, project workspace list, and file preview panes.
- `frontend/src/utils/api.js`
  - Shared API base URL helpers and small fetch wrappers if needed to avoid repeating resource fetch logic.

### New tests to create

- `frontend/src/App.test.jsx`
  - Verify navigation and route rendering.
- `frontend/src/components/SessionCreateDialog/SessionCreateDialog.test.jsx`
  - Verify create-session field dependency behavior.
- `frontend/src/components/ConversationList/ConversationList.test.jsx`
  - Verify create button and delete action rendering.
- `frontend/src/components/WorkspaceBrowser/WorkspaceBrowser.test.jsx`
  - Verify workspace grid, workspace detail, and file preview states.

## Task 1: Add frontend test harness

**Files:**
- Modify: `frontend/package.json`
- Create: `frontend/vitest.config.js`
- Create: `frontend/src/test/setup.js`
- Test: `frontend/src/App.test.jsx`

- [ ] **Step 1: Add failing test dependencies and scripts in `frontend/package.json`**

```json
{
  "scripts": {
    "dev": "vite",
    "build": "vite build",
    "lint": "eslint .",
    "preview": "vite preview",
    "test": "vitest run",
    "test:watch": "vitest"
  },
  "devDependencies": {
    "@eslint/js": "^10.0.1",
    "@testing-library/jest-dom": "^6.6.3",
    "@testing-library/react": "^16.0.1",
    "@testing-library/user-event": "^14.5.2",
    "@types/react": "^19.2.14",
    "@types/react-dom": "^19.2.3",
    "@vitejs/plugin-react": "^6.0.1",
    "eslint": "^10.3.0",
    "eslint-plugin-react-hooks": "^7.1.1",
    "eslint-plugin-react-refresh": "^0.5.2",
    "globals": "^17.6.0",
    "jsdom": "^25.0.1",
    "vite": "^8.0.12",
    "vitest": "^2.1.5"
  }
}
```

- [ ] **Step 2: Add Vitest config in `frontend/vitest.config.js`**

```js
import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: './src/test/setup.js',
  },
});
```

- [ ] **Step 3: Add shared test setup in `frontend/src/test/setup.js`**

```js
import '@testing-library/jest-dom/vitest';

beforeEach(() => {
  global.fetch = vi.fn();
});

afterEach(() => {
  vi.restoreAllMocks();
});
```

- [ ] **Step 4: Write the initial failing route smoke test in `frontend/src/App.test.jsx`**

```jsx
import { render, screen } from '@testing-library/react';
import App from './App';

describe('App routes', () => {
  it('renders the messages navigation entry on boot', () => {
    render(<App />);
    expect(screen.getByRole('link', { name: '消息' })).toBeInTheDocument();
  });
});
```

- [ ] **Step 5: Run the new test to confirm the harness works**

Run: `npm test -- App.test.jsx`

Expected: PASS with one route smoke test.

- [ ] **Step 6: Commit the test harness**

```bash
git add frontend/package.json frontend/package-lock.json frontend/vitest.config.js frontend/src/test/setup.js frontend/src/App.test.jsx
git commit -m "test(frontend): add vitest harness"
```

## Task 2: Add the Workspace route and navigation shell

**Files:**
- Modify: `frontend/src/App.jsx`
- Modify: `frontend/src/components/Sidebar/Sidebar.jsx`
- Modify: `frontend/src/components/Sidebar/Sidebar.css`
- Create: `frontend/src/pages/Workspace/Workspace.jsx`
- Create: `frontend/src/pages/Workspace/Workspace.css`
- Test: `frontend/src/App.test.jsx`

- [ ] **Step 1: Expand the failing route test to cover the new Workspace entry**

```jsx
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import App from './App';

describe('App routes', () => {
  it('navigates to the workspace page from the sidebar', async () => {
    const user = userEvent.setup();
    render(<App />);

    await user.click(screen.getByRole('link', { name: 'Workspace' }));

    expect(screen.getByRole('heading', { name: 'Workspace' })).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Add the route shell in `frontend/src/pages/Workspace/Workspace.jsx`**

```jsx
import './Workspace.css';

export default function Workspace() {
  return (
    <div className="workspace-page">
      <header className="workspace-page-header">
        <div>
          <h1>Workspace</h1>
          <p>管理所有 workspace 与 project workspace 资源。</p>
        </div>
      </header>
      <div className="workspace-page-empty">工作区页面正在加载资源...</div>
    </div>
  );
}
```

- [ ] **Step 3: Add the base page styles in `frontend/src/pages/Workspace/Workspace.css`**

```css
.workspace-page {
  display: flex;
  flex-direction: column;
  height: 100%;
  padding: 28px 32px;
  background: #f5f7fb;
  gap: 24px;
}

.workspace-page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
}

.workspace-page-header h1 {
  margin: 0;
  font-size: 30px;
}

.workspace-page-header p {
  margin: 8px 0 0;
  color: var(--fs-text-secondary);
}

.workspace-page-empty {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 20px;
  border: 1px dashed var(--fs-border);
  background: rgba(255, 255, 255, 0.78);
  color: var(--fs-text-secondary);
}
```

- [ ] **Step 4: Register the route and sidebar entry**

```jsx
// frontend/src/App.jsx
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import MainLayout from './layouts/MainLayout';
import Messages from './pages/Messages/Messages';
import Workspace from './pages/Workspace/Workspace';

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<MainLayout />}>
          <Route index element={<Navigate to="/messages" replace />} />
          <Route path="messages" element={<Messages />} />
          <Route path="workspace" element={<Workspace />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}

export default App;
```

```jsx
// frontend/src/components/Sidebar/Sidebar.jsx
import { FolderKanban, MessageSquare } from 'lucide-react';
import { NavLink } from 'react-router-dom';
import './Sidebar.css';

export default function Sidebar() {
  return (
    <div className="sidebar">
      <div className="sidebar-avatar">
        <div className="avatar-placeholder">U</div>
      </div>

      <nav className="sidebar-nav">
        <NavLink to="/messages" className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}>
          <MessageSquare size={24} strokeWidth={1.5} />
          <span>消息</span>
        </NavLink>
        <NavLink to="/workspace" className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}>
          <FolderKanban size={24} strokeWidth={1.5} />
          <span>Workspace</span>
        </NavLink>
      </nav>
    </div>
  );
}
```

- [ ] **Step 5: Run route tests and lint**

Run: `npm test -- App.test.jsx`

Expected: PASS with both sidebar entries rendering and the workspace route opening.

Run: `npm run lint`

Expected: PASS with no new lint errors.

- [ ] **Step 6: Commit the route shell**

```bash
git add frontend/src/App.jsx frontend/src/components/Sidebar/Sidebar.jsx frontend/src/components/Sidebar/Sidebar.css frontend/src/pages/Workspace/Workspace.jsx frontend/src/pages/Workspace/Workspace.css frontend/src/App.test.jsx
git commit -m "feat(frontend): add workspace route shell"
```

## Task 3: Build workspace resource browsing UI

**Files:**
- Create: `frontend/src/components/WorkspaceBrowser/WorkspaceBrowser.jsx`
- Create: `frontend/src/components/WorkspaceBrowser/WorkspaceBrowser.css`
- Modify: `frontend/src/pages/Workspace/Workspace.jsx`
- Modify: `frontend/src/pages/Workspace/Workspace.css`
- Create: `frontend/src/utils/api.js`
- Test: `frontend/src/components/WorkspaceBrowser/WorkspaceBrowser.test.jsx`

- [ ] **Step 1: Write failing tests for workspace grid, workspace detail, and file preview states**

```jsx
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import WorkspaceBrowser from './WorkspaceBrowser';

const workspaces = [
  { id: 'ws-1', name: 'EchoMind Core', description: '主协作空间', updated_at: '2026-06-08T08:00:00Z', project_count: 2 },
];

const projectWorkspaces = {
  'ws-1': [
    { id: 'pw-1', name: 'frontend', local_path: 'E:/Github/EchoMind/frontend', updated_at: '2026-06-08T08:30:00Z' },
    { id: 'pw-2', name: 'backend', local_path: 'E:/Github/EchoMind/backend', updated_at: '2026-06-08T08:10:00Z' },
  ],
};

const tree = [
  { path: 'src/App.jsx', type: 'file' },
  { path: 'src/components', type: 'directory' },
];

describe('WorkspaceBrowser', () => {
  it('shows workspace cards first and opens a workspace detail view', async () => {
    const user = userEvent.setup();
    render(
      <WorkspaceBrowser
        workspaces={workspaces}
        projectWorkspaces={projectWorkspaces}
        fileTree={tree}
        fileContent={'export default function App() {}'}
      />,
    );

    await user.click(screen.getByRole('button', { name: /EchoMind Core/i }));

    expect(screen.getByRole('heading', { name: 'EchoMind Core' })).toBeInTheDocument();
    expect(screen.getByText('frontend')).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Build the focused browser component**

```jsx
import { useState } from 'react';
import './WorkspaceBrowser.css';

function formatTime(value) {
  if (!value) {
    return '未知更新时间';
  }

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return '未知更新时间';
  }

  return date.toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  });
}

export default function WorkspaceBrowser({ workspaces, projectWorkspaces, fileTree, fileContent, onCreateWorkspace }) {
  const [activeWorkspaceId, setActiveWorkspaceId] = useState(null);
  const [activeProjectId, setActiveProjectId] = useState(null);

  const activeWorkspace = workspaces.find((item) => item.id === activeWorkspaceId) ?? null;
  const activeProjects = activeWorkspace ? projectWorkspaces[activeWorkspace.id] ?? [] : [];

  if (!activeWorkspace) {
    return (
      <div className="workspace-browser">
        <div className="workspace-browser-toolbar">
          <div>
            <h2>全部 Workspace</h2>
            <p>选择一个 workspace 进入 project workspace 浏览。</p>
          </div>
          <button type="button" className="workspace-primary-btn" onClick={onCreateWorkspace}>
            新建 Workspace
          </button>
        </div>

        <div className="workspace-card-grid">
          {workspaces.map((workspace) => (
            <button
              key={workspace.id}
              type="button"
              className="workspace-card"
              onClick={() => {
                setActiveWorkspaceId(workspace.id);
                setActiveProjectId(null);
              }}
              aria-label={workspace.name}
            >
              <div className="workspace-card-cover" />
              <div className="workspace-card-body">
                <h3>{workspace.name}</h3>
                <p>{workspace.description || '暂无描述'}</p>
                <div className="workspace-card-meta">
                  <span>{workspace.project_count ?? 0} 个项目</span>
                  <span>{formatTime(workspace.updated_at)}</span>
                </div>
              </div>
            </button>
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="workspace-browser">
      <div className="workspace-browser-toolbar">
        <button type="button" className="workspace-back-btn" onClick={() => setActiveWorkspaceId(null)}>
          返回 Workspace
        </button>
        <div>
          <h2>{activeWorkspace.name}</h2>
          <p>{activeWorkspace.description || '浏览该 workspace 下的 project workspace 资源。'}</p>
        </div>
      </div>

      <div className="project-workspace-layout">
        <section className="project-workspace-list">
          {activeProjects.map((project) => (
            <button
              key={project.id}
              type="button"
              className={`project-workspace-item ${activeProjectId === project.id ? 'active' : ''}`}
              onClick={() => setActiveProjectId(project.id)}
            >
              <strong>{project.name}</strong>
              <span>{project.local_path}</span>
              <span>{formatTime(project.updated_at)}</span>
            </button>
          ))}
        </section>

        <section className="project-workspace-preview">
          {!activeProjectId ? <div className="workspace-empty-state">选择一个 project workspace 查看文件。</div> : null}
          {activeProjectId ? (
            <>
              <div className="project-workspace-tree">
                {fileTree.map((entry) => (
                  <div key={entry.path} className={`tree-entry ${entry.type}`}>
                    {entry.path}
                  </div>
                ))}
              </div>
              <pre className="project-workspace-file-preview">{fileContent || '暂无文件内容'}</pre>
            </>
          ) : null}
        </section>
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Add the browser styling and mount it on the Workspace page**

```jsx
// frontend/src/pages/Workspace/Workspace.jsx
import WorkspaceBrowser from '../../components/WorkspaceBrowser/WorkspaceBrowser';
import './Workspace.css';

const demoWorkspaces = [
  { id: 'ws-1', name: 'EchoMind Core', description: '主协作空间', updated_at: '2026-06-08T08:00:00Z', project_count: 2 },
  { id: 'ws-2', name: 'Research Lab', description: '方案与调研沉淀', updated_at: '2026-06-07T14:00:00Z', project_count: 1 },
];

const demoProjectWorkspaces = {
  'ws-1': [
    { id: 'pw-1', name: 'frontend', local_path: 'E:/Github/EchoMind/frontend', updated_at: '2026-06-08T08:30:00Z' },
    { id: 'pw-2', name: 'backend', local_path: 'E:/Github/EchoMind/backend', updated_at: '2026-06-08T08:10:00Z' },
  ],
  'ws-2': [
    { id: 'pw-3', name: 'docs', local_path: 'E:/Github/EchoMind/docs', updated_at: '2026-06-07T14:20:00Z' },
  ],
};

const demoTree = [
  { path: 'src', type: 'directory' },
  { path: 'src/App.jsx', type: 'file' },
  { path: 'src/components', type: 'directory' },
  { path: 'package.json', type: 'file' },
];

export default function Workspace() {
  return (
    <div className="workspace-page">
      <WorkspaceBrowser
        workspaces={demoWorkspaces}
        projectWorkspaces={demoProjectWorkspaces}
        fileTree={demoTree}
        fileContent={'export default function App() {}'}
        onCreateWorkspace={() => {}}
      />
    </div>
  );
}
```

- [ ] **Step 4: Run focused tests and verify the workspace flow**

Run: `npm test -- WorkspaceBrowser.test.jsx App.test.jsx`

Expected: PASS with workspace card navigation and route rendering.

- [ ] **Step 5: Replace demo data reads with real resource loaders**

```js
// frontend/src/utils/api.js
export const API_BASE_URL = 'http://localhost:8000';

export async function fetchJson(path, options) {
  const response = await fetch(`${API_BASE_URL}${path}`, options);
  if (!response.ok) {
    throw new Error(`Request failed: ${response.status}`);
  }
  return response.json();
}
```

Use this helper inside `Workspace.jsx` to load:

- `GET /api/workspaces`
- `GET /api/workspaces/:workspaceId/project-workspaces`
- `GET /api/project-workspaces/:projectWorkspaceId/tree`
- `GET /api/project-workspaces/:projectWorkspaceId/file?path=...`

Keep the `WorkspaceBrowser` component presentation-focused by passing loaded state in as props.

- [ ] **Step 6: Commit the workspace browser**

```bash
git add frontend/src/pages/Workspace/Workspace.jsx frontend/src/pages/Workspace/Workspace.css frontend/src/components/WorkspaceBrowser/WorkspaceBrowser.jsx frontend/src/components/WorkspaceBrowser/WorkspaceBrowser.css frontend/src/components/WorkspaceBrowser/WorkspaceBrowser.test.jsx frontend/src/utils/api.js
git commit -m "feat(frontend): add workspace browser"
```

## Task 4: Add create-session flow using existing resources

**Files:**
- Create: `frontend/src/components/SessionCreateDialog/SessionCreateDialog.jsx`
- Create: `frontend/src/components/SessionCreateDialog/SessionCreateDialog.css`
- Modify: `frontend/src/components/ConversationList/ConversationList.jsx`
- Modify: `frontend/src/components/ConversationList/ConversationList.css`
- Modify: `frontend/src/pages/Messages/Messages.jsx`
- Modify: `frontend/src/pages/Messages/Messages.css`
- Test: `frontend/src/components/SessionCreateDialog/SessionCreateDialog.test.jsx`
- Test: `frontend/src/components/ConversationList/ConversationList.test.jsx`

- [ ] **Step 1: Write failing tests for workspace-dependent session creation**

```jsx
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import SessionCreateDialog from './SessionCreateDialog';

const workspaces = [
  { id: 'ws-1', name: 'EchoMind Core' },
  { id: 'ws-2', name: 'Research Lab' },
];

const projectWorkspaces = {
  'ws-1': [{ id: 'pw-1', name: 'frontend' }],
  'ws-2': [{ id: 'pw-2', name: 'docs' }],
};

describe('SessionCreateDialog', () => {
  it('filters project workspace options after selecting a workspace', async () => {
    const user = userEvent.setup();
    render(
      <SessionCreateDialog
        open
        workspaces={workspaces}
        projectWorkspaces={projectWorkspaces}
        onClose={() => {}}
        onSubmit={() => {}}
      />,
    );

    await user.selectOptions(screen.getByLabelText('Workspace'), 'ws-2');

    expect(screen.getByRole('option', { name: 'docs' })).toBeInTheDocument();
    expect(screen.queryByRole('option', { name: 'frontend' })).not.toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Build the dialog component**

```jsx
import { useEffect, useState } from 'react';
import './SessionCreateDialog.css';

export default function SessionCreateDialog({ open, workspaces, projectWorkspaces, onClose, onSubmit, loading }) {
  const [title, setTitle] = useState('');
  const [workspaceId, setWorkspaceId] = useState('');
  const [projectWorkspaceId, setProjectWorkspaceId] = useState('');

  useEffect(() => {
    if (!open) {
      setTitle('');
      setWorkspaceId('');
      setProjectWorkspaceId('');
    }
  }, [open]);

  const projects = workspaceId ? projectWorkspaces[workspaceId] ?? [] : [];
  const disabled = !title.trim() || !workspaceId || !projectWorkspaceId || loading;

  if (!open) {
    return null;
  }

  return (
    <div className="session-create-overlay" role="dialog" aria-modal="true" aria-label="新建 Session">
      <div className="session-create-dialog">
        <div className="session-create-header">
          <h3>新建 Session</h3>
          <button type="button" onClick={onClose}>取消</button>
        </div>

        <label>
          <span>Session 名称</span>
          <input value={title} onChange={(event) => setTitle(event.target.value)} />
        </label>

        <label>
          <span>Workspace</span>
          <select
            aria-label="Workspace"
            value={workspaceId}
            onChange={(event) => {
              setWorkspaceId(event.target.value);
              setProjectWorkspaceId('');
            }}
          >
            <option value="">请选择 Workspace</option>
            {workspaces.map((workspace) => (
              <option key={workspace.id} value={workspace.id}>
                {workspace.name}
              </option>
            ))}
          </select>
        </label>

        <label>
          <span>Project Workspace</span>
          <select
            aria-label="Project Workspace"
            value={projectWorkspaceId}
            onChange={(event) => setProjectWorkspaceId(event.target.value)}
            disabled={!workspaceId}
          >
            <option value="">请选择 Project Workspace</option>
            {projects.map((project) => (
              <option key={project.id} value={project.id}>
                {project.name}
              </option>
            ))}
          </select>
        </label>

        <div className="session-create-actions">
          <button type="button" onClick={onClose}>取消</button>
          <button
            type="button"
            disabled={disabled}
            onClick={() => onSubmit({ title: title.trim(), workspace_id: workspaceId, project_workspace_id: projectWorkspaceId })}
          >
            {loading ? '创建中' : '创建 Session'}
          </button>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Integrate dialog controls into `ConversationList.jsx` and `Messages.jsx`**

Implement these concrete UI changes:

- In `ConversationList.jsx`, add a header action button labeled `新建 Session`.
- Pass `onCreateSession`, `onDeleteSession`, and `deletingSessionId` props down from `Messages.jsx`.
- Add a per-session delete button with `aria-label={`删除 ${getSessionTitle(chat)}`}`.
- In `Messages.jsx`, add local state:

```jsx
const [workspaceOptions, setWorkspaceOptions] = useState([]);
const [projectWorkspaceOptions, setProjectWorkspaceOptions] = useState({});
const [createDialogOpen, setCreateDialogOpen] = useState(false);
const [creatingSession, setCreatingSession] = useState(false);
const [deletingSessionId, setDeletingSessionId] = useState('');
```

- Load workspaces when opening the dialog.
- Load project workspaces keyed by `workspace.id`.
- On submit, post to `/api/sessions` with:

```js
{
  title,
  type: 'single',
  workspace_id,
  project_workspace_id,
}
```

- After success, prepend or append the created session to `sessions` and call `setActiveChat(createdSession)`.

- [ ] **Step 4: Run focused session-creation tests**

Run: `npm test -- SessionCreateDialog.test.jsx ConversationList.test.jsx`

Expected: PASS with create-button rendering, workspace filtering, and delete-button rendering covered.

- [ ] **Step 5: Run app-level lint and smoke checks**

Run: `npm run lint`

Expected: PASS with no unused state or prop warnings.

- [ ] **Step 6: Commit the create-session flow**

```bash
git add frontend/src/components/SessionCreateDialog/SessionCreateDialog.jsx frontend/src/components/SessionCreateDialog/SessionCreateDialog.css frontend/src/components/SessionCreateDialog/SessionCreateDialog.test.jsx frontend/src/components/ConversationList/ConversationList.jsx frontend/src/components/ConversationList/ConversationList.css frontend/src/components/ConversationList/ConversationList.test.jsx frontend/src/pages/Messages/Messages.jsx frontend/src/pages/Messages/Messages.css
git commit -m "feat(frontend): add session creation flow"
```

## Task 5: Add delete-session flow and runtime panel cleanup

**Files:**
- Modify: `frontend/src/pages/Messages/Messages.jsx`
- Modify: `frontend/src/components/WorkspacePanel/WorkspacePanel.jsx`
- Modify: `frontend/src/components/WorkspacePanel/WorkspacePanel.css`
- Modify: `frontend/src/components/ConversationList/ConversationList.jsx`
- Test: `frontend/src/components/ConversationList/ConversationList.test.jsx`

- [ ] **Step 1: Add a failing delete-session interaction test**

```jsx
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import ConversationList from './ConversationList';

const sessions = [
  { id: 's-1', title: '前端重构', type: 'single', created_at: '2026-06-08T08:00:00Z' },
  { id: 's-2', title: '文档整理', type: 'single', created_at: '2026-06-08T09:00:00Z' },
];

describe('ConversationList', () => {
  it('calls delete handler for a session action', async () => {
    const user = userEvent.setup();
    const onDeleteSession = vi.fn();

    render(
      <ConversationList
        sessions={sessions}
        activeChat={sessions[0]}
        onSelectChat={() => {}}
        onCreateSession={() => {}}
        onDeleteSession={onDeleteSession}
        loading={false}
        error=""
      />,
    );

    await user.click(screen.getByRole('button', { name: '删除 前端重构' }));

    expect(onDeleteSession).toHaveBeenCalledWith('s-1');
  });
});
```

- [ ] **Step 2: Implement delete flow in `Messages.jsx`**

Use this logic in the delete handler:

```jsx
async function handleDeleteSession(sessionId) {
  const target = sessions.find((session) => session.id === sessionId);
  if (!target) {
    return;
  }

  const confirmed = window.confirm(`删除会话“${target.title || `会话 ${target.id.slice(0, 8)}`}”后，消息历史将被清空，但不会影响任何 workspace 资源。`);
  if (!confirmed) {
    return;
  }

  setDeletingSessionId(sessionId);

  try {
    const response = await fetch(`${API_BASE_URL}/api/sessions/${sessionId}`, { method: 'DELETE' });
    if (!response.ok) {
      throw new Error(`Failed to delete session: ${response.status}`);
    }

    setSessions((current) => {
      const next = current.filter((session) => session.id !== sessionId);
      setActiveChat((previous) => {
        if (!previous || previous.id !== sessionId) {
          return previous;
        }
        return next[0] ?? null;
      });
      return next;
    });
  } finally {
    setDeletingSessionId('');
  }
}
```

- [ ] **Step 3: Rename the runtime panel copy in `WorkspacePanel.jsx`**

Apply these exact copy changes:

- Header `工作区 (Workspace)` -> `运行态 (Runtime)`
- Placeholder `选择一个会话后查看工作区运行态。` -> `选择一个会话后查看当前运行态。`
- Placeholder `正在加载工作区快照...` -> `正在加载运行态快照...`
- Section title `Workspace` -> `Binding`
- Section title `Files` -> `Tree`

Do not remove the runtime data itself in this task. Only align semantics so it no longer conflicts with the new `Workspace` page.

- [ ] **Step 4: Run targeted tests, lint, and build**

Run: `npm test -- ConversationList.test.jsx App.test.jsx WorkspaceBrowser.test.jsx SessionCreateDialog.test.jsx`

Expected: PASS with route, workspace, create-session, and delete-session coverage.

Run: `npm run lint`

Expected: PASS with no new lint errors.

Run: `npm run build`

Expected: PASS with production bundle emitted under `dist/`.

- [ ] **Step 5: Commit delete flow and runtime cleanup**

```bash
git add frontend/src/pages/Messages/Messages.jsx frontend/src/components/WorkspacePanel/WorkspacePanel.jsx frontend/src/components/WorkspacePanel/WorkspacePanel.css frontend/src/components/ConversationList/ConversationList.jsx frontend/src/components/ConversationList/ConversationList.test.jsx
git commit -m "feat(frontend): add session deletion flow"
```

## Plan Self-Review

- Spec coverage: The plan covers sidebar navigation, independent workspace browsing, workspace creation entry point, project workspace browsing, file preview, session create/delete flows, and runtime-panel copy cleanup. The only deferred area is backend endpoint implementation; this plan assumes frontend can call the documented contracts and should be paired with backend work if those endpoints do not yet exist.
- Placeholder scan: No `TODO`, `TBD`, or vague “handle appropriately” instructions remain. Code steps, commands, and file paths are explicit.
- Type consistency: The plan consistently uses `workspace_id`, `project_workspace_id`, `workspaces`, `projectWorkspaces`, `createDialogOpen`, `creatingSession`, and `deletingSessionId` across component and route tasks.
