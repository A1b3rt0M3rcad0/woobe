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

const surface = 'rounded-container border border-border/75 bg-background/35'

function Metric({ label, value }: { label: string; value: string }) {
  return <div className="rounded-control border border-border/70 bg-background/45 p-ui-sm"><p className="font-mono text-system-meta uppercase tracking-ui-label text-muted-foreground">{label}</p><p className="mt-ui-xs truncate font-sans text-product-small font-medium text-white">{value}</p></div>
}

function CollapsibleSection({ title, badge, defaultOpen = false, children }: { title: string; badge?: string; defaultOpen?: boolean; children: ReactNode }) {
  const [open, setOpen] = useState(defaultOpen)
  return <div className={surface}><button type="button" onClick={() => setOpen((value) => !value)} className="flex w-full items-center gap-ui-sm px-ui-md py-ui-sm text-left font-mono text-system-label font-medium text-white" aria-expanded={open}>{open ? <ChevronDown className="h-3.5 w-3.5 text-muted-foreground" /> : <ChevronRight className="h-3.5 w-3.5 text-muted-foreground" />}<span>{title}</span>{badge ? <span className="ml-auto text-system-meta text-muted-foreground">{badge}</span> : null}</button>{open ? <div className="border-t border-border/70 p-ui-sm">{children}</div> : null}</div>
}

function ResolvedComposition({ trace }: { trace: NetworkTraceRecord }) {
  const rows: NetworkAgentInvocation[] = []
  const visit = (invocation: NetworkAgentInvocation) => { rows.push(invocation); invocation.children.forEach(visit) }
  visit(trace.execution.root)
  return <div className="space-y-ui-sm">{rows.map((invocation) => <div key={invocation.spanId} className="rounded-control border border-border/70 bg-background/45 p-ui-sm"><div className="flex items-center gap-ui-sm"><Bot className="h-3.5 w-3.5 text-primary-light" /><span className="min-w-0 flex-1 truncate font-sans text-product-caption font-medium text-white">{invocation.agentName}</span><Badge tone={invocation.source === 'release' ? 'production' : invocation.source}>{invocation.source}</Badge></div><p className="mt-ui-xs truncate font-mono text-system-meta text-muted-foreground">{invocation.version}</p><p className="mt-ui-xs truncate font-mono text-system-meta text-primary-light">{invocation.agentSessionId ? `agent session ${invocation.agentSessionId}` : 'stateless invocation'}</p></div>)}</div>
}

export function NetworkDebugPanel({ trace }: { trace: NetworkTraceRecord | null }) {
  if (!trace) return <div className="flex h-full items-center justify-center p-ui-xl text-center"><div><Bug className="mx-auto h-8 w-8 text-muted-foreground/50" /><p className="mt-ui-md font-sans text-product-small text-muted-foreground">Select a Run from the active Network Session to inspect debug data.</p></div></div>
  const routeEvents = trace.events.filter((event) => event.type.startsWith('network.route.'))
  const contextEvents = trace.events.filter((event) => event.type === 'network.agent.context.resolved')
  const activeEvent = trace.events[trace.events.length - 1]
  const lastPathNode = trace.execution.path[trace.execution.path.length - 1]
  return (
    <ScrollArea className="h-full min-h-0">
      <div className="space-y-ui-sm p-ui-md">
        <div className="flex items-start gap-ui-sm"><div className="min-w-0 flex-1"><p className="font-mono text-system-heading font-semibold text-white">Debug</p><p className="mt-ui-xs font-sans text-product-caption text-muted-foreground">{trace.status === 'running' ? 'Live execution' : trace.traceId ? `Historical trace ${trace.traceId.slice(0, 8)}…` : `Historical run ${trace.id.slice(0, 8)}…`}</p><p className="mt-ui-hairline truncate font-mono text-system-meta text-muted-foreground">Session {trace.networkSessionId}</p></div><Badge tone={trace.status === 'error' ? 'danger' : trace.status === 'running' ? 'warning' : 'production'}>{trace.status}</Badge></div>
        <div className="grid grid-cols-2 gap-ui-sm"><Metric label="Environment" value={trace.environment} /><Metric label="Elapsed" value={formatLatency(trace.durationMs)} /><Metric label="Current node" value={String(activeEvent?.nodeId ?? lastPathNode ?? '—')} /><Metric label="Hop" value={`${delegationCount(trace.execution.root)} / 8`} /></div>
        <CollapsibleSection title="Agent context resolution" badge={String(contextEvents.length)} defaultOpen><div className="space-y-ui-sm">{contextEvents.map((event) => <div key={event.id} className="rounded-control border border-border/70 bg-background/45 p-ui-sm"><p className="font-sans text-product-caption text-white">{event.label}</p><JsonCodeBlock value={event.payload} maxHeight={128} className="mt-ui-sm" /></div>)}</div></CollapsibleSection>
        <CollapsibleSection title="Routing decisions" badge={String(routeEvents.length)} defaultOpen><div className="space-y-ui-sm">{routeEvents.map((event) => <div key={event.id} className="rounded-control border border-border/70 bg-background/45 p-ui-sm"><div className="flex items-center gap-ui-sm"><GitBranch className="h-3 w-3 text-primary-light" /><code className="min-w-0 flex-1 truncate font-mono text-system-meta text-white">{event.type}</code><span className="font-mono text-system-meta text-muted-foreground">{new Date(event.timestamp).toLocaleTimeString()}</span></div><p className="mt-ui-xs font-sans text-product-caption text-muted-foreground">{event.label}</p><JsonCodeBlock value={event.payload} maxHeight={112} className="mt-ui-sm" /></div>)}</div></CollapsibleSection>
        <CollapsibleSection title="Request context" defaultOpen><JsonCodeBlock value={{ message: trace.userMessage, network_session_id: trace.networkSessionId, environment: trace.environment, network_version: trace.networkVersion, composition_hash: trace.compositionHash, max_hops: 8, timeout_seconds: 90, entrypoint: 'ENTRY' }} maxHeight={180} /></CollapsibleSection>
        <CollapsibleSection title="Session composition" badge={`${trace.agentContexts.length} contexts`}><NetworkSessionComposition contexts={trace.agentContexts} /></CollapsibleSection>
        <CollapsibleSection title="Resolved composition" badge={`${invocationCount(trace.execution.root)} Agents`}><ResolvedComposition trace={trace} /></CollapsibleSection>
        <CollapsibleSection title="Event log" badge={String(trace.events.length)} defaultOpen><div className="space-y-ui-sm">{trace.events.map((event) => <div key={event.id} className="rounded-control border border-border/70 bg-background/45 px-ui-sm py-ui-sm"><div className="flex items-center gap-ui-sm"><span className={cn('h-1.5 w-1.5 shrink-0 rounded-full', event.status === 'error' ? 'bg-red-400' : event.status === 'running' ? 'bg-blue-400' : 'bg-emerald-400')} /><code className="min-w-0 flex-1 truncate font-mono text-system-meta text-white">{event.type}</code><span className="font-mono text-system-meta text-muted-foreground">#{event.sequence}</span></div><p className="mt-ui-xs pl-ui-md font-sans text-product-caption text-muted-foreground">{event.label}</p></div>)}</div></CollapsibleSection>
        <CollapsibleSection title="Raw"><JsonCodeBlock value={trace} maxHeight={300} /></CollapsibleSection>
      </div>
    </ScrollArea>
  )
}
