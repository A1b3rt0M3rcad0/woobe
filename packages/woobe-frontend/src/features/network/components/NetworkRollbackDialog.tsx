import { useMemo, useState } from 'react'
import { History, RotateCcw } from 'lucide-react'
import { Alert, AlertDescription, Button, Dialog, EmptyStatePanel, TechnicalListItem } from '@woobe/ui'

import type { NetworkVersion } from '../types'

export function NetworkRollbackDialog({
  versions,
  currentVersionId,
  pending,
  onClose,
  onConfirm,
}: {
  versions: NetworkVersion[]
  currentVersionId: string | null
  pending: boolean
  onClose: () => void
  onConfirm: (versionId: string) => void
}) {
  const candidates = useMemo(
    () => versions.filter((version) => version.kind === 'release' && version.id !== currentVersionId),
    [currentVersionId, versions],
  )
  const [selectedId, setSelectedId] = useState(candidates[0]?.id ?? '')

  return (
    <Dialog open onClose={onClose} title="Select a historical Network release" className="max-w-dialog-compact" scrollMode="content">
      <div className="space-y-ui-md">
        <Alert variant="warning">
          <AlertDescription>
            <span className="flex items-start gap-ui-sm">
              <History className="mt-ui-hairline h-icon w-icon shrink-0" />
              <span>Rollback creates a new immutable Production version using the exact Network definition and Agent release IDs stored in the selected release.</span>
            </span>
          </AlertDescription>
        </Alert>

        {candidates.length ? (
          <div className="space-y-ui-sm">
            {candidates.map((version) => (
              <TechnicalListItem
                key={version.id}
                selected={selectedId === version.id}
                onClick={() => setSelectedId(version.id)}
                label={version.version}
                description={version.composition_hash}
                trailing={<span className="font-mono text-system-meta text-muted-foreground">{new Date(version.created_at).toLocaleString()}</span>}
              />
            ))}
          </div>
        ) : (
          <EmptyStatePanel compact title="No previous Production release is available" />
        )}

        <div className="flex justify-end gap-ui-sm border-t border-border pt-ui-md">
          <Button type="button" variant="outline" onClick={onClose}>Cancel</Button>
          <Button type="button" disabled={!selectedId || pending} onClick={() => onConfirm(selectedId)}>
            <RotateCcw className="mr-ui-xs h-icon-sm w-icon-sm" />
            {pending ? 'Rolling back…' : 'Create rollback release'}
          </Button>
        </div>
      </div>
    </Dialog>
  )
}
