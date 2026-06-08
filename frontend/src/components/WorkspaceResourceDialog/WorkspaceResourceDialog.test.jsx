import React from 'react';
import { render, screen } from '@testing-library/react';
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
    expect(screen.getByText('MVP 仅支持本地 workspace，请填写 localhost。')).toBeInTheDocument();
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
