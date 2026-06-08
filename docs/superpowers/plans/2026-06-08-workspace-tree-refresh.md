# Workspace Tree Refresh Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a manual refresh action for the currently selected local project so the Workspace page can re-scan disk state and show newly created files without leaving the page.

**Architecture:** Keep the existing backend file-tree and file-content endpoints unchanged. Add a frontend-only refresh path that invalidates the current project's cached tree and cached file contents, then re-runs the same tree/file loading pipeline for the selected project.

**Tech Stack:** React 19, Vite 8, Vitest, React Testing Library

---

## File Map

### Existing files to modify

- `frontend/src/pages/Workspace/Workspace.jsx`
  - Add a force-refresh handler for the selected project tree and clear related file caches.
- `frontend/src/components/WorkspaceBrowser/WorkspaceBrowser.jsx`
  - Expose a visible refresh button in the current project status area.
- `frontend/src/components/WorkspaceBrowser/WorkspaceBrowser.css`
  - Style the refresh control to match the compiler-style workspace view.
- `frontend/src/components/WorkspaceBrowser/WorkspaceBrowser.test.jsx`
  - Verify the refresh button renders and triggers the callback.

## Task 1: Add manual project tree refresh

**Files:**
- Modify: `frontend/src/components/WorkspaceBrowser/WorkspaceBrowser.test.jsx`
- Modify: `frontend/src/components/WorkspaceBrowser/WorkspaceBrowser.jsx`
- Modify: `frontend/src/components/WorkspaceBrowser/WorkspaceBrowser.css`
- Modify: `frontend/src/pages/Workspace/Workspace.jsx`

- [ ] **Step 1: Write the failing refresh-button test**

Add this test to `frontend/src/components/WorkspaceBrowser/WorkspaceBrowser.test.jsx`:

```jsx
  it('calls the refresh handler for the selected project', async () => {
    const user = userEvent.setup();
    const onRefreshProject = vi.fn();

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
        onRefreshProject={onRefreshProject}
        fileTree={fileTree}
        fileTreeLoading={false}
        fileTreeError=""
        fileContent={'export default function App() {}'}
        fileContentLoading={false}
        fileContentError=""
        loading={false}
        error=""
      />,
    );

    await user.click(screen.getByRole('button', { name: '刷新文件树' }));

    expect(onRefreshProject).toHaveBeenCalledWith('pw-1');
  });
```

- [ ] **Step 2: Run the test to verify it fails before implementation**

Run: `npm test -- WorkspaceBrowser.test.jsx`

Expected: FAIL because `WorkspaceBrowser` does not yet render `刷新文件树` or accept `onRefreshProject`.

- [ ] **Step 3: Add the refresh control to `WorkspaceBrowser.jsx`**

Apply these changes:

```jsx
// Add prop in the function signature
onRefreshProject,
```

```jsx
// In the project summary/status section, add:
<button
  type="button"
  className="workspace-subtle-btn"
  onClick={() => onRefreshProject(selectedProjectId)}
  disabled={!selectedProjectId || fileTreeLoading}
  aria-label="刷新文件树"
>
  {fileTreeLoading ? '刷新中' : '刷新文件树'}
</button>
```

Place it near the current project summary so it is visible while browsing files.

- [ ] **Step 4: Implement cache invalidation and forced reload in `Workspace.jsx`**

Add this handler:

```jsx
function handleRefreshProject(projectId) {
  if (!projectId) {
    return;
  }

  setProjectTrees((current) => {
    const next = { ...current };
    delete next[projectId];
    return next;
  });

  setFileContents((current) =>
    Object.fromEntries(Object.entries(current).filter(([key]) => !key.startsWith(`${projectId}:`))),
  );

  setSelectedFilePath('');
}
```

Then pass it down:

```jsx
onRefreshProject={handleRefreshProject}
```

This should cause the existing `useEffect` tree loader to re-run because the cached tree state for that project no longer exists.

- [ ] **Step 5: Add the minimal refresh-button styles**

In `frontend/src/components/WorkspaceBrowser/WorkspaceBrowser.css`, ensure the existing `.workspace-subtle-btn` style works in the status area. If needed, add:

```css
.workspace-status-actions {
  display: flex;
  gap: 8px;
  align-items: center;
}
```

And wrap the project-status controls with that class so the button aligns cleanly.

- [ ] **Step 6: Run tests, lint, and build to verify the refresh flow**

Run: `npm test -- WorkspaceBrowser.test.jsx App.test.jsx`

Expected: PASS with the refresh-button callback test green.

Run: `npm run lint`

Expected: PASS with no new lint errors.

Run: `npm run build`

Expected: PASS with the production bundle emitted under `dist/`.

- [ ] **Step 7: Commit the refresh feature**

```bash
git add frontend/src/pages/Workspace/Workspace.jsx frontend/src/components/WorkspaceBrowser/WorkspaceBrowser.jsx frontend/src/components/WorkspaceBrowser/WorkspaceBrowser.css frontend/src/components/WorkspaceBrowser/WorkspaceBrowser.test.jsx
git commit -m "feat(frontend): add workspace tree refresh"
```

## Plan Self-Review

- Spec coverage: This plan covers the agreed scope exactly: a manual refresh button for the selected local project, cache invalidation for the project's tree and file content, and no remote endpoint changes.
- Placeholder scan: No placeholders or vague “handle appropriately” instructions remain. The test, handler, and verification commands are explicit.
- Type consistency: The plan consistently uses `onRefreshProject`, `projectId`, `projectTrees`, `fileContents`, and `selectedFilePath` across the test and implementation steps.
