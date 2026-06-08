import React from 'react';
import { useState } from 'react';
import { Plus, Search, Trash2 } from 'lucide-react';
import './ConversationList.css';

function formatSessionTime(value) {
  if (!value) {
    return '';
  }

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return '';
  }

  return date.toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  });
}

function getSessionTitle(session) {
  return session.title || `会话 ${session.id.slice(0, 8)}`;
}

export default function ConversationList({
  sessions,
  activeChat,
  onSelectChat,
  onCreateSession,
  onDeleteSession,
  deletingSessionId,
  loading,
  error,
}) {
  const [filter, setFilter] = useState('single');
  const [keyword, setKeyword] = useState('');

  const filteredChats = sessions.filter((chat) => {
    if (chat.type !== filter) {
      return false;
    }

    if (!keyword.trim()) {
      return true;
    }

    return getSessionTitle(chat).toLowerCase().includes(keyword.trim().toLowerCase());
  });

  return (
    <div className="conversation-list-container">
      <div className="conversation-header">
        <div className="header-top">
          <h2>消息</h2>
          <button type="button" className="conversation-create-btn" onClick={onCreateSession}>
            <Plus size={16} />
            新建 Session
          </button>
        </div>

        <div className="search-bar">
          <Search size={16} className="search-icon" />
          <input
            type="text"
            placeholder="搜索会话"
            value={keyword}
            onChange={(e) => setKeyword(e.target.value)}
          />
        </div>

        <div className="conversation-tabs">
          <div
            className={`tab ${filter === 'single' ? 'active' : ''}`}
            onClick={() => setFilter('single')}
          >
            单聊
          </div>
          <div
            className={`tab ${filter === 'group' ? 'active' : ''}`}
            onClick={() => setFilter('group')}
          >
            群聊
          </div>
        </div>
      </div>

      <div className="conversation-list">
        {loading ? <div className="conversation-state">正在加载会话...</div> : null}
        {!loading && error ? <div className="conversation-state error">{error}</div> : null}
        {!loading && !error && filteredChats.length === 0 ? (
          <div className="conversation-state">暂无{filter === 'single' ? '单聊' : '群聊'}会话</div>
        ) : null}

        {!loading && !error
          ? filteredChats.map((chat) => (
              <div
                key={chat.id}
                className={`conversation-item ${activeChat?.id === chat.id ? 'active' : ''}`}
                onClick={() => onSelectChat(chat)}
              >
                <div className={`avatar ${chat.type === 'group' ? 'group-avatar' : ''}`}>
                  {getSessionTitle(chat)[0]}
                </div>
                <div className="info">
                  <div className="info-top">
                    <span className="name">{getSessionTitle(chat)}</span>
                    <span className="time">{formatSessionTime(chat.last_active_at || chat.created_at)}</span>
                  </div>
                  <div className="info-bottom">{chat.type === 'single' ? '单聊会话' : '群聊会话'}</div>
                </div>
                <button
                  type="button"
                  className="conversation-delete-btn"
                  aria-label={`删除 ${getSessionTitle(chat)}`}
                  onClick={(event) => {
                    event.stopPropagation();
                    onDeleteSession(chat.id);
                  }}
                  disabled={deletingSessionId === chat.id}
                >
                  <Trash2 size={16} />
                </button>
              </div>
            ))
          : null}
      </div>
    </div>
  );
}
