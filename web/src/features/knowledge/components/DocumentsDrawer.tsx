import { useDocumentsByCollection } from '@/features/knowledge/hooks'
import { Drawer } from '@/components/ui/Drawer'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { LoadingState } from '@/components/common/LoadingState'
import { formatBytes } from '@/lib/formatters/bytes'
import { RefreshCw } from 'lucide-react'
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

  return (
    <Drawer open={open} onClose={onClose} title={`Documents: ${collectionName}`}>
      <div className="space-y-4">
        <div className="flex justify-end">
          <Button variant="outline" size="sm" onClick={() => refetch()}>
            <RefreshCw className="mr-1 h-3 w-3" />
            Refresh
          </Button>
        </div>

        {isLoading ? (
          <LoadingState />
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
                  <Badge variant={documentStatusVariant[doc.status] || 'default'}>
                    {doc.status}
                  </Badge>
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
  )
}
