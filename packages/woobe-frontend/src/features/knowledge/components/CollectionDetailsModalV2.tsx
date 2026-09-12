import { useEffect, useMemo, useState } from 'react'
import { AlertTriangle, Cpu, Database, FileText, RefreshCw, Trash2, Upload } from 'lucide-react'
import { toast } from 'sonner'
import { LoadingState } from '@/components/common/LoadingState'
import { StatusBadge } from '@/components/common/StatusBadge'
import { Button } from '@/components/ui/Button'
import { Dialog } from '@/components/ui/Dialog'
import { Input } from '@/components/ui/Input'
import { Tabs } from '@/components/ui/Tabs'
import { Textarea } from '@/components/ui/Textarea'
import { BuildVectorSnapshotModalV2 } from '@/features/knowledge/components/BuildVectorSnapshotModalV2'
import { CollectionDocumentUploadModal } from '@/features/knowledge/components/CollectionDocumentUploadModal'
import { VectorSnapshotDetailsModal } from '@/features/knowledge/components/VectorSnapshotDetailsModal'
import { useDeleteDocument, useDocumentsByCollection, useUpdateCollection } from '@/features/knowledge/hooks'
import { useCollectionOverview, useVectorSnapshots } from '@/features/knowledge/vectorHooks'
import { formatBytes } from '@/lib/formatters/bytes'
import { formatDate } from '@/lib/formatters/date'
import type { Collection, Document, VectorSnapshot } from '@/features/knowledge/types'

interface CollectionDetailsModalProps {
  open: boolean
  onClose: () => void
  collection: Collection | null
  projectId: string
  onUseSnapshot?: (snapshot: VectorSnapshot) => void | Promise<void>
}

function isIndexed(status?: string) {
  const normalized = status?.toLowerCase()
  return normalized === 'indexed' || normalized === 'ready'
}

function documentMeta(document: Document) {
  return [document.file_name, formatBytes(document.size_bytes), document.content_type].filter(Boolean).join(' · ')
}

function numberLabel(value?: number | null) {
  return typeof value === 'number' ? value.toLocaleString() : '0'
}

function PanelHeader({ title, description, action }: { title: string; description: string; action?: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
      <div className="min-w-0">
        <h3 className="font-mono text-[10px] font-bold text-slate-50">{title}</h3>
        <p className="mt-1 font-sans text-[10px] leading-4 text-muted-foreground">{description}</p>
      </div>
      {action ? <div className="shrink-0">{action}</div> : null}
    </div>
  )
}

function FieldLabel({ children }: { children: React.ReactNode }) {
  return <label className="mb-1.5 block font-mono text-[8px] font-medium uppercase tracking-[0.1em] text-muted-foreground">{children}</label>
}

function TechItem({ label, value, detail }: { label: string; value: string; detail?: string }) {
  return (
    <div className="min-w-0 rounded-container border border-border bg-background/35 px-3 py-3">
      <p className="font-mono text-[8px] font-medium uppercase tracking-[0.1em] text-muted-foreground">{label}</p>
      <p className="mt-1.5 break-words font-mono text-[10px] font-semibold text-slate-100">{value}</p>
      {detail ? <p className="mt-1 font-sans text-[9px] leading-4 text-muted-foreground">{detail}</p> : null}
    </div>
  )
}

export function CollectionDetailsModal({ open, onClose, collection, projectId, onUseSnapshot }: CollectionDetailsModalProps) {
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [uploadModalOpen, setUploadModalOpen] = useState(false)
  const [buildModalOpen, setBuildModalOpen] = useState(false)
  const [documentToDelete, setDocumentToDelete] = useState<Document | null>(null)
  const [snapshotToView, setSnapshotToView] = useState<VectorSnapshot | null>(null)

  const updateCollection = useUpdateCollection()
  const deleteDocument = useDeleteDocument()
  const { data: documents, isLoading, refetch } = useDocumentsByCollection(collection?.id)
  const { data: overview, refetch: refetchOverview } = useCollectionOverview(collection?.id, projectId)
  const { data: snapshots, refetch: refetchSnapshots } = useVectorSnapshots(collection?.id, projectId)

  useEffect(() => {
    if (!collection) return
    setName(collection.name)
    setDescription(collection.description || '')
    setUploadModalOpen(false)
    setBuildModalOpen(false)
    setDocumentToDelete(null)
    setSnapshotToView(null)
  }, [collection])

  const items = documents ?? []
  const vectorSnapshots = snapshots ?? []
  const indexedCount = useMemo(() => items.filter((document) => isIndexed(document.status)).length, [items])
  const totalSize = useMemo(() => items.reduce((sum, document) => sum + document.size_bytes, 0), [items])
  const hasChanges = collection ? name.trim() !== collection.name || description.trim() !== (collection.description || '') : false
  const hasRunningBuild = overview?.rag_status === 'BUILDING' || vectorSnapshots.some((snapshot) => snapshot.status === 'BUILDING')
  const latestSnapshot = vectorSnapshots[0] ?? overview?.latest_snapshot ?? null
  const latestBuildFailed = latestSnapshot?.status === 'FAILED'
  const vectorStatusDetail = latestBuildFailed
    ? latestSnapshot?.error_message || 'The latest vector build failed.'
    : overview?.warnings?.[0] || 'Build an immutable vector snapshot from the current documents.'
  const buildButtonLabel = latestBuildFailed
    ? 'Retry build'
    : overview?.rag_status === 'OUTDATED'
      ? 'Rebuild vectors'
      : 'Build vectors'

  const refreshAll = () => {
    void refetch()
    void refetchOverview()
    void refetchSnapshots()
  }

  const close = () => {
    if (updateCollection.isPending || deleteDocument.isPending) return
    setUploadModalOpen(false)
    onClose()
  }

  const save = async () => {
    if (!collection) return
    const nextName = name.trim()
    if (!nextName) {
      toast.error('Collection name is required')
      return
    }
    try {
      await updateCollection.mutateAsync({ id: collection.id, data: { name: nextName, description: description.trim() || null } })
      toast.success('Collection updated')
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to update collection')
    }
  }

  const confirmDelete = async () => {
    if (!documentToDelete) return
    try {
      await deleteDocument.mutateAsync(documentToDelete.id)
      toast.success('Document deleted')
      setDocumentToDelete(null)
      refreshAll()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to delete document')
    }
  }

  const handleUploaded = () => {
    setUploadModalOpen(false)
    refreshAll()
  }

  const overviewTab = (
    <div className="space-y-4 pb-1">
      <section className="rounded-container border border-border bg-surface/[0.78] p-4">
        <PanelHeader title="Collection information" description="Edit the collection identity used across Knowledge." />
        <div className="mt-4 space-y-3">
          <div>
            <FieldLabel>Name</FieldLabel>
            <Input value={name} onChange={(event) => setName(event.target.value)} />
          </div>
          <div>
            <FieldLabel>Description</FieldLabel>
            <Textarea value={description} onChange={(event) => setDescription(event.target.value)} className="min-h-[104px]" />
          </div>
        </div>
      </section>

      <section className="rounded-container border border-border bg-surface/[0.78] p-4">
        <PanelHeader
          title="Documents"
          description={`${items.length} files · ${indexedCount} ready · ${formatBytes(totalSize)} total`}
          action={(
            <div className="flex gap-2">
              <Button type="button" variant="outline" size="sm" onClick={refreshAll} disabled={isLoading}><RefreshCw className="h-3.5 w-3.5" />Refresh</Button>
              <Button type="button" size="sm" onClick={() => setUploadModalOpen(true)}><Upload className="h-3.5 w-3.5" />Upload</Button>
            </div>
          )}
        />

        <div className="mt-4 min-h-[190px]">
          {isLoading ? (
            <div className="flex min-h-[190px] items-center justify-center rounded-container border border-border/70 bg-background/30"><LoadingState message="Loading documents..." variant="inline" /></div>
          ) : items.length === 0 ? (
            <div className="flex min-h-[190px] flex-col items-center justify-center rounded-container border border-dashed border-border/80 bg-background/25 p-5 text-center">
              <FileText className="h-4 w-4 text-muted-foreground" />
              <p className="mt-3 font-mono text-[9px] font-semibold text-slate-100">No documents in this collection</p>
              <p className="mt-1.5 max-w-sm font-sans text-[10px] leading-4 text-muted-foreground">Upload source material before building vectors.</p>
              <Button type="button" size="sm" onClick={() => setUploadModalOpen(true)} className="mt-4"><Upload className="h-3.5 w-3.5" />Upload document</Button>
            </div>
          ) : (
            <div className="divide-y divide-border/60 rounded-container border border-border/70 bg-background/20">
              {items.map((document) => (
                <div key={document.id} className="grid gap-3 px-3 py-2.5 lg:grid-cols-[minmax(0,1fr)_auto] lg:items-center">
                  <div className="flex min-w-0 items-center gap-2.5">
                    <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-control border border-border bg-control text-primary-light"><FileText className="h-3.5 w-3.5" /></div>
                    <div className="min-w-0">
                      <div className="flex flex-wrap items-center gap-2"><p className="truncate font-mono text-[9px] font-semibold text-slate-100">{document.title}</p>{document.status ? <StatusBadge status={document.status} size="compact" /> : null}</div>
                      <p className="mt-1 truncate font-sans text-[9px] text-muted-foreground">{documentMeta(document)}</p>
                      <div className="mt-1.5 flex flex-wrap gap-x-3 gap-y-1 font-mono text-[8px] text-muted-foreground"><span>Chunks {document.chunk_count ?? 0}</span><span>Pages {document.page_count ?? '-'}</span><span>Created {document.created_at ? formatDate(document.created_at) : '-'}</span></div>
                    </div>
                  </div>
                  <Button type="button" variant="ghost" size="icon" className="h-7 w-7 justify-self-end text-red-300 hover:text-red-200" disabled={deleteDocument.isPending} onClick={() => setDocumentToDelete(document)} aria-label={`Delete ${document.title}`}><Trash2 className="h-3.5 w-3.5" /></Button>
                </div>
              ))}
            </div>
          )}
        </div>
      </section>
    </div>
  )

  const vectorsTab = (
    <div className="space-y-4 pb-1">
      <section className="rounded-container border border-border bg-surface/[0.78] p-4">
        <PanelHeader
          title="Vector readiness"
          description={vectorStatusDetail}
          action={(
            <div className="flex items-center gap-2">
              <StatusBadge status={overview?.rag_status || 'UNKNOWN'} size="compact" />
              <Button type="button" size="sm" onClick={() => setBuildModalOpen(true)} disabled={items.length === 0 || hasRunningBuild}><Cpu className="h-3.5 w-3.5" />{buildButtonLabel}</Button>
            </div>
          )}
        />
        <div className="mt-4 grid gap-2.5 sm:grid-cols-3">
          <TechItem label="Latest snapshot" value={overview?.latest_ready_snapshot?.version || 'Not built'} detail={`${numberLabel(overview?.latest_ready_snapshot?.chunk_count)} chunks`} />
          <TechItem label="Documents" value={`${overview?.documents.active ?? items.length} active`} detail={`${overview?.documents.ready ?? indexedCount} ready`} />
          <TechItem label="Embedding" value={overview?.technology.embedding_model || 'Not selected'} />
        </div>
        {overview?.processing.has_running_job ? <div className="mt-3 border-l-2 border-l-primary bg-primary/[0.05] px-3 py-2 font-mono text-[8px] text-primary-light">Building vectors · {overview.processing.stage || 'QUEUED'} · {overview.processing.embedded_chunks}/{overview.processing.total_chunks || 0} chunks</div> : null}
        {latestBuildFailed ? (
          <div className="mt-3 flex gap-2.5 border border-red-500/20 bg-background/30 p-3 text-red-200">
            <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
            <div className="min-w-0">
              <p className="font-mono text-[9px] font-semibold">Vector build failed</p>
              <p className="mt-1 break-words font-sans text-[9px] leading-4 text-red-200/80">{latestSnapshot?.error_message || 'The latest vector build failed.'}</p>
              {latestSnapshot ? <p className="mt-1.5 font-mono text-[8px] text-red-200/60">{latestSnapshot.embedding_provider} · {latestSnapshot.embedding_model} · {latestSnapshot.build_stage || 'FAILED'}</p> : null}
            </div>
          </div>
        ) : null}
      </section>

      <section className="rounded-container border border-border bg-surface/[0.78] p-4">
        <PanelHeader title="Vector snapshots" description={onUseSnapshot ? 'Choose a READY version to use in the Agent Draft.' : 'Immutable builds generated from this Collection.'} />
        {vectorSnapshots.length === 0 ? (
          <div className="mt-4 flex min-h-[190px] items-center justify-center rounded-container border border-dashed border-border/80 bg-background/25 p-5 text-center font-sans text-[10px] text-muted-foreground">No vector snapshot built yet.</div>
        ) : (
          <div className="mt-4 divide-y divide-border/60 rounded-container border border-border/70 bg-background/20">
            {vectorSnapshots.map((snapshot) => (
              <div key={snapshot.id} className="grid gap-3 px-3 py-2.5 transition-colors hover:bg-control/20 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-center">
                <button type="button" onClick={() => setSnapshotToView(snapshot)} className="min-w-0 text-left">
                  <div className="flex flex-wrap items-center gap-2"><p className="font-mono text-[9px] font-semibold text-slate-100">{snapshot.version}</p><StatusBadge status={snapshot.status} size="compact" /></div>
                  <p className="mt-1 font-sans text-[9px] text-muted-foreground">{snapshot.embedding_model} · {numberLabel(snapshot.chunk_count)} chunks · {numberLabel(snapshot.vector_count ?? snapshot.chunk_count)} vectors</p>
                  {snapshot.status === 'FAILED' && snapshot.error_message ? <p className="mt-1 line-clamp-2 font-sans text-[9px] leading-4 text-red-300">{snapshot.error_message}</p> : null}
                </button>
                <div className="flex flex-wrap items-center justify-between gap-2 sm:justify-end">
                  <p className="font-mono text-[8px] text-muted-foreground">{snapshot.completed_at ? formatDate(snapshot.completed_at) : snapshot.build_stage || 'Queued'}</p>
                  {onUseSnapshot && snapshot.status === 'READY' ? <Button type="button" size="sm" onClick={() => void onUseSnapshot(snapshot)}>Use this version</Button> : null}
                </div>
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  )

  const technologyTab = (
    <section className="min-h-[340px] rounded-container border border-border bg-surface/[0.78] p-4">
      <PanelHeader title="Technology" description="Configuration captured by the latest vector snapshot." />
      <div className="mt-4 grid gap-2.5 sm:grid-cols-2">
        <TechItem label="Embedding" value={overview?.technology.embedding_model || 'Not selected'} detail={overview?.technology.embedding_provider || 'Managed in Knowledge > Embedding'} />
        <TechItem label="Chunking" value={overview?.technology.chunking_strategy || 'Not configured'} detail={overview?.technology.chunk_size ? `${overview.technology.chunk_size} size · ${overview.technology.chunk_overlap ?? 0} overlap` : undefined} />
        <TechItem label="Vector store" value={overview?.technology.vector_store || 'pgvector'} detail={overview?.technology.distance_metric || 'cosine'} />
      </div>
    </section>
  )

  return (
    <>
      <Dialog
        open={open && Boolean(collection)}
        onClose={close}
        title="Collection details"
        className="flex h-[min(760px,calc(100svh-2rem))] max-w-5xl flex-col overflow-hidden"
        contentClassName="min-h-0 flex-1 p-0"
      >
        {collection ? (
          <div className="flex h-full min-h-0 flex-col">
            <div className="grid min-h-0 flex-1 grid-rows-[auto_minmax(0,1fr)] lg:grid-cols-[250px_minmax(0,1fr)] lg:grid-rows-1">
              <aside className="border-b border-border bg-background/30 p-4 lg:border-b-0 lg:border-r">
                <div className="rounded-container border border-border bg-background/35 p-4">
                  <div className="flex h-9 w-9 items-center justify-center rounded-control border border-border bg-control text-primary-light"><Database className="h-4 w-4" /></div>
                  <div className="mt-3 flex items-start justify-between gap-3"><h3 className="min-w-0 flex-1 truncate font-mono text-[10px] font-bold text-slate-50">{collection.name}</h3>{collection.status ? <StatusBadge status={collection.status} size="compact" /> : null}</div>
                  <p className="mt-1.5 line-clamp-4 font-sans text-[10px] leading-4 text-muted-foreground">{collection.description || 'No description provided'}</p>
                  <div className="mt-3 flex flex-wrap gap-1.5 font-mono text-[8px]">
                    <span className="rounded-technical border border-primary/30 bg-primary/[0.08] px-2 py-1 text-primary-light">{items.length} documents</span>
                    <span className="rounded-technical border border-border bg-control/45 px-2 py-1 text-muted-foreground">{indexedCount} ready</span>
                    <span className="rounded-technical border border-border bg-control/45 px-2 py-1 text-muted-foreground">{formatBytes(totalSize)}</span>
                  </div>
                </div>
              </aside>

              <main className="min-h-0 min-w-0 p-4 lg:p-5">
                <Tabs
                  defaultTab="overview"
                  className="flex h-full min-h-0 flex-col"
                  contentClassName="scrollbar-thin min-h-0 flex-1 overflow-y-auto overscroll-contain pr-1"
                  tabs={[
                    { id: 'overview', label: 'Overview', content: overviewTab },
                    { id: 'vectors', label: 'Vectors', content: vectorsTab },
                    { id: 'technology', label: 'Technology', content: technologyTab },
                  ]}
                />
              </main>
            </div>

            <div className="flex min-h-[58px] shrink-0 flex-col-reverse gap-2 border-t border-border bg-surface/[0.98] px-4 py-3 sm:flex-row sm:items-center sm:justify-between lg:px-5">
              <p className="hidden font-mono text-[8px] text-muted-foreground sm:block">{hasChanges ? 'Unsaved collection changes' : `${items.length} documents · ${indexedCount} ready · ${formatBytes(totalSize)}`}</p>
              <div className="ml-auto flex gap-2">
                <Button type="button" variant="outline" onClick={close} disabled={updateCollection.isPending || deleteDocument.isPending}>Close</Button>
                <Button type="button" onClick={save} loading={updateCollection.isPending} disabled={!hasChanges}>Save changes</Button>
              </div>
            </div>
          </div>
        ) : null}
      </Dialog>

      <CollectionDocumentUploadModal open={uploadModalOpen} projectId={projectId} collection={collection ? { id: collection.id, name: collection.name } : null} onClose={() => setUploadModalOpen(false)} onUploaded={handleUploaded} />
      <BuildVectorSnapshotModalV2 open={buildModalOpen} projectId={projectId} collection={collection ? { id: collection.id, name: collection.name } : null} onClose={() => setBuildModalOpen(false)} onCreated={() => { setBuildModalOpen(false); refreshAll() }} />
      <VectorSnapshotDetailsModal snapshot={snapshotToView} onClose={() => setSnapshotToView(null)} />

      <Dialog open={Boolean(documentToDelete)} onClose={() => !deleteDocument.isPending && setDocumentToDelete(null)} title="Delete document" className="max-w-[460px]">
        {documentToDelete ? (
          <div className="space-y-4">
            <div className="flex gap-3">
              <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-control border border-red-500/25 bg-red-500/[0.07] text-red-300"><AlertTriangle className="h-3.5 w-3.5" /></div>
              <div>
                <p className="font-mono text-[9px] font-semibold text-slate-100">Remove this document?</p>
                <p className="mt-1 font-sans text-[10px] leading-4 text-muted-foreground">This action deletes the document record, stored file and generated chunks. It cannot be undone.</p>
              </div>
            </div>
            <div className="rounded-container border border-border bg-background/35 p-3"><p className="truncate font-mono text-[9px] font-semibold text-slate-100">{documentToDelete.title}</p><p className="mt-1 truncate font-sans text-[9px] text-muted-foreground">{documentMeta(documentToDelete)}</p></div>
            <div className="flex flex-col-reverse gap-2 border-t border-border pt-3 sm:flex-row sm:justify-end"><Button type="button" variant="outline" onClick={() => setDocumentToDelete(null)} disabled={deleteDocument.isPending}>Cancel</Button><Button type="button" variant="destructive" loading={deleteDocument.isPending} onClick={confirmDelete}>Delete document</Button></div>
          </div>
        ) : null}
      </Dialog>
    </>
  )
}
