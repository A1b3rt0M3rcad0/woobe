import { renderToStaticMarkup } from 'react-dom/server'
import type { ReactNode } from 'react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'

const hooks = vi.hoisted(() => ({
  useArtifactCapabilities: vi.fn(),
  useArtifactWorkspace: vi.fn(),
  useArtifactWorkspaces: vi.fn(),
  useArtifacts: vi.fn(),
  useCreateArtifactDirectory: vi.fn(),
  useCreateArtifactWorkspace: vi.fn(),
  useDeleteArtifact: vi.fn(),
  useMoveArtifact: vi.fn(),
}))

vi.mock('../hooks', () => hooks)

import { ArtifactExplorer } from './ArtifactExplorer'
import { ArtifactWorkspaces } from './ArtifactWorkspaces'
import type { ArtifactWorkspace } from '../types'

const workspace: ArtifactWorkspace = {
  schema_version: '1', id: 'artifact-workspace-private-id', project_id: 'project-1',
  environment: 'draft', external_namespace: 'course-files', external_key: 'course-17',
  name: 'Course materials', storage_profile: 'local', quota_bytes: 1000, retention_days: 30,
  labels: {}, status: 'active', version: 2, catalog_version: 12, used_bytes: 250, reserved_bytes: 0,
}

function inProjectRoute(element: ReactNode) {
  return renderToStaticMarkup(
    <MemoryRouter initialEntries={['/workspaces/human-workspace/projects/project-1/artifacts/artifact-workspace-private-id']}>
      <Routes>
        <Route path="/workspaces/:workspaceId/projects/:projectId/artifacts/:artifactWorkspaceId" element={element} />
      </Routes>
    </MemoryRouter>,
  )
}

describe('Artifact Workspace browser surfaces', () => {
  it('shows paginated Workspace names and Environment while disclosing external identity under details', () => {
    hooks.useArtifactWorkspaces.mockReturnValue({
      isPending: false,
      isError: false,
      isFetching: false,
      data: { schema_version: '1', items: [workspace], has_more: true, next_cursor: 'opaque-next', truncated: false },
    })
    hooks.useCreateArtifactWorkspace.mockReturnValue({ mutateAsync: vi.fn(), isPending: false })

    const html = renderToStaticMarkup(
      <MemoryRouter initialEntries={['/workspaces/human-workspace/projects/project-1/artifacts']}>
        <Routes>
          <Route path="/workspaces/:workspaceId/projects/:projectId/artifacts" element={
            <ArtifactWorkspaces projectId="project-1" environment="draft" onEnvironmentChange={vi.fn()} />
          } />
        </Routes>
      </MemoryRouter>,
    )

    expect(html).toContain('Course materials')
    expect(html).toContain('Environment')
    expect(html).toContain('External identity')
    expect(html).toContain('course-files')
    expect(html).toContain('course-17')
    expect(html).toContain('Next')
    expect(html).toContain('Search this page')
  })

  it('keeps long filenames and revision metadata responsive in the authorized file listing', () => {
    hooks.useArtifactWorkspace.mockReturnValue({ data: workspace, isPending: false, isError: false })
    hooks.useArtifactCapabilities.mockReturnValue({ data: {
      schema_version: '1', max_upload_bytes: 1000, max_upload_part_bytes: 256,
      max_upload_parts: 10, max_inline_bytes: 100, max_request_bytes: 1000,
      storage_readiness: 'ready', media_types: [], downloads: [],
    }, isPending: false, isError: false })
    hooks.useArtifacts.mockReturnValue({
      data: {
        schema_version: '1', has_more: false, next_cursor: null, truncated: false,
        items: [{
          schema_version: '1', id: 'artifact-file-1', workspace_id: workspace.id,
          path: `documents/${'a-very-long-file-name-'.repeat(8)}.pdf`, kind: 'file',
          revision_id: 'revision-1', version: 3, deleted: false,
          revision: {
            schema_version: '1', id: 'revision-1', artifact_id: 'artifact-file-1',
            content_type: 'application/pdf', size_bytes: 8192, sha256: 'a'.repeat(64),
            origin: 'upload',
          },
        }],
      },
      isPending: false,
      isError: false,
      isFetching: false,
    })
    hooks.useCreateArtifactDirectory.mockReturnValue({ mutateAsync: vi.fn(), isPending: false })
    hooks.useMoveArtifact.mockReturnValue({ mutateAsync: vi.fn(), isPending: false })
    hooks.useDeleteArtifact.mockReturnValue({ mutateAsync: vi.fn(), isPending: false })

    const html = inProjectRoute(
      <ArtifactExplorer projectId="project-1" workspaceId={workspace.id} environment="draft" onEnvironmentChange={vi.fn()} />,
    )
    expect(html).toContain('revision-1')
    expect(html).toContain('8,192 bytes')
    expect(html).toContain('Uploaded original')
    expect(html).toContain('Processing')
    expect(html).toContain('min-w-0')
    expect(html).toContain('break-all')
    expect(html).toContain('Move / rename')
    expect(html).toContain('Delete')
  })
})
