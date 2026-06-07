import { useEffect, useRef, useState } from 'react';
import ConversationList from '../../components/ConversationList/ConversationList';
import ChatPanel from '../../components/ChatPanel/ChatPanel';
import WorkspacePanel from '../../components/WorkspacePanel/WorkspacePanel';
import './Messages.css';

const API_BASE_URL = 'http://localhost:8000';
const LEFT_PANEL_INITIAL_WIDTH = 320;
const LEFT_PANEL_MIN_WIDTH = 260;
const LEFT_PANEL_MAX_WIDTH = 520;
const RIGHT_PANEL_INITIAL_WIDTH = 400;
const RIGHT_PANEL_MIN_WIDTH = RIGHT_PANEL_INITIAL_WIDTH;
const CENTER_PANEL_MIN_WIDTH = 720;
const WORKSPACE_COLLAPSED_WIDTH = 44;

function toDisplayMessages(items) {
  return items
    .filter((item) => item.role === 'user' || item.role === 'agent')
    .map((item, index) => ({
      id: item.id || `msg-${index}`,
      role: item.role,
      content: item.content,
      pending: false,
    }));
}

export default function Messages() {
  const [activeChat, setActiveChat] = useState(null);
  const [sessions, setSessions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [chatMessages, setChatMessages] = useState([]);
  const [chatLoading, setChatLoading] = useState(false);
  const [chatError, setChatError] = useState('');
  const [chatStatus, setChatStatus] = useState('');
  const [taskState, setTaskState] = useState('');
  const [sending, setSending] = useState(false);
  const [inputValue, setInputValue] = useState('');
  const [workspaceSnapshot, setWorkspaceSnapshot] = useState(null);
  const [workspaceTree, setWorkspaceTree] = useState([]);
  const [planState, setPlanState] = useState([]);
  const [sandboxState, setSandboxState] = useState({ status: 'idle' });
  const [agentState, setAgentState] = useState({ status: 'idle', last_error: '' });
  const [workspaceError, setWorkspaceError] = useState('');
  const [leftPanelWidth, setLeftPanelWidth] = useState(LEFT_PANEL_INITIAL_WIDTH);
  const [rightPanelWidth, setRightPanelWidth] = useState(RIGHT_PANEL_INITIAL_WIDTH);
  const [workspaceCollapsed, setWorkspaceCollapsed] = useState(false);
  const containerRef = useRef(null);
  const chatSocketRef = useRef(null);
  const workspaceSocketRef = useRef(null);
  const streamMessageIdRef = useRef(null);

  useEffect(() => {
    let cancelled = false;

    async function loadSessions() {
      setLoading(true);
      setError('');

      try {
        const response = await fetch(`${API_BASE_URL}/api/sessions?type=single`);
        if (!response.ok) {
          throw new Error(`Failed to load sessions: ${response.status}`);
        }

        const data = await response.json();
        if (cancelled) {
          return;
        }

        setSessions(data);
        setActiveChat((current) => {
          if (current && data.some((session) => session.id === current.id)) {
            return current;
          }
          return data[0] ?? null;
        });
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : 'Failed to load sessions');
          setSessions([]);
          setActiveChat(null);
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    loadSessions();

    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!activeChat) {
      setChatMessages([]);
      setChatStatus('');
      setTaskState('');
      setChatError('');
      setSending(false);
      streamMessageIdRef.current = null;
      return undefined;
    }

    setChatLoading(true);
    setChatError('');
    setChatStatus('');
    setTaskState('');
    streamMessageIdRef.current = null;

    const wsUrl = `${API_BASE_URL.replace('http', 'ws')}/ws/session/${activeChat.id}/chat`;
    const ws = new WebSocket(wsUrl);
    chatSocketRef.current = ws;

    ws.onmessage = (event) => {
      const payload = JSON.parse(event.data);

      if (payload.type === 'message.history.sync') {
        setChatMessages(toDisplayMessages(payload.data || []));
        setChatLoading(false);
        return;
      }

      if (payload.type === 'chat.status') {
        setChatStatus(payload.data || '');
        return;
      }

      if (payload.type === 'task.status') {
        setTaskState(payload.data || '');
        if (String(payload.data || '').startsWith('failed')) {
          setSending(false);
        }
        return;
      }

      if (payload.type === 'agent.token') {
        setChatMessages((current) => {
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
        setSending(false);
        setChatMessages((current) => {
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

      if (payload.type === 'error') {
        setChatError(payload.data || '消息发送失败');
        setSending(false);
      }
    };

    ws.onerror = () => {
      setChatError('Chat WebSocket 连接失败');
      setChatLoading(false);
      setSending(false);
    };

    ws.onclose = () => {
      setSending(false);
      setChatLoading(false);
    };

    return () => {
      streamMessageIdRef.current = null;
      ws.close();
      if (chatSocketRef.current === ws) {
        chatSocketRef.current = null;
      }
    };
  }, [activeChat]);

  useEffect(() => {
    if (!activeChat) {
      setWorkspaceSnapshot(null);
      setWorkspaceTree([]);
      setPlanState([]);
      setSandboxState({ status: 'idle' });
      setAgentState({ status: 'idle', last_error: '' });
      setWorkspaceError('');
      return undefined;
    }

    setWorkspaceError('');

    const wsUrl = `${API_BASE_URL.replace('http', 'ws')}/ws/session/${activeChat.id}/workspace`;
    const ws = new WebSocket(wsUrl);
    workspaceSocketRef.current = ws;

    ws.onmessage = (event) => {
      const payload = JSON.parse(event.data);

      if (payload.type === 'workspace.snapshot') {
        setWorkspaceSnapshot(payload.data || null);
        return;
      }

      if (payload.type === 'workspace.tree.snapshot' || payload.type === 'workspace.tree.updated') {
        setWorkspaceTree(payload.data || []);
        return;
      }

      if (payload.type === 'plan.snapshot' || payload.type === 'plan.updated') {
        setPlanState(payload.data || []);
        return;
      }

      if (payload.type === 'sandbox.snapshot' || payload.type === 'sandbox.status') {
        setSandboxState(payload.data || { status: 'idle' });
        return;
      }

      if (payload.type === 'agent.snapshot' || payload.type === 'agent.status') {
        setAgentState(payload.data || { status: 'idle', last_error: '' });
        return;
      }

      if (payload.type === 'task.status') {
        setTaskState(payload.data || '');
        return;
      }

      if (payload.type === 'error') {
        setWorkspaceError(payload.data || 'Workspace WebSocket 连接失败');
      }
    };

    ws.onerror = () => {
      setWorkspaceError('Workspace WebSocket 连接失败');
    };

    return () => {
      ws.close();
      if (workspaceSocketRef.current === ws) {
        workspaceSocketRef.current = null;
      }
    };
  }, [activeChat]);

  function handleSend() {
    const text = inputValue.trim();
    const ws = chatSocketRef.current;
    if (!text || !ws || ws.readyState !== WebSocket.OPEN) {
      return;
    }

    setChatError('');
    setChatStatus('');
    setTaskState('');
    setSending(true);
    setChatMessages((current) => [
      ...current,
      { id: `user-${Date.now()}`, role: 'user', content: text, pending: false },
    ]);
    ws.send(text);
    setInputValue('');
  }

  function clampWidth(value, min, max) {
    const safeMax = Math.max(min, max);
    return Math.min(Math.max(value, min), safeMax);
  }

  function startResize(panel) {
    return (event) => {
      event.preventDefault();

      const container = containerRef.current;
      if (!container) {
        return;
      }

      const rect = container.getBoundingClientRect();

      function handleMouseMove(moveEvent) {
        const totalWidth = rect.width;
        const reservedRightWidth = workspaceCollapsed
          ? WORKSPACE_COLLAPSED_WIDTH
          : rightPanelWidth;

        if (panel === 'left') {
          const nextWidth = clampWidth(
            moveEvent.clientX - rect.left,
            LEFT_PANEL_MIN_WIDTH,
            Math.min(LEFT_PANEL_MAX_WIDTH, totalWidth - reservedRightWidth - CENTER_PANEL_MIN_WIDTH),
          );
          setLeftPanelWidth(nextWidth);
          return;
        }

        if (workspaceCollapsed) {
          return;
        }

        const nextWidth = clampWidth(
          rect.right - moveEvent.clientX,
          RIGHT_PANEL_MIN_WIDTH,
          totalWidth - leftPanelWidth - CENTER_PANEL_MIN_WIDTH,
        );
        setRightPanelWidth(nextWidth);
      }

      function handleMouseUp() {
        window.removeEventListener('mousemove', handleMouseMove);
        window.removeEventListener('mouseup', handleMouseUp);
        document.body.classList.remove('is-resizing-panels');
      }

      document.body.classList.add('is-resizing-panels');
      window.addEventListener('mousemove', handleMouseMove);
      window.addEventListener('mouseup', handleMouseUp);
    };
  }

  return (
    <div className="messages-page" ref={containerRef}>
      <div className="messages-pane messages-pane-left" style={{ width: `${leftPanelWidth}px` }}>
        <ConversationList
          sessions={sessions}
          activeChat={activeChat}
          onSelectChat={setActiveChat}
          loading={loading}
          error={error}
        />
        <button
          className="panel-resize-handle panel-resize-handle-left"
          type="button"
          aria-label="调整会话区宽度"
          onMouseDown={startResize('left')}
        />
      </div>

      <div className="messages-pane-center">
        <ChatPanel
          activeChat={activeChat}
          inputValue={inputValue}
          messages={chatMessages}
          loading={chatLoading}
          error={chatError}
          statusText={taskState || chatStatus}
          sending={sending}
          onInputChange={setInputValue}
          onSend={handleSend}
        />
      </div>

      <div
        className={`messages-pane messages-pane-right ${workspaceCollapsed ? 'collapsed' : ''}`}
        style={{ width: `${workspaceCollapsed ? WORKSPACE_COLLAPSED_WIDTH : rightPanelWidth}px` }}
      >
        <WorkspacePanel
          collapsed={workspaceCollapsed}
          onToggleCollapse={() => setWorkspaceCollapsed((current) => !current)}
          activeChat={activeChat}
          workspaceSnapshot={workspaceSnapshot}
          workspaceTree={workspaceTree}
          planState={planState}
          sandboxState={sandboxState}
          agentState={agentState}
          taskState={taskState}
          error={workspaceError}
        />
        {!workspaceCollapsed ? (
          <button
            className="panel-resize-handle panel-resize-handle-right"
            type="button"
            aria-label="调整工作区宽度"
            onMouseDown={startResize('right')}
          />
        ) : null}
      </div>
    </div>
  );
}
