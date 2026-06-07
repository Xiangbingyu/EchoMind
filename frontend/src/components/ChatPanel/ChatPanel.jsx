import { useEffect, useRef, useState } from 'react';
import { Send, Smile, Paperclip, Phone, Video, MoreHorizontal } from 'lucide-react';
import './ChatPanel.css';

function getSessionTitle(session) {
  return session.title || `会话 ${session.id.slice(0, 8)}`;
}

function toDisplayMessages(items) {
  return items
    .filter((item) => item.role === 'user' || item.role === 'agent')
    .map((item) => ({
      id: item.id,
      role: item.role,
      content: item.content,
      pending: false,
    }));
}

export default function ChatPanel({ activeChat, apiBaseUrl }) {
  const [inputValue, setInputValue] = useState('');
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [statusText, setStatusText] = useState('');
  const [sending, setSending] = useState(false);
  const wsRef = useRef(null);
  const streamMessageIdRef = useRef(null);
  const messageEndRef = useRef(null);

  useEffect(() => {
    messageEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, statusText]);

  useEffect(() => {
    if (!activeChat) {
      setMessages([]);
      setError('');
      setStatusText('');
      return undefined;
    }

    let cancelled = false;
    const wsUrl = `${apiBaseUrl.replace('http', 'ws')}/ws/session/${activeChat.id}`;

    async function loadMessages() {
      setLoading(true);
      setError('');
      setStatusText('');
      streamMessageIdRef.current = null;

      try {
        const response = await fetch(`${apiBaseUrl}/api/sessions/${activeChat.id}/messages`);
        if (!response.ok) {
          throw new Error(`Failed to load messages: ${response.status}`);
        }
        const data = await response.json();
        if (!cancelled) {
          setMessages(toDisplayMessages(data));
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : 'Failed to load messages');
          setMessages([]);
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    loadMessages();

    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onmessage = (event) => {
      const payload = JSON.parse(event.data);

      if (payload.type === 'task.status') {
        if (!cancelled) {
          setStatusText(payload.data || '');
          if (String(payload.data || '').startsWith('failed')) {
            setSending(false);
          }
        }
        return;
      }

      if (payload.type === 'agent.token') {
        if (cancelled) {
          return;
        }

        setMessages((current) => {
          const streamId = streamMessageIdRef.current;
          if (!streamId) {
            const newId = `stream-${Date.now()}`;
            streamMessageIdRef.current = newId;
            return [...current, { id: newId, role: 'agent', content: payload.data || '', pending: true }];
          }

          return current.map((item) =>
            item.id === streamId ? { ...item, content: `${item.content}${payload.data || ''}` } : item,
          );
        });
        return;
      }

      if (payload.type === 'agent.done') {
        if (cancelled) {
          return;
        }

        setSending(false);
        setMessages((current) => {
          const streamId = streamMessageIdRef.current;
          streamMessageIdRef.current = null;
          if (!streamId) {
            return [...current, { id: `done-${Date.now()}`, role: 'agent', content: payload.data || '', pending: false }];
          }

          return current.map((item) =>
            item.id === streamId ? { ...item, content: payload.data || item.content, pending: false } : item,
          );
        });
        return;
      }

      if (payload.type === 'error' && !cancelled) {
        setError(payload.data || '消息发送失败');
        setSending(false);
      }
    };

    ws.onerror = () => {
      if (!cancelled) {
        setError('WebSocket 连接失败');
        setSending(false);
      }
    };

    ws.onclose = () => {
      if (!cancelled) {
        setSending(false);
      }
    };

    return () => {
      cancelled = true;
      streamMessageIdRef.current = null;
      ws.close();
      if (wsRef.current === ws) {
        wsRef.current = null;
      }
    };
  }, [activeChat, apiBaseUrl]);

  function handleSend() {
    const text = inputValue.trim();
    const ws = wsRef.current;
    if (!text || !ws || ws.readyState !== WebSocket.OPEN) {
      return;
    }

    setError('');
    setStatusText('');
    setSending(true);
    setMessages((current) => [
      ...current,
      { id: `user-${Date.now()}`, role: 'user', content: text, pending: false },
    ]);
    ws.send(text);
    setInputValue('');
  }

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
          onChange={(e) => setInputValue(e.target.value)}
        />
        <div className="chat-input-actions">
          <button className="send-btn" disabled={!inputValue.trim() || sending} onClick={handleSend}>
            <Send size={16} />
            {sending ? '发送中' : '发送'}
          </button>
        </div>
      </div>
    </div>
  );
}
