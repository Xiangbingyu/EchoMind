import React from 'react';
import {
  Boxes,
  ChevronDown,
  ChevronRight,
  FileCode2,
  FolderClosed,
  FolderOpen,
  FolderTree,
  GitBranch,
} from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
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
  activeProject,
  activeWorkspace,
  error,
  fileContent,
  fileContentError,
  fileContentLoading,
  deletingProjectId,
  deletingWorkspaceId,
  projectsByWorkspace,
  fileTree,
  fileTreeError,
  fileTreeLoading,
  loading,
  navWidth,
  onCreateWorkspace,
  onCreateProject,
  onDeleteProject,
  onRefreshProject,
  onDeleteWorkspace,
  onFileSelect,
  onProjectSelect,
  onNavResizeStart,
  onWorkspaceSelect,
  selectedProjectId,
  selectedFilePath,
  selectedWorkspaceId,
  workspaces,
}) {
  const [expandedKeys, setExpandedKeys] = useState(() => new Set());

  useEffect(() => {
    setExpandedKeys((current) => {
      const next = new Set(current);
      if (selectedWorkspaceId) {
        next.add(`workspace:${selectedWorkspaceId}`);
      }
      if (selectedProjectId) {
        next.add(`project:${selectedProjectId}`);
      }
      return next;
    });
  }, [selectedProjectId, selectedWorkspaceId]);

  const activeProjects = activeWorkspace ? projectsByWorkspace[activeWorkspace.id] ?? [] : [];
  const totalProjects = useMemo(
    () => Object.values(projectsByWorkspace).reduce((count, items) => count + items.length, 0),
    [projectsByWorkspace],
  );
  const treeStats = useMemo(() => {
    function walk(nodes) {
      return nodes.reduce(
        (stats, node) => {
          if (node.type === 'directory') {
            stats.directories += 1;
            const childStats = walk(node.children ?? []);
            stats.directories += childStats.directories;
            stats.files += childStats.files;
          } else {
            stats.files += 1;
          }
          return stats;
        },
        { directories: 0, files: 0 },
      );
    }

    return walk(fileTree);
  }, [fileTree]);

  function toggleNode(key) {
    setExpandedKeys((current) => {
      const next = new Set(current);
      if (next.has(key)) {
        next.delete(key);
      } else {
        next.add(key);
      }
      return next;
    });
  }

  function renderTreeNodes(nodes, depth = 0) {
    return nodes.map((node) => {
      const isDirectory = node.type === 'directory';
      const nodeKey = `${node.type}:${node.path}`;
      const isExpanded = expandedKeys.has(nodeKey);
      const isSelected = node.path === selectedFilePath;

      return (
        <div key={nodeKey} className="workspace-explorer-node">
          <button
            type="button"
            className={`workspace-explorer-row ${isSelected ? 'selected' : ''}`}
            style={{ '--tree-depth': depth }}
            onClick={() => {
              if (isDirectory) {
                toggleNode(nodeKey);
                return;
              }

              onFileSelect(node.path);
            }}
          >
            <span className="workspace-explorer-indent" />
            {isDirectory ? (
              <span className="workspace-explorer-chevron" aria-hidden="true">
                {isExpanded ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
              </span>
            ) : (
              <span className="workspace-explorer-chevron spacer" aria-hidden="true" />
            )}
            <span className="workspace-explorer-icon" aria-hidden="true">
              {isDirectory ? (isExpanded ? <FolderOpen size={16} /> : <FolderClosed size={16} />) : <FileCode2 size={16} />}
            </span>
            <span className="workspace-explorer-label">{node.name}</span>
          </button>
          {isDirectory && isExpanded ? renderTreeNodes(node.children ?? [], depth + 1) : null}
        </div>
      );
    });
  }

  if (loading && workspaces.length === 0) {
    return <div className="workspace-browser-empty">正在加载 workspace...</div>;
  }

  if (workspaces.length === 0) {
    return (
      <div className="workspace-browser">
        <aside className="workspace-browser-nav" style={navWidth ? { width: `${navWidth}px` } : undefined}>
          <div className="workspace-browser-nav-header">
            <div>
              <h2>Workspace</h2>
              <p>资源导航</p>
            </div>
            <button type="button" className="workspace-primary-btn" onClick={onCreateWorkspace}>
              新建
            </button>
          </div>
          {error ? <div className="workspace-browser-alert">{error}</div> : null}
          <div className="workspace-browser-empty">还没有 workspace，先创建一个资源空间。</div>
          {onNavResizeStart ? (
            <button
              className="workspace-resize-handle"
              type="button"
              aria-label="调整资源导航宽度"
              onMouseDown={onNavResizeStart}
            />
          ) : null}
        </aside>

        <section className="workspace-browser-status">
          <div className="workspace-browser-status-header">
            <h3>当前状态</h3>
          </div>
          <div className="workspace-browser-empty">选择左侧资源后，这里会显示当前状态和代码预览。</div>
        </section>
      </div>
    );
  }

  return (
    <div className="workspace-browser">
      <aside className="workspace-browser-nav" style={navWidth ? { width: `${navWidth}px` } : undefined}>
        <div className="workspace-browser-nav-header">
          <div>
            <h2>Workspace</h2>
            <p>资源导航</p>
          </div>
          <button type="button" className="workspace-primary-btn" onClick={onCreateWorkspace}>
            新建
          </button>
        </div>
        {workspaces.length > 0 ? <span className="workspace-count">{workspaces.length}</span> : null}
        <div className="workspace-browser-tree">
          {workspaces.map((workspace) => {
            const workspaceKey = `workspace:${workspace.id}`;
            const projectItems = projectsByWorkspace[workspace.id] ?? [];
            const isWorkspaceExpanded = expandedKeys.has(workspaceKey);
            const isWorkspaceSelected = workspace.id === selectedWorkspaceId;

            return (
              <div key={workspace.id} className="workspace-explorer-group">
                <div className={`workspace-explorer-row workspace-level ${isWorkspaceSelected ? 'selected' : ''}`}>
                  <button
                    type="button"
                    className="workspace-toggle-btn"
                    onClick={() => toggleNode(workspaceKey)}
                    aria-label={`${isWorkspaceExpanded ? '收起' : '展开'} ${workspace.name}`}
                  >
                    {isWorkspaceExpanded ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
                  </button>
                  <button
                    type="button"
                    className="workspace-item-btn"
                    onClick={() => onWorkspaceSelect(workspace.id)}
                  >
                    <span className="workspace-explorer-icon" aria-hidden="true">
                      <Boxes size={16} />
                    </span>
                    <span className="workspace-explorer-label">{workspace.name}</span>
                    <span className="workspace-explorer-meta">{workspace.project_count ?? projectItems.length}</span>
                  </button>
                  <button
                    type="button"
                    className="workspace-action-btn danger"
                    aria-label="删除 Workspace"
                    onClick={() => onDeleteWorkspace(workspace.id)}
                    disabled={deletingWorkspaceId === workspace.id}
                  >
                    {deletingWorkspaceId === workspace.id ? '删除中' : '删除'}
                  </button>
                </div>

                {isWorkspaceExpanded ? (
                  <div className="workspace-project-list">
                    <div className="workspace-project-toolbar">
                      <span>Projects</span>
                      <button type="button" className="workspace-subtle-btn" onClick={() => onCreateProject(workspace.id)}>
                        新建 Project
                      </button>
                    </div>
                    {projectItems.length === 0 ? (
                      <div className="workspace-explorer-empty">暂无 project</div>
                    ) : (
                      projectItems.map((project) => {
                        const projectKey = `project:${project.id}`;
                        const isProjectExpanded = expandedKeys.has(projectKey);
                        const isProjectSelected = project.id === selectedProjectId;

                        return (
                          <div key={project.id} className="workspace-explorer-group">
                            <div className={`workspace-explorer-row project-level ${isProjectSelected ? 'selected' : ''}`}>
                              <button
                                type="button"
                                className="workspace-toggle-btn"
                                onClick={() => toggleNode(projectKey)}
                                aria-label={`${isProjectExpanded ? '收起' : '展开'} ${project.name}`}
                              >
                                {isProjectExpanded ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
                              </button>
                              <button
                                type="button"
                                className="workspace-item-btn"
                                onClick={() => {
                                  onWorkspaceSelect(workspace.id);
                                  onProjectSelect(project.id);
                                }}
                              >
                                <span className="workspace-explorer-icon" aria-hidden="true">
                                  <GitBranch size={16} />
                                </span>
                                <span className="workspace-explorer-label">{project.name}</span>
                              </button>
                              <button
                                type="button"
                                className="workspace-action-btn danger"
                                aria-label="删除 Project"
                                onClick={() => onDeleteProject(project.id)}
                                disabled={deletingProjectId === project.id}
                              >
                                {deletingProjectId === project.id ? '删除中' : '删除'}
                              </button>
                            </div>

                            {isProjectExpanded && isProjectSelected ? (
                              <div className="workspace-project-tree">
                                {fileTreeLoading ? <div className="workspace-explorer-empty">正在加载代码树...</div> : null}
                                {!fileTreeLoading && fileTreeError ? (
                                  <div className="workspace-explorer-empty error">{fileTreeError}</div>
                                ) : null}
                                {!fileTreeLoading && !fileTreeError && fileTree.length === 0 ? (
                                  <div className="workspace-explorer-empty">这个 project 里还没有代码文件。</div>
                                ) : null}
                                {!fileTreeLoading && !fileTreeError && fileTree.length > 0 ? renderTreeNodes(fileTree, 2) : null}
                              </div>
                            ) : null}
                          </div>
                        );
                      })
                    )}
                  </div>
                ) : null}
              </div>
            );
          })}
        </div>
        {onNavResizeStart ? (
          <button
            className="workspace-resize-handle"
            type="button"
            aria-label="调整资源导航宽度"
            onMouseDown={onNavResizeStart}
          />
        ) : null}
      </aside>

      <section className="workspace-browser-status">
        <div className="workspace-browser-status-header">
          <div>
            <h3>当前状态</h3>
            <p>{activeProject ? activeProject.name : '未选择 Project'}</p>
          </div>
          <div className="workspace-status-header-actions">
            <span>{selectedFilePath || '等待选择文件'}</span>
            <button
              type="button"
              className="workspace-subtle-btn"
              onClick={() => onRefreshProject(selectedProjectId)}
              disabled={!selectedProjectId || fileTreeLoading}
              aria-label="刷新文件树"
            >
              {fileTreeLoading ? '刷新中' : '刷新文件树'}
            </button>
          </div>
        </div>

        {error ? <div className="workspace-browser-alert">{error}</div> : null}

        <div className="workspace-browser-status-content">
          <div className="workspace-status-summary">
            <section className="workspace-status-section">
              <div className="workspace-status-section-title">
                <FolderTree size={16} />
                <span>Workspace 状况</span>
              </div>
              {!activeWorkspace ? (
                <div className="workspace-browser-empty compact">选择左侧 workspace 后，这里会显示资源概览。</div>
              ) : (
                <>
                  <p>Workspace：{activeWorkspace.name}</p>
                  <p>创建时间：{formatTime(activeWorkspace.created_at)}</p>
                  <p>Project 数量：{activeProjects.length}</p>
                  <p>代码树：{treeStats.directories} 个目录 / {treeStats.files} 个文件</p>
                  <p>当前 MVP 仅支持本机路径扫描，endpoint 仅作为本地环境标识使用。</p>
                </>
              )}
            </section>

            <section className="workspace-status-section">
              <div className="workspace-status-section-title">
                <GitBranch size={16} />
                <span>项目绑定</span>
              </div>
              <p>当前 Project：{activeProject?.name || '未选择'}</p>
              <p>当前目录：{activeProject?.path || '选择左侧 project 后查看目录'}</p>
              <p>Workspace 总数：{workspaces.length}</p>
              <p>Project 总数：{totalProjects}</p>
            </section>
          </div>

          <section className="workspace-status-section workspace-code-section">
            <div className="workspace-status-section-title">
              <FileCode2 size={16} />
              <span>代码预览</span>
            </div>
            <div className="workspace-code-body">
              {!selectedProjectId ? (
                <div className="workspace-browser-empty compact">先在左侧选择一个 project。</div>
              ) : !selectedFilePath ? (
                <div className="workspace-browser-empty compact">选择一个文件后，在这里查看源码内容。</div>
              ) : fileContentLoading ? (
                <div className="workspace-browser-empty compact">正在加载文件内容...</div>
              ) : fileContentError ? (
                <div className="workspace-browser-empty compact">{fileContentError}</div>
              ) : (
                <>
                  <button
                    type="button"
                    className="workspace-file-breadcrumb"
                    onClick={() => onFileSelect(selectedFilePath)}
                  >
                    {selectedFilePath}
                  </button>
                  <pre className="workspace-code-preview">{fileContent || '文件为空。'}</pre>
                </>
              )}
            </div>
          </section>
        </div>
      </section>
    </div>
  );
}
