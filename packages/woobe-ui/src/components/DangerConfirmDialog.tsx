import type { ReactNode } from 'react'
import { AlertTriangle } from 'lucide-react'
import { Alert, AlertDescription } from './Alert'
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
    <Dialog open={open} onClose={onClose} title={title} className="max-w-dialog-compact">
      <div className="space-y-ui-lg">
        <Alert variant="destructive">
          <AlertDescription>
            <span className="flex items-start gap-ui-sm">
              <AlertTriangle className="mt-ui-hairline h-icon w-icon shrink-0" />
              <span>{description}</span>
            </span>
          </AlertDescription>
        </Alert>
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
