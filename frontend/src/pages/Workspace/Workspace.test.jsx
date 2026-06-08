import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import Workspace from './Workspace';

describe('Workspace page', () => {
  function createDeferred() {
    let resolve;
    const promise = new Promise((innerResolve) => {
      resolve = innerResolve;
    });
    return { promise, resolve };
  }

  it('loads project tree data without getting stuck in loading state', async () => {
    const treeDeferred = createDeferred();

    global.fetch = vi.fn((input) => {
      const url = String(input);

      if (url.endsWith('/api/workspaces')) {
        return Promise.resolve({
          ok: true,
          json: async () => [
            {
              id: 'ws-1',
              name: 'test',
              endpoint: 'localhost',
              created_at: '2026-06-08T00:00:00Z',
            },
          ],
        });
      }

      if (url.endsWith('/api/workspaces/ws-1/projects')) {
        return Promise.resolve({
          ok: true,
          json: async () => [
            {
              id: 'pw-1',
              workspace_id: 'ws-1',
              name: 'test',
              path: 'E:/Github/EchoMind/.echo/test',
              created_at: '2026-06-08T00:00:00Z',
            },
          ],
        });
      }

      if (url.endsWith('/api/projects/pw-1/files/tree')) {
        return treeDeferred.promise;
      }

      return Promise.resolve({
        ok: true,
        json: async () => ({ path: 'README.md', content: '# EchoMind' }),
      });
    });

    render(<Workspace />);

    treeDeferred.resolve({
      ok: true,
      json: async () => [
        { path: 'README.md', type: 'file' },
      ],
    });

    expect(await screen.findByText('README.md')).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.queryByText('正在加载代码树...')).not.toBeInTheDocument();
    });
  });

  it('loads selected file content into the preview panel', async () => {
    const fileContentDeferred = createDeferred();

    global.fetch = vi.fn((input) => {
      const url = String(input);

      if (url.endsWith('/api/workspaces')) {
        return Promise.resolve({
          ok: true,
          json: async () => [
            {
              id: 'ws-1',
              name: 'test',
              endpoint: 'localhost',
              created_at: '2026-06-08T00:00:00Z',
            },
          ],
        });
      }

      if (url.endsWith('/api/workspaces/ws-1/projects')) {
        return Promise.resolve({
          ok: true,
          json: async () => [
            {
              id: 'pw-1',
              workspace_id: 'ws-1',
              name: 'test',
              path: 'E:/Github/EchoMind/.echo/test',
              created_at: '2026-06-08T00:00:00Z',
            },
          ],
        });
      }

      if (url.endsWith('/api/projects/pw-1/files/tree')) {
        return Promise.resolve({
          ok: true,
          json: async () => [{ path: 'README.md', type: 'file' }],
        });
      }

      if (url.endsWith('/api/projects/pw-1/files/content?path=README.md')) {
        return fileContentDeferred.promise;
      }

      throw new Error(`Unexpected request: ${url}`);
    });

    render(<Workspace />);

    const fileNode = await screen.findByText('README.md');
    fireEvent.click(fileNode);

    expect(await screen.findByText('正在加载文件内容...')).toBeInTheDocument();

    fileContentDeferred.resolve({
      ok: true,
      json: async () => ({ path: 'README.md', content: '# EchoMind' }),
    });

    expect(await screen.findByText('# EchoMind')).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.queryByText('正在加载文件内容...')).not.toBeInTheDocument();
    });
  });
});
