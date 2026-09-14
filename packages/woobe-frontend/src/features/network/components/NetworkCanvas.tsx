import { Bot, CircleDot } from 'lucide-react'

import { ScrollArea } from '@/components/ui/ScrollArea'
import { cn } from '@/lib/utils'

import type { AgentNodeId, Environment, NetworkBinding, NetworkRun, NodeId } from './networkWorkspaceTypes'

const sourceTone = {
  draft: 'border-blue-500/30 bg-blue-500/10 text-blue-300',
  staging: 'border-indigo-500/30 bg-indigo-500/10 text-indigo-300',
  release: 'border-emerald-500/30 bg-emerald-500/10 text-emerald-300',
} as const

function NodeCard({ id, binding, active, selected, dirty, className, onSelect }: { id: NodeId; binding?: NetworkBinding; active: boolean; selected: boolean; dirty?: boolean; className: string; onSelect: () => void }) {
  const terminal = id === 'entry' || id === 'end'
  return (
    <button
      type="button"
      onClick={onSelect}
      className={cn(
        'absolute z-20 border bg-surface/95 text-left transition-colors',
        terminal ? 'flex h-14 w-28 items-center justify-center rounded-full' : 'w-56 rounded-container p-ui-md',
        selected ? 'border-primary/70 ring-1 ring-primary/25' : active ? 'border-emerald-500/45' : 'border-border/90 hover:border-primary/30',
        className,
      )}
    >
      {terminal ? (
        <div className="flex items-center gap-ui-sm">
          <CircleDot className="h-4 w-4 text-primary-light" />
          <span className="font-mono text-system-control font-semibold tracking-ui-label text-white">{id.toUpperCase()}</span>
        </div>
      ) : binding ? (
        <>
          <div className="flex gap-ui-md">
            <div className="flex h-control w-control shrink-0 items-center justify-center rounded-control border border-primary/25 bg-primary/10 text-primary-light">
              <Bot className="h-icon w-icon" />
            </div>
            <div className="min-w-0 flex-1">
              <p className="truncate font-sans text-product-small font-semibold text-white">{binding.agent.name}</p>
              <p className="mt-ui-xs truncate font-mono text-system-meta text-muted-foreground">{binding.agent.provider}/{binding.agent.model}</p>
            </div>
            <span className={cn('mt-ui-xs h-2 w-2 rounded-full', dirty ? 'bg-amber-400' : 'bg-emerald-400')} />
          </div>
          <div className="mt-ui-md flex items-center justify-between border-t border-border/70 pt-ui-sm">
            <span className={cn('rounded-technical border px-ui-xs py-ui-hairline font-mono text-system-meta font-semibold uppercase', sourceTone[binding.source])}>{binding.source}</span>
            <span className="font-mono text-system-meta text-slate-300">{binding.source === 'draft' && dirty ? `${binding.draftVersion} preview` : binding.version}</span>
          </div>
        </>
      ) : null}
    </button>
  )
}

export function NetworkCanvas({ bindings, run, selectedNode, environment, dirtyAgentIds, onSelect }: { bindings: Record<AgentNodeId, NetworkBinding>; run: NetworkRun; selectedNode: NodeId; environment: Environment; dirtyAgentIds: Set<string>; onSelect: (node: NodeId) => void }) {
  const active = new Set(run.path)
  const counts = Object.values(bindings).reduce<Record<NetworkBinding['source'], number>>((acc, item) => ({ ...acc, [item.source]: acc[item.source] + 1 }), { draft: 0, staging: 0, release: 0 })
  return (
    <ScrollArea orientation="both" className="min-h-0 flex-1 bg-background">
      <div className="relative mx-auto h-[660px] w-[1040px]" style={{ backgroundImage: 'radial-gradient(circle, rgba(100,116,139,.16) 1px, transparent 1px)', backgroundSize: '22px 22px' }}>
        <div className="absolute left-ui-md top-ui-md z-30 rounded-container border border-border bg-surface/90 px-ui-md py-ui-sm font-mono text-system-micro text-muted-foreground"><span className="font-medium text-white">Working composition</span> · {counts.draft} Draft · {counts.staging} Staging · {counts.release} Release</div>
        {environment !== 'draft' ? <div className="absolute left-1/2 top-ui-md z-30 -translate-x-1/2 rounded-control border border-border bg-surface/90 px-ui-md py-ui-sm font-mono text-system-meta text-muted-foreground">Read-only exact {environment} snapshot</div> : null}
        <svg className="absolute inset-0 z-10" width="1040" height="660"><path d="M188 326 C220 326 225 326 254 326" fill="none" stroke="#475569" strokeWidth="2" /><path d="M478 306 C515 306 500 202 540 202" fill="none" stroke="#475569" strokeWidth="2" /><path d="M478 348 C515 348 500 452 540 452" fill="none" stroke="#475569" strokeWidth="2" /><path d="M764 202 C820 202 790 326 852 326" fill="none" stroke="#475569" strokeWidth="2" /><path d="M764 452 C820 452 790 326 852 326" fill="none" stroke="#475569" strokeWidth="2" /></svg>
        <NodeCard id="entry" active={active.has('entry')} selected={selectedNode === 'entry'} className="left-[60px] top-[298px]" onSelect={() => onSelect('entry')} />
        <NodeCard id="coordinator" binding={bindings.coordinator} dirty={dirtyAgentIds.has(bindings.coordinator.agent.id)} active={active.has('coordinator')} selected={selectedNode === 'coordinator'} className="left-[254px] top-[268px]" onSelect={() => onSelect('coordinator')} />
        <NodeCard id="billing" binding={bindings.billing} dirty={dirtyAgentIds.has(bindings.billing.agent.id)} active={active.has('billing')} selected={selectedNode === 'billing'} className="left-[540px] top-[142px]" onSelect={() => onSelect('billing')} />
        <NodeCard id="technical" binding={bindings.technical} dirty={dirtyAgentIds.has(bindings.technical.agent.id)} active={active.has('technical')} selected={selectedNode === 'technical'} className="left-[540px] top-[392px]" onSelect={() => onSelect('technical')} />
        <NodeCard id="end" active={active.has('end')} selected={selectedNode === 'end'} className="left-[852px] top-[298px]" onSelect={() => onSelect('end')} />
        <div className="absolute bottom-ui-md left-ui-md z-30 w-80 rounded-container border border-primary/20 bg-surface/90 p-ui-md"><p className="font-mono text-system-control font-medium text-white">Agent workspace inside the Network</p><p className="mt-ui-xs font-sans text-product-caption leading-4 text-muted-foreground">Select an Agent to edit its Draft, inspect Versions and run an isolated Chat without leaving the Network.</p></div>
      </div>
    </ScrollArea>
  )
}
