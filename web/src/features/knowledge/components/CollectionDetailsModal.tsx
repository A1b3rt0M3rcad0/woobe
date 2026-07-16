import { useEffect, useMemo, useState } from 'react'
import { AlertTriangle, Database, FileText, RefreshCw, Trash2, Upload } from 'lucide-react'
import { toast } from 'sonner'
import { LoadingState } from '@/components/common/LoadingState'
import { StatusBadge } from '@/components/common/StatusBadge'
import { Button } from '@/components/ui/Button'
import { Dialog } from '@/components/ui/Dialog'
import { Input } from '@/components/ui/Input'
import { Textarea } from '@/components/ui/Textarea'
import { CollectionDocumentUploadModal } from '@/features/knowledge/components/CollectionDocumentUploadModal'
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

function isIndexed(status?: string) {
  const normalized = status?.toLowerCase()
  return normalized === 'indexed' || normalized === 'ready'
}

function documentMeta(document: Document) {
  return [document.file_name, formatBytes(document.size_bytes), document.content_type].filter(Boolean).join(' · ')
}

export function CollectionDetailsModal({ open, onClose, collection, projectId }: CollectionDetailsModalProps) {
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [uploadModalOpen, setUploadModalOpen] = useState(false)
  const [documentToDelete, setDocumentToDelete] = useState<Document | null>(null)

  const updateCollection = useUpdateCollection()
  const deleteDocument = useDeleteDocument()
  const { data: documents, isLoading, refetch } = useDocumentsByCollection(collection?.id)

  useEffect(() => {
    if (!collection) return
    setName(collection.name)
    setDescription(collection.description || '')
    setUploadModalOpen(false)
    setDocumentToDelete(null)
  }, [collection])

  const items = documents ?? []
  const indexedCount = useMemo(() => items.filter((document) => isIndexed(document.status)).length, [items])
  const totalSize = useMemo(() => items.reduce((sum, document) => sum + document.size_bytes, 0), [items])
  const hasChanges = collection ? name.trim() !== collection.name || description.trim() !== (collection.description || '') : false

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
      void refetch()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to delete document')
    }
  }

  const openUploadModal = () => {
    setUploadModalOpen(true)
  }

  const handleUploaded = () => {
    setUploadModalOpen(false)
    void refetch()
  }

  return (
    <>
      <Dialog open={open && Boolean(collection)} onClose={close} title="Collection details" className="max-h-[calc(100svh-2rem)] max-w-5xl overflow-hidden">
        {collection && (
          <div className="max-h-[calc(100svh-8rem)] overflow-y-auto pr-1">
            <div className="grid gap-6 lg:grid-cols-[280px_minmax(0,1fr)]">
              <aside className="space-y-4 lg:sticky lg:top-0 lg:self-start">
                <div className="rounded-xl border border-border/80 bg-background/70 p-4">
                  <div className="flex h-12 w-12 items-center justify-center rounded-xl border border-border bg-surface text-primary-light">
                    <Database className="h-5 w-5" />
                  </div>
                  <div className="mt-4 flex items-start justify-between gap-3">
                    <h3 className="truncate text-base font-semibold text-white">{collection.name}</h3>
                    {collection.status && <StatusBadge status={collection.status} />}
                  </div>
                  <p className="mt-2 line-clamp-4 text-sm leading-6 text-muted">{collection.description || 'No description provided'}</p>
                  <div className="mt-4 flex flex-wrap gap-2 text-xs">
                    <span className="rounded-full border border-primary/30 bg-primary/10 px-2.5 py-1 text-primary-light">{items.length} documents</span>
                    <span className="rounded-full border border-border/80 bg-background/70 px-2.5 py-1 text-muted">{indexedCount} indexed</span>
                    <span className="rounded-full border border-border/80 bg-background/70 px-2.5 py-1 text-muted">{formatBytes(totalSize)}</span>
                  </div>
                </div>

                <div className="rounded-xl border border-border/80 bg-surface/65 p-4 text-xs">
                  <h3 className="text-sm font-semibold text-white">Metadata</h3>
                  <dl className="mt-4 space-y-3">
                    <div><dt className="text-muted">Collection ID</dt><dd className="mt-1 break-all font-mono text-white/80">{collection.id}</dd></div>
                    <div><dt className="text-muted">Created</dt><dd className="mt-1 text-white/80">{collection.created_at ? formatDate(collection.created_at) : '-'}</dd></div>
                    <div><dt className="text-muted">Updated</dt><dd className="mt-1 text-white/80">{collection.updated_at ? formatDate(collection.updated_at) : '-'}</dd></div>
                  </dl>
                </div>
              </aside>

              <main className="space-y-5">
                <section className="rounded-xl border border-border/80 bg-surface/65 p-4">
                  <h3 className="text-sm font-semibold text-white">Collection information</h3>
                  <p className="mt-1 text-xs text-muted">Edit the collection identity used across Knowledge.</p>
                  <div className="mt-4 space-y-4">
                    <div><label className="mb-1.5 block text-[11px] font-medium uppercase tracking-wider text-muted">Name</label><Input value={name} onChange={(event) => setName(event.target.value)} /></div>
                    <div><label className="mb-1.5 block text-[11px] font-medium uppercase tracking-wider text-muted">Description</label><Textarea value={description} onChange={(event) => setDescription(event.target.value)} className="min-h-[120px]" /></div>
                  </div>
                </section>

                <section className="rounded-xl border border-border/80 bg-surface/65 p-4">
                  <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                    <div>
                      <h3 className="text-sm font-semibold text-white">Documents</h3>
                      <p className="mt-1 text-xs leading-5 text-muted">{items.length} files · {indexedCount} indexed · {formatBytes(totalSize)} total</p>
                    </div>
                    <div className="flex gap-2">
                      <Button type="button" variant="outline" size="sm" onClick={() => void refetch()} disabled={isLoading}><RefreshCw className="mr-2 h-3.5 w-3.5" />Refresh</Button>
                      <Button type="button" size="sm" onClick={openUploadModal}><Upload className="mr-2 h-3.5 w-3.5" />Upload</Button>
                    </div>
                  </div>

                  {isLoading ? (
                    <div className="rounded-xl border border-border/70 bg-background/60 p-8"><LoadingState message="Loading documents..." variant="inline" /></div>
                  ) : items.length === 0 ? (
                    <div className="flex min-h-[220px] flex-col items-center justify-center rounded-xl border border-dashed border-border/80 bg-background/50 p-6 text-center">
                      <FileText className="h-5 w-5 text-muted" />
                      <p className="mt-4 text-sm font-medium text-white">No documents in this collection.</p>
                      <p className="mt-2 max-w-sm text-sm leading-6 text-muted">Upload source material to make it available for retrieval.</p>
                      <Button type="button" onClick={openUploadModal} className="mt-5"><Upload className="mr-2 h-4 w-4" />Upload document</Button>
                    </div>
                  ) : (
                    <div className="space-y-2">
                      {items.map((document) => (
                        <div key={document.id} className="grid gap-3 rounded-lg border border-border/70 bg-background/55 p-3 lg:grid-cols-[minmax(0,1fr)_auto] lg:items-center">
                          <div className="flex min-w-0 gap-3">
                            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-border bg-surface text-primary-light"><FileText className="h-4 w-4" /></div>
                            <div className="min-w-0">
                              <div className="flex flex-wrap items-center gap-2"><p className="truncate text-sm font-medium text-white">{document.title}</p>{document.status && <StatusBadge status={document.status} />}</div>
                              <p className="mt-1 truncate text-xs text-muted">{documentMeta(document)}</p>
                              <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-[11px] text-muted"><span>Chunks: {document.chunk_count ?? 0}</span><span>Pages: {document.page_count ?? '-'}</span><span>Created: {document.created_at ? formatDate(document.created_at) : '-'}</span></div>
                            </div>
                          </div>
                          <Button type="button" variant="ghost" size="icon" className="h-8 w-8 justify-self-end text-red-400 hover:text-red-300" disabled={deleteDocument.isPending} onClick={() => setDocumentToDelete(document)} aria-label={`Delete ${document.title}`}><Trash2 className="h-4 w-4" /></Button>
                        </div>
                      ))}
                    </div>
                  )}
                </section>
              </main>
            </div>

            <div className="sticky bottom-0 -mx-1 mt-6 flex flex-col-reverse gap-2 border-t border-border bg-surface/95 px-1 py-4 backdrop-blur sm:flex-row sm:justify-end">
              <Button type="button" variant="outline" onClick={close} disabled={updateCollection.isPending || deleteDocument.isPending}>Close</Button>
              <Button type="button" onClick={save} loading={updateCollection.isPending} disabled={!hasChanges}>Save changes</Button>
            </div>
          </div>
        )}
      </Dialog>

      <CollectionDocumentUploadModal
        open={uploadModalOpen}
        projectId={projectId}
        collection={collection ? { id: collection.id, name: collection.name } : null}
        onClose={() => setUploadModalOpen(false)}
        onUploaded={handleUploaded}
      />

      <Dialog open={Boolean(documentToDelete)} onClose={() => !deleteDocument.isPending && setDocumentToDelete(null)} title="Delete document" className="max-w-[460px]">
        {documentToDelete && <div className="space-y-5"><div className="flex gap-3"><div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-red-500/20 bg-red-500/10 text-red-400"><AlertTriangle className="h-5 w-5" /></div><div><p className="text-sm font-medium text-white">Remove this document?</p><p className="text-sm leading-6 text-muted">This action deletes the document record, stored file and generated chunks. It cannot be undone.</p></div></div><div className="rounded-xl border border-border bg-background/70 p-3"><p className="truncate text-sm font-medium text-white">{documentToDelete.title}</p><p className="mt-1 truncate text-xs text-muted">{documentMeta(documentToDelete)}</p></div><div className="flex flex-col-reverse gap-2 border-t border-border pt-4 sm:flex-row sm:justify-end"><Button type="button" variant="outline" onClick={() => setDocumentToDelete(null)} disabled={deleteDocument.isPending}>Cancel</Button><Button type="button" variant="destructive" loading={deleteDocument.isPending} onClick={confirmDelete}>Delete document</Button></div></div>}
      </Dialog>
    </>
  )
}
