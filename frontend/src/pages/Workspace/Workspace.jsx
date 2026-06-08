import React from 'react';
import { useEffect, useState } from 'react';
import WorkspaceBrowser from '../../components/WorkspaceBrowser/WorkspaceBrowser';
import { fetchJson } from '../../utils/api';
import './Workspace.css';

export default function Workspace() {
  const [workspaces, setWorkspaces] = useState([]);
  const [projectsByWorkspace, setProjectsByWorkspace] = useState({});
  const [selectedProjectId, setSelectedProjectId] = useState('');
  const [projectFiles, setProjectFiles] = useState({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    let cancelled = false;

    async function loadWorkspaces() {
      setLoading(true);
      setError('');

      try {
        const workspaceData = await fetchJson('/api/workspaces');
        if (cancelled) {
          return;
        }

        setWorkspaces(workspaceData);

        const projectEntries = await Promise.all(
          workspaceData.map(async (workspace) => [
            workspace.id,
            await fetchJson(`/api/workspaces/${workspace.id}/projects`),
          ]),
        );

        if (cancelled) {
          return;
        }

        setProjectsByWorkspace(Object.fromEntries(projectEntries));
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
    if (!selectedProjectId || projectFiles[selectedProjectId]) {
      return;
    }

    let cancelled = false;

    async function loadProjectFiles() {
      try {
        const treeData = await fetchJson(`/api/projects/${selectedProjectId}/files/tree`);
        if (cancelled) {
          return;
        }

        const firstFile = treeData.find((entry) => entry.type === 'file');
        if (!firstFile) {
          setProjectFiles((current) => ({
            ...current,
            [selectedProjectId]: {
              tree: treeData,
              content: '当前 project workspace 下没有可预览文件。',
            },
          }));
          return;
        }

        const queryPath = encodeURIComponent(firstFile.path);
        const contentData = await fetchJson(`/api/projects/${selectedProjectId}/files/content?path=${queryPath}`);
        if (!cancelled) {
          setProjectFiles((current) => ({
            ...current,
            [selectedProjectId]: {
              tree: treeData,
              content: contentData.content || '',
            },
          }));
        }
      } catch (err) {
        if (!cancelled) {
          setProjectFiles((current) => ({
            ...current,
            [selectedProjectId]: {
              tree: [],
              content: err instanceof Error ? err.message : '加载文件失败',
            },
          }));
        }
      }
    }

    loadProjectFiles();

    return () => {
      cancelled = true;
    };
  }, [projectFiles, selectedProjectId]);

  const activeProjectFiles = selectedProjectId ? projectFiles[selectedProjectId] : null;

  return (
    <div className="workspace-page">
      <WorkspaceBrowser
        workspaces={workspaces}
        projectsByWorkspace={projectsByWorkspace}
        selectedProjectId={selectedProjectId}
        onProjectSelect={setSelectedProjectId}
        fileTree={activeProjectFiles?.tree || []}
        fileContent={activeProjectFiles?.content || ''}
        onCreateWorkspace={() => {}}
        loading={loading}
        error={error}
      />
    </div>
  );
}
