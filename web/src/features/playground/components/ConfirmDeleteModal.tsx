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
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4 backdrop-blur-md"
      onClick={(e) => { if (e.target === e.currentTarget) onClose() }}
    >
      <div className="w-full max-w-md overflow-hidden rounded-2xl border border-border/90 bg-surface/95 shadow-2xl shadow-black/40">
        <div className="flex items-center justify-between border-b border-border/90 bg-background/20 p-4">
          <h2 className="text-sm font-semibold text-white">Delete version</h2>
          <button onClick={onClose} className="rounded-lg border border-transparent p-1 text-muted transition-colors hover:border-border/80 hover:bg-background/60 hover:text-white">
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="p-4">
          <div className="flex items-start gap-3 rounded-xl border border-red-500/30 bg-red-500/10 p-3">
            <AlertTriangle className="h-5 w-5 text-red-300 shrink-0 mt-0.5" />
            <div>
              <p className="text-sm text-white font-medium">Delete {versionName}?</p>
              <p className="text-xs text-muted mt-1">This version will be permanently removed. This action cannot be undone.</p>
            </div>
          </div>
        </div>

        <div className="flex items-center justify-end gap-2 border-t border-border/90 bg-background/20 p-4">
          <Button size="sm" variant="outline" onClick={onClose}>Cancel</Button>
          <Button size="sm" variant="ghost" className="border border-red-500/30 bg-red-500/10 text-red-200 hover:bg-red-500/15 hover:text-red-100" onClick={onConfirm} loading={isPending}>
            Delete
          </Button>
        </div>
      </div>
    </div>
  )
}
