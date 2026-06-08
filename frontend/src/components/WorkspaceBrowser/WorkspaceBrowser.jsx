import React from 'react';
import { useMemo, useState } from 'react';
import './WorkspaceBrowser.css';

function formatTime(value) {
  if (!value) {
    return '未知时间';
  }

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return '未知时间';
  }

  return date.toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  });
}

export default function WorkspaceBrowser({
  workspaces,
  projectsByWorkspace,
  selectedProjectId,
  onProjectSelect,
  fileTree,
  fileContent,
  onCreateWorkspace,
  loading,
  error,
}) {
  const [activeWorkspaceId, setActiveWorkspaceId] = useState(null);
  const activeWorkspace = useMemo(
    () => workspaces.find((item) => item.id === activeWorkspaceId) ?? null,
    [activeWorkspaceId, workspaces],
  );
  const activeProjects = activeWorkspace ? projectsByWorkspace[activeWorkspace.id] ?? [] : [];

  if (loading && workspaces.length === 0) {
    return <div className="workspace-browser-empty">正在加载 workspace...</div>;
  }

  if (!activeWorkspace) {
    return (
      <div className="workspace-browser">
        <div className="workspace-browser-toolbar">
          <div>
            <h2>全部 Workspace</h2>
            <p>选择一个 workspace 进入 project workspace 浏览。</p>
          </div>
          <button type="button" className="workspace-primary-btn" onClick={onCreateWorkspace}>
            新建 Workspace
          </button>
        </div>

        {error ? <div className="workspace-browser-alert">{error}</div> : null}

        {workspaces.length === 0 ? (
          <div className="workspace-browser-empty">还没有 workspace，先创建一个资源空间。</div>
        ) : (
          <div className="workspace-card-grid">
            {workspaces.map((workspace) => (
              <button
                key={workspace.id}
                type="button"
                className="workspace-card"
                onClick={() => setActiveWorkspaceId(workspace.id)}
                aria-label={workspace.name}
              >
                <div className="workspace-card-cover" />
                <div className="workspace-card-body">
                  <h3>{workspace.name}</h3>
                  <p>{workspace.endpoint || workspace.config_json || '项目与资源管理容器'}</p>
                  <div className="workspace-card-meta">
                    <span>{workspace.project_count ?? (projectsByWorkspace[workspace.id] ?? []).length} 个项目</span>
                    <span>{formatTime(workspace.created_at)}</span>
                  </div>
                </div>
              </button>
            ))}
          </div>
        )}
      </div>
    );
  }

  return (
    <div className="workspace-browser">
      <div className="workspace-browser-toolbar">
        <button type="button" className="workspace-back-btn" onClick={() => setActiveWorkspaceId(null)}>
          返回 Workspace
        </button>
        <div>
          <h2>{activeWorkspace.name}</h2>
          <p>浏览该 workspace 下的 project workspace 资源。</p>
        </div>
      </div>

      <div className="project-workspace-layout">
        <section className="project-workspace-list">
          <div className="project-workspace-list-header">
            <h3>Project Workspace</h3>
            <span>{activeProjects.length} 个项目</span>
          </div>

          {activeProjects.length === 0 ? (
            <div className="workspace-browser-empty compact">这个 workspace 下还没有 project workspace。</div>
          ) : (
            activeProjects.map((project) => (
              <button
                key={project.id}
                type="button"
                className={`project-workspace-item ${selectedProjectId === project.id ? 'active' : ''}`}
                onClick={() => onProjectSelect(project.id)}
              >
                <strong>{project.name}</strong>
                <span>{project.local_path || '未绑定本地目录'}</span>
                <span>{formatTime(project.created_at)}</span>
              </button>
            ))
          )}
        </section>

        <section className="project-workspace-preview">
          {!selectedProjectId ? (
            <div className="workspace-browser-empty compact">选择一个 project workspace 查看文件。</div>
          ) : (
            <>
              <div className="project-workspace-tree">
                <div className="project-workspace-preview-header">文件树</div>
                {fileTree.length === 0 ? (
                  <div className="workspace-browser-empty compact">暂无文件树快照。</div>
                ) : (
                  fileTree.map((entry) => (
                    <div key={`${entry.type}-${entry.path}`} className={`tree-entry ${entry.type}`}>
                      {entry.path}
                    </div>
                  ))
                )}
              </div>
              <div className="project-workspace-file-panel">
                <div className="project-workspace-preview-header">文件预览</div>
                <pre className="project-workspace-file-preview">{fileContent || '选择文件后在这里预览内容。'}</pre>
              </div>
            </>
          )}
        </section>
      </div>
    </div>
  );
}
