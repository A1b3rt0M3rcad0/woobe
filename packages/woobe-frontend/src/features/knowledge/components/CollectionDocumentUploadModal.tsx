import { CollectionDocumentUploadPanel } from '@/features/knowledge/components/CollectionDocumentUploadPanel'
import { Dialog } from '@/components/ui/Dialog'

interface CollectionDocumentUploadModalProps {
  open: boolean
  projectId: string
  collection: { id: string; name: string } | null
  onClose: () => void
  onUploaded: () => void
}

export function CollectionDocumentUploadModal({
  open,
  projectId,
  collection,
  onClose,
  onUploaded,
}: CollectionDocumentUploadModalProps) {
  return (
    <Dialog
      open={open && Boolean(collection)}
      onClose={onClose}
      title="Upload document"
      className="max-h-[calc(100svh-2rem)] max-w-2xl overflow-hidden"
    >
      {collection && (
        <div className="max-h-[calc(100svh-8rem)] overflow-y-auto pr-1">
          <CollectionDocumentUploadPanel
            projectId={projectId}
            collection={collection}
            onCancel={onClose}
            onUploaded={onUploaded}
          />
        </div>
      )}
    </Dialog>
  )
}
