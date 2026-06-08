import React from 'react';
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
