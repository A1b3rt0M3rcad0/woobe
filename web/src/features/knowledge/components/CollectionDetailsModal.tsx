import { useEffect, useMemo, useState, type ReactNode } from 'react'
import { AlertTriangle, Database, FileText, RefreshCw, Trash2, Upload } from 'lucide-react'
import { toast } from 'sonner'
import { LoadingState } from '@i/components/common/LoadingState'
import { StatusBadge } from '@/components/common/StatusBadge'
import { Button } from '@/components/ui/Button'
import { Dialog } from '@/components/ui/Dialog'
import { Input } from '@i/components/ui/Input'
import { Textarea } from '@/components/ui/Textarea'
import { CollectionDocumentUploadPanel } from '@/features/knowledge/components/CollectionDocumentUploadPanel'
import { useDeleteDocument, useDocumentsByCollection, useUpdateCollection } from '@/features/knowledge/hooks'
import { formatBytes } from '@/lib/formatters/bytes'
import { formatDate } from '@/lib/formatters/date'
import type { Collection, Document } from '@/features/knowledge/types'

interface CollectionDetailsModalProps {
  open: boolean
  onClose: () => void
  collection: Collection | null
  projectId: string
}

function Section({ title, description, children }: { title: string; description?: string; children: ReactNode }) {
  return (
    <section className="rounded-xl border border-border/80 bg-surface/65 p-4">
      <div className="mb-4">
        <h3 className="text-sm font-semibold text-white">{title}</h3>
        {description && <p className="mt-1 text-xs leading-5 text-muted">{description}</p>}
      </div>
      {children}
    </section>
  )
}

function Pill({ children, tone = 'default' }: { children: ReactNode; tone?: 'default' | 'primary' | 'danger' }) {
  const toneClass = tone === 'primary'
    ? 'border-primary/30 bg-primary/10 text-primary-light'
    : tone === 'danger'
      ? 'border-red-500/30 bg-red-500/10 text-red-200'
      : 'border-border/80 bg-background/70 text-muted'
  return <span className={`rounded-full border px-2.5 py-1 text-xs ${toneClass}`}>{children}</span>
}

function isIndexedStatus(status: string | undefined): boolean {
  const normalized = status?.toLowerCase()
  return normalized === 'indexed' || normalized === 'ready'
}

function documentMeta(document: Document): string {
  return [document.file_name, formatBytes(document.size_bytes), document.content_type].filter(Boolean).join(' × ')
}

export function CollectionDetailsModal({ open, onClose, collection, projectId }: CollectionDetailsModalProps) {
  const [editName, setEditName] = useState('')
  const [editDescription, setEditDescription] = useState('')
  const [showUpload, setShowUpload] = useState(false)
  const [documentToDelete, setDocumentToDelete] = useState<Document | null>(null)

  const updateCollection = useUpdateCollection()
  const deleteDocument = useDeleteDocument()
  const {
    data: documents,
    isLoading: documentsLoading,
    refetch: refetchDocuments,
  } = useDocumentsByCollection(collection?.id)

  useEffect(() => {
    if (!collection) return
    setEditName(collection.name)
    setEditDescription(collection.description || '')
    setShowUpload(false)
    setDocumentToDelete(null)
  }, [collection])

  const documentItems = documents ?? []
  const indexedCount = useMemo(() => documentItems.filter((document) => isIndexedStatus(document.status)).length, [documentItems])
  const totalSize = useMemo(() => documentItems.reduce((acc, document) => acc + document.size_bytes, 0), [documentItems])
  const hasChanges = collection
    ? editName.trim() !== collection.name || editDescription.trim() !== (collection.description || '')
    : false

  const closeModal = () => {
    if (updateCollection.isPending || deleteDocument.isPending) return
    onClose()
  }

  const closeDeleteModal = () => {
    if (deleteDocument.isPending) return
    setDocumentToDelete(null)
  }

  const handleSave = async () => {
    if (!collection) return
    const name = editName.trim()
    if (!name) {
      toast.error('Collection name is required')
      return
    }
    try {
      await updateCollection.mutateAsync({id: collection.id, data: { name, description: editDescription.trim() || null }})
      toast.success('Collection updated')
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to update collection')
    }
  }

  const handleConfirmDeleteDocument = async () => {
    if (!documentToDelete) return
    try {
      await deleteDocument.mutateAsync(documentToDelete.id)
      toast.success('Document deleted')
      setDocumentToDelete(null)
      void refetchDocuments()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to delete document')
    }
  }

  const refreshDocuments = () => {
    void refetchDocuments()
  }

  const handleUploaded = () => {
    setShowUpload(false)
    void refetchDocuments()
  }

  return (
    <>
      <Dialog
        open={open && Boolean(collection)}
        onClose={closeModal}
        title="Collection details"
        className="max-h-[calc(100svh-2rem)] max-w-5xl overflow-hidden"
      >
        {collection && (
          <div className="max-h-[calc(100svh-8rem)] overflow-y-auto pr-1">
            <div className="grid gap-6 lg:grid-cols-[280px_minmax(0,1fr)]">
              <aside className="space-y-4 lg:sticky lg:top-0 lg:self-start">
                <div className="rounded-xl border border-border/80 bg-background/70 p-4">
                  <div className="flex h-12 w-12 items-center justify-center rounded-xl border border bg-surface text-primary-light">
                    <Database className="h-5 w-5" />
                  </div>
                  <div className="mt-4 min-w-0">
                    <div className="flex items-start justify-between gap-3">
                      <h3 className="truncate text-base font-semibold text-white">{collection.name}</h3>
                      {collection.status && <StatusBadge status={collection.status} />}
                    </div>
                    <p className="mt-2 line-clamp-4 text-sm leading-6 text-muted">
                      {collection.description || 'No description provided'}
                    </p>
                  </div>
                  <div className="mt-4 flex flex-wrap gap-2">
                    <Pill tone="primary">{documentItems.length} documents</Pill>
                    <Pill>{indexedCount} indexed</Pill>
                    <Pill>{formatBytes(totalSize)}</Pill>
                  </div>
                </div>

                <Section title="Metadata">
                  <dl className="space-y-3 text-xs">
                    <div>
                      <dt className="text-muted">Collection ID</dt>
                      <dd className="mt-1 break-all font-mono text-white/80">{collection.id}</dd>
                    </div>
                    <div>
                      <dt className="text-muted">Created</dt>
                      <dd className="mt-1 text-white/80">{collection.created_at ? formatDate(collection.created_at) : '-'}</dd>
                    </div>
                    <div>
                      <dt className="text-muted">Updated</dt>
                      <dd className="mt-1 text-white/80">{collection.updated_at ? formatDate(collection.updated_at) : '-'}</dd>
                    </div>
                  </dl>
                </Section>
              </aside>

              <main className="space-y-5">
                <Section title="Collection information" description="Edit the collection name and description used across Knowledge.">
                  <div className="space-y-4">
                    <div>
                      <label className="mb-1.5 block text-[11px] font-medium uppercase tracking-wider text-muted">Name</label>
                      <Input value={editName} onChange={(event) => setEditName(event.target.value)} placeholder="Collection name" />
                    </div>
                    <div>
                      <label className="mb-1.5 block text-[11px] font-medium uppercase tracking-wider text-muted">Description</label>
                      <Textarea
                        value={editDescription}
                        onChange={(event) => setEditDescription(event.target.value)}
                        placeholder="Optional description"
                        className="min-h-[120px]"
                      />
                    </div>
                  </div>
                </Section>

                <section className="rounded-xl border border-border/80 bg-surface/65 p-4">
                  <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                    <div>
                      <h3 className="text-sm font-semibold text-white">{showUpload ? 'Upload document' : 'Documents'}</h3>
                      <p className="mt-1 text-xs leading-5 text-muted">
                        {showUpload
                          ? `Upload directly to ${collection.name}. The collection is already selected.`
                          : `${documentItems.length} files · ${indexedCount} indexed · ${formatBytes(totalSize)} total`}
                      </p>
                    </div>
                    <div className="flex gap-2">
                      {showUpload ? (
                        <Button type="button" variant="outline" size="sm" onClick={() => setShowUpload(false)}>
                          Back to documents
                        </Button>
                      ) : (
                        <>
                          <Button type="button" variant="outline" size="sm" onClick={refreshDocuments} disabled={documentsLoading}>
                            <RefreshCw className="mr-2 h-3.5 w-3.5" />
                          Refresh
                          </Button>
                          <Button type="button" size="sm" onClick={() => setShowUpload(true)}>
                          <Upload className="mr-2 h-3.5 w-3.5" />
                          Upload
                        </Button>
                        </>
                      )}
                    </div>
                  </div>

                  {showUpload ? (
                    <CollectionDocumentUploadPanel
                      projectId={projectId}
                      collection={{ id: collection.id, name: collection.name }}
                      onCancel={() => setShowUpload(false)}
                      onUploaded={handleUploaded}
                    />
                  ) : documentsLoading ? (
                    <div className="rounded-xl border border-border/70 bg-background/60 p-8">
                      <LoadingState message="Loading documents..." variant="inline" />
                    </div>
                  ) : documentItems.length === 0 ? (
                    <div className="flex min-h-[220px] flex-col items-center justify-center rounded-xl border border-dashed border-border/80 bg-background/50 p-6 text-center">
                      <div className="flex h-11 w-11 items-center justify-center rounded-xl border border bg-surface text-muted">
                        <FileText className="h-5 w-5" />
                      </div>
                      <p className="mt-4 text-sm font-medium text-white">No documents in this collection.</p>
                      <p className="mt-2 max-w-sm text-sm leading-6 text-muted">Upload source material to make it available for retrieval.</p>
                      <Button type="button" onClick={() => setShowUpload(true)} className="mt-5">
                        <Upload className="mr-2 h-4 w-4" />
                        Upload document
                      </Button>
                    </div>
                  ) : (
                    <div className="space-y-2">
                      {documentItems.map((document) => (
                        <div
                          key={document.id}
                          className="grid gap-3 rounded-lg border border-border/70 bg-background/55 p-3 lg:grid-cols-[minmax(0,1fr)_auto] lg:items-center"
                        >
                          <div className="flex min-w-0 gap-3">
                            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border bg-surface text-primary-light">
                              <FileText className="h-4 w-4" />
                            </div>
                            <div className="min-w-0">
                              <div className="flex min-w-0 flex-wrap items-center gap-2">
                                <p className="truncate text-sm font-medium text-white">{document.title}</p>
                                {document.status && <StatusBadge status={document.status} />}
                              </div>
                              <p className="mt-1 truncate text-xs text-muted">{documentMeta(document)}</p>
                              <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-[11px] text-muted">
                                <span>Chunks: {document.chunk_count ?? 0}</span>
                                <span>Pages: {document.page_count ?? '-'}</span>
                                <span>Created: {document.created_at ? formatDate(document.created_at) : '-'}</span>
                              </div>
                            </div>
                          </div>

                          <Button
                            type="button"
                            variant="ghost"
                            size="icon"
                            className="h-8 w-8 justify-self-end text-red-400 hover:text-red-300"
                            disabled={deleteDocument.isPending}
                            onClick={() => setDocumentToDelete(document)}
                            aria-label={@Delete ${document.title}`}
                          >
                            <Trash2 className="h-4 w-4" />
                          </Button>
                        </div>
                      ))}
                    </div>
                  )}
                </section>
              </main>
            </div>

            <div className="sticky bottom-0 -mx-1 mt-6 flex flex-col-reverse gap-2 border-t border-border bg-surface/95 px-1 py-4 backdrop-blur sm:flex-row sm:justify-end">
              <Button type="button" variant="outline" onClick={closeModal} disabled={updateCollection.isPending || deleteDocument.isPending}>
                Close
              </Button>
              <Button type="button" onClick={handleSave} loading={updateCollection.isPending} disabled={!hasChanges}>
                Save changes
              </Button>
            </div>
          </div>
        )}
      </Dialog>

      <Dialog open={Boolean(documentToDelete)} onClose={closeDeleteModal} title="Delete document" className="max-w[[460px]">
        {documentToDelete && (
          <div className="space-y-5">
            <div className="flex gap-3">
              <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-red-500/20 bg-red-500/10 text-red-400">
                <AlertTriangle className="h-5 w-5" />
              </div>
              <div className="min-w-0 space-y-1">
                <p className="text-sm font-medium text-white">Remove this document?</p>
                <p className="text-sm leading-6 text-muted">This action deletes the document record, stored file and generated chunks. It cannot be undone.</p>
              </div>
            </div>

            <div className="rounded-xl border border-border bg-background/70 p-3">
              <p className="truncate text-sm font-medium text-white">{documentToDelete.title}</p>
              <p className="mt-1 truncate text-xs text-muted">{documentMeta(documentToDelete)}</p>
            </div>

            <div className="flex flex-col-reverse gap-2 border-t border-border pt-4 sm:flex-row sm:justify-end">
              <Button type="button" variant="outline" onClick={closeDeleteModal} disabled={deleteDocument.isPending}>
                Cancel
              </Button>
              <Button type="button" variant="destructive" loading={deleteDocument.isPending} onClick={handleConfirmDeleteDocument}>
                Delete document
              </Button>
            </div>
          </div>
        )}
      </Dialog>
    </>
  )
}
