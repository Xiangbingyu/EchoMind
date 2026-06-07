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

export default function Messages() {
  const [activeChat, setActiveChat] = useState(null);
  const [sessions, setSessions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [leftPanelWidth, setLeftPanelWidth] = useState(LEFT_PANEL_INITIAL_WIDTH);
  const [rightPanelWidth, setRightPanelWidth] = useState(RIGHT_PANEL_INITIAL_WIDTH);
  const [workspaceCollapsed, setWorkspaceCollapsed] = useState(false);
  const containerRef = useRef(null);

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
        <ChatPanel activeChat={activeChat} apiBaseUrl={API_BASE_URL} />
      </div>

      <div
        className={`messages-pane messages-pane-right ${workspaceCollapsed ? 'collapsed' : ''}`}
        style={{ width: `${workspaceCollapsed ? WORKSPACE_COLLAPSED_WIDTH : rightPanelWidth}px` }}
      >
        <WorkspacePanel
          collapsed={workspaceCollapsed}
          onToggleCollapse={() => setWorkspaceCollapsed((current) => !current)}
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
