import React from 'react';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import WorkspaceBrowser from './WorkspaceBrowser';

const workspaces = [
  {
    id: 'ws-1',
    name: 'EchoMind Core',
    description: '主协作空间',
    created_at: '2026-06-08T08:00:00Z',
    project_count: 2,
  },
];

const projectsByWorkspace = {
  'ws-1': [
    {
      id: 'pw-1',
      name: 'frontend',
      path: 'E:/Github/EchoMind/frontend',
      created_at: '2026-06-08T08:30:00Z',
    },
    {
      id: 'pw-2',
      name: 'backend',
      path: 'E:/Github/EchoMind/backend',
      created_at: '2026-06-08T08:10:00Z',
    },
  ],
};

const fileTree = [
  {
    path: 'src',
    name: 'src',
    type: 'directory',
    children: [
      {
        path: 'src/App.jsx',
        name: 'App.jsx',
        type: 'file',
        children: [],
      },
    ],
  },
];

describe('WorkspaceBrowser', () => {
  it('renders a single-page explorer layout and lets users open files from the tree', async () => {
    const user = userEvent.setup();
    const onFileSelect = vi.fn();

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
        onFileSelect={onFileSelect}
        fileTree={fileTree}
        fileTreeLoading={false}
        fileTreeError=""
        fileContent={'export default function App() {}'}
        fileContentLoading={false}
        fileContentError=""
        onCreateWorkspace={() => {}}
        loading={false}
        error=""
      />,
    );

    expect(screen.getByRole('heading', { name: 'Workspace' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'frontend' })).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'src' }));
    await user.click(screen.getByRole('button', { name: 'App.jsx' }));

    expect(onFileSelect).toHaveBeenCalledWith('src/App.jsx');
  });

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
        fileContent={'export default function App() {}'}
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
        fileContent={'export default function App() {}'}
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
});
