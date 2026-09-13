import { AlertTriangle } from 'lucide-react'
import { Alert, AlertDescription, Badge, Button, Dialog, ScrollArea, TechnicalListItem } from '@woobe/ui'

import type { AgentNodeId, NetworkBinding } from './networkWorkspaceTypes'
import { sourceLabel } from './networkPageData'

export type ReleaseAction = 'stage' | 'publish' | 'rollback' | null

export function NetworkReleaseModal({ action, draftBindings, stagingBindings, onClose, onConfirm }: { action: Exclude<ReleaseAction, null>; draftBindings: Record<AgentNodeId, NetworkBinding>; stagingBindings: Record<AgentNodeId, NetworkBinding>; onClose: () => void; onConfirm: () => void }) {
  const items = action === 'stage' ? Object.values(draftBindings) : Object.values(stagingBindings)
  const required = items.filter((item) => action === 'stage' ? item.source === 'draft' : item.source === 'staging').length
  const title = action === 'stage' ? 'Stage working composition?' : action === 'publish' ? 'Publish Network Release?' : 'Rollback Network Production?'
  const eyebrow = action === 'stage' ? 'Draft → Staging' : action === 'publish' ? 'Staging → Release' : 'Production rollback'

  return (
    <Dialog open onClose={onClose} title={title} className="max-w-dialog" scrollMode="content">
      <div className="space-y-ui-md">
        <div>
          <p className="font-mono text-system-meta uppercase tracking-ui-eyebrow text-primary-light">{eyebrow}</p>
          <p className="mt-ui-xs font-sans text-product-caption text-muted-foreground">The plan resolves every node to a compatible exact version.</p>
        </div>

        {action !== 'rollback' ? (
          <ScrollArea className="max-h-popover">
            <div className="space-y-ui-sm pr-ui-xs">
              {items.map((item) => {
                const promote = action === 'stage' ? item.source === 'draft' : item.source === 'staging'
                const variant = promote ? 'warning' : item.source === 'release' ? 'success' : 'default'
                const outcome = promote
                  ? action === 'stage' ? 'Save Draft and create exact Agent Staging' : 'Create or reuse immutable Agent Release'
                  : `Reuse exact ${sourceLabel(item.source)}`
                return (
                  <TechnicalListItem
                    key={item.nodeId}
                    label={item.agent.name}
                    description={`${sourceLabel(item.source)} · ${item.version}`}
                    meta={outcome}
                    trailing={<Badge size="compact" variant={variant}>{promote ? 'required' : 'reuse'}</Badge>}
                  />
                )
              })}
            </div>
          </ScrollArea>
        ) : null}

        {action === 'stage' ? (
          <Alert variant="info"><AlertDescription>Atomic operation: save pending Drafts, promote {required} Agent{required === 1 ? '' : 's'} to Staging, resolve exact snapshot IDs and create Network Staging.</AlertDescription></Alert>
        ) : null}
        {action === 'publish' ? (
          <Alert variant="success"><AlertDescription>Create or reuse {required} immutable Agent Release{required === 1 ? '' : 's'}, then pin them in the Network Release.</AlertDescription></Alert>
        ) : null}
        {action === 'rollback' ? (
          <Alert variant="success"><AlertDescription>Reactivate historical Network Release v0.8 and every exact Agent Release ID stored in its composition.</AlertDescription></Alert>
        ) : null}

        <div className="flex justify-end gap-ui-sm border-t border-border pt-ui-md">
          <Button type="button" variant="outline" onClick={onClose}>Cancel</Button>
          <Button type="button" onClick={onConfirm}>
            {action === 'stage' ? `Stage Network and ${required} Agent${required === 1 ? '' : 's'}` : action === 'publish' ? `Publish Network and ${required} Agent Release${required === 1 ? '' : 's'}` : 'Rollback Network'}
          </Button>
        </div>
      </div>
    </Dialog>
  )
}

export function UnsavedAgentSwitchDialog({ agentName, onStay, onDiscard, onSave }: { agentName: string; onStay: () => void; onDiscard: () => void; onSave: () => void }) {
  return (
    <Dialog open onClose={onStay} title="Unsaved Agent changes" className="max-w-dialog-compact">
      <div className="space-y-ui-md">
        <Alert variant="warning">
          <AlertDescription>
            <span className="flex items-start gap-ui-sm">
              <AlertTriangle className="mt-ui-hairline h-icon w-icon shrink-0" />
              <span>{agentName} contains unsaved Draft changes. Save them before switching context, discard them, or remain on this Agent.</span>
            </span>
          </AlertDescription>
        </Alert>
        <div className="flex flex-wrap justify-end gap-ui-sm border-t border-border pt-ui-md">
          <Button type="button" variant="outline" onClick={onStay}>Stay</Button>
          <Button type="button" variant="destructive" onClick={onDiscard}>Discard and switch</Button>
          <Button type="button" onClick={onSave}>Save and switch</Button>
        </div>
      </div>
    </Dialog>
  )
}
