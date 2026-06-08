import React from 'react';
import { useState } from 'react';
import './WorkspaceResourceDialog.css';

export default function WorkspaceResourceDialog({ mode, open, loading, onClose, onSubmit }) {
  const [name, setName] = useState('');
  const [value, setValue] = useState('');

  if (!open) {
    return null;
  }

  const isWorkspace = mode === 'workspace';
  const disabled = !name.trim() || !value.trim() || loading;

  return (
    <div className="workspace-resource-overlay" role="dialog" aria-modal="true">
      <div className="workspace-resource-dialog">
        <h3>{isWorkspace ? '新建 Workspace' : '新建 Project'}</h3>
        <label className="workspace-resource-field">
          <span>{isWorkspace ? 'Workspace 名称' : 'Project 名称'}</span>
          <input value={name} onChange={(event) => setName(event.target.value)} />
        </label>
        <label className="workspace-resource-field">
          <span>{isWorkspace ? 'Endpoint' : 'Path'}</span>
          <input value={value} onChange={(event) => setValue(event.target.value)} />
        </label>
        {isWorkspace ? <p className="workspace-resource-hint">MVP 仅支持本地 workspace，请填写 localhost。</p> : null}
        <div className="workspace-resource-actions">
          <button type="button" className="workspace-resource-ghost-btn" onClick={onClose}>
            取消
          </button>
          <button
            type="button"
            className="workspace-resource-primary-btn"
            disabled={disabled}
            onClick={() =>
              onSubmit(
                isWorkspace
                  ? { name: name.trim(), endpoint: value.trim() }
                  : { name: name.trim(), path: value.trim() },
              )
            }
          >
            {loading ? '处理中' : '确认'}
          </button>
        </div>
      </div>
    </div>
  );
}
