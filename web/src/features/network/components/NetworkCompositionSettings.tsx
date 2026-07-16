import { useState } from 'react'
import { Bot, CheckCircle2 } from 'lucide-react'
import { toast } from 'sonner'

import { cn } from '@/lib/utils'

import type { AgentNodeId, BindingSource, NetworkBinding, NetworkVersionOption } from './networkWorkspaceTypes'

const surface = 'rounded-xl border border-border/75 bg-background/35'
const smallButton = 'rounded-lg border border-border/80 bg-background/40 px-2.5 py-1.5 text-[10px] font-medium text-muted hover:border-primary/30 hover:text-white disabled:cursor-not-allowed disabled:opacity-45'
const sourceTone: Record<BindingSource, string> = {
  draft: 'border-blue-500/30 bg-blue-500/10 text-blue-300',
  staging: 'border-indigo-500/30 bg-indigo-500/10 text-indigo-300',
  release: 'border-emerald-500/30 bg-emerald-500/10 text-emerald-300',
}

function sourceLabel(source: BindingSource) {
  if (source === 'draft') return 'Agent Draft'
  if (source === 'staging') return 'Agent Staging'
  return 'Agent Release'
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

function CompositionVersionCard({
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
    <article className={cn(surface, 'p-3 transition-colors', selected && 'border-primary/40 bg-primary/5')}>
      <div className="flex items-start gap-2.5">
        <div className="min-w-0 flex-1">
          <div className="flex min-w-0 flex-wrap items-center gap-2">
            <span className={cn('rounded-md border px-1.5 py-0.5 text-[8px] font-semibold uppercase', sourceTone[option.source])}>{option.source}</span>
            <span className="truncate font-mono text-[10px] text-white">{option.version}</span>
            {selected ? <CheckCircle2 className="h-3.5 w-3.5 shrink-0 text-primary-light" /> : null}
          </div>
          <p className="mt-1.5 text-[10px] text-slate-200">{option.note}</p>
          <p className="mt-1 text-[9px] text-muted">{option.created}</p>
        </div>
      </div>
      <div className="mt-2.5 flex items-center gap-3 border-t border-border/65 pt-2.5">
        <button type="button" onClick={() => toast.info(`Viewing ${option.version}`)} className="text-[9px] text-muted hover:text-white">View snapshot</button>
        {selected ? (
          <span className="ml-auto text-[9px] font-medium text-primary-light">Selected</span>
        ) : (
          <button type="button" disabled={readOnly} onClick={onUse} className={cn(smallButton, 'ml-auto text-primary-light')}>Use in Network</button>
        )}
      </div>
    </article>
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
    <div className="space-y-5">
      <section>
        <p className="text-sm font-semibold text-white">Agent composition</p>
        <p className="mt-1 text-[10px] leading-4 text-muted">Choose the exact Agent source used by each Network node. This does not edit the Agent Draft.</p>
        <div className="mt-4 space-y-2">
          {(Object.keys(bindings) as AgentNodeId[]).map((node) => {
            const item = bindings[node]
            const selected = node === compositionNode
            return (
              <button
                key={node}
                type="button"
                onClick={() => selectAgent(node)}
                className={cn(
                  'w-full rounded-xl border p-3 text-left transition-colors',
                  selected ? 'border-primary/35 bg-primary/5' : 'border-border/75 bg-background/30 hover:border-primary/20',
                )}
              >
                <div className="flex items-center gap-3">
                  <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl border border-primary/20 bg-primary/5 text-primary-light"><Bot className="h-4 w-4" /></div>
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-[11px] font-medium text-white">{item.agent.name}</p>
                    <p className="mt-1 truncate text-[9px] text-muted">{sourceLabel(item.source)} · <span className="font-mono">{item.version}</span></p>
                  </div>
                  <span className={cn('rounded-md border px-1.5 py-0.5 text-[8px] font-semibold uppercase', sourceTone[item.source])}>{item.source}</span>
                </div>
              </button>
            )
          })}
        </div>
      </section>

      <section className="border-t border-border pt-4">
        <div className="sticky top-0 z-10 -mx-1 rounded-lg border border-border/80 bg-surface/95 px-3 py-2 shadow-sm">
          <p className="text-[9px] font-semibold uppercase tracking-wide text-muted">Selected Agent</p>
          <div className="mt-1 flex min-w-0 items-center gap-2">
            <span className="truncate text-[10px] font-medium text-white">{active.agent.name}</span>
            <span className={cn('rounded border px-1.5 py-0.5 text-[8px] font-semibold uppercase', sourceTone[active.source])}>{active.source}</span>
            <span className="ml-auto truncate font-mono text-[8px] text-muted">{active.version}</span>
          </div>
        </div>

        <div className="mt-3 grid grid-cols-3 gap-2">
          {(['draft', 'staging', 'release'] as BindingSource[]).map((item) => (
            <button
              key={item}
              type="button"
              onClick={() => setSource(item)}
              className={cn('rounded-xl border p-3 text-left', source === item ? 'border-primary/35 bg-primary/10' : 'border-border bg-background/35 hover:border-primary/20')}
            >
              <p className="text-[10px] font-semibold capitalize text-white">{item}</p>
              <p className="mt-1 text-[9px] leading-4 text-muted">{item === 'draft' ? 'Mutable preview' : item === 'staging' ? 'Exact snapshot' : 'Immutable history'}</p>
            </button>
          ))}
        </div>

        <div className="mt-3 space-y-2">
          {versions[source].map((option) => (
            <CompositionVersionCard
              key={option.ref}
              option={option}
              selected={active.ref === option.ref}
              readOnly={readOnly}
              onUse={() => onUse(compositionNode, option)}
            />
          ))}
        </div>
      </section>
    </div>
  )
}
