import './WorkspacePanel.css';
import { ChevronLeft, ChevronRight, FolderGit2 } from 'lucide-react';

export default function WorkspacePanel({ collapsed, onToggleCollapse }) {
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
          <div className="workspace-placeholder">
            <FolderGit2 size={48} className="placeholder-icon" />
            <p>此处将展示代码、文件结构和终端等工作区信息</p>
          </div>
        </div>
      ) : null}
    </div>
  );
}
