import { AlertTriangle, Save } from 'lucide-react'
import { Alert, AlertDescription, Button, Dialog, TechnicalListItem } from '@woobe/ui'

import type { Environment } from './networkWorkspaceTypes'

export function NetworkUnsavedChangesDialog({
  target,
  networkDirty,
  agentNames,
  pending,
  onClose,
  onConfirm,
}: {
  target: Environment
  networkDirty: boolean
  agentNames: string[]
  pending: boolean
  onClose: () => void
  onConfirm: () => void
}) {
  return (
    <Dialog open onClose={onClose} title="Save Draft changes?" className="max-w-dialog-compact">
      <div className="space-y-ui-md">
        <Alert variant="warning">
          <AlertDescription>
            <span className="flex items-start gap-ui-sm">
              <AlertTriangle className="mt-ui-hairline h-icon w-icon shrink-0" />
              <span>Draft changes must be saved before opening {target}. The environment will only change after every required save succeeds.</span>
            </span>
          </AlertDescription>
        </Alert>

        <div className="space-y-ui-sm">
          {networkDirty ? <TechnicalListItem label="Network composition and settings" /> : null}
          {agentNames.map((name) => <TechnicalListItem key={name} label={`Agent Draft · ${name}`} />)}
        </div>

        <div className="flex justify-end gap-ui-sm border-t border-border pt-ui-md">
          <Button type="button" variant="outline" disabled={pending} onClick={onClose}>Stay in Draft</Button>
          <Button type="button" disabled={pending} onClick={onConfirm}>
            <Save className="mr-ui-xs h-icon-sm w-icon-sm" />
            {pending ? 'Saving…' : `Save and open ${target}`}
          </Button>
        </div>
      </div>
    </Dialog>
  )
}
