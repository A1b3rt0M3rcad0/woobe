import { Alert, AlertDescription, DangerConfirmDialog } from '@woobe/ui'

export function NetworkRemoveDialog({
  title,
  description,
  impact,
  onClose,
  onConfirm,
}: {
  title: string
  description: string
  impact: string
  onClose: () => void
  onConfirm: () => void
}) {
  return (
    <DangerConfirmDialog
      open
      title={title}
      description={(
        <span className="space-y-ui-md">
          <span className="block">{description}</span>
          <Alert variant="warning">
            <AlertDescription>{impact}</AlertDescription>
          </Alert>
        </span>
      )}
      confirmLabel="Remove"
      onClose={onClose}
      onConfirm={onConfirm}
    />
  )
}
