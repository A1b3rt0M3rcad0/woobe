import type { ReactNode } from 'react'
import { AlertTriangle } from 'lucide-react'
import { Button } from './Button'
import { Dialog } from './Dialog'

export interface DangerConfirmDialogProps {
  open: boolean
  title: string
  description: ReactNode
  confirmLabel: string
  loading?: boolean
  disabled?: boolean
  onConfirm: () => void
  onClose: () => void
}

export function DangerConfirmDialog({
  open,
  title,
  description,
  confirmLabel,
  loading = false,
  disabled = false,
  onConfirm,
  onClose,
}: DangerConfirmDialogProps) {
  return (
    <Dialog open={open} onClose={onClose} title={title} className="max-w-lg">
      <div className="space-y-ui-lg">
        <div className="rounded-container border border-red-500/35 bg-red-500/[0.06] p-ui-lg">
          <div className="flex items-start gap-ui-md">
            <div className="mt-px flex h-7 w-7 shrink-0 items-center justify-center rounded-control border border-red-500/25 bg-red-500/10 text-red-300">
              <AlertTriangle className="h-3.5 w-3.5" />
            </div>
            <div className="font-sans text-product-caption leading-5 text-slate-300">{description}</div>
          </div>
        </div>
        <div className="flex justify-end gap-ui-sm border-t border-border pt-ui-md">
          <Button type="button" variant="outline" onClick={onClose}>Cancel</Button>
          <Button type="button" variant="destructive" loading={loading} disabled={disabled} onClick={onConfirm}>
            {confirmLabel}
          </Button>
        </div>
      </div>
    </Dialog>
  )
}
