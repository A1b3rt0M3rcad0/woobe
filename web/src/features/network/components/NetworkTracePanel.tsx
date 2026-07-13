import { useMemo, useState } from 'react'
import { Activity, ChevronRight, Filter, Search } from 'lucide-react'

import { ScrollArea } from '@/components/ui/ScrollArea'
import { formatLatency } from '@/lib/formatters/number'
import { cn } from '@/lib/utils'

import { invocationCount } from './networkChatExecution'
import type { AgentNodeId, Environment } from './networkWorkspaceTypes'
import type { NetworkTraceRecord } from './networkObservabilityTypes'
import { Badge } from './NetworkOperationsRail'
import { NetworkTraceDetails } from './NetworkTraceDetails'

type TraceScope = 'all' | 'current-chat'

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

function TraceListItem({ trace, selected, onSelect }: { trace: NetworkTraceRecord; selected: boolean; onSelect: () => void }) {
  const agents = invocationCount(trace.execution.root)
  return (
    <button type="button" onClick={onSelect} className={cn('w-full rounded-xl border p-3 text-left transition-colors', selected ? 'border-primary/35 bg-primary/10' : 'border-border/70 bg-background/35 hover:border-primary/20 hover:bg-background/55')}>
      <div className="flex items-start gap-2.5">
        <span className={cn('mt-1.5 h-2 w-2 shrink-0 rounded-full', statusTone(trace.status))} />
        <div className="min-w-0 flex-1">
          <p className={cn('truncate text-[11px] font-medium', selected ? 'text-white' : 'text-slate-200')}>{trace.title}</p>
          <div className="mt-1.5 flex flex-wrap items-center gap-1.5"><Badge tone={trace.environment}>{trace.environment}</Badge><span className="text-[9px] text-muted">{trace.networkVersion}</span></div>
          <div className="mt-2 flex flex-wrap items-center gap-x-2 gap-y-1 text-[9px] text-muted"><span>{agents} Agents</span><span>{trace.execution.path.length} hops</span><span>{formatLatency(trace.durationMs)}</span><span>${trace.costUsd.toFixed(3)}</span></div>
          <p className="mt-1 text-[9px] text-muted/80">{formatTraceTime(trace.startedAt)}</p>
        </div>
        <ChevronRight className={cn('mt-1 h-3.5 w-3.5 shrink-0', selected ? 'text-primary-light' : 'text-muted/50')} />
      </div>
    </button>
  )
}

export function NetworkTracePanel({ traces, selectedTraceId, currentSessionId, onSelectTrace, onViewCanvas, onOpenAgent }: {
  traces: NetworkTraceRecord[]
  selectedTraceId: string | null
  currentSessionId: string
  onSelectTrace: (trace: NetworkTraceRecord) => void
  onViewCanvas: (trace: NetworkTraceRecord) => void
  onOpenAgent: (nodeId: AgentNodeId) => void
}) {
  const [scope, setScope] = useState<TraceScope>('all')
  const [query, setQuery] = useState('')
  const [environment, setEnvironment] = useState<'all' | Environment>('all')
  const [status, setStatus] = useState<'all' | NetworkTraceRecord['status']>('all')
  const filtered = useMemo(() => traces.filter((trace) => {
    if (scope === 'current-chat' && trace.sessionId !== currentSessionId) return false
    if (environment !== 'all' && trace.environment !== environment) return false
    if (status !== 'all' && trace.status !== status) return false
    const normalized = query.trim().toLowerCase()
    return !normalized || `${trace.title} ${trace.userMessage} ${trace.traceId}`.toLowerCase().includes(normalized)
  }), [currentSessionId, environment, query, scope, status, traces])
  const selected = filtered.find((trace) => trace.id === selectedTraceId) ?? filtered[0] ?? null

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="shrink-0 border-b border-border/80 p-3">
        <div className="flex items-start justify-between gap-2"><div><h2 className="text-xs font-semibold text-white">Network Traces</h2><p className="mt-1 text-[9px] leading-4 text-muted">Inspect execution paths, exact versions, Tools and Sources.</p></div><div className="flex items-center gap-1 text-[8px] text-muted"><Filter className="h-3 w-3" />{filtered.length}</div></div>
        <div className="mt-3 flex rounded-lg border border-border bg-background/40 p-0.5">{(['all', 'current-chat'] as TraceScope[]).map((item) => <button key={item} type="button" onClick={() => setScope(item)} className={cn('flex-1 rounded-md px-2 py-1.5 text-[9px]', scope === item ? 'bg-primary/10 text-primary-light' : 'text-muted hover:text-white')}>{item === 'all' ? 'All traces' : 'Current chat'}</button>)}</div>
        <div className="relative mt-2"><Search className="absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted" /><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search request or trace ID" className="h-8 w-full rounded-lg border border-border bg-background/45 pl-8 pr-3 text-[9px] text-white outline-none placeholder:text-muted/70 focus:border-primary/35" /></div>
        <div className="mt-2 grid grid-cols-2 gap-2">
          <select value={environment} onChange={(event) => setEnvironment(event.target.value as 'all' | Environment)} className="h-8 rounded-lg border border-border bg-background/45 px-2 text-[9px] text-muted outline-none"><option value="all">All environments</option><option value="draft">Draft</option><option value="staging">Staging</option><option value="production">Production</option></select>
          <select value={status} onChange={(event) => setStatus(event.target.value as 'all' | NetworkTraceRecord['status'])} className="h-8 rounded-lg border border-border bg-background/45 px-2 text-[9px] text-muted outline-none"><option value="all">All statuses</option><option value="success">Completed</option><option value="error">Failed</option><option value="running">Running</option></select>
        </div>
      </div>
      <ScrollArea className="max-h-[250px] shrink-0 border-b border-border/80"><div className="space-y-2 p-3">{filtered.length ? filtered.map((trace) => <TraceListItem key={trace.id} trace={trace} selected={selected?.id === trace.id} onSelect={() => onSelectTrace(trace)} />) : <div className="rounded-xl border border-dashed border-border p-6 text-center"><Activity className="mx-auto h-7 w-7 text-muted/50" /><p className="mt-2 text-[10px] text-muted">No traces match these filters.</p></div>}</div></ScrollArea>
      <ScrollArea className="min-h-0 flex-1">{selected ? <NetworkTraceDetails trace={selected} onViewCanvas={onViewCanvas} onOpenAgent={onOpenAgent} /> : <div className="p-6 text-center text-[10px] text-muted">Select a trace to inspect its execution.</div>}</ScrollArea>
    </div>
  )
}
