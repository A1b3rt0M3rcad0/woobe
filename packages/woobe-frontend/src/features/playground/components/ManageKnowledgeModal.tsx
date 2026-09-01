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

function TechItem({ label, value, detail }: { label: string; value: string; detail?: string }) {
  return (
    <div className="rounded-xl border border-border/80 bg-background/60 p-4">
      <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-muted">{label}</p>
      <p className="mt-1.5 truncate text-sm font-medium text-white">{value}</p>
      {detail ? <p className="mt-1 truncate text-xs text-muted">{detail}</p> : null}
    </div>
  )
}

function TabButton({ active, label, onClick }: { active: boolean; label: string; onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`rounded-lg border px-3 py-2 text-xs font-medium transition-colors ${
        active
          ? 'border-primary/35 bg-primary/10 text-primary-light shadow-sm shadow-primary/5'
          : 'border-transparent text-muted hover:border-border/80 hover:bg-background/60 hover:text-white'
      }`}
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
    return collections.filter((collection) => (
      `${collection.name} ${collection.description || ''}`.toLowerCase().includes(normalizedQuery)
    ))
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

  useEffect(() => {
    setUsedSnapshotId(currentSnapshotId || null)
  }, [currentSnapshotId])

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
    if (!nextName) {
      toast.error('Collection name is required')
      return
    }

    try {
      const collection = await createCollection.mutateAsync({
        project_id: projectId,
        name: nextName,
        description: createDescription.trim() || undefined,
      })
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
    if (!nextName) {
      toast.error('Collection name is required')
      return
    }

    try {
      const updated = await updateCollection.mutateAsync({
        id: selectedCollection.id,
        data: { name: nextName, description: description.trim() || null },
      })
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

  const collectionOverview = (
    <div className="space-y-4">
      <section className="rounded-xl border border-border/80 bg-surface/65 p-4">
        <div>
          <h3 className="text-sm font-semibold text-white">Collection information</h3>
          <p className="mt-1 text-xs text-muted">Edit the identity used across Knowledge.</p>
        </div>
        <div className="mt-4 grid gap-4 lg:grid-cols-[minmax(0,0.85fr)_minmax(0,1.15fr)]">
          <div>
            <label className="mb-1.5 block text-[10px] font-semibold uppercase tracking-[0.16em] text-muted">Name</label>
            <Input value={name} onChange={(event) => setName(event.target.value)} />
          </div>
          <div>
            <label className="mb-1.5 block text-[10px] font-semibold uppercase tracking-[0.16em] text-muted">Description</label>
            <Textarea value={description} onChange={(event) => setDescription(event.target.value)} className="min-h-[84px]" />
          </div>
        </div>
      </section>

      <section className="rounded-xl border border-border/80 bg-surface/65 p-4">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <h3 className="text-sm font-semibold text-white">Documents</h3>
            <p className="mt-1 text-xs text-muted">{items.length} files · {indexedCount} ready · {formatBytes(totalSize)} total</p>
          </div>
          <div className="flex gap-2">
            <Button type="button" variant="outline" size="sm" onClick={refreshAll} disabled={documentsLoading}>
              <RefreshCw className="mr-2 h-3.5 w-3.5" />
              Refresh
            </Button>
            <Button type="button" size="sm" onClick={() => setScreen('upload')}>
              <Upload className="mr-2 h-3.5 w-3.5" />
              Upload
            </Button>
          </div>
        </div>

        {documentToDelete ? (
          <div className="mt-4 flex flex-col gap-3 rounded-xl border border-red-500/25 bg-red-500/5 p-3 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex min-w-0 items-start gap-3">
              <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-red-500/20 bg-red-500/10 text-red-300">
                <AlertTriangle className="h-4 w-4" />
              </div>
              <div className="min-w-0">
                <p className="truncate text-sm font-medium text-white">Delete {documentToDelete.title}?</p>
                <p className="mt-1 text-xs text-muted">Stored file and generated chunks will be removed.</p>
              </div>
            </div>
            <div className="flex shrink-0 gap-2">
              <Button type="button" size="sm" variant="outline" onClick={() => setDocumentToDelete(null)} disabled={deleteDocument.isPending}>Cancel</Button>
              <Button type="button" size="sm" variant="destructive" onClick={handleDeleteDocument} loading={deleteDocument.isPending}>Delete</Button>
            </div>
          </div>
        ) : null}

        <div className="mt-4">
          {documentsLoading ? (
            <div className="rounded-xl border border-border/70 bg-background/60 p-8"><LoadingState message="Loading documents..." variant="inline" /></div>
          ) : items.length === 0 ? (
            <div className="flex min-h-[180px] flex-col items-center justify-center rounded-xl border border-dashed border-border/80 bg-background/50 p-6 text-center">
              <FileText className="h-5 w-5 text-muted" />
              <p className="mt-3 text-sm font-medium text-white">No documents in this collection</p>
              <p className="mt-1 text-xs text-muted">Upload source material before building vectors.</p>
              <Button type="button" size="sm" onClick={() => setScreen('upload')} className="mt-4">
                <Upload className="mr-2 h-3.5 w-3.5" />
                Upload document
              </Button>
            </div>
          ) : (
            <div className="space-y-2">
              {items.map((document) => (
                <div key={document.id} className="grid gap-3 rounded-lg border border-border/70 bg-background/55 p-3 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-center">
                  <div className="flex min-w-0 gap-3">
                    <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-border bg-surface text-primary-light">
                      <FileText className="h-4 w-4" />
                    </div>
                    <div className="min-w-0">
                      <div className="flex flex-wrap items-center gap-2">
                        <p className="truncate text-sm font-medium text-white">{document.title}</p>
                        {document.status ? <StatusBadge status={document.status} /> : null}
                      </div>
                      <p className="mt-1 truncate text-xs text-muted">{documentMeta(document)}</p>
                      <p className="mt-1.5 text-[11px] text-muted">{document.chunk_count ?? 0} chunks · {document.page_count ?? '-'} pages · {document.created_at ? formatDate(document.created_at) : '-'}</p>
                    </div>
                  </div>
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    className="h-8 w-8 justify-self-end text-red-400 hover:text-red-300"
                    onClick={() => setDocumentToDelete(document)}
                    aria-label={`Delete ${document.title}`}
                  >
                    <Trash2 className="h-4 w-4" />
                  </Button>
                </div>
              ))}
            </div>
          )}
        </div>
      </section>
    </div>
  )

  const collectionVectors = (
    <div className="space-y-4">
      <section className="rounded-xl border border-border/80 bg-surface/65 p-4">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <h3 className="text-sm font-semibold text-white">Vector readiness</h3>
              <StatusBadge status={overview?.rag_status || 'UNKNOWN'} />
            </div>
            <p className="mt-1 text-xs text-muted">{overview?.warnings?.[0] || 'Build an immutable vector snapshot from the current documents.'}</p>
          </div>
          <Button type="button" size="sm" onClick={() => setBuildModalOpen(true)} disabled={items.length === 0 || hasRunningBuild}>
            <Cpu className="mr-2 h-3.5 w-3.5" />
            {overview?.rag_status === 'OUTDATED' ? 'Rebuild vectors' : 'Build vectors'}
          </Button>
        </div>
        <div className="mt-4 grid gap-3 sm:grid-cols-3">
          <TechItem label="Latest snapshot" value={overview?.latest_ready_snapshot?.version || 'Not built'} detail={`${numberLabel(overview?.latest_ready_snapshot?.chunk_count)} chunks`} />
          <TechItem label="Documents" value={`${overview?.documents.active ?? items.length} active`} detail={`${overview?.documents.ready ?? indexedCount} ready`} />
          <TechItem label="Embedding" value={overview?.technology.embedding_model || 'Not selected'} />
        </div>
        {overview?.processing.has_running_job ? (
          <div className="mt-4 rounded-xl border border-primary/25 bg-primary/10 p-3 text-xs text-primary-light">
            Building vectors · {overview.processing.stage || 'QUEUED'} · {overview.processing.embedded_chunks}/{overview.processing.total_chunks || 0} chunks
          </div>
        ) : null}
      </section>

      <section className="rounded-xl border border-border/80 bg-surface/65 p-4">
        <div className="flex items-start justify-between gap-3">
          <div>
            <h3 className="text-sm font-semibold text-white">Vector versions</h3>
            <p className="mt-1 text-xs text-muted">Immutable builds generated from this Collection.</p>
          </div>
          <span className="text-xs text-muted">{vectorSnapshots.length} versions</span>
        </div>

        {vectorSnapshots.length === 0 ? (
          <div className="mt-4 rounded-xl border border-dashed border-border bg-background/50 p-8 text-center text-sm text-muted">No vector snapshot built yet.</div>
        ) : (
          <div className="mt-4 space-y-2">
            {vectorSnapshots.map((snapshot) => {
              const inUse = snapshot.id === usedSnapshotId
              return (
                <div key={snapshot.id} className={`grid gap-3 rounded-lg border p-3 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-center ${inUse ? 'border-primary/35 bg-primary/10' : 'border-border/70 bg-background/55'}`}>
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <p className="font-mono text-sm font-semibold text-white">{snapshot.version}</p>
                      <StatusBadge status={snapshot.status} />
                      {inUse ? <span className="rounded-full border border-primary/30 bg-primary/10 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-primary-light">In use</span> : null}
                    </div>
                    <p className="mt-1 text-xs text-muted">{snapshot.embedding_model} · {numberLabel(snapshot.chunk_count)} chunks · {numberLabel(snapshot.vector_count ?? snapshot.chunk_count)} vectors</p>
                    <p className="mt-1 text-[11px] text-muted">{snapshot.completed_at ? `Built ${formatDate(snapshot.completed_at)}` : snapshot.build_stage || 'Queued'}</p>
                  </div>
                  <div className="flex items-center justify-end gap-2">
                    {!inUse && snapshot.status === 'READY' ? (
                      <Button type="button" size="sm" variant="outline" onClick={() => void handleUseSnapshot(snapshot)} loading={applyingSnapshotId === snapshot.id} disabled={Boolean(applyingSnapshotId)}>
                        Use this version
                      </Button>
                    ) : null}
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </section>
    </div>
  )

  const collectionTechnology = (
    <section className="rounded-xl border border-border/80 bg-surface/65 p-4">
      <h3 className="text-sm font-semibold text-white">Technology</h3>
      <p className="mt-1 text-xs text-muted">Configuration captured by the latest vector snapshot.</p>
      <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        <TechItem label="Embedding" value={overview?.technology.embedding_model || 'Not selected'} detail={overview?.technology.embedding_provider || 'No provider selected'} />
        <TechItem label="Chunking" value={overview?.technology.chunking_strategy || 'Not configured'} detail={overview?.technology.chunk_size ? `${overview.technology.chunk_size} size · ${overview.technology.chunk_overlap ?? 0} overlap` : undefined} />
        <TechItem label="Vector store" value={overview?.technology.vector_store || 'pgvector'} detail={overview?.technology.distance_metric || 'cosine'} />
      </div>
    </section>
  )

  const sidebar = screen === 'collections' ? (
    <div className="space-y-4">
      <section className="rounded-xl border border-border/90 bg-background/55 p-4">
        <div className="flex h-11 w-11 items-center justify-center rounded-xl border border-border bg-surface text-primary-light">
          <Database className="h-5 w-5" />
        </div>
        <p className="mt-5 text-[10px] font-semibold uppercase tracking-[0.18em] text-muted/75">Knowledge</p>
        <h3 className="mt-2 text-base font-semibold text-white">Project knowledge</h3>
        <p className="mt-2 text-xs leading-5 text-muted">Create and manage the Collections available to this Project without leaving the Playground.</p>
      </section>

      <section className="rounded-xl border border-border/90 bg-background/55 p-4">
        <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-muted/75">Current Agent</p>
        {activeBinding ? (
          <div className="mt-3">
            <p className="truncate text-sm font-medium text-white">{activeBinding.collectionName}</p>
            <p className="mt-1 text-xs text-muted">Knowledge {activeBinding.knowledgeVersion}</p>
            <p className="mt-1 text-xs text-muted">Vector {activeBinding.vectorVersion}</p>
          </div>
        ) : (
          <div className="mt-3 rounded-lg border border-border/80 bg-surface/50 p-3">
            <p className="text-sm font-medium text-white">No knowledge selected</p>
            <p className="mt-1 text-xs leading-5 text-muted">The Agent Draft is not bound to a vector version.</p>
          </div>
        )}
      </section>
    </div>
  ) : screen === 'create' ? (
    <div className="space-y-4">
      <Button type="button" size="sm" variant="ghost" className="-ml-2" onClick={backToCollections}>
        <ArrowLeft className="mr-2 h-3.5 w-3.5" />
        Collections
      </Button>
      <section className="rounded-xl border border-border/90 bg-background/55 p-4">
        <div className="flex h-11 w-11 items-center justify-center rounded-xl border border-border bg-surface text-primary-light">
          <Plus className="h-5 w-5" />
        </div>
        <p className="mt-5 text-[10px] font-semibold uppercase tracking-[0.18em] text-muted/75">New Collection</p>
        <h3 className="mt-2 text-base font-semibold text-white">Create a knowledge source</h3>
        <p className="mt-2 text-xs leading-5 text-muted">Documents always belong to one Collection. Create it first, then upload source material.</p>
      </section>
    </div>
  ) : selectedCollection ? (
    <div className="space-y-4">
      <Button
        type="button"
        size="sm"
        variant="ghost"
        className="-ml-2"
        onClick={screen === 'upload' ? () => setScreen('collection') : backToCollections}
      >
        <ArrowLeft className="mr-2 h-3.5 w-3.5" />
        {screen === 'upload' ? 'Back to collection' : 'Collections'}
      </Button>
      <section className="rounded-xl border border-border/90 bg-background/55 p-4">
        <div className="flex h-11 w-11 items-center justify-center rounded-xl border border-border bg-surface text-primary-light">
          <Database className="h-5 w-5" />
        </div>
        <div className="mt-4 flex items-start justify-between gap-3">
          <h3 className="truncate text-base font-semibold text-white">{selectedCollection.name}</h3>
          {selectedCollection.status ? <StatusBadge status={selectedCollection.status} /> : null}
        </div>
        <p className="mt-2 line-clamp-4 text-xs leading-5 text-muted">{selectedCollection.description || 'No description provided'}</p>
        <div className="mt-4 grid grid-cols-3 gap-2 border-t border-border/70 pt-4 text-center">
          <div><p className="text-sm font-semibold text-white">{items.length}</p><p className="mt-0.5 text-[10px] text-muted">documents</p></div>
          <div><p className="text-sm font-semibold text-white">{indexedCount}</p><p className="mt-0.5 text-[10px] text-muted">ready</p></div>
          <div><p className="truncate text-sm font-semibold text-white">{formatBytes(totalSize)}</p><p className="mt-0.5 text-[10px] text-muted">total</p></div>
        </div>
      </section>
    </div>
  ) : null

  return (
    <>
      {!buildModalOpen ? (
        <div
          ref={overlayRef}
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4 backdrop-blur-md"
          onClick={(event) => { if (event.target === overlayRef.current) onClose() }}
        >
          <div className="flex h-[84vh] w-full max-w-[1180px] flex-col overflow-hidden rounded-2xl border border-border/90 bg-surface/95 shadow-2xl shadow-black/40">
            <div className="flex items-start justify-between gap-4 border-b border-border/90 bg-background/20 px-5 py-4">
              <div>
                <h2 className="text-sm font-semibold text-white">Manage Knowledge</h2>
                <p className="mt-0.5 text-[11px] text-muted">Collections, documents and immutable vector versions.</p>
              </div>
              <button
                type="button"
                onClick={onClose}
                className="rounded-lg border border-transparent p-1 text-muted transition-colors hover:border-border/80 hover:bg-background/60 hover:text-white"
                aria-label="Close Manage Knowledge"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            <div className="grid min-h-0 flex-1 grid-cols-[280px_minmax(0,1fr)]">
              <aside className="min-h-0 overflow-y-auto border-r border-border/90 bg-background/20 p-4">
                {sidebar}
              </aside>

              {screen === 'collections' ? (
                <section className="flex min-h-0 flex-col">
                  <div className="flex items-start justify-between gap-4 border-b border-border/90 bg-surface/70 px-5 py-4">
                    <div>
                      <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-primary-light">Collections</p>
                      <h3 className="mt-1.5 text-lg font-semibold text-white">Knowledge sources</h3>
                      <p className="mt-1 text-xs text-muted">Open a Collection to manage documents and vectors.</p>
                    </div>
                    <Button type="button" size="sm" onClick={() => setScreen('create')}>
                      <Plus className="mr-2 h-3.5 w-3.5" />
                      New collection
                    </Button>
                  </div>
                  <div className="min-h-0 flex-1 overflow-y-auto p-5">
                    <div className="relative">
                      <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted" />
                      <Input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search collections..." className="pl-9" />
                    </div>

                    {collectionsLoading ? (
                      <div className="mt-5"><LoadingState variant="panel" layout="list" message="Loading collections..." /></div>
                    ) : visibleCollections.length === 0 ? (
                      <div className="mt-5 flex min-h-[260px] flex-col items-center justify-center rounded-xl border border-dashed border-border/80 bg-background/45 p-8 text-center">
                        <Database className="h-5 w-5 text-muted" />
                        <p className="mt-4 text-sm font-medium text-white">{normalizedQuery ? 'No collections found' : 'No collections yet'}</p>
                        <p className="mt-1 text-xs text-muted">{normalizedQuery ? 'Adjust the search term.' : 'Create the first Collection for this Project.'}</p>
                        {!normalizedQuery ? <Button type="button" size="sm" onClick={() => setScreen('create')} className="mt-4"><Plus className="mr-2 h-3.5 w-3.5" />New collection</Button> : null}
                      </div>
                    ) : (
                      <div className="mt-5 grid gap-3 sm:grid-cols-2">
                        {visibleCollections.map((collection) => (
                          <button
                            key={collection.id}
                            type="button"
                            onClick={() => openCollection(collection)}
                            className="group flex min-h-[132px] flex-col rounded-xl border border-border/80 bg-background/55 p-4 text-left transition-colors hover:border-primary/35 hover:bg-surface/70"
                          >
                            <div className="flex items-start justify-between gap-3">
                              <span className="flex h-9 w-9 items-center justify-center rounded-lg border border-border bg-surface text-primary-light">
                                <Database className="h-4 w-4" />
                              </span>
                              {collection.status ? <StatusBadge status={collection.status} /> : null}
                            </div>
                            <div className="mt-3 min-w-0">
                              <p className="truncate text-sm font-medium text-white">{collection.name}</p>
                              <p className="mt-1 line-clamp-2 text-xs leading-5 text-muted">{collection.description || 'No description provided'}</p>
                            </div>
                            <div className="mt-auto flex items-center justify-between gap-3 pt-3 text-[11px] text-muted">
                              <span>{collection.documents_count ?? 0} documents</span>
                              <span className="transition-transform group-hover:translate-x-0.5">→</span>
                            </div>
                          </button>
                        ))}
                      </div>
                    )}
                  </div>
                </section>
              ) : screen === 'create' ? (
                <form onSubmit={handleCreate} className="flex min-h-0 flex-col">
                  <div className="min-h-0 flex-1 overflow-y-auto p-5">
                    <div>
                      <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-primary-light">New Collection</p>
                      <h3 className="mt-1.5 text-lg font-semibold text-white">Create a knowledge source</h3>
                      <p className="mt-1 text-xs text-muted">Create the Collection, then add documents and build an immutable vector version.</p>
                    </div>
                    <div className="mt-6 grid gap-5 lg:grid-cols-[minmax(0,0.8fr)_minmax(0,1.2fr)]">
                      <div>
                        <label className="mb-1.5 block text-[10px] font-semibold uppercase tracking-[0.16em] text-muted">Name</label>
                        <Input value={createName} onChange={(event) => setCreateName(event.target.value)} placeholder="Customer Support" autoFocus />
                        <p className="mt-2 text-xs leading-5 text-muted">Use a clear operational name for the document group.</p>
                      </div>
                      <div>
                        <label className="mb-1.5 block text-[10px] font-semibold uppercase tracking-[0.16em] text-muted">Description</label>
                        <Textarea value={createDescription} onChange={(event) => setCreateDescription(event.target.value)} placeholder="Product documentation and support policies" className="min-h-[140px]" />
                      </div>
                    </div>
                  </div>
                  <div className="flex justify-end gap-2 border-t border-border/90 bg-background/20 px-5 py-4">
                    <Button type="button" variant="outline" onClick={backToCollections} disabled={createCollection.isPending}>Cancel</Button>
                    <Button type="submit" loading={createCollection.isPending}>Create collection</Button>
                  </div>
                </form>
              ) : screen === 'upload' && selectedCollection ? (
                <section className="flex min-h-0 flex-col">
                  <div className="border-b border-border/90 bg-surface/70 px-5 py-4">
                    <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-primary-light">Upload Document</p>
                    <h3 className="mt-1.5 text-lg font-semibold text-white">Add source material</h3>
                    <p className="mt-1 text-xs text-muted">Upload directly to {selectedCollection.name}. TXT, MD and PDF are supported.</p>
                  </div>
                  <div className="min-h-0 flex-1 overflow-y-auto p-5">
                    <CollectionDocumentUploadPanel
                      projectId={projectId}
                      collection={{ id: selectedCollection.id, name: selectedCollection.name }}
                      onCancel={() => setScreen('collection')}
                      onUploaded={handleUploaded}
                      showDestination={false}
                    />
                  </div>
                </section>
              ) : selectedCollection ? (
                <section className="flex min-h-0 flex-col">
                  <div className="flex gap-1 border-b border-border/90 bg-surface/70 p-1.5">
                    <TabButton active={collectionTab === 'overview'} label="Overview" onClick={() => setCollectionTab('overview')} />
                    <TabButton active={collectionTab === 'vectors'} label="Vectors" onClick={() => setCollectionTab('vectors')} />
                    <TabButton active={collectionTab === 'technology'} label="Technology" onClick={() => setCollectionTab('technology')} />
                  </div>
                  <div className="min-h-0 flex-1 overflow-y-auto p-5">
                    {collectionTab === 'overview' ? collectionOverview : null}
                    {collectionTab === 'vectors' ? collectionVectors : null}
                    {collectionTab === 'technology' ? collectionTechnology : null}
                  </div>
                  {collectionTab === 'overview' ? (
                    <div className="flex justify-end gap-2 border-t border-border/90 bg-background/20 px-5 py-4">
                      <Button type="button" variant="outline" onClick={backToCollections}>Close collection</Button>
                      <Button type="button" onClick={handleSaveCollection} loading={updateCollection.isPending} disabled={!hasChanges}>Save changes</Button>
                    </div>
                  ) : null}
                </section>
              ) : null}
            </div>
          </div>
        </div>
      ) : null}

      <BuildVectorSnapshotModalV2
        open={buildModalOpen && Boolean(selectedCollection)}
        projectId={projectId}
        collection={selectedCollection ? { id: selectedCollection.id, name: selectedCollection.name } : null}
        onClose={() => setBuildModalOpen(false)}
        onCreated={handleBuildCreated}
      />
    </>
  )
}
