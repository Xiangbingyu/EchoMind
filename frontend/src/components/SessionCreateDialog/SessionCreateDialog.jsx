import React from 'react';
import { useState } from 'react';
import './SessionCreateDialog.css';

export default function SessionCreateDialog({
  open,
  workspaces,
  projectWorkspaces,
  onClose,
  onSubmit,
  loading = false,
}) {
  const [title, setTitle] = useState('');
  const [workspaceId, setWorkspaceId] = useState('');
  const [projectWorkspaceId, setProjectWorkspaceId] = useState('');

  const projects = workspaceId ? projectWorkspaces[workspaceId] ?? [] : [];
  const disabled = !title.trim() || !workspaceId || !projectWorkspaceId || loading;

  if (!open) {
    return null;
  }

  return (
    <div className="session-create-overlay" role="dialog" aria-modal="true" aria-label="新建 Session">
      <div className="session-create-dialog">
        <div className="session-create-header">
          <h3>新建 Session</h3>
          <button type="button" className="session-create-ghost-btn" onClick={onClose}>
            取消
          </button>
        </div>

        <label className="session-create-field">
          <span>Session 名称</span>
          <input value={title} onChange={(event) => setTitle(event.target.value)} />
        </label>

        <label className="session-create-field">
          <span>Workspace</span>
          <select
            aria-label="Workspace"
            value={workspaceId}
            onChange={(event) => {
              setWorkspaceId(event.target.value);
              setProjectWorkspaceId('');
            }}
          >
            <option value="">请选择 Workspace</option>
            {workspaces.map((workspace) => (
              <option key={workspace.id} value={workspace.id}>
                {workspace.name}
              </option>
            ))}
          </select>
        </label>

        <label className="session-create-field">
          <span>Project Workspace</span>
          <select
            aria-label="Project Workspace"
            value={projectWorkspaceId}
            onChange={(event) => setProjectWorkspaceId(event.target.value)}
            disabled={!workspaceId}
          >
            <option value="">请选择 Project Workspace</option>
            {projects.map((project) => (
              <option key={project.id} value={project.id}>
                {project.name}
              </option>
            ))}
          </select>
        </label>

        <div className="session-create-actions">
          <button type="button" className="session-create-ghost-btn" onClick={onClose}>
            取消
          </button>
          <button
            type="button"
            className="session-create-primary-btn"
            disabled={disabled}
            onClick={() =>
              onSubmit({
                title: title.trim(),
                workspace_id: workspaceId,
                project_workspace_id: projectWorkspaceId,
              })
            }
          >
            {loading ? '创建中' : '创建 Session'}
          </button>
        </div>
      </div>
    </div>
  );
}
