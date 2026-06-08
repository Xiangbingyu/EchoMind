import React from 'react';
import { useEffect, useRef } from 'react';
import { Send, Smile, Paperclip, Phone, Video, MoreHorizontal } from 'lucide-react';
import './ChatPanel.css';

function getSessionTitle(session) {
  return session.title || `会话 ${session.id.slice(0, 8)}`;
}

export default function ChatPanel({
  activeChat,
  inputValue,
  messages,
  loading,
  error,
  statusText,
  sending,
  onInputChange,
  onSend,
}) {
  const messageEndRef = useRef(null);

  useEffect(() => {
    messageEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, statusText]);

  if (!activeChat) {
    return (
      <div className="chat-panel-empty">
        <div className="empty-icon">💬</div>
        <p>选择一个聊天开始交谈</p>
      </div>
    );
  }

  return (
    <div className="chat-panel">
      <div className="chat-header">
        <div className="header-left">
          <h3>{getSessionTitle(activeChat)}</h3>
          <span className="chat-type">{activeChat.type === 'single' ? '单聊' : '群聊'}</span>
        </div>
        <div className="header-right">
          <button className="icon-btn"><Phone size={20} /></button>
          <button className="icon-btn"><Video size={20} /></button>
          <button className="icon-btn"><MoreHorizontal size={20} /></button>
        </div>
      </div>

      <div className="chat-messages">
        {loading ? <div className="chat-state">正在加载消息...</div> : null}
        {!loading && error ? <div className="chat-state error">{error}</div> : null}
        {!loading && !error && messages.length === 0 ? <div className="chat-state">还没有消息，开始对话吧。</div> : null}

        {messages.map((message) => (
          <div key={message.id} className={`message-wrapper ${message.role === 'user' ? 'send' : 'receive'}`}>
            <div className={`message-avatar ${message.role === 'user' ? 'self' : ''}`}>
              {message.role === 'user' ? 'U' : getSessionTitle(activeChat)[0]}
            </div>
            <div className="message-content">
              <div className="message-name">{message.role === 'user' ? '你' : getSessionTitle(activeChat)}</div>
              <div className="message-bubble">
                {message.content}
                {message.pending ? <span className="stream-cursor">|</span> : null}
              </div>
            </div>
          </div>
        ))}

        {statusText ? <div className="chat-status-line">状态：{statusText}</div> : null}
        <div ref={messageEndRef} />
      </div>

      <div className="chat-input-area">
        <div className="chat-toolbar">
          <button className="toolbar-btn" title="表情"><Smile size={20} /></button>
          <button className="toolbar-btn" title="附件"><Paperclip size={20} /></button>
        </div>
        <textarea
          className="chat-textarea"
          placeholder="发送消息..."
          value={inputValue}
          onChange={(e) => onInputChange(e.target.value)}
        />
        <div className="chat-input-actions">
          <button className="send-btn" disabled={!inputValue.trim() || sending} onClick={onSend}>
            <Send size={16} />
            {sending ? '发送中' : '发送'}
          </button>
        </div>
      </div>
    </div>
  );
}
