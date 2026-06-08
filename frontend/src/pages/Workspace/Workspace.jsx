import React from 'react';
import { useEffect, useMemo, useRef, useState } from 'react';
import WorkspaceBrowser from '../../components/WorkspaceBrowser/WorkspaceBrowser';
import WorkspaceResourceDialog from '../../components/WorkspaceResourceDialog/WorkspaceResourceDialog';
import { fetchJson } from '../../utils/api';
import './Workspace.css';

const WORKSPACE_NAV_MIN_WIDTH = 280;
const WORKSPACE_NAV_DEFAULT_WIDTH = 360;

function getNodeName(path) {
  if (!path) {
    return '';
  }

  const segments = path.split('/');
  return segments[segments.length - 1];
}

async function loadDirectoryTree(projectId, path = '') {
  const query = path ? `?path=${encodeURIComponent(path)}` : '';
  const entries = await fetchJson(`/api/projects/${projectId}/files/tree${query}`);

  return Promise.all(
    entries.map(async (entry) => {
      if (entry.type === 'directory') {
        return {
          ...entry,
          name: getNodeName(entry.path),
          children: await loadDirectoryTree(projectId, entry.path),
        };
      }

      return {
        ...entry,
        name: getNodeName(entry.path),
        children: [],
      };
    }),
  );
}

export default function Workspace() {
  const containerRef = useRef(null);
  const projectTreesRef = useRef({});
  const fileContentsRef = useRef({});
  const [workspaces, setWorkspaces] = useState([]);
  const [projectsByWorkspace, setProjectsByWorkspace] = useState({});
  const [selectedWorkspaceId, setSelectedWorkspaceId] = useState('');
  const [selectedProjectId, setSelectedProjectId] = useState('');
  const [selectedFilePath, setSelectedFilePath] = useState('');
  const [projectTrees, setProjectTrees] = useState({});
  const [projectTreeVersions, setProjectTreeVersions] = useState({});
  const [fileContents, setFileContents] = useState({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [navWidth, setNavWidth] = useState(WORKSPACE_NAV_DEFAULT_WIDTH);
  const [resourceDialog, setResourceDialog] = useState({ open: false, mode: 'workspace', workspaceId: '' });
  const [creatingWorkspace, setCreatingWorkspace] = useState(false);
  const [creatingProject, setCreatingProject] = useState(false);
  const [deletingWorkspaceId, setDeletingWorkspaceId] = useState('');
  const [deletingProjectId, setDeletingProjectId] = useState('');

  async function reloadResources() {
    const workspaceData = await fetchJson('/api/workspaces');
    setWorkspaces(workspaceData);

    const projectEntries = await Promise.all(
      workspaceData.map(async (workspace) => [
        workspace.id,
        await fetchJson(`/api/workspaces/${workspace.id}/projects`),
      ]),
    );
    setProjectsByWorkspace(Object.fromEntries(projectEntries));
    return { workspaceData, projectEntries: Object.fromEntries(projectEntries) };
  }

  useEffect(() => {
    projectTreesRef.current = projectTrees;
  }, [projectTrees]);

  useEffect(() => {
    fileContentsRef.current = fileContents;
  }, [fileContents]);

  useEffect(() => {
    let cancelled = false;

    async function loadWorkspaces() {
      setLoading(true);
      setError('');

      try {
        const { workspaceData, projectEntries } = await reloadResources();
        if (cancelled) {
          return;
        }

        setWorkspaces(workspaceData);
        setProjectsByWorkspace(projectEntries);
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : '加载 workspace 失败');
          setWorkspaces([]);
          setProjectsByWorkspace({});
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    loadWorkspaces();

    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!selectedWorkspaceId && workspaces.length > 0) {
      setSelectedWorkspaceId(workspaces[0].id);
    }
  }, [selectedWorkspaceId, workspaces]);

  useEffect(() => {
    if (!selectedWorkspaceId) {
      if (selectedProjectId) {
        setSelectedProjectId('');
      }
      if (selectedFilePath) {
        setSelectedFilePath('');
      }
      return;
    }

    const activeProjects = projectsByWorkspace[selectedWorkspaceId] ?? [];
    if (activeProjects.length === 0) {
      if (selectedProjectId) {
        setSelectedProjectId('');
      }
      if (selectedFilePath) {
        setSelectedFilePath('');
      }
      return;
    }

    const hasSelectedProject = activeProjects.some((project) => project.id === selectedProjectId);
    if (!hasSelectedProject) {
      setSelectedProjectId(activeProjects[0].id);
      setSelectedFilePath('');
    }
  }, [projectsByWorkspace, selectedFilePath, selectedProjectId, selectedWorkspaceId]);

  useEffect(() => {
    const activeVersion = selectedProjectId ? projectTreeVersions[selectedProjectId] ?? 0 : 0;
    if (!selectedProjectId) {
      return;
    }

    let cancelled = false;

    async function loadProjectTree() {
      const activeTree = projectTreesRef.current[selectedProjectId];
      if (activeTree?.status === 'loading') {
        return;
      }

      setProjectTrees((current) => ({
        ...current,
        [selectedProjectId]: {
          status: 'loading',
          tree: current[selectedProjectId]?.tree ?? [],
          error: '',
        },
      }));

      try {
        const treeData = await loadDirectoryTree(selectedProjectId);
        if (cancelled) {
          return;
        }

        setProjectTrees((current) => ({
          ...current,
          [selectedProjectId]: {
            status: 'loaded',
            tree: treeData,
            error: '',
            version: activeVersion,
          },
        }));
      } catch (err) {
        if (!cancelled) {
          setProjectTrees((current) => ({
            ...current,
              [selectedProjectId]: {
                status: 'error',
                tree: [],
                error: err instanceof Error ? err.message : '加载文件树失败',
                version: activeVersion,
              },
            }));
        }
      }
    }

    loadProjectTree();

    return () => {
      cancelled = true;
    };
  }, [projectTreeVersions, selectedProjectId]);

  useEffect(() => {
    if (!selectedProjectId || !selectedFilePath) {
      return;
    }

    const cacheKey = `${selectedProjectId}:${selectedFilePath}`;
    const activeFile = fileContentsRef.current[cacheKey];
    if (activeFile?.status === 'loading' || activeFile?.status === 'loaded') {
      return;
    }

    let cancelled = false;

    async function loadFileContent() {
      setFileContents((current) => ({
        ...current,
        [cacheKey]: {
          status: 'loading',
          content: current[cacheKey]?.content ?? '',
          error: '',
        },
      }));

      try {
        const contentData = await fetchJson(
          `/api/projects/${selectedProjectId}/files/content?path=${encodeURIComponent(selectedFilePath)}`,
        );
        if (cancelled) {
          return;
        }

        setFileContents((current) => ({
          ...current,
          [cacheKey]: {
            status: 'loaded',
            content: contentData.content || '',
            error: '',
          },
        }));
      } catch (err) {
        if (!cancelled) {
          setFileContents((current) => ({
            ...current,
            [cacheKey]: {
              status: 'error',
              content: '',
              error: err instanceof Error ? err.message : '加载文件内容失败',
            },
          }));
        }
      }
    }

    loadFileContent();

    return () => {
      cancelled = true;
    };
  }, [selectedFilePath, selectedProjectId]);

  const activeWorkspace = useMemo(
    () => workspaces.find((workspace) => workspace.id === selectedWorkspaceId) ?? null,
    [selectedWorkspaceId, workspaces],
  );
  const activeProject = useMemo(
    () => (projectsByWorkspace[selectedWorkspaceId] ?? []).find((project) => project.id === selectedProjectId) ?? null,
    [projectsByWorkspace, selectedProjectId, selectedWorkspaceId],
  );
  const activeTreeState = selectedProjectId ? projectTrees[selectedProjectId] : null;
  const activeTree = activeTreeState?.tree ?? [];
  const activeFileState =
    selectedProjectId && selectedFilePath ? fileContents[`${selectedProjectId}:${selectedFilePath}`] : null;

  function clampWidth(value, min, max) {
    const safeMax = Math.max(min, max);
    return Math.min(Math.max(value, min), safeMax);
  }

  function startNavResize(event) {
    event.preventDefault();

    const container = containerRef.current;
    if (!container) {
      return;
    }

    const rect = container.getBoundingClientRect();

    function handleMouseMove(moveEvent) {
      const nextWidth = clampWidth(
        moveEvent.clientX - rect.left,
        WORKSPACE_NAV_MIN_WIDTH,
        rect.width / 2,
      );
      setNavWidth(nextWidth);
    }

    function handleMouseUp() {
      window.removeEventListener('mousemove', handleMouseMove);
      window.removeEventListener('mouseup', handleMouseUp);
      document.body.classList.remove('is-resizing-panels');
    }

    document.body.classList.add('is-resizing-panels');
    window.addEventListener('mousemove', handleMouseMove);
    window.addEventListener('mouseup', handleMouseUp);
  }

  async function handleCreateWorkspace(payload) {
    setCreatingWorkspace(true);
    setError('');
    try {
      const createdWorkspace = await fetchJson('/api/workspaces', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      await reloadResources();
      setSelectedWorkspaceId(createdWorkspace.id);
      setSelectedProjectId('');
      setSelectedFilePath('');
      setResourceDialog({ open: false, mode: 'workspace', workspaceId: '' });
    } catch (err) {
      setError(err instanceof Error ? err.message : '创建 workspace 失败');
    } finally {
      setCreatingWorkspace(false);
    }
  }

  async function handleCreateProject(workspaceId, payload) {
    setCreatingProject(true);
    setError('');
    try {
      const createdProject = await fetchJson(`/api/workspaces/${workspaceId}/projects`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      await reloadResources();
      setSelectedWorkspaceId(workspaceId);
      setSelectedProjectId(createdProject.id);
      setSelectedFilePath('');
      setResourceDialog({ open: false, mode: 'workspace', workspaceId: '' });
    } catch (err) {
      setError(err instanceof Error ? err.message : '创建 project 失败');
    } finally {
      setCreatingProject(false);
    }
  }

  async function handleDeleteProject(projectId) {
    const confirmed = window.confirm('删除该 project 会同时删除所有相关 session，确认继续吗？');
    if (!confirmed) {
      return;
    }

    setDeletingProjectId(projectId);
    setError('');
    try {
      await fetchJson(`/api/projects/${projectId}`, { method: 'DELETE' });
      const nextProjectTrees = { ...projectTrees };
      delete nextProjectTrees[projectId];
      setProjectTrees(nextProjectTrees);
      setProjectTreeVersions((current) => {
        const next = { ...current };
        delete next[projectId];
        return next;
      });

      setFileContents((current) =>
        Object.fromEntries(Object.entries(current).filter(([key]) => !key.startsWith(`${projectId}:`))),
      );

      await reloadResources();

      if (selectedProjectId === projectId) {
        setSelectedProjectId('');
        setSelectedFilePath('');
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : '删除 project 失败');
    } finally {
      setDeletingProjectId('');
    }
  }

  async function handleDeleteWorkspace(workspaceId) {
    const confirmed = window.confirm('删除该 workspace 会同时删除其下所有 project 和相关 session，确认继续吗？');
    if (!confirmed) {
      return;
    }

    setDeletingWorkspaceId(workspaceId);
    setError('');
    try {
      const removedProjects = (projectsByWorkspace[workspaceId] ?? []).map((project) => project.id);
      await fetchJson(`/api/workspaces/${workspaceId}`, { method: 'DELETE' });

      setProjectTrees((current) =>
        Object.fromEntries(Object.entries(current).filter(([key]) => !removedProjects.includes(key))),
      );
      setProjectTreeVersions((current) =>
        Object.fromEntries(Object.entries(current).filter(([key]) => !removedProjects.includes(key))),
      );
      setFileContents((current) =>
        Object.fromEntries(
          Object.entries(current).filter(([key]) => !removedProjects.some((projectId) => key.startsWith(`${projectId}:`))),
        ),
      );

      await reloadResources();

      if (selectedWorkspaceId === workspaceId) {
        setSelectedWorkspaceId('');
        setSelectedProjectId('');
        setSelectedFilePath('');
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : '删除 workspace 失败');
    } finally {
      setDeletingWorkspaceId('');
    }
  }

  function handleRefreshProject(projectId) {
    if (!projectId) {
      return;
    }

    setProjectTrees((current) => {
      const next = { ...current };
      delete next[projectId];
      return next;
    });

    setProjectTreeVersions((current) => ({
      ...current,
      [projectId]: (current[projectId] ?? 0) + 1,
    }));

    setFileContents((current) =>
      Object.fromEntries(Object.entries(current).filter(([key]) => !key.startsWith(`${projectId}:`))),
    );

    setSelectedFilePath('');
  }

  return (
    <div className="workspace-page" ref={containerRef}>
      <WorkspaceBrowser
        workspaces={workspaces}
        projectsByWorkspace={projectsByWorkspace}
        selectedWorkspaceId={selectedWorkspaceId}
        onWorkspaceSelect={(workspaceId) => {
          setSelectedWorkspaceId(workspaceId);
          setSelectedFilePath('');
        }}
        selectedProjectId={selectedProjectId}
        onProjectSelect={(projectId) => {
          setSelectedProjectId(projectId);
          setSelectedFilePath('');
        }}
        selectedFilePath={selectedFilePath}
        onFileSelect={setSelectedFilePath}
        fileTree={activeTree}
        fileTreeLoading={activeTreeState?.status === 'loading'}
        fileTreeError={activeTreeState?.error || ''}
        fileContent={activeFileState?.content || ''}
        fileContentLoading={activeFileState?.status === 'loading'}
        fileContentError={activeFileState?.error || ''}
        deletingWorkspaceId={deletingWorkspaceId}
        deletingProjectId={deletingProjectId}
        activeWorkspace={activeWorkspace}
        activeProject={activeProject}
        onCreateWorkspace={() => setResourceDialog({ open: true, mode: 'workspace', workspaceId: '' })}
        onCreateProject={(workspaceId) => setResourceDialog({ open: true, mode: 'project', workspaceId })}
        onDeleteWorkspace={handleDeleteWorkspace}
        onDeleteProject={handleDeleteProject}
        onRefreshProject={handleRefreshProject}
        loading={loading}
        error={error}
        navWidth={navWidth}
        onNavResizeStart={startNavResize}
      />
      <WorkspaceResourceDialog
        open={resourceDialog.open}
        mode={resourceDialog.mode}
        loading={resourceDialog.mode === 'workspace' ? creatingWorkspace : creatingProject}
        onClose={() => setResourceDialog({ open: false, mode: 'workspace', workspaceId: '' })}
        onSubmit={(payload) => {
          if (resourceDialog.mode === 'workspace') {
            return handleCreateWorkspace(payload);
          }
          return handleCreateProject(resourceDialog.workspaceId, payload);
        }}
      />
    </div>
  );
}
