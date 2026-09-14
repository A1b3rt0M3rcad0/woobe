import { useEffect, useMemo, useState } from 'react'
import { AlertTriangle, Cpu, Database, FileText, RefreshCw, Trash2, Upload } from 'lucide-react'
import {
  Alert,
  AlertDescription,
  AlertTitle,
  Badge,
  Button,
  Dialog,
  DialogContextBar,
  DialogFooter,
  EmptyStatePanel,
  Field,
  FieldLabel,
  Input,
  MetricTile,
  SectionBlock,
  Skeleton,
  Tabs,
  TechnicalListItem,
  Textarea,
} from '@woobe/ui'
import { toast } from 'sonner'

import { StatusBadge } from '@/components/common/StatusBadge'
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
    if (!nextName) return void toast.error('Collection name is required')
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
    <div className="grid gap-ui-md pb-ui-xs">
      <SectionBlock title="Collection information" description="Edit the Collection identity used across Knowledge." density="compact">
        <div className="grid gap-ui-md">
          <Field>
            <FieldLabel>Name</FieldLabel>
            <Input value={name} onChange={(event) => setName(event.target.value)} />
          </Field>
          <Field>
            <FieldLabel>Description</FieldLabel>
            <Textarea value={description} onChange={(event) => setDescription(event.target.value)} />
          </Field>
        </div>
      </SectionBlock>

      <SectionBlock
        title="Documents"
        description={`${items.length} files · ${indexedCount} ready · ${formatBytes(totalSize)} total`}
        density="compact"
        actions={(
          <div className="flex gap-ui-sm">
            <Button type="button" variant="outline" size="sm" onClick={refreshAll} disabled={isLoading}>
              <RefreshCw className="h-icon w-icon" />Refresh
            </Button>
            <Button type="button" size="sm" onClick={() => setUploadModalOpen(true)}>
              <Upload className="h-icon w-icon" />Upload
            </Button>
          </div>
        )}
      >
        {isLoading ? (
          <div className="grid gap-ui-xs">
            <Skeleton className="h-control-row w-full" />
            <Skeleton className="h-control-row w-full" />
            <Skeleton className="h-control-row w-full" />
          </div>
        ) : items.length === 0 ? (
          <EmptyStatePanel
            icon={<FileText className="h-icon-lg w-icon-lg" />}
            title="No documents in this Collection"
            description="Upload source material before building vectors."
            action={(
              <Button type="button" size="sm" onClick={() => setUploadModalOpen(true)}>
                <Upload className="h-icon w-icon" />Upload document
              </Button>
            )}
          />
        ) : (
          <div className="grid gap-ui-xs">
            {items.map((document) => (
              <TechnicalListItem
                key={document.id}
                label={document.title}
                description={documentMeta(document)}
                density="compact"
                leading={(
                  <span className="flex h-control-sm w-control-sm items-center justify-center rounded-control border border-border bg-control text-primary-light">
                    <FileText className="h-icon w-icon" />
                  </span>
                )}
                meta={(
                  <>
                    {document.status ? <StatusBadge status={document.status} size="compact" /> : null}
                    <Badge variant="outline" size="compact">Chunks {document.chunk_count ?? 0}</Badge>
                    <Badge variant="outline" size="compact">Pages {document.page_count ?? '-'}</Badge>
                  </>
                )}
                trailing={(
                  <div className="flex items-center gap-ui-sm">
                    {document.created_at ? <span className="hidden font-mono text-system-meta text-muted-foreground lg:inline">{formatDate(document.created_at)}</span> : null}
                    <Button
                      type="button"
                      variant="ghost"
                      size="iconSm"
                      disabled={deleteDocument.isPending}
                      onClick={() => setDocumentToDelete(document)}
                      aria-label={`Delete ${document.title}`}
                    >
                      <Trash2 className="h-icon w-icon text-error" />
                    </Button>
                  </div>
                )}
              />
            ))}
          </div>
        )}
      </SectionBlock>
    </div>
  )

  const vectorsTab = (
    <div className="grid gap-ui-md pb-ui-xs">
      <SectionBlock
        title="Vector readiness"
        description={vectorStatusDetail}
        density="compact"
        actions={(
          <div className="flex items-center gap-ui-sm">
            <StatusBadge status={overview?.rag_status || 'UNKNOWN'} size="compact" />
            <Button type="button" size="sm" onClick={() => setBuildModalOpen(true)} disabled={items.length === 0 || hasRunningBuild}>
              <Cpu className="h-icon w-icon" />{buildButtonLabel}
            </Button>
          </div>
        )}
      >
        <div className="grid gap-ui-xs sm:grid-cols-3">
          <MetricTile label="Latest snapshot" value={overview?.latest_ready_snapshot?.version || 'Not built'} detail={`${numberLabel(overview?.latest_ready_snapshot?.chunk_count)} chunks`} />
          <MetricTile label="Documents" value={`${overview?.documents.active ?? items.length} active`} detail={`${overview?.documents.ready ?? indexedCount} ready`} />
          <MetricTile label="Embedding" value={overview?.technology.embedding_model || 'Not selected'} />
        </div>

        {overview?.processing.has_running_job ? (
          <Alert variant="info" className="mt-ui-md">
            <AlertTitle>Building vectors</AlertTitle>
            <AlertDescription>{overview.processing.stage || 'QUEUED'} · {overview.processing.embedded_chunks}/{overview.processing.total_chunks || 0} chunks</AlertDescription>
          </Alert>
        ) : null}

        {latestBuildFailed ? (
          <Alert variant="destructive" className="mt-ui-md">
            <AlertTitle>Vector build failed</AlertTitle>
            <AlertDescription>{latestSnapshot?.error_message || 'The latest vector build failed.'}</AlertDescription>
            {latestSnapshot ? (
              <div className="mt-ui-sm font-mono text-system-meta text-error/80">
                {latestSnapshot.embedding_provider} · {latestSnapshot.embedding_model} · {latestSnapshot.build_stage || 'FAILED'}
              </div>
            ) : null}
          </Alert>
        ) : null}
      </SectionBlock>

      <SectionBlock
        title="Vector snapshots"
        description={onUseSnapshot ? 'Choose a READY version to use in the Agent Draft.' : 'Immutable builds generated from this Collection.'}
        density="compact"
      >
        {vectorSnapshots.length === 0 ? (
          <EmptyStatePanel compact title="No vector snapshot built yet" description="Build vectors from the current Collection documents to create the first immutable snapshot." />
        ) : (
          <div className="grid gap-ui-xs">
            {vectorSnapshots.map((snapshot) => (
              <TechnicalListItem
                key={snapshot.id}
                label={snapshot.version}
                description={`${snapshot.embedding_model} · ${numberLabel(snapshot.chunk_count)} chunks · ${numberLabel(snapshot.vector_count ?? snapshot.chunk_count)} vectors${snapshot.status === 'FAILED' && snapshot.error_message ? ` · ${snapshot.error_message}` : ''}`}
                density="compact"
                meta={<StatusBadge status={snapshot.status} size="compact" />}
                trailing={(
                  <div className="flex items-center gap-ui-sm">
                    <span className="hidden font-mono text-system-meta text-muted-foreground md:inline">
                      {snapshot.completed_at ? formatDate(snapshot.completed_at) : snapshot.build_stage || 'Queued'}
                    </span>
                    {onUseSnapshot && snapshot.status === 'READY' ? (
                      <Button type="button" size="sm" onClick={(event) => { event.stopPropagation(); void onUseSnapshot(snapshot) }}>Use this version</Button>
                    ) : null}
                  </div>
                )}
                onClick={() => setSnapshotToView(snapshot)}
              />
            ))}
          </div>
        )}
      </SectionBlock>
    </div>
  )

  const technologyTab = (
    <SectionBlock title="Technology" description="Configuration captured by the latest vector snapshot." density="compact">
      <div className="grid gap-ui-xs sm:grid-cols-2">
        <TechnicalListItem density="compact" label="Embedding" description={overview?.technology.embedding_model || 'Not selected'} meta={overview?.technology.embedding_provider || 'Managed in Knowledge > Embedding'} />
        <TechnicalListItem
          density="compact"
          label="Chunking"
          description={overview?.technology.chunking_strategy || 'Not configured'}
          meta={overview?.technology.chunk_size ? `${overview.technology.chunk_size} size · ${overview.technology.chunk_overlap ?? 0} overlap` : undefined}
        />
        <TechnicalListItem density="compact" label="Vector store" description={overview?.technology.vector_store || 'pgvector'} meta={overview?.technology.distance_metric || 'cosine'} />
      </div>
    </SectionBlock>
  )

  return (
    <>
      <Dialog
        open={open && Boolean(collection)}
        onClose={close}
        title="Collection details"
        variant="workspace"
      >
        {collection ? (
          <div className="flex h-full min-h-0 flex-col">
            <DialogContextBar>
              <TechnicalListItem
                label={collection.name}
                description={collection.description || 'No description provided'}
                density="compact"
                leading={(
                  <span className="flex h-control-nav w-control-nav items-center justify-center rounded-control border border-primary/25 bg-primary/[0.08] text-primary-light">
                    <Database className="h-icon w-icon" />
                  </span>
                )}
                meta={(
                  <>
                    {collection.status ? <StatusBadge status={collection.status} size="compact" /> : null}
                    <Badge variant="outline" size="compact">{items.length} documents</Badge>
                    <Badge variant="outline" size="compact">{indexedCount} ready</Badge>
                    <Badge variant="outline" size="compact">{formatBytes(totalSize)}</Badge>
                  </>
                )}
              />
            </DialogContextBar>

            <main className="min-h-0 min-w-0 flex-1 p-ui-lg">
              <Tabs
                defaultTab="overview"
                className="flex h-full min-h-0 flex-col"
                contentClassName="scrollbar-thin min-h-0 flex-1 overflow-y-auto overscroll-contain pr-ui-xs"
                tabs={[
                  { id: 'overview', label: 'Overview', content: overviewTab },
                  { id: 'vectors', label: 'Vectors', content: vectorsTab },
                  { id: 'technology', label: 'Technology', content: technologyTab },
                ]}
              />
            </main>

            <DialogFooter
              meta={(
                <p className="font-mono text-system-meta text-muted-foreground">
                  {hasChanges ? 'Unsaved Collection changes' : `${items.length} documents · ${indexedCount} ready · ${formatBytes(totalSize)}`}
                </p>
              )}
              actions={(
                <>
                  <Button type="button" variant="outline" onClick={close} disabled={updateCollection.isPending || deleteDocument.isPending}>Close</Button>
                  <Button type="button" onClick={save} loading={updateCollection.isPending} disabled={!hasChanges}>Save changes</Button>
                </>
              )}
            />
          </div>
        ) : null}
      </Dialog>

      <CollectionDocumentUploadModal
        open={uploadModalOpen}
        projectId={projectId}
        collection={collection ? { id: collection.id, name: collection.name } : null}
        onClose={() => setUploadModalOpen(false)}
        onUploaded={handleUploaded}
      />
      <BuildVectorSnapshotModalV2
        open={buildModalOpen}
        projectId={projectId}
        collection={collection ? { id: collection.id, name: collection.name } : null}
        onClose={() => setBuildModalOpen(false)}
        onCreated={() => { setBuildModalOpen(false); refreshAll() }}
      />
      <VectorSnapshotDetailsModal snapshot={snapshotToView} onClose={() => setSnapshotToView(null)} />

      <Dialog
        open={Boolean(documentToDelete)}
        onClose={() => !deleteDocument.isPending && setDocumentToDelete(null)}
        title="Delete document"
        className="max-w-dialog-compact"
        layer="nestedModal"
      >
        {documentToDelete ? (
          <div className="grid gap-ui-md">
            <Alert variant="destructive">
              <div className="flex items-start gap-ui-sm">
                <AlertTriangle className="mt-ui-hairline h-icon w-icon shrink-0" />
                <div>
                  <AlertTitle>Remove this document?</AlertTitle>
                  <AlertDescription>This action deletes the document record, stored file and generated chunks. It cannot be undone.</AlertDescription>
                </div>
              </div>
            </Alert>
            <TechnicalListItem density="compact" label={documentToDelete.title} description={documentMeta(documentToDelete)} />
            <div className="flex flex-col-reverse gap-ui-sm border-t border-border pt-ui-md sm:flex-row sm:justify-end">
              <Button type="button" variant="outline" onClick={() => setDocumentToDelete(null)} disabled={deleteDocument.isPending}>Cancel</Button>
              <Button type="button" variant="destructive" loading={deleteDocument.isPending} onClick={confirmDelete}>Delete document</Button>
            </div>
          </div>
        ) : null}
      </Dialog>
    </>
  )
}
