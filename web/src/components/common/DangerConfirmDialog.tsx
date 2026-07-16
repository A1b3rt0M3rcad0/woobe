import { type ReactNode } from 'react'
import { AlertTriangle } from 'lucide-react'
import { Dialog } from '@/components/ui/Dialog'
import { Button } from '@/components/ui/Button'

interface DangerConfirmDialogProps {
  open: boolean
  title: string
  description: ReactNode
  confirmLabel: string
  loading?: boolean
  onConfirm: () => void
  onClose: () => void
}

export function DangerConfirmDialog({ open, title, description, confirmLabel, loading, onConfirm, onClose }: DangerConfirmDialogProps) {
  return (
    <Dialog open={open} onClose={onClose} title={title}>
      <div className="space-y-4">
        <div className="rounded-xl border border-red-500/40 bg-red-500/10 p-4">
          <div className="flex items-start gap-3">
            <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0 text-red-400" />
            <div className="text-sm text-red-100">{description}</div>
          </div>
        </div>
        <div className="flex justify-end gap-2">
          <Button type="button" variant="outline" onClick={onClose}>Cancel</Button>
          <Button type="button" variant="destructive" loading={loading} onClick={onConfirm}>{confirmLabel}</Button>
        </div>
      </div>
    </Dialog>
  )
}
