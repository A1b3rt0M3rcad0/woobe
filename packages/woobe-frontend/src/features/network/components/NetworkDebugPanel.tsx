import { useState, type ReactNode } from 'react'
import { Bot, Bug, ChevronDown, ChevronRight, GitBranch } from 'lucide-react'

import { JsonCodeBlock } from '@/components/ui/JsonCodeBlock'
import { ScrollArea } from '@/components/ui/ScrollArea'
import { formatLatency } from '@/lib/formatters/number'
import { cn } from '@/lib/utils'

import { delegationCount, invocationCount, type NetworkAgentInvocation } from './networkChatExecution'
import type { NetworkTraceRecord } from './networkObservabilityTypes'
import { Badge } from './NetworkOperationsRail'
import { NetworkSessionComposition } from './NetworkSessionComposition'

const surface = 'rounded-xl border border-border/75 bg-background/35'

function Metric({ label, value }: { label: string; value: string }) {
  return <div className="rounded-lg border border-border/70 bg-background/45 p-2.5"><p className="text-[9px] uppercase tracking-wide text-muted">{label}</p><p className="mt-1 text-[11px] font-medium text-white">{value}</p></div>
}

function CollapsibleSection({ title, badge, defaultOpen = false, children }: { title: string; badge?: string; defaultOpen?: boolean; children: ReactNode }) {
  const [open, setOpen] = useState(defaultOpen)
  return <div className={surface}><button type="button" onClick={() => setOpen((value) => !value)} className="flex w-full items-center gap-2 px-3 py-2.5 text-left text-[10px] font-medium text-white" aria-expanded={open}>{open ? <ChevronDown className="h-3.5 w-3.5 text-muted" /> : <ChevronRight className="h-3.5 w-3.5 text-muted" />}<span>{title}</span>{badge ? <span className="ml-auto text-[9px] text-muted">{badge}</span> : null}</button>{open ? <div className="border-t border-border/70 p-2.5">{children}</div> : null}</div>
}

function ResolvedComposition({ trace }: { trace: NetworkTraceRecord }) {
  const rows: NetworkAgentInvocation[] = []
  const visit = (invocation: NetworkAgentInvocation) => { rows.push(invocation); invocation.children.forEach(visit) }
  visit(trace.execution.root)
  return <div className="space-y-1.5">{rows.map((invocation) => <div key={invocation.spanId} className="rounded-lg border border-border/70 bg-background/45 p-2.5"><div className="flex items-center gap-2"><Bot className="h-3.5 w-3.5 text-primary-light" /><span className="min-w-0 flex-1 truncate text-[10px] font-medium text-white">{invocation.agentName}</span><Badge tone={invocation.source === 'release' ? 'production' : invocation.source}>{invocation.source}</Badge></div><p className="mt-1 truncate font-mono text-[9px] text-muted">{invocation.version}</p><p className="mt-1 truncate font-mono text-[9px] text-primary-light">{invocation.agentSessionId ? `agent session ${invocation.agentSessionId}` : 'stateless invocation'}</p></div>)}</div>
}

export function NetworkDebugPanel({ trace }: { trace: NetworkTraceRecord | null }) {
  if (!trace) return <div className="flex h-full items-center justify-center p-6 text-center"><div><Bug className="mx-auto h-8 w-8 text-muted/50" /><p className="mt-3 text-[12px] text-muted">Select a Run from the active Network Session to inspect debug data.</p></div></div>
  const routeEvents = trace.events.filter((event) => event.type.startsWith('network.route.'))
  const contextEvents = trace.events.filter((event) => event.type === 'network.agent.context.resolved')
  const activeEvent = trace.events[trace.events.length - 1]
  const lastPathNode = trace.execution.path[trace.execution.path.length - 1]
  return (
    <ScrollArea className="h-full min-h-0">
      <div className="space-y-2.5 p-3">
        <div className="flex items-start gap-2"><div className="min-w-0 flex-1"><p className="text-[12px] font-semibold text-white">Debug</p><p className="mt-1 text-[10px] text-muted">{trace.status === 'running' ? 'Live execution' : trace.traceId ? `Historical trace ${trace.traceId.slice(0, 8)}…` : `Historical run ${trace.id.slice(0, 8)}…`}</p><p className="mt-0.5 truncate text-[9px] text-muted">Session {trace.networkSessionId}</p></div><Badge tone={trace.status === 'error' ? 'danger' : trace.status === 'running' ? 'warning' : 'production'}>{trace.status}</Badge></div>
        <div className="grid grid-cols-2 gap-1.5"><Metric label="Environment" value={trace.environment} /><Metric label="Elapsed" value={formatLatency(trace.durationMs)} /><Metric label="Current node" value={String(activeEvent?.nodeId ?? lastPathNode ?? '—')} /><Metric label="Hop" value={`${delegationCount(trace.execution.root)} / 8`} /></div>
        <CollapsibleSection title="Agent context resolution" badge={String(contextEvents.length)} defaultOpen><div className="space-y-1.5">{contextEvents.map((event) => <div key={event.id} className="rounded-lg border border-border/70 bg-background/45 p-2.5"><p className="text-[10px] text-white">{event.label}</p><JsonCodeBlock value={event.payload} maxHeight={128} className="mt-2" /></div>)}</div></CollapsibleSection>
        <CollapsibleSection title="Routing decisions" badge={String(routeEvents.length)} defaultOpen><div className="space-y-1.5">{routeEvents.map((event) => <div key={event.id} className="rounded-lg border border-border/70 bg-background/45 p-2.5"><div className="flex items-center gap-2"><GitBranch className="h-3 w-3 text-primary-light" /><code className="min-w-0 flex-1 truncate text-[10px] text-white">{event.type}</code><span className="text-[9px] text-muted">{new Date(event.timestamp).toLocaleTimeString()}</span></div><p className="mt-1 text-[9px] text-muted">{event.label}</p><JsonCodeBlock value={event.payload} maxHeight={112} className="mt-2" /></div>)}</div></CollapsibleSection>
        <CollapsibleSection title="Request context" defaultOpen><JsonCodeBlock value={{ message: trace.userMessage, network_session_id: trace.networkSessionId, environment: trace.environment, network_version: trace.networkVersion, composition_hash: trace.compositionHash, max_hops: 8, timeout_seconds: 90, entrypoint: 'ENTRY' }} maxHeight={180} /></CollapsibleSection>
        <CollapsibleSection title="Session composition" badge={`${trace.agentContexts.length} contexts`}><NetworkSessionComposition contexts={trace.agentContexts} /></CollapsibleSection>
        <CollapsibleSection title="Resolved composition" badge={`${invocationCount(trace.execution.root)} Agents`}><ResolvedComposition trace={trace} /></CollapsibleSection>
        <CollapsibleSection title="Event log" badge={String(trace.events.length)} defaultOpen><div className="space-y-1.5">{trace.events.map((event) => <div key={event.id} className="rounded-lg border border-border/70 bg-background/45 px-2.5 py-2"><div className="flex items-center gap-2"><span className={cn('h-1.5 w-1.5 shrink-0 rounded-full', event.status === 'error' ? 'bg-red-400' : event.status === 'running' ? 'bg-blue-400' : 'bg-emerald-400')} /><code className="min-w-0 flex-1 truncate text-[9px] text-white">{event.type}</code><span className="text-[9px] text-muted">#{event.sequence}</span></div><p className="mt-1 pl-3.5 text-[9px] text-muted">{event.label}</p></div>)}</div></CollapsibleSection>
        <CollapsibleSection title="Raw"><JsonCodeBlock value={trace} maxHeight={300} /></CollapsibleSection>
      </div>
    </ScrollArea>
  )
}
