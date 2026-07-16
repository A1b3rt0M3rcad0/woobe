import { Info, Link2, Trash2 } from 'lucide-react'

import type { Agent } from '@/features/agents/types'

import type { NetworkDefinition } from '../types'
import { delegationToolName } from '../editor/networkGraphValidation'
import type { NetworkDefinitionChange } from '../editor/types'

function Help({ text }: { text: string }) {
  return <span title={text} aria-label={text} className="inline-flex h-5 w-5 items-center justify-center rounded-full border border-border bg-background/45 text-muted"><Info className="h-3 w-3" /></span>
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
      <header className="border-b border-border p-4">
        <div className="flex items-start gap-3">
          <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl border border-primary/20 bg-primary/5 text-primary-light"><Link2 className="h-4 w-4" /></div>
          <div className="min-w-0">
            <p className="text-[8px] font-semibold uppercase tracking-widest text-primary-light">Delegation</p>
            <h2 className="mt-1 truncate text-sm font-semibold text-white">{source?.label ?? 'Agent'} → {target?.label ?? 'Agent'}</h2>
            <p className="mt-1 text-[9px] text-muted">Internal delegation path</p>
          </div>
        </div>
      </header>

      <div className="space-y-4 p-4">
        <section className="rounded-xl border border-border bg-background/30 p-3">
          <div className="grid grid-cols-[1fr_auto_1fr] items-center gap-2 text-[10px] text-white">
            <span className="truncate">{source?.label}</span>
            <Link2 className="h-3.5 w-3.5 text-primary-light" />
            <span className="truncate text-right">{target?.label}</span>
          </div>
        </section>

        <section className="rounded-xl border border-border bg-background/30 p-3">
          <div className="flex items-center gap-2">
            <p className="text-[9px] font-semibold uppercase tracking-wider text-muted">Target capability</p>
            <Help text="The source Agent receives this capability through its internal delegation Tool." />
          </div>
          <p className="mt-2 text-[10px] leading-5 text-slate-200">{target?.capability_description || targetAgent?.description || 'No delegation capability described.'}</p>
        </section>

        {target ? (
          <section className="rounded-xl border border-border bg-background/30 p-3">
            <p className="text-[9px] uppercase tracking-wide text-muted">Internal tool</p>
            <p className="mt-1 break-all font-mono text-[10px] text-slate-200">{delegationToolName(target)}</p>
          </section>
        ) : null}

        <button disabled={readOnly} type="button" onClick={() => onChange({ type: 'remove-edge', edgeId: edge.id })} className="inline-flex items-center gap-2 text-[9px] font-medium text-red-300 disabled:opacity-45">
          <Trash2 className="h-3.5 w-3.5" />Remove delegation
        </button>
      </div>
    </>
  )
}
