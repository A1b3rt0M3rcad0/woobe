import { useEffect, useMemo, useState, type FormEvent } from 'react'
import { ArrowLeft, Database, FileText, Plus, Search, Trash2, Upload, Workflow } from 'lucide-react'
import { toast } from 'sonner'

import { Button } from '@/components/ui/Button'
import { Dialog } from '@/components/ui/Dialog'
import { Input } from '@/components/ui/Input'
import { Select } from '@/components/ui/Select'
import { Textarea } from '@/components/ui/Textarea'
import { useCreateKnowledgeVersion } from '@/features/agents/hooks'
import { useCollections, useCreateCollection, useDeleteDocument, useDocumentsByCollection, useUpdateCollection, useUploadDocumentFile } from '@/features/knowledge/hooks'
import type { Collection, Document, VectorSnapshot } from '@/features/knowledge/types'
import { useCreateVectorSnapshot, useVectorSnapshots } from '@/features/knowledge/vectorHooks'
import { useProviderModels } from '@/features/provider-models/hooks'
import { cn } from '@/lib/utils'

type Screen = 'collections' | 'create' | 'collection' | 'upload' | 'build'
type CollectionTab = 'documents' | 'vectors'

interface Props {
  open: boolean
  projectId: string
  agentId: string
  currentSnapshotId: string | null
  onClose: () => void
  onApplied: (knowledgeVersionId: string) => void
}

function ready(status?: string) {
  return ['ready', 'indexed'].includes(String(status || '').toLowerCase())
}

function formatBytes(value?: number) {
  if (!value) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB']
  const index = Math.min(Math.floor(Math.log(value) / Math.log(1024)), units.length - 1)
  return `${(value / 1024 ** index).toFixed(index === 0 ? 0 : 1)} ${units[index]}`
}

export function NetworkKnowledgeManagerModal({ open, projectId, agentId, currentSnapshotId, onClose, onApplied }: Props) {
  const collectionsQuery = useCollections(projectId)
  const createCollection = useCreateCollection()
  const updateCollection = useUpdateCollection()
  const uploadDocument = useUploadDocumentFile()
  const deleteDocument = useDeleteDocument()
  const createKnowledgeVersion = useCreateKnowledgeVersion(agentId)
  const { data: providerModels = [] } = useProviderModels(projectId)

  const [screen, setScreen] = useState<Screen>('collections')
  const [tab, setTab] = useState<CollectionTab>('documents')
  const [query, setQuery] = useState('')
  const [selected, setSelected] = useState<Collection | null>(null)
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [file, setFile] = useState<File | null>(null)
  const [documentTitle, setDocumentTitle] = useState('')
  const [documentToDelete, setDocumentToDelete] = useState<Document | null>(null)
  const [embeddingModelId, setEmbeddingModelId] = useState('')
  const [snapshotDescription, setSnapshotDescription] = useState('')
  const [chunkSize, setChunkSize] = useState(800)
  const [chunkOverlap, setChunkOverlap] = useState(120)
  const [applyingId, setApplyingId] = useState<string | null>(null)

  const documentsQuery = useDocumentsByCollection(selected?.id)
  const snapshotsQuery = useVectorSnapshots(selected?.id, projectId)
  const createSnapshot = useCreateVectorSnapshot(selected?.id, projectId)
  const collections = collectionsQuery.data ?? []
  const documents = documentsQuery.data ?? []
  const snapshots = snapshotsQuery.data ?? []
  const embeddingModels = providerModels.filter((model) => {
    const capability = String(model.metadata?.capability || model.metadata?.type || `${model.name} ${model.model}`).toLowerCase()
    return model.status === 'active' && capability.includes('embed')
  })

  const visibleCollections = useMemo(() => {
    const normalized = query.trim().toLowerCase()
    return normalized ? collections.filter((item) => `${item.name} ${item.description || ''}`.toLowerCase().includes(normalized)) : collections
  }, [collections, query])

  useEffect(() => {
    if (!open) return
    setScreen('collections')
    setSelected(null)
    setQuery('')
    setDocumentToDelete(null)
  }, [open])

  useEffect(() => {
    if (!selected) return
    setName(selected.name)
    setDescription(selected.description || '')
  }, [selected?.id])

  useEffect(() => {
    if (!embeddingModelId && embeddingModels[0]) setEmbeddingModelId(embeddingModels[0].id)
  }, [embeddingModelId, embeddingModels])

  const openCollection = (collection: Collection, nextTab: CollectionTab = 'documents') => {
    setSelected(collection)
    setTab(nextTab)
    setScreen('collection')
  }

  const refresh = () => {
    void collectionsQuery.refetch()
    void documentsQuery.refetch()
    void snapshotsQuery.refetch()
  }

  const createNewCollection = async (event: FormEvent) => {
    event.preventDefault()
    if (!name.trim()) return toast.error('Collection name is required')
    try {
      const collection = await createCollection.mutateAsync({ project_id: projectId, name: name.trim(), description: description.trim() || undefined })
      toast.success('Collection created')
      openCollection(collection)
    } catch (error) { toast.error(error instanceof Error ? error.message : 'Failed to create Collection') }
  }

  const saveCollection = async () => {
    if (!selected || !name.trim()) return
    try {
      const updated = await updateCollection.mutateAsync({ id: selected.id, data: { name: name.trim(), description: description.trim() || null } })
      setSelected(updated)
      toast.success('Collection updated')
      void collectionsQuery.refetch()
    } catch (error) { toast.error(error instanceof Error ? error.message : 'Failed to update Collection') }
  }

  const upload = async (event: FormEvent) => {
    event.preventDefault()
    if (!selected || !file) return toast.error('Choose a file')
    try {
      await uploadDocument.mutateAsync({ projectId, collectionId: selected.id, title: documentTitle.trim() || file.name, file })
      setFile(null)
      setDocumentTitle('')
      setScreen('collection')
      setTab('documents')
      refresh()
      toast.success('Document uploaded')
    } catch (error) { toast.error(error instanceof Error ? error.message : 'Failed to upload Document') }
  }

  const removeDocument = async () => {
    if (!documentToDelete) return
    try {
      await deleteDocument.mutateAsync(documentToDelete.id)
      setDocumentToDelete(null)
      refresh()
      toast.success('Document deleted')
    } catch (error) { toast.error(error instanceof Error ? error.message : 'Failed to delete Document') }
  }

  const buildSnapshot = async (event: FormEvent) => {
    event.preventDefault()
    if (!selected || !embeddingModelId) return toast.error('Choose an embedding model')
    try {
      await createSnapshot.mutateAsync({ project_id: projectId, embedding_provider_model_id: embeddingModelId, description: snapshotDescription.trim() || undefined, chunk_size: chunkSize, chunk_overlap: chunkOverlap, chunking_strategy: 'recursive_text' })
      setSnapshotDescription('')
      setScreen('collection')
      setTab('vectors')
      refresh()
      toast.success('Vector Snapshot build started')
    } catch (error) { toast.error(error instanceof Error ? error.message : 'Failed to build Vector Snapshot') }
  }

  const useSnapshot = async (snapshot: VectorSnapshot) => {
    if (!selected || !ready(snapshot.status)) return
    setApplyingId(snapshot.id)
    try {
      const version = await createKnowledgeVersion.mutateAsync({ project_id: projectId, agent_id: agentId, version: `kv-${Date.now()}`, collection_ids: [selected.id], snapshot_metadata: { vector_snapshot_id: snapshot.id, vector_snapshot_version: snapshot.version } } as any)
      onApplied(version.id)
      toast.success(`${snapshot.version} applied to the Agent Draft`)
      onClose()
    } catch (error) { toast.error(error instanceof Error ? error.message : 'Failed to apply Vector Snapshot') }
    finally { setApplyingId(null) }
  }

  return (
    <Dialog open={open} onClose={onClose} title="Manage Knowledge" className="max-w-6xl overflow-hidden bg-surface/95">
      <div className="-m-6 flex h-[78vh] min-h-[580px] flex-col overflow-hidden">
        {screen === 'collections' ? <>
          <div className="flex shrink-0 gap-3 border-b border-border/80 p-4">
            <div className="relative min-w-0 flex-1"><Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted" /><Input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search Collections..." className="pl-9" /></div>
            <Button size="sm" onClick={() => { setName(''); setDescription(''); setScreen('create') }}><Plus className="mr-2 h-3.5 w-3.5" />New Collection</Button>
          </div>
          <div className="scrollbar-thin min-h-0 flex-1 overflow-y-auto p-5">
            {visibleCollections.length === 0 ? <div className="rounded-xl border border-dashed border-border p-10 text-center text-sm text-muted">No Collections found.</div> : <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">{visibleCollections.map((collection) => <button key={collection.id} type="button" onClick={() => openCollection(collection)} className="rounded-xl border border-border/80 bg-background/50 p-4 text-left hover:border-primary/35"><Database className="h-4 w-4 text-primary-light" /><p className="mt-3 truncate text-sm font-medium text-white">{collection.name}</p><p className="mt-1 line-clamp-2 text-xs leading-5 text-muted">{collection.description || 'No description'}</p><p className="mt-3 text-[10px] text-muted">{collection.documents_count ?? 0} documents</p></button>)}</div>}
          </div>
        </> : screen === 'create' ? <form onSubmit={createNewCollection} className="flex min-h-0 flex-1 flex-col"><div className="scrollbar-thin min-h-0 flex-1 overflow-y-auto p-5"><Button type="button" size="sm" variant="ghost" onClick={() => setScreen('collections')}><ArrowLeft className="mr-2 h-3.5 w-3.5" />Collections</Button><div className="mx-auto mt-5 max-w-2xl space-y-4"><label className="block text-xs font-medium text-muted">Name<Input className="mt-1.5" value={name} onChange={(event) => setName(event.target.value)} autoFocus /></label><label className="block text-xs font-medium text-muted">Description<Textarea className="mt-1.5 min-h-[130px]" value={description} onChange={(event) => setDescription(event.target.value)} /></label></div></div><div className="flex justify-end gap-2 border-t border-border/80 p-4"><Button type="button" variant="outline" onClick={() => setScreen('collections')}>Cancel</Button><Button type="submit" loading={createCollection.isPending}>Create Collection</Button></div></form> : screen === 'upload' && selected ? <form onSubmit={upload} className="flex min-h-0 flex-1 flex-col"><div className="scrollbar-thin min-h-0 flex-1 overflow-y-auto p-5"><Button type="button" size="sm" variant="ghost" onClick={() => setScreen('collection')}><ArrowLeft className="mr-2 h-3.5 w-3.5" />{selected.name}</Button><div className="mx-auto mt-5 max-w-2xl space-y-4"><label className="block text-xs font-medium text-muted">File<Input type="file" accept=".txt,.md,.pdf,text/plain,text/markdown,application/pdf" className="mt-1.5" onChange={(event) => setFile(event.target.files?.[0] || null)} /></label><label className="block text-xs font-medium text-muted">Title<Input className="mt-1.5" value={documentTitle} onChange={(event) => setDocumentTitle(event.target.value)} placeholder={file?.name || 'Optional'} /></label></div></div><div className="flex justify-end gap-2 border-t border-border/80 p-4"><Button type="button" variant="outline" onClick={() => setScreen('collection')}>Cancel</Button><Button type="submit" loading={uploadDocument.isPending}>Upload Document</Button></div></form> : screen === 'build' && selected ? <form onSubmit={buildSnapshot} className="flex min-h-0 flex-1 flex-col"><div className="scrollbar-thin min-h-0 flex-1 overflow-y-auto p-5"><Button type="button" size="sm" variant="ghost" onClick={() => setScreen('collection')}><ArrowLeft className="mr-2 h-3.5 w-3.5" />{selected.name}</Button><div className="mx-auto mt-5 max-w-2xl space-y-4"><label className="block text-xs font-medium text-muted">Embedding model<Select className="mt-1.5" value={embeddingModelId} onChange={(event) => setEmbeddingModelId(event.target.value)} options={[{ value: '', label: 'Select embedding model' }, ...embeddingModels.map((model) => ({ value: model.id, label: `${model.name} · ${model.model}` }))]} /></label><label className="block text-xs font-medium text-muted">Description<Input className="mt-1.5" value={snapshotDescription} onChange={(event) => setSnapshotDescription(event.target.value)} placeholder="What changed in this knowledge version" /></label><div className="grid grid-cols-2 gap-4"><label className="text-xs font-medium text-muted">Chunk size<Input type="number" min="100" className="mt-1.5" value={chunkSize} onChange={(event) => setChunkSize(Number(event.target.value) || 800)} /></label><label className="text-xs font-medium text-muted">Overlap<Input type="number" min="0" className="mt-1.5" value={chunkOverlap} onChange={(event) => setChunkOverlap(Number(event.target.value) || 0)} /></label></div></div></div><div className="flex justify-end gap-2 border-t border-border/80 p-4"><Button type="button" variant="outline" onClick={() => setScreen('collection')}>Cancel</Button><Button type="submit" loading={createSnapshot.isPending}>Build Snapshot</Button></div></form> : selected ? <>
          <div className="flex shrink-0 items-center gap-3 border-b border-border/80 p-4"><Button size="sm" variant="ghost" onClick={() => { setSelected(null); setScreen('collections') }}><ArrowLeft className="mr-2 h-3.5 w-3.5" />Collections</Button><div className="min-w-0 flex-1"><p className="truncate text-sm font-medium text-white">{selected.name}</p><p className="truncate text-xs text-muted">{selected.description || 'No description'}</p></div><Button size="sm" variant="outline" onClick={refresh}>Refresh</Button></div>
          <div className="flex shrink-0 gap-1 border-b border-border/80 p-1.5">{(['documents', 'vectors'] as CollectionTab[]).map((item) => <button key={item} type="button" onClick={() => setTab(item)} className={cn('rounded-lg border px-3 py-2 text-xs font-medium capitalize', tab === item ? 'border-primary/35 bg-primary/10 text-primary-light' : 'border-transparent text-muted hover:text-white')}>{item}</button>)}</div>
          <div className="scrollbar-thin min-h-0 flex-1 overflow-y-auto p-5">{tab === 'documents' ? <div><div className="flex items-center justify-between"><div><p className="text-sm font-medium text-white">Documents</p><p className="mt-1 text-xs text-muted">{documents.length} files · {documents.filter((item) => ready(item.status)).length} ready</p></div><Button size="sm" onClick={() => setScreen('upload')}><Upload className="mr-2 h-3.5 w-3.5" />Upload</Button></div>{documentToDelete ? <div className="mt-4 flex items-center gap-3 rounded-xl border border-red-500/25 bg-red-500/[0.045] p-3"><div className="min-w-0 flex-1"><p className="truncate text-xs font-medium text-white">Delete {documentToDelete.title}?</p><p className="mt-1 text-[10px] text-muted">Stored file and generated chunks will be removed.</p></div><Button size="sm" variant="outline" onClick={() => setDocumentToDelete(null)}>Cancel</Button><Button size="sm" variant="destructive" onClick={() => void removeDocument()} loading={deleteDocument.isPending}>Delete</Button></div> : null}<div className="mt-4 space-y-2">{documents.length === 0 ? <div className="rounded-xl border border-dashed border-border p-8 text-center text-xs text-muted">No Documents uploaded.</div> : documents.map((document) => <article key={document.id} className="flex items-start gap-3 rounded-xl border border-border/80 bg-background/50 p-3"><FileText className="mt-0.5 h-4 w-4 shrink-0 text-primary-light" /><div className="min-w-0 flex-1"><p className="truncate text-xs font-medium text-white">{document.title}</p><p className="mt-1 truncate text-[10px] text-muted">{document.file_name} · {formatBytes(document.size_bytes)} · {document.status}</p></div><button type="button" onClick={() => setDocumentToDelete(document)} className="rounded-lg border border-border p-2 text-muted hover:border-red-500/30 hover:text-red-300"><Trash2 className="h-3.5 w-3.5" /></button></article>)}</div></div> : <div><div className="flex items-center justify-between"><div><p className="text-sm font-medium text-white">Vector Snapshots</p><p className="mt-1 text-xs text-muted">Immutable versions available to Agent Drafts and Releases.</p></div><Button size="sm" onClick={() => setScreen('build')}><Workflow className="mr-2 h-3.5 w-3.5" />Build</Button></div><div className="mt-4 space-y-2">{snapshots.length === 0 ? <div className="rounded-xl border border-dashed border-border p-8 text-center text-xs text-muted">No Vector Snapshots yet.</div> : snapshots.map((snapshot) => <article key={snapshot.id} className={cn('rounded-xl border p-4', snapshot.id === currentSnapshotId ? 'border-primary/40 bg-primary/[0.05]' : 'border-border/80 bg-background/50')}><div className="flex items-start gap-3"><div className="min-w-0 flex-1"><p className="font-mono text-xs font-medium text-white">{snapshot.version}</p><p className="mt-1 text-[10px] text-muted">{snapshot.document_count} documents · {snapshot.chunk_count} chunks · {snapshot.status}</p><p className="mt-1 text-[10px] text-muted">{snapshot.embedding_provider}/{snapshot.embedding_model}</p></div><Button size="sm" disabled={!ready(snapshot.status) || snapshot.id === currentSnapshotId} loading={applyingId === snapshot.id} onClick={() => void useSnapshot(snapshot)}>{snapshot.id === currentSnapshotId ? 'In use' : 'Use in Agent'}</Button></div>{snapshot.description ? <p className="mt-3 border-t border-border/70 pt-3 text-xs leading-5 text-muted">{snapshot.description}</p> : null}</article>)}</div></div>}</div>
          {tab === 'documents' ? <div className="flex shrink-0 justify-end border-t border-border/80 p-4"><Button size="sm" onClick={() => void saveCollection()} loading={updateCollection.isPending}>Save Collection</Button></div> : null}
        </> : null}
      </div>
    </Dialog>
  )
}
