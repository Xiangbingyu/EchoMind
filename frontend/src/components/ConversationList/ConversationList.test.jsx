import React from 'react';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import ConversationList from './ConversationList';

const sessions = [
  { id: 's-1', title: '前端重构', type: 'single', created_at: '2026-06-08T08:00:00Z' },
  { id: 's-2', title: '文档整理', type: 'single', created_at: '2026-06-08T09:00:00Z' },
];

describe('ConversationList', () => {
  it('renders create session entry point', () => {
    render(
      <ConversationList
        sessions={sessions}
        activeChat={sessions[0]}
        onSelectChat={() => {}}
        onCreateSession={() => {}}
        onDeleteSession={() => {}}
        loading={false}
        error=""
      />,
    );

    expect(screen.getByRole('button', { name: '新建 Session' })).toBeInTheDocument();
  });

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
