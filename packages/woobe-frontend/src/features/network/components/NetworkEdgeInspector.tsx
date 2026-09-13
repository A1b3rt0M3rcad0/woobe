import { Info, Link2, Trash2 } from 'lucide-react'
import { Button, PanelHeader, SectionBlock } from '@woobe/ui'

import type { Agent } from '@/features/agents/types'

import type { NetworkDefinition } from '../types'
import { delegationToolName } from '../editor/networkGraphValidation'
import type { NetworkDefinitionChange } from '../editor/types'

function Help({ text }: { text: string }) {
  return (
    <span title={text} aria-label={text} className="inline-flex h-control-xs w-control-xs items-center justify-center rounded-technical border border-border bg-background/35 text-muted-foreground">
      <Info className="h-icon-sm w-icon-sm" />
    </span>
  )
}

export function NetworkEdgeInspector({
  definition,
  edgeId,
  agents,
  readOnly,
  onChange,
}: {
  definition: NetworkDefinition
  edgeId: string
  agents: Agent[]
  readOnly: boolean
  onChange: (change: NetworkDefinitionChange) => void
}) {
  const edge = definition.edges.find((item) => item.id === edgeId) ?? null
  const source = edge ? definition.nodes.find((item) => item.id === edge.source_node_id) ?? null : null
  const target = edge ? definition.nodes.find((item) => item.id === edge.target_node_id) ?? null : null
  const targetAgent = target ? agents.find((item) => item.id === target.agent_id) ?? null : null

  if (!edge) return null

  return (
    <>
      <PanelHeader
        icon={<Link2 className="h-icon w-icon" />}
        title={`${source?.label ?? 'Agent'} → ${target?.label ?? 'Agent'}`}
        description="Internal delegation path"
      />

      <div className="space-y-ui-md p-ui-md">
        <SectionBlock density="compact" eyebrow="Delegation" title="Path">
          <div className="grid grid-cols-[1fr_auto_1fr] items-center gap-ui-sm font-mono text-system-control text-accent-foreground">
            <span className="truncate">{source?.label}</span>
            <Link2 className="h-icon w-icon text-primary-light" />
            <span className="truncate text-right">{target?.label}</span>
          </div>
        </SectionBlock>

        <SectionBlock
          density="compact"
          title="Target capability"
          actions={<Help text="The source Agent receives this capability through its internal delegation Tool." />}
        >
          <p className="font-sans text-product-small leading-5 text-muted-foreground">
            {target?.capability_description || targetAgent?.description || 'No delegation capability described.'}
          </p>
        </SectionBlock>

        {target ? (
          <SectionBlock density="compact" title="Internal tool">
            <p className="break-all font-mono text-system-control text-accent-foreground/85">{delegationToolName(target)}</p>
          </SectionBlock>
        ) : null}

        <Button disabled={readOnly} type="button" variant="destructive" size="sm" onClick={() => onChange({ type: 'remove-edge', edgeId: edge.id })}>
          <Trash2 className="mr-ui-xs h-icon-sm w-icon-sm" />Remove delegation
        </Button>
      </div>
    </>
  )
}
