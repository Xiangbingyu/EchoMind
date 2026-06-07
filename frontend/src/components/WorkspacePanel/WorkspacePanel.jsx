import './WorkspacePanel.css';
import { ChevronLeft, ChevronRight, FolderGit2 } from 'lucide-react';

export default function WorkspacePanel({
  collapsed,
  onToggleCollapse,
  activeChat,
  workspaceSnapshot,
  loading,
  workspaceTree,
  planState,
  sandboxState,
  agentState,
  taskState,
  error,
}) {
  return (
    <div className={`workspace-panel ${collapsed ? 'collapsed' : ''}`}>
      <div className="workspace-header">
        <button
          className="workspace-collapse-btn"
          type="button"
          onClick={onToggleCollapse}
          aria-label={collapsed ? '展开工作区' : '收起工作区'}
          title={collapsed ? '展开工作区' : '收起工作区'}
        >
          {collapsed ? <ChevronLeft size={18} /> : <ChevronRight size={18} />}
        </button>
        {!collapsed ? <h3>工作区 (Workspace)</h3> : null}
      </div>
      {!collapsed ? (
        <div className="workspace-content">
          {!activeChat ? (
            <div className="workspace-placeholder">
              <FolderGit2 size={48} className="placeholder-icon" />
              <p>选择一个会话后查看工作区运行态。</p>
            </div>
          ) : loading ? (
            <div className="workspace-placeholder">
              <FolderGit2 size={48} className="placeholder-icon" />
              <p>正在加载工作区快照...</p>
            </div>
          ) : (
            <>
              {error ? <div className="workspace-alert">{error}</div> : null}
              <section className="workspace-section">
                <h4>Session</h4>
                <p>{activeChat.title || `会话 ${activeChat.id.slice(0, 8)}`}</p>
                <p>类型：{activeChat.type === 'single' ? '单聊' : '群聊'}</p>
              </section>

              <section className="workspace-section">
                <h4>Runtime</h4>
                <p>Agent：{agentState?.status || 'idle'}</p>
                <p>Task：{taskState || 'idle'}</p>
                <p>Sandbox：{sandboxState?.status || 'idle'}</p>
              </section>

              <section className="workspace-section">
                <h4>Workspace</h4>
                <p>Workspace ID：{workspaceSnapshot?.workspace_id || '未加载'}</p>
                <p>Project ID：{workspaceSnapshot?.project_workspace_id || activeChat.project_workspace_id}</p>
                <p>Root：{workspaceSnapshot?.workspace_root || '未绑定本地目录'}</p>
              </section>

              <section className="workspace-section">
                <h4>Files</h4>
                <p>{workspaceTree.length > 0 ? `${workspaceTree.length} 个条目` : '暂无文件树快照'}</p>
              </section>

              <section className="workspace-section">
                <h4>Plan</h4>
                <p>{planState.length > 0 ? `${planState.length} 个步骤` : '暂无计划'}</p>
              </section>

              <section className="workspace-section">
                <h4>Agent</h4>
                <p>状态：{agentState?.status || 'idle'}</p>
                <p>错误：{agentState?.last_error || '无'}</p>
              </section>
            </>
          )}
        </div>
      ) : null}
    </div>
  );
}
