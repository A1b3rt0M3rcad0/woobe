import { Dialog } from '@woobe/ui'

import { CollectionDocumentUploadPanel } from '@/features/knowledge/components/CollectionDocumentUploadPanel'

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
      className="flex max-h-dialog max-w-dialog flex-col overflow-hidden"
      contentClassName="min-h-0 flex-1 p-0"
    >
      {collection ? (
        <div className="scrollbar-thin h-full min-h-0 overflow-y-auto p-ui-lg">
          <CollectionDocumentUploadPanel
            projectId={projectId}
            collection={collection}
            onCancel={onClose}
            onUploaded={onUploaded}
          />
        </div>
      ) : null}
    </Dialog>
  )
}
