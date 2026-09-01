import { useMemo, useState } from 'react'
import { Bot, Check, Plus, Search, X } from 'lucide-react'
import type { Agent } from '@/features/agents/types'
import { cn } from '@/lib/utils'

export type NetworkAgentCatalogMode = 'first-agent' | 'add-specialist'

export function NetworkAgentCatalogDrawer({
  open,
  mode = 'add-specialist',
  agents,
  addedAgentIds,
  onClose,
  onAdd,
  onCreate,
}: {
  open: boolean
  mode?: NetworkAgentCatalogMode
  agents: Agent[]
  addedAgentIds: Set<string>
  onClose: () => void
  onAdd: (agent: Agent) => void
  onCreate: () => void
}) {
  const [query, setQuery] = useState('')
  const filtered = useMemo(() => {
    const term = query.trim().toLowerCase()
    const matched = !term
      ? agents
      : agents.filter((agent) => `${agent.name} ${agent.description ?? ''} ${agent.provider} ${agent.model}`.toLowerCase().includes(term))
    return [...matched].sort((left, right) => {
      const leftReady = left.status?.toLowerCase() === 'active' ? 0 : 1
      const rightReady = right.status?.toLowerCase() === 'active' ? 0 : 1
      return leftReady - rightReady || left.name.localeCompare(right.name)
    })
  }, [agents, query])
  if (!open) return null

  const firstAgent = mode === 'first-agent'
  return (
    <div className="absolute inset-0 z-50 bg-black/55 backdrop-blur-[2px]" onMouseDown={onClose}>
      <aside className="flex h-full w-[min(92vw,430px)] flex-col border-r border-border bg-surface shadow-2xl" onMouseDown={(event) => event.stopPropagation()}>
        <header className="flex items-start gap-3 border-b border-border p-5">
          <div className="min-w-0 flex-1">
            <p className="text-sm font-semibold text-white">{firstAgent ? 'Choose entry Agent' : 'Add specialist'}</p>
            <p className="mt-1 text-[10px] leading-4 text-muted">{firstAgent ? 'This Agent receives Network requests and becomes the entry point automatically.' : 'Add an Agent to the composition, then connect the delegation path on the Canvas.'}</p>
          </div>
          <button type="button" onClick={onClose} className="rounded-lg border border-border p-2 text-muted hover:text-white"><X className="h-4 w-4" /></button>
        </header>
        <div className="space-y-3 border-b border-border p-4">
          <button type="button" onClick={onCreate} className="flex w-full items-center justify-center gap-2 rounded-xl border border-primary/30 bg-primary/5 px-3 py-2.5 text-[10px] font-medium text-primary-light hover:bg-primary/10 hover:text-white"><Plus className="h-3.5 w-3.5" />{firstAgent ? 'Create entry Agent' : 'Create and add specialist'}</button>
          <label className="flex items-center gap-2 rounded-xl border border-border bg-background/45 px-3 py-2.5"><Search className="h-3.5 w-3.5 text-muted" /><input autoFocus value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search name, model or provider" className="min-w-0 flex-1 bg-transparent text-xs text-white outline-none placeholder:text-muted" /></label>
        </div>
        <div className="scrollbar-thin min-h-0 flex-1 space-y-2 overflow-y-auto overscroll-contain p-4">
          {filtered.map((agent) => {
            const added = addedAgentIds.has(agent.id)
            const inactive = agent.status?.toLowerCase() !== 'active'
            const disabled = added || inactive
            return <article key={agent.id} className={cn('rounded-xl border p-3', added ? 'border-primary/20 bg-primary/5' : inactive ? 'border-amber-500/20 bg-amber-500/5' : 'border-border bg-background/30')}>
              <div className="flex items-start gap-3"><div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-border bg-background/50 text-primary-light"><Bot className="h-4 w-4" /></div><div className="min-w-0 flex-1"><div className="flex items-center gap-2"><p className="truncate text-xs font-medium text-white">{agent.name}</p><span className={cn('rounded border px-1.5 py-0.5 text-[8px] uppercase', inactive ? 'border-amber-500/25 text-amber-300' : 'border-emerald-500/25 text-emerald-300')}>{inactive ? 'Unavailable' : 'Ready'}</span></div><p className="mt-1 truncate text-[9px] text-muted">{agent.provider}/{agent.model}</p><p className="mt-2 line-clamp-2 text-[9px] leading-4 text-slate-300">{agent.description || 'No description'}</p></div></div>
              <button disabled={disabled} title={inactive ? 'Activate the Agent before using it in a Network Draft.' : undefined} type="button" onClick={() => onAdd(agent)} className={cn('mt-3 flex w-full items-center justify-center gap-2 rounded-lg border px-3 py-2 text-[10px] font-medium', added ? 'cursor-default border-primary/20 text-primary-light' : inactive ? 'cursor-not-allowed border-amber-500/20 text-amber-300/70' : 'border-border text-white hover:border-primary/40 hover:bg-primary/5')}>{added ? <Check className="h-3.5 w-3.5" /> : <Plus className="h-3.5 w-3.5" />}{added ? 'Already in Network' : inactive ? 'Agent unavailable' : firstAgent ? 'Use as entry Agent' : 'Add specialist'}</button>
            </article>
          })}
          {!filtered.length ? <div className="p-8 text-center text-[10px] text-muted">No Agents match this search.</div> : null}
        </div>
      </aside>
    </div>
  )
}
