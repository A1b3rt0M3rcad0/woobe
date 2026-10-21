// @vitest-environment jsdom
import { act } from 'react'
import { createRoot } from 'react-dom/client'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { afterEach, describe, expect, it, vi } from 'vitest'

const api = vi.hoisted(() => ({
  createArtifactDirectory: vi.fn(),
  createArtifactWorkspace: vi.fn(),
  deleteArtifact: vi.fn(),
  getArtifactCapabilities: vi.fn(),
  getArtifactWorkspace: vi.fn(),
  listArtifactWorkspaces: vi.fn(),
  listArtifacts: vi.fn(),
  moveArtifact: vi.fn(),
}))

vi.mock('./api', () => api)

import { useArtifacts } from './hooks'

function deferred<T>() {
  let resolve!: (value: T) => void
  const promise = new Promise<T>(done => { resolve = done })
  return { promise, resolve }
}

function page(path: string) {
  return {
    schema_version: '1' as const,
    items: [{
      schema_version: '1' as const,
      id: `artifact-${path}`,
      workspace_id: 'workspace',
      path,
      kind: 'file' as const,
      revision_id: `revision-${path}`,
      version: 1,
      deleted: false,
      revision: null,
    }],
    has_more: false,
    next_cursor: null,
    truncated: false,
  }
}

function Harness({ workspaceId }: { workspaceId: string }) {
  const query = useArtifacts('project-1', 'draft', workspaceId, '', null)
  return <output>{query.data?.items.map(item => item.path).join(',') ?? 'Loading'}</output>
}

function render() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  const container = document.createElement('div')
  document.body.appendChild(container)
  const root = createRoot(container)
  return {
    container,
    queryClient,
    root,
    show: (workspaceId: string) => act(async () => {
      root.render(<QueryClientProvider client={queryClient}><Harness workspaceId={workspaceId} /></QueryClientProvider>)
    }),
    cleanup: () => act(async () => {
      root.unmount()
      queryClient.clear()
      container.remove()
    }),
  }
}

afterEach(() => {
  vi.clearAllMocks()
})

describe('Artifact Explorer selection isolation', () => {
  it('does not display a late response from a previously selected Workspace', async () => {
    const workspaceA = deferred<ReturnType<typeof page>>()
    const workspaceB = deferred<ReturnType<typeof page>>()
    api.listArtifacts.mockImplementation((_scope, workspaceId: string) =>
      workspaceId === 'artifact-workspace-a' ? workspaceA.promise : workspaceB.promise,
    )
    const view = render()
    try {
      await view.show('artifact-workspace-a')
      await vi.waitFor(() => expect(api.listArtifacts).toHaveBeenCalledWith(
        { projectId: 'project-1', environment: 'draft' },
        'artifact-workspace-a',
        { directory: '', cursor: null, limit: 100 },
      ))

      await view.show('artifact-workspace-b')
      await vi.waitFor(() => expect(api.listArtifacts).toHaveBeenCalledWith(
        { projectId: 'project-1', environment: 'draft' },
        'artifact-workspace-b',
        { directory: '', cursor: null, limit: 100 },
      ))

      await act(async () => { workspaceA.resolve(page('old-workspace-secret.txt')) })
      expect(view.container.textContent).not.toContain('old-workspace-secret.txt')
      expect(view.container.textContent).toContain('Loading')

      await act(async () => { workspaceB.resolve(page('current-workspace.txt')) })
      await vi.waitFor(() => expect(view.container.textContent).toContain('current-workspace.txt'))
      expect(view.container.textContent).not.toContain('old-workspace-secret.txt')
    } finally {
      await view.cleanup()
    }
  })
})
