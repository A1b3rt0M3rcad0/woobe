import { useState } from 'react'
import { useDeleteDocument, useDocumentsByCollection } from '@/features/knowledge/hooks'
import { Drawer } from '@/components/ui/Drawer'
import { Dialog } from '@/components/ui/Dialog'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { LoadingState } from '@/components/common/LoadingState'
import { formatBytes } from '@/lib/formatters/bytes'
import { AlertTriangle, RefreshCw, Trash2 } from 'lucide-react'
import { toast } from 'sonner'
import type { Document } from '@/features/knowledge/types'

const documentStatusVariant: Record<string, 'default' | 'secondary' | 'success' | 'warning' | 'destructive'> = {
  uploaded: 'default',
  queued: 'secondary',
  parsing: 'warning',
  parsed: 'secondary',
  chunking: 'warning',
  embedding: 'warning',
  indexing: 'warning',
  indexed: 'success',
  ready: 'success',
  failed: 'destructive',
  deleted: 'destructive',
}

interface DocumentsDrawerProps {
  open: boolean
  onClose: () => void
  collectionId: string
  collectionName: string
}

export function DocumentsDrawer({ open, onClose, collectionId, collectionName }: DocumentsDrawerProps) {
  const { data: documents, isLoading, refetch } = useDocumentsByCollection(collectionId)
  const deleteDocument = useDeleteDocument()
  const [documentToDelete, setDocumentToDelete] = useState<Document | null>(null)

  const closeDeleteModal = () => {
    if (deleteDocument.isPending) return
    setDocumentToDelete(null)
  }

  const handleConfirmDelete = async () => {
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

  return (
    <>
      <Drawer open={open} onClose={onClose} title={`Documents: ${collectionName}`}>
        <div className="space-y-4">
          <div className="flex justify-end">
            <Button variant="outline" size="sm" onClick={() => refetch()}>
              <RefreshCw className="mr-1 h-3 w-3" />
              Refresh
            </Button>
          </div>

          {isLoading ? (
            <LoadingState variant="panel" layout="list" message="Loading documents..." />
          ) : !documents || documents.length === 0 ? (
            <div className="text-center py-8">
              <p className="text-sm text-muted">No documents in this collection.</p>
            </div>
          ) : (
            <div className="space-y-3">
              {documents.map((doc: Document) => (
                <div key={doc.id} className="rounded-lg border border-border p-4 space-y-2">
                  <div className="flex items-start justify-between gap-2">
                    <div className="min-w-0 flex-1">
                      <p className="text-sm font-medium truncate">{doc.title}</p>
                      <p className="text-xs text-muted truncate">{doc.file_name}</p>
                    </div>
                    <div className="flex shrink-0 items-center gap-2">
                      <Badge variant={documentStatusVariant[doc.status] || 'default'}>
                        {doc.status}
                      </Badge>
                      <Button
                        type="button"
                        variant="ghost"
                        size="icon"
                        className="h-8 w-8 text-muted hover:bg-red-500/10 hover:text-red-400"
                        onClick={() => setDocumentToDelete(doc)}
                        aria-label={`Delete document ${doc.title || doc.file_name}`}
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </div>
                  </div>
                  <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted">
                    <span>{formatBytes(doc.size_bytes)}</span>
                    <span>{doc.content_type}</span>
                    {doc.page_count != null && <span>{doc.page_count} pages</span>}
                    {doc.chunk_count != null && <span>{doc.chunk_count} chunks</span>}
                  </div>
                  {doc.status === 'indexed' && doc.indexed_at && (
                    <p className="text-xs text-emerald-400">Indexed: {new Date(doc.indexed_at).toLocaleString()}</p>
                  )}
                  {doc.status === 'failed' && doc.error && (
                    <div className="rounded bg-red-500/10 p-2">
                      <p className="text-xs text-red-400">{doc.error}</p>
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      </Drawer>

      <Dialog
        open={Boolean(documentToDelete)}
        onClose={closeDeleteModal}
        title="Delete document"
        className="max-w-[460px]"
      >
        {documentToDelete && (
          <div className="space-y-5">
            <div className="flex gap-3">
              <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-red-500/20 bg-red-500/10 text-red-400">
                <AlertTriangle className="h-5 w-5" />
              </div>
              <div className="min-w-0 space-y-1">
                <p className="text-sm font-medium text-white">Remove this document from the collection?</p>
                <p className="text-sm leading-6 text-muted">
                  This action deletes the document record and its stored file. It cannot be undone.
                </p>
              </div>
            </div>

            <div className="rounded-xl border border-border bg-background/70 p-3">
              <p className="truncate text-sm font-medium text-white">{documentToDelete.title}</p>
              <p className="mt-1 truncate text-xs text-muted">{documentToDelete.file_name}</p>
              <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted">
                <span>{formatBytes(documentToDelete.size_bytes)}</span>
                <span>{documentToDelete.content_type}</span>
                <span>{documentToDelete.status}</span>
              </div>
            </div>

            <div className="flex flex-col-reverse gap-2 border-t border-border pt-4 sm:flex-row sm:justify-end">
              <Button type="button" variant="outline" onClick={closeDeleteModal} disabled={deleteDocument.isPending}>
                Cancel
              </Button>
              <Button
                type="button"
                variant="destructive"
                loading={deleteDocument.isPending}
                onClick={handleConfirmDelete}
              >
                Delete document
              </Button>
            </div>
          </div>
        )}
      </Dialog>
    </>
  )
}
