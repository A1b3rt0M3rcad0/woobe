import { X, AlertTriangle } from 'lucide-react'
import { Button } from '@/components/ui/Button'

interface ConfirmDeleteModalProps {
  open: boolean
  onClose: () => void
  onConfirm: () => void
  versionName: string
  isPending: boolean
}

export function ConfirmDeleteModal({ open, onClose, onConfirm, versionName, isPending }: ConfirmDeleteModalProps) {
  if (!open) return null

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60"
      onClick={(e) => { if (e.target === e.currentTarget) onClose() }}
    >
      <div className="w-full max-w-sm rounded-xl border border-border bg-surface shadow-xl">
        <div className="flex items-center justify-between p-4 border-b border-border">
          <h2 className="text-sm font-semibold text-white">Delete version</h2>
          <button onClick={onClose} className="p-1 rounded-md text-muted hover:text-white hover:bg-accent transition-colors">
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="p-4 space-y-4">
          <div className="flex items-start gap-3">
            <AlertTriangle className="h-5 w-5 text-red-400 shrink-0 mt-0.5" />
            <div>
              <p className="text-sm text-white font-medium">Delete {versionName}?</p>
              <p className="text-xs text-muted mt-1">
                This version will be permanently removed. This action cannot be undone.
              </p>
            </div>
          </div>
        </div>

        <div className="flex items-center justify-end gap-2 p-4 border-t border-border">
          <Button size="sm" variant="outline" onClick={onClose}>Cancel</Button>
          <Button size="sm" variant="ghost" className="text-red-400 hover:text-red-300 hover:bg-red-500/10" onClick={onConfirm} loading={isPending}>
            Delete
          </Button>
        </div>
      </div>
    </div>
  )
}
