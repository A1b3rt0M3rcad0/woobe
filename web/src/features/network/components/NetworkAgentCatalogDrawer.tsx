import { useMemo, useState } from 'react'
import { Bot, Check, Plus, Search, X } from 'lucide-react'
import type { Agent } from '@/features/agents/types'
import { cn } from '@/lib/utils'

export function NetworkAgentCatalogDrawer({
  open,
  agents,
  addedAgentIds,
  onClose,
  onAdd,
}: {
  open: boolean
  agents: Agent[]
  addedAgentIds: Set<string>
  onClose: () => void
  onAdd: (agent: Agent) => void
}) {
  const [query, setQuery] = useState('')
  const filtered = useMemo(() => {
    const term = query.trim().toLowerCase()
    if (!term) return agents
    return agents.filter((agent) => `${agent.name} ${agent.description ?? ''} ${agent.provider} ${agent.model}`.toLowerCase().includes(term))
  }, [agents, query])
  if (!open) return null
  return (
    <div className="absolute inset-0 z-50 bg-black/55 backdrop-blur-[2px]" onMouseDown={onClose}>
      <aside className="flex h-full w-[min(92vw,430px)] flex-col border-r border-border bg-surface shadow-2xl" onMouseDown={(event) => event.stopPropagation()}>
        <header className="flex items-start gap-3 border-b border-border p-5">
          <div className="min-w-0 flex-1"><p className="text-sm font-semibold text-white">Add Agent</p><p className="mt-1 text-[10px] text-muted">Choose an Agent from this Project.</p></div>
          <button type="button" onClick={onClose} className="rounded-lg border border-border p-2 text-muted hover:text-white"><X className="h-4 w-4" /></button>
        </header>
        <div className="border-b border-border p-4">
          <label className="flex items-center gap-2 rounded-xl border border-border bg-background/45 px-3 py-2.5"><Search className="h-3.5 w-3.5 text-muted" /><input autoFocus value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search name, model or provider" className="min-w-0 flex-1 bg-transparent text-xs text-white outline-none placeholder:text-muted" /></label>
        </div>
        <div className="min-h-0 flex-1 space-y-2 overflow-y-auto p-4">
          {filtered.map((agent) => {
            const added = addedAgentIds.has(agent.id)
            return <article key={agent.id} className={cn('rounded-xl border p-3', added ? 'border-primary/20 bg-primary/5' : 'border-border bg-background/30')}>
              <div className="flex items-start gap-3"><div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-border bg-background/50 text-primary-light"><Bot className="h-4 w-4" /></div><div className="min-w-0 flex-1"><p className="truncate text-xs font-medium text-white">{agent.name}</p><p className="mt-1 truncate text-[9px] text-muted">{agent.provider}/{agent.model}</p><p className="mt-2 line-clamp-2 text-[9px] leading-4 text-slate-300">{agent.description || 'No description'}</p></div></div>
              <button disabled={added} type="button" onClick={() => onAdd(agent)} className={cn('mt-3 flex w-full items-center justify-center gap-2 rounded-lg border px-3 py-2 text-[10px] font-medium', added ? 'cursor-default border-primary/20 text-primary-light' : 'border-border text-white hover:border-primary/40 hover:bg-primary/5')}>{added ? <Check className="h-3.5 w-3.5" /> : <Plus className="h-3.5 w-3.5" />}{added ? 'Already in Network' : 'Add to Network'}</button>
            </article>
          })}
          {!filtered.length ? <div className="p-8 text-center text-[10px] text-muted">No Agents match this search.</div> : null}
        </div>
      </aside>
    </div>
  )
}

