import React from 'react';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import App from './App';

describe('App routes', () => {
  it('renders the messages navigation entry on boot', async () => {
    render(<App />);
    await screen.findByText('暂无单聊会话');
    expect(screen.getByRole('link', { name: '消息' })).toBeInTheDocument();
  });

  it('navigates to the workspace page from the sidebar', async () => {
    const user = userEvent.setup();
    render(<App />);

    await user.click(screen.getByRole('link', { name: 'Workspace' }));

    expect(screen.getByRole('heading', { name: 'Workspace' })).toBeInTheDocument();
  });
});
