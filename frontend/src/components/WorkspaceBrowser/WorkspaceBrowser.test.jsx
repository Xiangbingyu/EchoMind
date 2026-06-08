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
      local_path: 'E:/Github/EchoMind/frontend',
      created_at: '2026-06-08T08:30:00Z',
    },
    {
      id: 'pw-2',
      name: 'backend',
      local_path: 'E:/Github/EchoMind/backend',
      created_at: '2026-06-08T08:10:00Z',
    },
  ],
};

const fileTree = [
  { path: 'src', type: 'directory' },
  { path: 'src/App.jsx', type: 'file' },
];

describe('WorkspaceBrowser', () => {
  it('shows workspace cards first and opens a workspace detail view', async () => {
    const user = userEvent.setup();

    render(
      <WorkspaceBrowser
        workspaces={workspaces}
        projectsByWorkspace={projectsByWorkspace}
        selectedProjectId="pw-1"
        fileTree={fileTree}
        fileContent={'export default function App() {}'}
      />,
    );

    await user.click(screen.getByRole('button', { name: /EchoMind Core/i }));

    expect(screen.getByRole('heading', { name: 'EchoMind Core' })).toBeInTheDocument();
    expect(screen.getByText('frontend')).toBeInTheDocument();
    expect(screen.getByText('src/App.jsx')).toBeInTheDocument();
  });
});
