import React from 'react';
import { useEffect, useRef, useState } from 'react';
import ConversationList from '../../components/ConversationList/ConversationList';
import ChatPanel from '../../components/ChatPanel/ChatPanel';
import SessionCreateDialog from '../../components/SessionCreateDialog/SessionCreateDialog';
import WorkspacePanel from '../../components/WorkspacePanel/WorkspacePanel';
import { API_BASE_URL, createWsUrl, fetchJson } from '../../utils/api';
import './Messages.css';

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
  const [workspaceLoading, setWorkspaceLoading] = useState(false);
  const [workspaceTree, setWorkspaceTree] = useState([]);
  const [planState, setPlanState] = useState([]);
  const [sandboxState, setSandboxState] = useState({ status: 'idle' });
  const [agentState, setAgentState] = useState({ status: 'idle', last_error: '' });
  const [workspaceError, setWorkspaceError] = useState('');
  const [leftPanelWidth, setLeftPanelWidth] = useState(LEFT_PANEL_INITIAL_WIDTH);
  const [rightPanelWidth, setRightPanelWidth] = useState(RIGHT_PANEL_INITIAL_WIDTH);
  const [workspaceCollapsed, setWorkspaceCollapsed] = useState(false);
  const [workspaceOptions, setWorkspaceOptions] = useState([]);
  const [projectWorkspaceOptions, setProjectWorkspaceOptions] = useState({});
  const [createDialogOpen, setCreateDialogOpen] = useState(false);
  const [creatingSession, setCreatingSession] = useState(false);
  const [deletingSessionId, setDeletingSessionId] = useState('');
  const [sessionDialogKey, setSessionDialogKey] = useState(0);
  const containerRef = useRef(null);
  const socketRef = useRef(null);
  const streamMessageIdRef = useRef(null);
  const sessionGenerationRef = useRef(0);

  function resetSessionViewState() {
    setChatMessages([]);
    setChatLoading(false);
    setChatStatus('');
    setTaskState('');
    setChatError('');
    setSending(false);
    setWorkspaceSnapshot(null);
    setWorkspaceLoading(false);
    setWorkspaceTree([]);
    setPlanState([]);
    setSandboxState({ status: 'idle' });
    setAgentState({ status: 'idle', last_error: '' });
    setWorkspaceError('');
    streamMessageIdRef.current = null;
  }

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
          const nextActiveChat = data[0] ?? null;
          if (!nextActiveChat) {
            resetSessionViewState();
          }
          return nextActiveChat;
        });
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : 'Failed to load sessions');
          setSessions([]);
          setActiveChat(null);
          resetSessionViewState();
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
      return undefined;
    }

    sessionGenerationRef.current += 1;
    const generation = sessionGenerationRef.current;

    setChatLoading(true);
    setWorkspaceLoading(true);
    setChatError('');
    setChatStatus('');
    setTaskState('');
    setWorkspaceError('');
    setWorkspaceSnapshot(null);
    setWorkspaceTree([]);
    setPlanState([]);
    setSandboxState({ status: 'idle' });
    setAgentState({ status: 'idle', last_error: '' });
    setSending(false);
    streamMessageIdRef.current = null;

    let cancelled = false;
    const controller = new AbortController();

    async function loadInitialState() {
      try {
        const [messagesResponse, sessionResponse, projectResponse] = await Promise.all([
          fetch(`${API_BASE_URL}/api/sessions/${activeChat.id}/messages`, { signal: controller.signal }),
          fetch(`${API_BASE_URL}/api/sessions/${activeChat.id}`, { signal: controller.signal }),
          fetch(`${API_BASE_URL}/api/projects/${activeChat.project_workspace_id}`, { signal: controller.signal }),
        ]);

        if (!messagesResponse.ok) {
          throw new Error(`Failed to load messages: ${messagesResponse.status}`);
        }
        if (!sessionResponse.ok) {
          throw new Error(`Failed to load session: ${sessionResponse.status}`);
        }
        if (!projectResponse.ok) {
          throw new Error(`Failed to load project: ${projectResponse.status}`);
        }

        const [messagesData, sessionData, projectData] = await Promise.all([
          messagesResponse.json(),
          sessionResponse.json(),
          projectResponse.json(),
        ]);

        if (cancelled || generation !== sessionGenerationRef.current) {
          return;
        }

        setChatMessages(toDisplayMessages(messagesData));
        setWorkspaceSnapshot({
          workspace_id: sessionData.workspace_id,
          project_workspace_id: sessionData.project_workspace_id,
          workspace_root: projectData.path || '',
        });

        if (cancelled || generation !== sessionGenerationRef.current) {
          return;
        }

        const wsUrl = createWsUrl(`/ws/session/${activeChat.id}`);
        const ws = new WebSocket(wsUrl);
        socketRef.current = ws;

        ws.onmessage = (event) => {
          if (cancelled || generation !== sessionGenerationRef.current) {
            return;
          }

          const payload = JSON.parse(event.data);

          if (payload.type === 'message.history.sync') {
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
            setWorkspaceError(payload.data || '工作区状态同步失败');
            setSending(false);
            setChatLoading(false);
            return;
          }

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
          }
        };

        ws.onerror = () => {
          if (cancelled || generation !== sessionGenerationRef.current) {
            return;
          }
          setChatError('WebSocket 连接失败，已回退为 HTTP 初始加载');
          setWorkspaceError('WebSocket 连接失败，运行态更新暂停');
          setSending(false);
        };

        ws.onclose = () => {
          if (cancelled || generation !== sessionGenerationRef.current) {
            return;
          }
          setSending(false);
        };
      } catch (err) {
        if (cancelled || generation !== sessionGenerationRef.current) {
          return;
        }
        if (err instanceof Error && err.name === 'AbortError') {
          return;
        }
        const message = err instanceof Error ? err.message : 'Failed to load session state';
        setChatError(message);
        setWorkspaceError(message);
      } finally {
        if (!cancelled && generation === sessionGenerationRef.current) {
          setChatLoading(false);
          setWorkspaceLoading(false);
        }
      }
    }

    loadInitialState();

    return () => {
      cancelled = true;
      controller.abort();
      streamMessageIdRef.current = null;
      if (socketRef.current) {
        socketRef.current.close();
        socketRef.current = null;
      }
    };
  }, [activeChat]);

  function handleSend() {
    const text = inputValue.trim();
    const ws = socketRef.current;
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

  async function handleOpenCreateDialog() {
    setSessionDialogKey((current) => current + 1);
    setCreateDialogOpen(true);

    if (workspaceOptions.length > 0) {
      return;
    }

    try {
      const workspaces = await fetchJson('/api/workspaces');
      setWorkspaceOptions(workspaces);
      const entries = await Promise.all(
        workspaces.map(async (workspace) => [workspace.id, await fetchJson(`/api/workspaces/${workspace.id}/projects`)]),
      );
      setProjectWorkspaceOptions(Object.fromEntries(entries));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load workspaces');
    }
  }

  async function handleCreateSession(payload) {
    setCreatingSession(true);
    setError('');

    try {
      const response = await fetch(`${API_BASE_URL}/api/sessions`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          title: payload.title,
          type: 'single',
          workspace_id: payload.workspace_id,
          project_workspace_id: payload.project_workspace_id,
        }),
      });

      if (!response.ok) {
        throw new Error(`Failed to create session: ${response.status}`);
      }

      const createdSession = await response.json();
      setSessions((current) => [createdSession, ...current]);
      setActiveChat(createdSession);
      setCreateDialogOpen(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create session');
    } finally {
      setCreatingSession(false);
    }
  }

  async function handleDeleteSession(sessionId) {
    const target = sessions.find((session) => session.id === sessionId);
    if (!target) {
      return;
    }

    const title = target.title || `会话 ${target.id.slice(0, 8)}`;
    const confirmed = window.confirm(`删除会话“${title}”后，消息历史将被清空，但不会影响任何 workspace 资源。`);
    if (!confirmed) {
      return;
    }

    setDeletingSessionId(sessionId);
    setError('');

    try {
      const response = await fetch(`${API_BASE_URL}/api/sessions/${sessionId}`, { method: 'DELETE' });
      if (!response.ok) {
        throw new Error(`Failed to delete session: ${response.status}`);
      }

      const nextSessions = sessions.filter((session) => session.id !== sessionId);
      setSessions(nextSessions);
      if (activeChat?.id === sessionId) {
        setActiveChat(nextSessions[0] ?? null);
        if (nextSessions.length === 0) {
          resetSessionViewState();
        }
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete session');
    } finally {
      setDeletingSessionId('');
    }
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
          onCreateSession={handleOpenCreateDialog}
          onDeleteSession={handleDeleteSession}
          deletingSessionId={deletingSessionId}
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
          loading={workspaceLoading}
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

      <SessionCreateDialog
        key={sessionDialogKey}
        open={createDialogOpen}
        workspaces={workspaceOptions}
        projectWorkspaces={projectWorkspaceOptions}
        onClose={() => setCreateDialogOpen(false)}
        onSubmit={handleCreateSession}
        loading={creatingSession}
      />
    </div>
  );
}
