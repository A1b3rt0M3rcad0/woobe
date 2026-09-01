import { useMemo, useState } from 'react'
import { Activity, ChevronRight, Filter, Search } from 'lucide-react'

import { ScrollArea } from '@/components/ui/ScrollArea'
import { formatLatency } from '@/lib/formatters/number'
import { cn } from '@/lib/utils'

import { invocationCount, toolCount } from './networkChatExecution'
import type { AgentNodeId } from './networkWorkspaceTypes'
import type { NetworkTraceRecord } from './networkObservabilityTypes'
import type { NetworkSession } from './networkSessionTypes'
import { NetworkTraceDetails } from './NetworkTraceDetails'

function statusTone(status: NetworkTraceRecord['status']) {
  if (status === 'success') return 'bg-emerald-400 shadow-[0_0_5px_rgba(52,211,153,.45)]'
  if (status === 'error') return 'bg-red-400 shadow-[0_0_5px_rgba(248,113,113,.45)]'
  return 'animate-pulse bg-blue-400 shadow-[0_0_5px_rgba(96,165,250,.45)]'
}

function formatTraceTime(value: string) {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return 'Unknown time'
  return new Intl.DateTimeFormat(undefined, { hour: '2-digit', minute: '2-digit', month: 'short', day: 'numeric' }).format(date)
}

function newestFirst(left: NetworkTraceRecord, right: NetworkTraceRecord) {
  const startedDelta = new Date(right.startedAt).getTime() - new Date(left.startedAt).getTime()
  if (startedDelta) return startedDelta
  const completedDelta = new Date(right.completedAt ?? right.startedAt).getTime() - new Date(left.completedAt ?? left.startedAt).getTime()
  if (completedDelta) return completedDelta
  return right.id.localeCompare(left.id)
}

function TraceListItem({ trace, selected, onSelect }: { trace: NetworkTraceRecord; selected: boolean; onSelect: () => void }) {
  const agents = invocationCount(trace.execution.root)
  const tools = toolCount(trace.execution.root)
  return (
    <button type="button" onClick={onSelect} className={cn('w-full rounded-lg border px-3 py-2.5 text-left transition-colors', selected ? 'border-primary/35 bg-primary/10' : 'border-transparent hover:border-border/70 hover:bg-background/55')}>
      <div className="flex items-start gap-2.5">
        <span className={cn('mt-1.5 h-2 w-2 shrink-0 rounded-full', statusTone(trace.status))} />
        <div className="min-w-0 flex-1">
          <p className={cn('truncate text-[11px]', selected ? 'font-medium text-white' : 'text-slate-300')}>{trace.title}</p>
          <div className="mt-1 flex items-center gap-2 text-[9px] text-muted">
            <span>{formatTraceTime(trace.startedAt)}</span>
            <span>{formatLatency(trace.durationMs)}</span>
            <span>{agents} Agents</span>
            {tools ? <span>{tools} Tools</span> : null}
          </div>
        </div>
        <ChevronRight className={cn('mt-1 h-3.5 w-3.5 shrink-0', selected ? 'text-primary-light' : 'text-muted/50')} />
      </div>
    </button>
  )
}

export function NetworkTracePanel({ traces, session, selectedTraceId, onSelectTrace, onViewCanvas, onOpenAgent }: {
  traces: NetworkTraceRecord[]
  session: NetworkSession | null
  selectedTraceId: string | null
  onSelectTrace: (trace: NetworkTraceRecord) => void
  onViewCanvas: (trace: NetworkTraceRecord) => void
  onOpenAgent: (nodeId: AgentNodeId) => void
}) {
  const [query, setQuery] = useState('')
  const [status, setStatus] = useState<'all' | NetworkTraceRecord['status']>('all')
  const filtered = useMemo(() => traces.filter((trace) => {
    if (status !== 'all' && trace.status !== status) return false
    const normalized = query.trim().toLowerCase()
    return !normalized || `${trace.title} ${trace.userMessage} ${trace.traceId ?? ''}`.toLowerCase().includes(normalized)
  }).sort(newestFirst), [query, status, traces])
  const selected = selectedTraceId ? filtered.find((trace) => trace.id === selectedTraceId) ?? null : null

  if (!session) {
    return (
      <div className="flex h-full items-center justify-center p-6 text-center">
        <div>
          <Activity className="mx-auto h-8 w-8 text-muted/40" />
          <p className="mt-3 text-[12px] font-medium text-white">No Network Session selected</p>
          <p className="mt-1 max-w-[260px] text-[10px] leading-5 text-muted">Select or create a session in Network Chat to view its Runs.</p>
        </div>
      </div>
    )
  }

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="shrink-0 border-b border-border/80 p-3">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <h2 className="text-[12px] font-semibold text-white">Network Runs</h2>
            <p className="mt-1 truncate text-[10px] text-slate-300">{session.title}</p>
            <p className="mt-0.5 text-[9px] text-muted">{session.versionLabel} · select a Run to inspect its path</p>
          </div>
          <div className="flex items-center gap-1 text-[9px] text-muted"><Filter className="h-3.5 w-3.5" />{filtered.length}</div>
        </div>
        {traces.length > 3 ? (
          <div className="mt-3 flex gap-2">
            <div className="relative min-w-0 flex-1"><Search className="absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted" /><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search Run" className="h-8 w-full rounded-lg border border-border bg-background/45 pl-8 pr-3 text-[10px] text-white outline-none placeholder:text-muted/70 focus:border-primary/35" /></div>
            <select value={status} onChange={(event) => setStatus(event.target.value as 'all' | NetworkTraceRecord['status'])} aria-label="Filter Runs by status" className="h-8 rounded-lg border border-border bg-background/45 px-2 text-[10px] text-muted outline-none"><option value="all">All status</option><option value="success">Completed</option><option value="error">Failed</option><option value="running">Running</option></select>
          </div>
        ) : null}
      </div>
      <ScrollArea className={cn('shrink-0 border-b border-border/80', selected ? 'max-h-[190px]' : 'min-h-0 flex-1')}>
        <div className="space-y-0.5 p-2">
          {filtered.length ? filtered.map((trace) => <TraceListItem key={trace.id} trace={trace} selected={selected?.id === trace.id} onSelect={() => onSelectTrace(trace)} />) : (
            <div className="p-6 text-center"><Activity className="mx-auto h-7 w-7 text-muted/40" /><p className="mt-2 text-[11px] text-muted">No Runs in this session match the current filter.</p></div>
          )}
        </div>
      </ScrollArea>
      {selected ? (
        <ScrollArea className="min-h-0 flex-1"><NetworkTraceDetails trace={selected} session={session} onViewCanvas={onViewCanvas} onOpenAgent={onOpenAgent} /></ScrollArea>
      ) : traces.length ? (
        <div className="p-4 text-center"><div className="rounded-xl border border-dashed border-border/80 px-4 py-8"><p className="text-[11px] text-muted">Select a Network Run to understand the result and execution path.</p></div></div>
      ) : (
        <div className="p-4 text-center"><div className="rounded-xl border border-dashed border-border/80 px-4 py-8"><p className="text-[11px] text-muted">Send a message in Network Chat to create the first Run for this session.</p></div></div>
      )}
    </div>
  )
}
