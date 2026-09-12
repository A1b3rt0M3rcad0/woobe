import { useEffect, useMemo, useRef, useState, type FormEvent } from 'react'
import {
  AlertTriangle,
  ArrowLeft,
  Cpu,
  Database,
  FileText,
  Plus,
  RefreshCw,
  Search,
  Trash2,
  Upload,
  X,
} from 'lucide-react'
import { EmptyStatePanel, MetricTile, SectionBlock, TechnicalListItem } from '@woobe/ui'
import { toast } from 'sonner'
import { LoadingState } from '@/components/common/LoadingState'
import { StatusBadge } from '@/components/common/StatusBadge'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { Textarea } from '@/components/ui/Textarea'
import { BuildVectorSnapshotModalV2 } from '@/features/knowledge/components/BuildVectorSnapshotModalV2'
import { CollectionDocumentUploadPanel } from '@/features/knowledge/components/CollectionDocumentUploadPanel'
import {
  useCollections,
  useCreateCollection,
  useDeleteDocument,
  useDocumentsByCollection,
  useUpdateCollection,
} from '@/features/knowledge/hooks'
import { useCollectionOverview, useVectorSnapshots } from '@/features/knowledge/vectorHooks'
import { formatBytes } from '@/lib/formatters/bytes'
import { formatDate } from '@/lib/formatters/date'
import { cn } from '@/lib/utils'
import type { Collection, Document, VectorSnapshot } from '@/features/knowledge/types'

type ManagerScreen = 'collections' | 'create' | 'collection' | 'upload'
type CollectionTab = 'overview' | 'vectors' | 'technology'

interface ActiveKnowledgeBinding {
  collectionId: string | null
  collectionName: string
  knowledgeVersion: string
  vectorVersion: string
}

interface ManageKnowledgeModalProps {
  open: boolean
  projectId: string
  activeBinding: ActiveKnowledgeBinding | null
  currentSnapshotId?: string | null
  onClose: () => void
  onUseSnapshot: (snapshot: VectorSnapshot) => boolean | Promise<boolean>
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

function TabButton({ active, label, onClick }: { active: boolean; label: string; onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        'h-[27px] rounded-technical border px-2.5 font-mono text-[8px] transition-colors',
        active
          ? 'border-primary/35 bg-primary/[0.10] text-primary-light'
          : 'border-transparent text-muted-foreground hover:border-border hover:bg-control/35 hover:text-slate-50',
      )}
    >
      {label}
    </button>
  )
}

export function ManageKnowledgeModal({
  open,
  projectId,
  activeBinding,
  currentSnapshotId,
  onClose,
  onUseSnapshot,
}: ManageKnowledgeModalProps) {
  const overlayRef = useRef<HTMLDivElement>(null)
  const { data: collections = [], isLoading: collectionsLoading, refetch: refetchCollections } = useCollections(projectId)
  const createCollection = useCreateCollection()
  const updateCollection = useUpdateCollection()
  const deleteDocument = useDeleteDocument()

  const [screen, setScreen] = useState<ManagerScreen>('collections')
  const [collectionTab, setCollectionTab] = useState<CollectionTab>('overview')
  const [query, setQuery] = useState('')
  const [selectedCollectionId, setSelectedCollectionId] = useState<string | null>(null)
  const [collectionFallback, setCollectionFallback] = useState<Collection | null>(null)
  const [createName, setCreateName] = useState('')
  const [createDescription, setCreateDescription] = useState('')
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [documentToDelete, setDocumentToDelete] = useState<Document | null>(null)
  const [buildModalOpen, setBuildModalOpen] = useState(false)
  const [applyingSnapshotId, setApplyingSnapshotId] = useState<string | null>(null)
  const [usedSnapshotId, setUsedSnapshotId] = useState<string | null>(currentSnapshotId || null)

  const selectedCollection = useMemo(() => {
    if (!selectedCollectionId) return null
    return collections.find((collection) => collection.id === selectedCollectionId)
      || (collectionFallback?.id === selectedCollectionId ? collectionFallback : null)
  }, [collections, collectionFallback, selectedCollectionId])

  const { data: documents, isLoading: documentsLoading, refetch: refetchDocuments } = useDocumentsByCollection(selectedCollection?.id)
  const { data: overview, refetch: refetchOverview } = useCollectionOverview(selectedCollection?.id, projectId)
  const { data: snapshots, refetch: refetchSnapshots } = useVectorSnapshots(selectedCollection?.id, projectId)

  const items = documents ?? []
  const vectorSnapshots = snapshots ?? []
  const indexedCount = useMemo(() => items.filter((document) => isIndexed(document.status)).length, [items])
  const totalSize = useMemo(() => items.reduce((sum, document) => sum + document.size_bytes, 0), [items])
  const hasChanges = selectedCollection
    ? name.trim() !== selectedCollection.name || description.trim() !== (selectedCollection.description || '')
    : false
  const hasRunningBuild = overview?.rag_status === 'BUILDING' || vectorSnapshots.some((snapshot) => snapshot.status === 'BUILDING')
  const normalizedQuery = query.trim().toLowerCase()
  const visibleCollections = useMemo(() => {
    if (!normalizedQuery) return collections
    return collections.filter((collection) => `${collection.name} ${collection.description || ''}`.toLowerCase().includes(normalizedQuery))
  }, [collections, normalizedQuery])

  useEffect(() => {
    if (!open) return
    setScreen('collections')
    setCollectionTab('overview')
    setQuery('')
    setSelectedCollectionId(null)
    setCollectionFallback(null)
    setCreateName('')
    setCreateDescription('')
    setDocumentToDelete(null)
    setBuildModalOpen(false)
  }, [open])

  useEffect(() => setUsedSnapshotId(currentSnapshotId || null), [currentSnapshotId])

  useEffect(() => {
    if (!selectedCollection) return
    setName(selectedCollection.name)
    setDescription(selectedCollection.description || '')
    setDocumentToDelete(null)
  }, [selectedCollection?.id])

  useEffect(() => {
    if (!open || buildModalOpen) return
    const handleEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape' && !createCollection.isPending && !updateCollection.isPending && !deleteDocument.isPending) onClose()
    }
    document.addEventListener('keydown', handleEscape)
    document.body.style.overflow = 'hidden'
    return () => {
      document.removeEventListener('keydown', handleEscape)
      document.body.style.overflow = ''
    }
  }, [open, buildModalOpen, createCollection.isPending, updateCollection.isPending, deleteDocument.isPending, onClose])

  const refreshAll = () => {
    void refetchCollections()
    void refetchDocuments()
    void refetchOverview()
    void refetchSnapshots()
  }

  const openCollection = (collection: Collection, tab: CollectionTab = 'overview') => {
    setCollectionFallback(collection)
    setSelectedCollectionId(collection.id)
    setCollectionTab(tab)
    setDocumentToDelete(null)
    setScreen('collection')
  }

  const backToCollections = () => {
    setScreen('collections')
    setSelectedCollectionId(null)
    setCollectionFallback(null)
    setDocumentToDelete(null)
    void refetchCollections()
  }

  const handleCreate = async (event: FormEvent) => {
    event.preventDefault()
    const nextName = createName.trim()
    if (!nextName) return void toast.error('Collection name is required')
    try {
      const collection = await createCollection.mutateAsync({ project_id: projectId, name: nextName, description: createDescription.trim() || undefined })
      toast.success('Collection created')
      setCreateName('')
      setCreateDescription('')
      openCollection(collection)
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Failed to create collection')
    }
  }

  const handleSaveCollection = async () => {
    if (!selectedCollection) return
    const nextName = name.trim()
    if (!nextName) return void toast.error('Collection name is required')
    try {
      const updated = await updateCollection.mutateAsync({ id: selectedCollection.id, data: { name: nextName, description: description.trim() || null } })
      setCollectionFallback(updated)
      toast.success('Collection updated')
      void refetchCollections()
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Failed to update collection')
    }
  }

  const handleDeleteDocument = async () => {
    if (!documentToDelete) return
    try {
      await deleteDocument.mutateAsync(documentToDelete.id)
      toast.success('Document deleted')
      setDocumentToDelete(null)
      refreshAll()
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Failed to delete document')
    }
  }

  const handleUseSnapshot = async (snapshot: VectorSnapshot) => {
    setApplyingSnapshotId(snapshot.id)
    try {
      const applied = await onUseSnapshot(snapshot)
      if (applied !== false) setUsedSnapshotId(snapshot.id)
    } finally {
      setApplyingSnapshotId(null)
    }
  }

  const handleUploaded = () => {
    setScreen('collection')
    setCollectionTab('overview')
    refreshAll()
  }

  const handleBuildCreated = () => {
    setBuildModalOpen(false)
    setScreen('collection')
    setCollectionTab('vectors')
    refreshAll()
  }

  if (!open) return null

  const collectionOverview = selectedCollection ? (
    <div className="space-y-3">
      <SectionBlock title="Collection information" description="Identity used across Knowledge." density="compact">
        <div className="grid gap-3 lg:grid-cols-[minmax(0,0.8fr)_minmax(0,1.2fr)]">
          <div><label className="mb-1 block font-mono text-[8px] uppercase tracking-[0.08em] text-muted-foreground">Name</label><Input value={name} onChange={(event) => setName(event.target.value)} /></div>
          <div><label className="mb-1 block font-mono text-[8px] uppercase tracking-[0.08em] text-muted-foreground">Description</label><Textarea value={description} onChange={(event) => setDescription(event.target.value)} className="min-h-[72px]" /></div>
        </div>
      </SectionBlock>

      <SectionBlock
        title="Documents"
        description={`${items.length} files · ${indexedCount} ready · ${formatBytes(totalSize)} total`}
        density="compact"
        actions={<div className="flex gap-1.5"><Button type="button" variant="outline" size="sm" onClick={refreshAll} disabled={documentsLoading}><RefreshCw className="h-3 w-3" />Refresh</Button><Button type="button" size="sm" onClick={() => setScreen('upload')}><Upload className="h-3 w-3" />Upload</Button></div>}
      >
        {documentToDelete ? (
          <div className="mb-2 flex items-center gap-3 rounded-container border border-red-500/20 bg-background/30 px-3 py-2">
            <AlertTriangle className="h-3.5 w-3.5 shrink-0 text-red-300" />
            <div className="min-w-0 flex-1"><p className="truncate font-mono text-[9px] text-slate-100">Delete {documentToDelete.title}?</p><p className="font-sans text-[8px] text-muted-foreground">Stored file and generated chunks will be removed.</p></div>
            <Button type="button" size="sm" variant="outline" onClick={() => setDocumentToDelete(null)} disabled={deleteDocument.isPending}>Cancel</Button>
            <Button type="button" size="sm" variant="destructive" onClick={handleDeleteDocument} loading={deleteDocument.isPending}>Delete</Button>
          </div>
        ) : null}

        {documentsLoading ? <LoadingState message="Loading documents..." variant="inline" /> : items.length === 0 ? (
          <EmptyStatePanel compact icon={<FileText className="h-4 w-4" />} title="No documents in this Collection" description="Upload source material before building vectors." action={<Button type="button" size="sm" onClick={() => setScreen('upload')}><Upload className="h-3 w-3" />Upload document</Button>} />
        ) : (
          <div className="space-y-1.5">
            {items.map((document) => <TechnicalListItem key={document.id} label={document.title} description={documentMeta(document)} leading={<FileText className="h-3.5 w-3.5 text-primary-light" />} meta={<><span>{document.chunk_count ?? 0} chunks</span><span>{document.page_count ?? '-'} pages</span><span>{document.created_at ? formatDate(document.created_at) : '-'}</span></>} trailing={<div className="flex items-center gap-2">{document.status ? <StatusBadge status={document.status} /> : null}<Button type="button" variant="ghost" size="icon" className="h-7 w-7 text-muted-foreground hover:text-red-300" onClick={(event) => { event.stopPropagation(); setDocumentToDelete(document) }} aria-label={`Delete ${document.title}`}><Trash2 className="h-3.5 w-3.5" /></Button></div>} onClick={() => {}} />)}
          </div>
        )}
      </SectionBlock>
    </div>
  ) : null

  const collectionVectors = (
    <div className="space-y-3">
      <SectionBlock
        title="Vector readiness"
        description={overview?.warnings?.[0] || 'Build an immutable vector snapshot from the current documents.'}
        density="compact"
        actions={<div className="flex items-center gap-2"><StatusBadge status={overview?.rag_status || 'UNKNOWN'} /><Button type="button" size="sm" onClick={() => setBuildModalOpen(true)} disabled={items.length === 0 || hasRunningBuild}><Cpu className="h-3 w-3" />{overview?.rag_status === 'OUTDATED' ? 'Rebuild vectors' : 'Build vectors'}</Button></div>}
      >
        <div className="grid grid-cols-3 gap-1.5">
          <MetricTile label="Latest snapshot" value={overview?.latest_ready_snapshot?.version || 'Not built'} detail={`${numberLabel(overview?.latest_ready_snapshot?.chunk_count)} chunks`} />
          <MetricTile label="Documents" value={`${overview?.documents.active ?? items.length} active`} detail={`${overview?.documents.ready ?? indexedCount} ready`} />
          <MetricTile label="Embedding" value={overview?.technology.embedding_model || 'Not selected'} />
        </div>
        {overview?.processing.has_running_job ? <div className="mt-2 rounded-container border border-primary/25 bg-primary/[0.06] px-3 py-2 font-mono text-[8px] text-primary-light">Building vectors · {overview.processing.stage || 'QUEUED'} · {overview.processing.embedded_chunks}/{overview.processing.total_chunks || 0} chunks</div> : null}
      </SectionBlock>

      <SectionBlock title="Vector versions" description="Immutable builds generated from this Collection." density="compact" actions={<span className="font-mono text-[8px] text-muted-foreground">{vectorSnapshots.length} versions</span>}>
        {vectorSnapshots.length === 0 ? <EmptyStatePanel compact title="No vector snapshot built yet" /> : <div className="space-y-1.5">{vectorSnapshots.map((snapshot) => {
          const inUse = snapshot.id === usedSnapshotId
          return <TechnicalListItem key={snapshot.id} selected={inUse} label={snapshot.version} description={`${snapshot.embedding_model} · ${numberLabel(snapshot.chunk_count)} chunks · ${numberLabel(snapshot.vector_count ?? snapshot.chunk_count)} vectors`} meta={<span>{snapshot.completed_at ? `Built ${formatDate(snapshot.completed_at)}` : snapshot.build_stage || 'Queued'}</span>} leading={<Database className="h-3.5 w-3.5 text-primary-light" />} trailing={<div className="flex items-center gap-2"><StatusBadge status={snapshot.status} />{inUse ? <span className="font-mono text-[8px] text-primary-light">In use</span> : snapshot.status === 'READY' ? <Button type="button" size="sm" variant="outline" onClick={(event) => { event.stopPropagation(); void handleUseSnapshot(snapshot) }} loading={applyingSnapshotId === snapshot.id} disabled={Boolean(applyingSnapshotId)}>Use</Button> : null}</div>} onClick={() => {}} />
        })}</div>}
      </SectionBlock>
    </div>
  )

  const collectionTechnology = (
    <SectionBlock title="Technology" description="Configuration captured by the latest vector snapshot." density="compact">
      <div className="grid gap-1.5 sm:grid-cols-2 lg:grid-cols-3">
        <MetricTile label="Embedding" value={overview?.technology.embedding_model || 'Not selected'} detail={overview?.technology.embedding_provider || 'No provider selected'} />
        <MetricTile label="Chunking" value={overview?.technology.chunking_strategy || 'Not configured'} detail={overview?.technology.chunk_size ? `${overview.technology.chunk_size} size · ${overview.technology.chunk_overlap ?? 0} overlap` : undefined} />
        <MetricTile label="Vector store" value={overview?.technology.vector_store || 'pgvector'} detail={overview?.technology.distance_metric || 'cosine'} />
      </div>
    </SectionBlock>
  )

  const contextPanel = (
    <aside className="border-r border-border bg-background/20 p-3">
      <SectionBlock density="compact" eyebrow="Knowledge" title={selectedCollection?.name || 'Project knowledge'} description={selectedCollection?.description || 'Collections, documents and immutable vector versions.'} className="bg-background/20">
        <div className="grid grid-cols-3 gap-1.5">
          <MetricTile label="Collections" value={String(collections.length)} />
          <MetricTile label="Documents" value={String(selectedCollection ? items.length : collections.reduce((sum, item) => sum + (item.documents_count ?? 0), 0))} />
          <MetricTile label="Ready" value={String(selectedCollection ? indexedCount : '—')} />
        </div>
      </SectionBlock>
      <div className="mt-3 border-t border-border pt-3">
        <p className="font-mono text-[8px] uppercase tracking-[0.08em] text-muted-foreground">Current Agent binding</p>
        {activeBinding ? <div className="mt-2 space-y-1"><p className="truncate font-mono text-[9px] text-slate-100">{activeBinding.collectionName}</p><p className="font-mono text-[8px] text-muted-foreground">Knowledge {activeBinding.knowledgeVersion}</p><p className="font-mono text-[8px] text-muted-foreground">Vector {activeBinding.vectorVersion}</p></div> : <p className="mt-2 font-sans text-[9px] leading-4 text-muted-foreground">No vector version is bound to this Agent Draft.</p>}
      </div>
    </aside>
  )

  return (
    <>
      {!buildModalOpen ? (
        <div ref={overlayRef} className="fixed inset-0 z-50 flex items-center justify-center bg-background/78 p-4 backdrop-blur-[2px]" onClick={(event) => { if (event.target === overlayRef.current) onClose() }}>
          <div role="dialog" aria-modal="true" aria-label="Manage Knowledge" className="flex max-h-[min(760px,calc(100svh-2rem))] w-full max-w-[1040px] flex-col overflow-hidden rounded-container border border-border bg-surface">
            <div className="flex min-h-[48px] shrink-0 items-center justify-between border-b border-border px-4">
              <div><h2 className="font-mono text-[10px] font-semibold text-slate-50">Manage Knowledge</h2><p className="mt-0.5 font-sans text-[9px] text-muted-foreground">Collections, documents and immutable vector versions.</p></div>
              <button type="button" onClick={onClose} className="flex h-7 w-7 items-center justify-center rounded-control border border-transparent text-muted-foreground hover:border-border hover:bg-control hover:text-slate-50" aria-label="Close Manage Knowledge"><X className="h-3.5 w-3.5" /></button>
            </div>

            <div className="grid min-h-0 flex-1 grid-cols-[220px_minmax(0,1fr)] overflow-hidden">
              {contextPanel}
              <section className="flex min-h-0 flex-col">
                {screen === 'collections' ? (
                  <>
                    <div className="flex items-center justify-between gap-3 border-b border-border px-4 py-3"><div><p className="font-mono text-[8px] uppercase tracking-[0.08em] text-primary-light">Collections</p><h3 className="mt-0.5 font-mono text-[10px] font-semibold text-slate-50">Knowledge sources</h3></div><Button type="button" size="sm" onClick={() => setScreen('create')}><Plus className="h-3 w-3" />New collection</Button></div>
                    <div className="min-h-0 flex-1 overflow-y-auto p-4">
                      <div className="relative"><Search className="pointer-events-none absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" /><Input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search collections..." className="pl-8" /></div>
                      {collectionsLoading ? <div className="mt-3"><LoadingState variant="panel" layout="list" message="Loading collections..." /></div> : visibleCollections.length === 0 ? <div className="mt-3"><EmptyStatePanel compact icon={<Database className="h-4 w-4" />} title={normalizedQuery ? 'No Collections found' : 'No Collections yet'} description={normalizedQuery ? 'Adjust the search term.' : 'Create the first Collection for this Project.'} action={!normalizedQuery ? <Button type="button" size="sm" onClick={() => setScreen('create')}><Plus className="h-3 w-3" />New collection</Button> : undefined} /></div> : <div className="mt-3 grid gap-1.5 sm:grid-cols-2">{visibleCollections.map((collection) => <TechnicalListItem key={collection.id} label={collection.name} description={collection.description || 'No description provided'} leading={<Database className="h-3.5 w-3.5 text-primary-light" />} meta={<span>{collection.documents_count ?? 0} documents</span>} trailing={collection.status ? <StatusBadge status={collection.status} /> : undefined} onClick={() => openCollection(collection)} />)}</div>}
                    </div>
                  </>
                ) : screen === 'create' ? (
                  <form onSubmit={handleCreate} className="flex min-h-0 flex-1 flex-col">
                    <div className="min-h-0 flex-1 overflow-y-auto p-4"><Button type="button" size="sm" variant="ghost" className="mb-3" onClick={backToCollections}><ArrowLeft className="h-3 w-3" />Collections</Button><SectionBlock title="Create a knowledge source" description="Create the Collection, then add documents and build an immutable vector version." density="compact"><div className="grid gap-3 lg:grid-cols-[minmax(0,0.8fr)_minmax(0,1.2fr)]"><div><label className="mb-1 block font-mono text-[8px] uppercase tracking-[0.08em] text-muted-foreground">Name</label><Input value={createName} onChange={(event) => setCreateName(event.target.value)} placeholder="Customer Support" autoFocus /></div><div><label className="mb-1 block font-mono text-[8px] uppercase tracking-[0.08em] text-muted-foreground">Description</label><Textarea value={createDescription} onChange={(event) => setCreateDescription(event.target.value)} placeholder="Product documentation and support policies" className="min-h-[96px]" /></div></div></SectionBlock></div>
                    <div className="flex min-h-[52px] shrink-0 justify-end gap-2 border-t border-border px-4 py-2.5"><Button type="button" variant="outline" onClick={backToCollections} disabled={createCollection.isPending}>Cancel</Button><Button type="submit" loading={createCollection.isPending}>Create collection</Button></div>
                  </form>
                ) : screen === 'upload' && selectedCollection ? (
                  <div className="flex min-h-0 flex-1 flex-col"><div className="border-b border-border px-4 py-3"><Button type="button" size="sm" variant="ghost" className="mb-2" onClick={() => setScreen('collection')}><ArrowLeft className="h-3 w-3" />Back to collection</Button><p className="font-mono text-[10px] font-semibold text-slate-50">Add source material</p><p className="mt-0.5 font-sans text-[9px] text-muted-foreground">Upload directly to {selectedCollection.name}. TXT, MD and PDF are supported.</p></div><div className="min-h-0 flex-1 overflow-y-auto p-4"><CollectionDocumentUploadPanel projectId={projectId} collection={{ id: selectedCollection.id, name: selectedCollection.name }} onCancel={() => setScreen('collection')} onUploaded={handleUploaded} showDestination={false} /></div></div>
                ) : selectedCollection ? (
                  <div className="flex min-h-0 flex-1 flex-col">
                    <div className="flex items-center gap-1 border-b border-border p-1.5"><Button type="button" size="sm" variant="ghost" onClick={backToCollections}><ArrowLeft className="h-3 w-3" />Collections</Button><div className="ml-auto flex gap-1"><TabButton active={collectionTab === 'overview'} label="Overview" onClick={() => setCollectionTab('overview')} /><TabButton active={collectionTab === 'vectors'} label="Vectors" onClick={() => setCollectionTab('vectors')} /><TabButton active={collectionTab === 'technology'} label="Technology" onClick={() => setCollectionTab('technology')} /></div></div>
                    <div className="min-h-0 flex-1 overflow-y-auto p-4">{collectionTab === 'overview' ? collectionOverview : collectionTab === 'vectors' ? collectionVectors : collectionTechnology}</div>
                    {collectionTab === 'overview' ? <div className="flex min-h-[52px] shrink-0 justify-end gap-2 border-t border-border px-4 py-2.5"><Button type="button" variant="outline" onClick={backToCollections}>Close collection</Button><Button type="button" onClick={handleSaveCollection} loading={updateCollection.isPending} disabled={!hasChanges}>Save changes</Button></div> : null}
                  </div>
                ) : null}
              </section>
            </div>
          </div>
        </div>
      ) : null}

      <BuildVectorSnapshotModalV2 open={buildModalOpen && Boolean(selectedCollection)} projectId={projectId} collection={selectedCollection ? { id: selectedCollection.id, name: selectedCollection.name } : null} onClose={() => setBuildModalOpen(false)} onCreated={handleBuildCreated} />
    </>
  )
}
