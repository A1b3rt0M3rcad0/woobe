import { useState } from 'react'
import { Bot } from 'lucide-react'
import { toast } from 'sonner'
import { Badge, Button, SectionBlock, SegmentedControl, TechnicalListItem, type BadgeVariant } from '@woobe/ui'

import type { AgentNodeId, BindingSource, NetworkBinding, NetworkVersionOption } from './networkWorkspaceTypes'

const sourceVariant: Record<BindingSource, BadgeVariant> = {
  draft: 'default',
  staging: 'network',
  release: 'success',
}

function sourceLabel(source: BindingSource) {
  if (source === 'draft') return 'Agent Draft'
  if (source === 'staging') return 'Agent Staging'
  return 'Agent Release'
}

function sourceDescription(source: BindingSource) {
  if (source === 'draft') return 'Mutable preview'
  if (source === 'staging') return 'Exact snapshot'
  return 'Immutable history'
}

function catalog(binding: NetworkBinding): Record<BindingSource, NetworkVersionOption[]> {
  const prefix = binding.nodeId
  const staging = binding.nodeId === 'coordinator'
    ? 'v0.4.20260713.02'
    : binding.nodeId === 'billing'
      ? 'v0.3.20260713.01'
      : 'v0.2.20260713.00'

  const releases = binding.nodeId === 'coordinator'
    ? [['v0.5.20260713.00', 'Current orchestration behavior'], ['v0.4.20260708.01', 'Previous routing policy'], ['v0.3.20260701.00', 'Stable June composition']]
    : binding.nodeId === 'billing'
      ? [['v0.4.20260713.00', 'Refund tool validation'], ['v0.3.20260706.02', 'Invoice lookup improvements'], ['v0.2.20260629.01', 'Previous billing behavior']]
      : [['v0.3.20260713.00', 'Incident routing update'], ['v0.2.20260705.00', 'Status page integration'], ['v0.1.20260712.00', 'Initial technical support release']]

  return {
    draft: [{ source: 'draft', ref: `draft-${prefix}`, version: binding.draftVersion, note: binding.draftBase ? `Based on ${binding.draftBase}` : 'Current mutable Agent Draft', created: 'Updated moments ago' }],
    staging: [{ source: 'staging', ref: `staging-${prefix}`, version: staging, note: 'Exact read-only validation snapshot', created: '13 Jul 2026, 14:42' }],
    release: releases.map(([version, note], index) => ({ source: 'release', ref: `release-${prefix}-${index}`, version, note, created: `${13 - index * 4} Jul 2026` })),
  }
}

function CompositionVersionRow({
  option,
  selected,
  readOnly,
  onUse,
}: {
  option: NetworkVersionOption
  selected: boolean
  readOnly: boolean
  onUse: () => void
}) {
  return (
    <TechnicalListItem
      selected={selected}
      leading={<Badge size="compact" variant={sourceVariant[option.source]}>{option.source}</Badge>}
      label={option.version}
      description={option.note}
      meta={option.created}
      trailing={(
        <div className="flex items-center gap-ui-xs">
          <Button type="button" size="sm" variant="ghost" onClick={() => toast.info(`Viewing ${option.version}`)}>View snapshot</Button>
          {selected ? <Badge size="compact" variant="default">Selected</Badge> : <Button type="button" size="sm" variant="outline" disabled={readOnly} onClick={onUse}>Use in Network</Button>}
        </div>
      )}
    />
  )
}

export function CompositionSettings({
  bindings,
  compositionNode,
  readOnly,
  onCompositionNode,
  onUse,
}: {
  bindings: Record<AgentNodeId, NetworkBinding>
  compositionNode: AgentNodeId
  readOnly: boolean
  onCompositionNode: (node: AgentNodeId) => void
  onUse: (node: AgentNodeId, option: NetworkVersionOption) => void
}) {
  const active = bindings[compositionNode]
  const [source, setSource] = useState<BindingSource>(active.source)
  const versions = catalog(active)

  const selectAgent = (node: AgentNodeId) => {
    onCompositionNode(node)
    setSource(bindings[node].source)
  }

  return (
    <div className="space-y-ui-lg">
      <SectionBlock
        density="compact"
        title="Agent composition"
        description="Choose the exact Agent source used by each Network node. This does not edit the Agent Draft."
      >
        <div className="space-y-ui-sm">
          {(Object.keys(bindings) as AgentNodeId[]).map((node) => {
            const item = bindings[node]
            return (
              <TechnicalListItem
                key={node}
                selected={node === compositionNode}
                onClick={() => selectAgent(node)}
                leading={<Bot className="h-icon w-icon text-primary-light" />}
                label={item.agent.name}
                description={`${sourceLabel(item.source)} · ${item.version}`}
                trailing={<Badge size="compact" variant={sourceVariant[item.source]}>{item.source}</Badge>}
              />
            )
          })}
        </div>
      </SectionBlock>

      <SectionBlock density="compact" eyebrow="Selected Agent" title={active.agent.name} description={`${sourceLabel(active.source)} · ${active.version}`}>
        <div className="space-y-ui-md">
          <SegmentedControl
            stretch
            value={source}
            onValueChange={(value) => setSource(value as BindingSource)}
            ariaLabel="Agent source"
            items={[
              { value: 'draft', label: 'Draft' },
              { value: 'staging', label: 'Staging' },
              { value: 'release', label: 'Release' },
            ]}
          />
          <p className="font-sans text-product-caption text-muted-foreground">{sourceDescription(source)}</p>
          <div className="space-y-ui-sm">
            {versions[source].map((option) => (
              <CompositionVersionRow
                key={option.ref}
                option={option}
                selected={active.ref === option.ref}
                readOnly={readOnly}
                onUse={() => onUse(compositionNode, option)}
              />
            ))}
          </div>
        </div>
      </SectionBlock>
    </div>
  )
}
