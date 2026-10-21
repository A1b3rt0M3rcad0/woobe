import { useEffect, useState } from 'react'
import { ArrowLeft, ChevronDown, ChevronRight, Download, Search } from 'lucide-react'
import { Button, Input } from '@woobe/ui'
import { ResourcePage } from '@/components/common/ResourcePage'
import { ApiError } from '@/lib/api/errors'
import { useArtifactWorkspace } from '../hooks'
import {
  useArtifactDocumentIndex,
  useArtifactRevisionHistory,
  useDocumentNode,
  useDocumentNodeContent,
  useDocumentNodes,
  useDownloadRepresentation,
  useRenderPdfPage,
  useRepresentationEntries,
} from '../hooks'
import type { ArtifactEnvironment, DocumentNode } from '../types'
import { SafeMarkdown } from './SafeMarkdown'

type Pane = 'tree' | 'reader' | 'details'

function errorMessage(error: unknown) {
  if (error instanceof ApiError && error.status === 403) return 'The current Project and Artifact Workspace grants do not authorize this read.'
  if (error instanceof ApiError && error.status === 404) return 'This revision is unavailable or has no published document index.'
  return error instanceof Error ? error.message : 'Document reading failed.'
}

function coverageLabel(coverage: string) {
  switch (coverage) {
    case 'complete': return 'Extraction coverage complete'
    case 'partial': return 'Partial extraction: some source content is unavailable'
    case 'needs_ocr': return 'OCR is missing for visual pages'
    default: return 'This document format is stored, but its contents are not supported by the current profile'
  }
}

function useObjectUrl(blob: Blob | undefined) {
  const [url, setUrl] = useState<string | null>(null)
  useEffect(() => {
    if (!blob) { setUrl(null); return }
    const next = URL.createObjectURL(blob)
    setUrl(next)
    return () => URL.revokeObjectURL(next)
  }, [blob])
  return url
}

function NodeBranch({
  node, projectId, environment, workspaceId, indexId, selectedNodeId, onSelect,
}: {
  node: DocumentNode
  projectId: string
  environment: ArtifactEnvironment
  workspaceId: string
  indexId: string
  selectedNodeId: string
  onSelect: (nodeId: string) => void
}) {
  const [expanded, setExpanded] = useState(node.kind === 'root')
  const [cursor, setCursor] = useState<string | null>(null)
  const children = useDocumentNodes(projectId, environment, workspaceId, indexId, node.id, cursor, undefined, expanded)
  const canExpand = node.children_count > 0
  return (
    <li className="min-w-0" role="treeitem" aria-expanded={canExpand ? expanded : undefined}>
      <div className="flex min-w-0 items-center gap-ui-xs">
        {canExpand ? <button type="button" aria-label={`${expanded ? 'Collapse' : 'Expand'} ${node.title}`} onClick={() => setExpanded(value => !value)} className="shrink-0 rounded-control p-ui-xs focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary">{expanded ? <ChevronDown className="h-icon w-icon" /> : <ChevronRight className="h-icon w-icon" />}</button> : <span className="w-icon shrink-0" />}
        <button type="button" aria-current={selectedNodeId === node.id ? 'true' : undefined} onClick={() => onSelect(node.id)} className={`min-w-0 break-words rounded-control px-ui-xs py-ui-xs text-left text-product-small focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary ${selectedNodeId === node.id ? 'bg-primary/10 font-semibold text-primary' : 'hover:bg-muted/50'}`}>
          {node.title || 'Untitled section'}
          {node.inferred && <span className="ml-ui-xs text-system-meta text-muted-foreground">Inferred</span>}
        </button>
      </div>
      {expanded && canExpand && (
        <div className="ml-ui-md border-l border-border pl-ui-sm">
          {children.isPending ? <p role="status" className="p-ui-xs text-system-meta">Loading sections…</p>
            : children.isError ? <p role="alert" className="p-ui-xs text-system-meta text-error">{errorMessage(children.error)}</p>
              : <ul role="group" className="grid gap-ui-xs">
                {children.data.items.map(item => <NodeBranch key={item.id} node={item} projectId={projectId} environment={environment} workspaceId={workspaceId} indexId={indexId} selectedNodeId={selectedNodeId} onSelect={onSelect} />)}
                {children.data.has_more && children.data.next_cursor && <li><Button size="sm" variant="ghost" onClick={() => setCursor(children.data?.next_cursor ?? null)}>Load more sections</Button></li>}
              </ul>}
        </div>
      )}
    </li>
  )
}

function RepresentationPreview({ blob, entry }: { blob: Blob; entry: { path: string; content_type: string } }) {
  const url = useObjectUrl(blob)
  const [text, setText] = useState<string | null>(null)
  useEffect(() => {
    if (!entry.content_type.startsWith('text/') && !['application/json', 'application/xml'].includes(entry.content_type)) { setText(null); return }
    let current = true
    void blob.slice(0, 262144).text().then(value => { if (current) setText(value) })
    return () => { current = false }
  }, [blob, entry.content_type])
  if (entry.content_type.startsWith('image/') && entry.content_type !== 'image/svg+xml') {
    return url ? <img src={url} alt={entry.path} className="max-h-[60vh] max-w-full rounded-technical object-contain" /> : null
  }
  if (entry.content_type === 'text/markdown' && text != null) return <SafeMarkdown source={text} />
  if ((entry.content_type.startsWith('text/') || ['application/json', 'application/xml'].includes(entry.content_type)) && text != null) return <pre className="max-h-[60vh] overflow-auto whitespace-pre-wrap break-words rounded-technical bg-muted/40 p-ui-sm text-product-small">{text}{blob.size > 262144 ? '\n\nPreview truncated at 256 KiB.' : ''}</pre>
  return url ? <a className="inline-flex items-center gap-ui-xs underline" href={url} download={entry.path.split('/').pop() ?? 'representation'}><Download className="h-icon w-icon" />Download {entry.path}</a> : null
}

export function ArtifactDocumentReader({
  projectId, workspaceId, artifactId, revisionId, environment, onBack, onSelectRevision,
  accountWorkspaceId,
}: {
  projectId: string
  workspaceId: string
  artifactId: string
  revisionId: string
  environment: ArtifactEnvironment
  onBack: () => void
  accountWorkspaceId?: string
  onSelectRevision?: (revisionId: string) => void
}) {
  const [selectedNodeId, setSelectedNodeId] = useState('')
  const [pane, setPane] = useState<Pane>('reader')
  const [titleSearch, setTitleSearch] = useState('')
  const [searchCursor, setSearchCursor] = useState<string | null>(null)
  const [contentOffset, setContentOffset] = useState(0)
  const [activeRepresentation, setActiveRepresentation] = useState<string | null>(null)
  const [representationBlob, setRepresentationBlob] = useState<Blob | null>(null)
  const [revisionCursor, setRevisionCursor] = useState<string | null>(null)
  const [revisionHistory, setRevisionHistory] = useState<Array<{ id: string; created_at: string; origin: string }>>([])
  const workspace = useArtifactWorkspace(projectId, environment, workspaceId)
  const revisions = useArtifactRevisionHistory(projectId, environment, workspaceId, artifactId, revisionCursor)
  const index = useArtifactDocumentIndex(projectId, environment, workspaceId, artifactId, revisionId)
  const rootNode = useDocumentNode(projectId, environment, workspaceId, index.data?.id ?? '', index.data?.root_node_id ?? '')
  const selectedNode = useDocumentNode(projectId, environment, workspaceId, index.data?.id ?? '', selectedNodeId)
  const content = useDocumentNodeContent(projectId, environment, workspaceId, index.data?.id ?? '', selectedNodeId, contentOffset, Boolean(selectedNode.data?.has_own_text))
  const searchResults = useDocumentNodes(projectId, environment, workspaceId, index.data?.id ?? '', null, searchCursor, titleSearch.trim().length >= 2 ? titleSearch.trim() : undefined, titleSearch.trim().length >= 2)
  const representations = useRepresentationEntries(projectId, environment, workspaceId, artifactId, revisionId, index.data?.representation_set_id ?? '')
  const download = useDownloadRepresentation(projectId, environment, workspaceId, artifactId, revisionId, index.data?.representation_set_id ?? '')
  const currentSource = selectedNode.data?.source
  const pageIndex = currentSource?.locator?.page_index
  const pageImage = useRenderPdfPage(projectId, environment, workspaceId, artifactId, revisionId,
    index.data?.representation_set_id ?? '', pageIndex ?? 0, pageIndex !== undefined && pageIndex !== null)
  const currentEntry = representations.data?.items.find(item => item.id === activeRepresentation)
  const pageImageUrl = useObjectUrl(pageImage.data)

  useEffect(() => {
    if (index.data?.root_node_id && !selectedNodeId) setSelectedNodeId(index.data.root_node_id)
  }, [index.data?.root_node_id, selectedNodeId])
  useEffect(() => { setContentOffset(0) }, [selectedNodeId])
  useEffect(() => {
    if (!revisions.data) return
    setRevisionHistory(current => {
      const known = new Set(current.map(item => item.id))
      return [...current, ...revisions.data.items.filter(item => !known.has(item.id))]
    })
  }, [revisions.data])

  function openRevision(nextRevisionId: string) {
    if (!onSelectRevision || nextRevisionId === revisionId) return
    onSelectRevision(nextRevisionId)
  }

  async function openRepresentation(entryId: string) {
    setRepresentationBlob(null)
    setActiveRepresentation(entryId)
    try { setRepresentationBlob(await download.mutateAsync(entryId)) }
    catch { setActiveRepresentation(entryId) }
  }

  const tree = titleSearch.trim().length >= 2 ? searchResults.data?.items ?? [] : []
  const hasSearch = titleSearch.trim().length >= 2
  const sourceLabel = currentSource ? `${currentSource.artifact_id} @ ${currentSource.revision_id}` : 'No exact source selected'

  return (
    <ResourcePage title="Document reader" description={`${workspace.data?.name ?? 'Artifact Workspace'} · exact revision ${revisionId}`} action={<Button type="button" variant="outline" onClick={onBack}><ArrowLeft className="h-icon w-icon" />Explorer</Button>}>
      {workspace.isError ? <div role="alert" className="rounded-technical border border-error/40 p-ui-md">{errorMessage(workspace.error)}</div>
        : index.isPending ? <p role="status" className="rounded-technical border border-border p-ui-lg">Loading the exact document index…</p>
          : index.isError ? <div role="alert" className="grid gap-ui-sm rounded-technical border border-border p-ui-lg"><p>{errorMessage(index.error)}</p><p className="text-product-small text-muted-foreground">This reader never substitutes a newer revision. Check processing status or return to the Explorer.</p></div>
            : <>
              <section className={`rounded-technical border p-ui-md text-product-small ${index.data.coverage === 'complete' ? 'border-primary/30 bg-primary/5' : 'border-warning/40 bg-warning/5'}`} role="status">
                <p className="font-medium">{coverageLabel(index.data.coverage)}</p>
                <p className="mt-ui-xs text-muted-foreground">{index.data.engine} {index.data.engine_version} · {index.data.node_count.toLocaleString()} sections/nodes · {index.data.source_block_count.toLocaleString()} source blocks · {new Date(index.data.created_at).toLocaleString()}</p>
              </section>
              <nav aria-label="Document reader panels" className="flex flex-wrap gap-ui-xs lg:hidden">
                {(['tree', 'reader', 'details'] as Pane[]).map(item => <Button key={item} type="button" size="sm" variant={pane === item ? 'default' : 'outline'} onClick={() => setPane(item)}>{item[0].toUpperCase()}{item.slice(1)}</Button>)}
              </nav>
              <div className="grid min-w-0 gap-ui-md lg:grid-cols-[minmax(14rem,0.75fr)_minmax(0,2fr)]">
                <aside aria-label="Document sections" className={`min-w-0 rounded-technical border border-border bg-card p-ui-md ${pane !== 'tree' ? 'hidden lg:block' : ''}`}>
                  <h2 className="mb-ui-sm font-medium">Sections</h2>
                  <label htmlFor="artifact-section-search" className="sr-only">Search section titles</label>
                  <div className="relative mb-ui-sm"><Search aria-hidden="true" className="absolute left-ui-sm top-1/2 h-icon w-icon -translate-y-1/2 text-muted-foreground" /><Input id="artifact-section-search" value={titleSearch} onChange={event => { setTitleSearch(event.target.value); setSearchCursor(null) }} placeholder="Search section titles" className="pl-control-icon" /></div>
                  {hasSearch ? searchResults.isPending ? <p role="status" className="text-product-small">Searching sections…</p>
                    : searchResults.isError ? <p role="alert" className="text-product-small text-error">{errorMessage(searchResults.error)}</p>
                      : tree.length === 0 ? <p className="text-product-small text-muted-foreground">No matching section titles.</p>
                        : <ul role="tree" className="grid gap-ui-xs">{tree.map(node => <li role="treeitem" key={node.id}><button type="button" onClick={() => { setSelectedNodeId(node.id); setPane('reader') }} className="w-full break-words rounded-control p-ui-xs text-left text-product-small hover:bg-muted/50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary">{node.title}</button></li>)}{searchResults.data?.has_more && searchResults.data.next_cursor && <li><Button size="sm" variant="ghost" onClick={() => setSearchCursor(searchResults.data?.next_cursor ?? null)}>Load more matches</Button></li>}</ul>
                    : rootNode.isPending ? <p role="status" className="text-product-small">Loading document tree…</p>
                      : rootNode.isError ? <p role="alert" className="text-product-small text-error">{errorMessage(rootNode.error)}</p>
                        : <ul role="tree" className="grid gap-ui-xs"><NodeBranch node={rootNode.data} projectId={projectId} environment={environment} workspaceId={workspaceId} indexId={index.data.id} selectedNodeId={selectedNodeId} onSelect={setSelectedNodeId} /></ul>}
                </aside>
                <section aria-label="Document content" className={`min-w-0 grid content-start gap-ui-md rounded-technical border border-border bg-card p-ui-md ${pane !== 'reader' ? 'hidden lg:grid' : ''}`}>
                  <div className="flex min-w-0 flex-wrap items-start justify-between gap-ui-sm"><div className="min-w-0"><h2 className="break-words text-title-md font-semibold">{selectedNode.data?.title ?? 'Loading section…'}</h2><p className="mt-ui-xs break-all font-mono text-system-meta text-muted-foreground">{sourceLabel}</p></div>{selectedNode.data?.source?.locator?.page_index != null && <span className="rounded-control border border-border px-ui-sm py-ui-xs text-product-small">Physical page {(selectedNode.data.source.locator.page_index ?? 0) + 1}{selectedNode.data.source.locator.page_label ? ` · printed ${selectedNode.data.source.locator.page_label}` : ''}</span>}</div>
                  {pageImageUrl && <img src={pageImageUrl} alt={`Physical page ${(pageIndex ?? 0) + 1}`} className="max-h-[65vh] max-w-full justify-self-center rounded-technical border border-border object-contain" />}
                  {pageImage.isError && <p role="status" className="text-product-small text-muted-foreground">The source page image is unavailable; extracted text remains shown below.</p>}
                  {selectedNode.isPending ? <p role="status" className="text-product-small">Loading source text…</p>
                    : content.isError ? <p role="alert" className="text-product-small text-warning">{errorMessage(content.error)} Source content is unavailable for this node.</p>
                      : content.data?.text ? <><SafeMarkdown source={content.data.text} />{content.data.next_offset != null && <Button type="button" size="sm" variant="outline" className="w-fit" onClick={() => setContentOffset(content.data?.next_offset ?? 0)}>Continue reading at {content.data.next_offset}</Button>}</>
                        : <p className="text-product-small text-muted-foreground">This container has no own text. Select a child section to read its source.</p>}
                </section>
                <aside aria-label="Source details and representations" className={`min-w-0 grid content-start gap-ui-md rounded-technical border border-border bg-card p-ui-md lg:col-span-2 ${pane !== 'details' ? 'hidden lg:grid' : ''}`}>
                  <section><h2 className="font-medium">Exact source</h2><dl className="mt-ui-sm grid min-w-0 gap-ui-sm text-product-small sm:grid-cols-2"><div className="min-w-0"><dt className="text-muted-foreground">Artifact</dt><dd className="break-all font-mono">{artifactId}</dd></div><div className="min-w-0"><dt className="text-muted-foreground">Revision</dt><dd className="break-all font-mono">{revisionId}</dd></div><div><dt className="text-muted-foreground">SHA-256</dt><dd className="break-all font-mono">{index.data.source_sha256}</dd></div><div><dt className="text-muted-foreground">Extraction</dt><dd>{selectedNode.data?.extraction_method ?? 'No text block'}</dd></div></dl>
                    <div className="mt-ui-md grid gap-ui-xs"><h3 className="text-product-small font-medium">Revision history</h3>{revisions.isError && <p role="alert" className="text-product-small text-warning">{errorMessage(revisions.error)}</p>}{revisionHistory.map(item => <button key={item.id} type="button" aria-current={item.id === revisionId ? 'true' : undefined} disabled={!onSelectRevision || item.id === revisionId} onClick={() => openRevision(item.id)} className="flex min-w-0 flex-wrap justify-between gap-ui-sm rounded-technical border border-border p-ui-sm text-left text-product-small hover:bg-muted/40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary disabled:opacity-60"><span className="break-all font-mono">{item.id}{item.id === revisionId ? ' · selected exact revision' : ''}</span><span>{item.origin} · {new Date(item.created_at).toLocaleString()}</span></button>)}{revisionHistory.length === 0 && revisions.isPending && <p role="status" className="text-product-small">Loading revision history…</p>}{revisions.data?.has_more && revisions.data.next_cursor && <Button type="button" size="sm" variant="outline" className="w-fit" disabled={revisions.isFetching} onClick={() => setRevisionCursor(revisions.data?.next_cursor ?? null)}>Load older revisions</Button>}</div>
                  </section>
                  <section><h2 className="font-medium">Representations</h2>{representations.isPending ? <p role="status" className="mt-ui-sm text-product-small">Loading representations…</p> : representations.isError ? <p role="alert" className="mt-ui-sm text-product-small text-warning">{errorMessage(representations.error)}</p> : representations.data.items.length === 0 ? <p className="mt-ui-sm text-product-small text-muted-foreground">No published derived files for this revision.</p> : <ul className="mt-ui-sm grid gap-ui-xs">{representations.data.items.map(entry => <li key={entry.id} className="flex min-w-0 flex-wrap items-center justify-between gap-ui-sm rounded-technical border border-border p-ui-sm"><span className="min-w-0 break-all text-product-small">{entry.path} · {entry.kind} · {entry.size_bytes.toLocaleString()} bytes</span><Button type="button" size="sm" variant="outline" onClick={() => void openRepresentation(entry.id)}>{activeRepresentation === entry.id ? 'Selected' : 'Preview / download'}</Button></li>)}</ul>}
                    {currentEntry && <div className="mt-ui-md grid gap-ui-sm rounded-technical border border-border p-ui-md"><h3 className="break-all text-product-small font-medium">{currentEntry.path}</h3>{download.isPending ? <p role="status" className="text-product-small">Loading representation…</p> : download.isError ? <p role="alert" className="text-product-small text-error">{errorMessage(download.error)}</p> : representationBlob ? <RepresentationPreview blob={representationBlob} entry={currentEntry} /> : <p className="text-product-small text-muted-foreground">Preview unavailable. Use the explicit download link when supported.</p>}</div>}
                  </section>
                </aside>
              </div>
            </>}
    </ResourcePage>
  )
}
