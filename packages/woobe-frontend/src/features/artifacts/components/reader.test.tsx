import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it, vi } from 'vitest'

const hooks = vi.hoisted(() => ({
  useArtifactWorkspace: vi.fn(),
  useArtifactRevisionHistory: vi.fn(),
  useArtifactDocumentIndex: vi.fn(),
  useDocumentNode: vi.fn(),
  useDocumentNodeContent: vi.fn(),
  useDocumentNodes: vi.fn(),
  useDownloadRepresentation: vi.fn(),
  useRenderPdfPage: vi.fn(),
  useRepresentationEntries: vi.fn(),
}))

vi.mock('../hooks', () => hooks)

import { ArtifactDocumentReader } from './ArtifactDocumentReader'
import { SafeMarkdown } from './SafeMarkdown'

const index = {
  schema_version: '1', id: 'index-1', workspace_id: 'workspace-1', artifact_id: 'artifact-1',
  revision_id: 'revision-7', representation_set_id: 'set-1', source_sha256: 'a'.repeat(64),
  recipe_fingerprint: 'b'.repeat(64), processing_fingerprint: 'c'.repeat(64), engine: 'structural',
  engine_version: '1', status: 'ready', tree_kind: 'pages', coverage: 'partial', root_node_id: 'root-1',
  node_count: 2, source_block_count: 1, max_depth: 1, manifest_sha256: 'd'.repeat(64),
  created_at: '2026-10-21T00:00:00Z',
} as const

const root = {
  schema_version: '1', id: 'root-1', document_index_id: 'index-1', representation_set_id: 'set-1',
  parent_id: null, title: 'Document', kind: 'root', ordinal: 0, depth: 0, children_count: 1,
  source_ranges: [], source: null, has_own_text: false, inferred: false, extraction_method: null,
} as const

const page = {
  ...root, id: 'node-1', title: 'Chapter 1', kind: 'page', ordinal: 1, depth: 1,
  parent_id: 'root-1', children_count: 0, has_own_text: true, extraction_method: 'native',
  source: {
    artifact_id: 'artifact-1', revision_id: 'revision-7', source_sha256: 'a'.repeat(64),
    representation_set_id: 'set-1', document_index_id: 'index-1', node_id: 'node-1',
    locator: { page_index: 1, page_number: 2, page_label: 'iv' },
  },
} as const

describe('document reader and sanitized content', () => {
  it('keeps source revision and physical page distinct from the printed label', () => {
    hooks.useArtifactWorkspace.mockReturnValue({ data: { name: 'Research notes' }, isPending: false, isError: false })
    hooks.useArtifactRevisionHistory.mockReturnValue({ data: { items: [], has_more: false, next_cursor: null }, isPending: false, isError: false })
    hooks.useArtifactDocumentIndex.mockReturnValue({ data: index, isPending: false, isError: false })
    hooks.useDocumentNode.mockImplementation((_project: string, _environment: string, _workspace: string, _index: string, nodeId: string) => ({
      data: nodeId === 'root-1' ? root : page, isPending: false, isError: false,
    }))
    hooks.useDocumentNodeContent.mockReturnValue({ data: { text: '<script>alert(1)</script>\n\nEvidence', next_offset: null }, isPending: false, isError: false })
    hooks.useDocumentNodes.mockReturnValue({ data: { items: [], has_more: false, next_cursor: null }, isPending: false, isError: false })
    hooks.useRepresentationEntries.mockReturnValue({ data: { items: [] }, isPending: false, isError: false })
    hooks.useDownloadRepresentation.mockReturnValue({ mutateAsync: vi.fn(), isPending: false, isError: false })
    hooks.useRenderPdfPage.mockReturnValue({ isPending: false, isError: false })

    const html = renderToStaticMarkup(<ArtifactDocumentReader projectId="project-1" workspaceId="workspace-1" artifactId="artifact-1" revisionId="revision-7" environment="draft" onBack={vi.fn()} />)

    expect(html).toContain('Partial extraction')
    expect(html).toContain('revision-7')
    expect(html).toContain('Physical page 2')
    expect(html).toContain('printed iv')
    expect(html).toContain('&lt;script&gt;alert(1)&lt;/script&gt;')
    expect(html).not.toContain('<script>')
  })

  it('escapes HTML and rejects script or SVG data links in Markdown', () => {
    const html = renderToStaticMarkup(<SafeMarkdown source={'<svg onload="alert(1)"></svg>\n\n[run](javascript:alert(1))\n\n[docs](https://example.com)'} />)
    expect(html).toContain('&lt;svg onload=&quot;alert(1)&quot;&gt;&lt;/svg&gt;')
    expect(html).not.toContain('<svg')
    expect(html).not.toContain('href="javascript:')
    expect(html).toContain('href="https://example.com/"')
    expect(html).toContain('rel="noopener noreferrer"')
  })
})
