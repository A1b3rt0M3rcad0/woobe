import { Badge, Button, ScrollArea, SectionBlock, TechnicalListItem } from '@woobe/ui'

import type { AgentNodeId, BindingSource, NetworkBinding } from './networkWorkspaceTypes'

export function NetworkVersions({
  draftBindings,
  stagingBindings,
  productionBindings,
  onStage,
  onPublish,
  onRollback,
  onLoadNetwork,
}: {
  draftBindings: Record<AgentNodeId, NetworkBinding>
  stagingBindings: Record<AgentNodeId, NetworkBinding>
  productionBindings: Record<AgentNodeId, NetworkBinding>
  onStage: () => void
  onPublish: () => void
  onRollback: () => void
  onLoadNetwork: () => void
}) {
  const count = (items: Record<AgentNodeId, NetworkBinding>, type: BindingSource) => Object.values(items).filter((item) => item.source === type).length

  return (
    <ScrollArea className="min-h-0 flex-1 overscroll-contain">
      <div className="space-y-ui-md p-ui-md">
        <SectionBlock
          density="compact"
          eyebrow="Lifecycle"
          title="Network lifecycle"
          description="Draft is mutable. Staging and Production preserve exact composition snapshots."
        />

        <SectionBlock
          density="compact"
          title="Draft Revision 29"
          description={`${count(draftBindings, 'draft')} Draft · ${count(draftBindings, 'staging')} Staging · ${count(draftBindings, 'release')} Release`}
          actions={<Button type="button" size="sm" onClick={onStage}>Stage</Button>}
        />

        <SectionBlock
          density="compact"
          eyebrow="Staging"
          title="Staging v0.12"
          description={`${count(stagingBindings, 'staging')} Staging · ${count(stagingBindings, 'release')} Release`}
          actions={<Button type="button" size="sm" variant="outline" onClick={onPublish}>Publish</Button>}
        />

        <SectionBlock density="compact" eyebrow="Production" title="Production v0.10">
          <TechnicalListItem
            label={`${count(productionBindings, 'release')} immutable Agent Releases`}
            trailing={<Badge size="compact" variant="success">active</Badge>}
          />
        </SectionBlock>

        <SectionBlock density="compact" title="Historical releases">
          <TechnicalListItem
            label="Historical v0.8"
            description="Exact composition preserved"
            trailing={<Badge size="compact" variant="outline">Archived</Badge>}
            meta={(
              <span className="flex gap-ui-sm">
                <button type="button" onClick={onLoadNetwork} className="font-mono text-system-meta text-primary-light hover:underline">Load to Draft</button>
                <button type="button" onClick={onRollback} className="font-mono text-system-meta text-success hover:underline">Rollback</button>
              </span>
            )}
          />
        </SectionBlock>
      </div>
    </ScrollArea>
  )
}
