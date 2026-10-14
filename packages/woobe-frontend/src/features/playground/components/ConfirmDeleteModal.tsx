import { DangerConfirmDialog } from '@woobe/ui'

interface ConfirmDeleteModalProps {
  open: boolean
  onClose: () => void
  onConfirm: () => void
  versionName: string
  isPending: boolean
}


export function ConfirmDeleteModal({ open, onClose, onConfirm, versionName, isPending }: ConfirmDeleteModalProps) {
  return <DangerConfirmDialog open={open} onClose={onClose} onConfirm={onConfirm}
    title="Delete version" confirmLabel="Delete" loading={isPending}
    description={<>Delete {versionName}? This version will be permanently removed. This action cannot be undone.</>} />
}
