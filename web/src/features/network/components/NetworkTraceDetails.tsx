import { useState, type ReactNode } from 'react'
import { CheckCircle2, ChevronDown, ChevronRight, CircleDot, Copy, GitBranch, Play, XCircle } from 'lucide-react'

import { JsonCodeBlock } from '@/components/ui/JsonCodeBlock'
import { formatCurrency, formatLatency, formatTokens } from '@/lib/formatters/number'
import { cn } from '@/lib/utils'

import { invocationCount, sourceCount, toolCount } from './networkChatExecution'
import type { AgentNodeId } from './networkWorkspaceTypes'
import type { NetworkTraceRecord } from './networkObservabilityTypes'
import type { NetworkSession } from './networkSessionTypes'
import { NetworkSessionComposition } from './NetworkSessionComposition'
import { NetworkTraceInvocation } from './NetworkTraceTree'

function CollapsibleSection({ title, badge, defaultOpen = false, children }: { title: string; badge?: string; defaultOpen?: boolean; children: ReactNode }) {
  const [open, setOpen] = useState(defaultOpen)
  return (
    <div className="border-t border-border/80 first:border-t-0">
      <button type="button" onClick={() => setOpen((value) => !value)} className="flex w-full items-center gap-1.5 py-2 text-left text-[11px] font-medium text-muted transition-colors hover:text-white" aria-expanded={open}>
        {open ? <ChevronDown className="h-3.5 w-3.5" /> : <ChevronRight className="h-3.5 w-3.5" />}
        <span>{title}</span>
        {badge ? <span className="ml-auto text-[10px] text-muted">{badge}</span> : null}
      </button>
      {open ? <div className="pb-3">{children}</div> : null}
    </div>
  )
}

function CopyableIdRow({ label, value }: { label: string; value: string }) {
  const [copied, setCopied] = useState(false)
  const copy = () => {
    void navigator.clipboard.writeText(value)
    setCopied(true)
    setTimeout(() => setCopied(false), 1200)
  }
  return (
    <div className="grid grid-cols-[92px_1fr_24px] items-center gap-2 rounded-md border border-border bg-background px-2.5 py-1.5">
      <span className="text-[10px] uppercase text-muted">{label}</span>
      <code className="truncate text-[10px] text-white">{value}</code>
      <button type="button" onClick={copy} className="text-muted hover:text-white" aria-label={`Copy ${label}`} title={copied ? 'Copied' : 'Copy'}><Copy className="h-3 w-3" /></button>
    </div>
  )
}

function Metric({ label, value }: { label: string; value: string }) {
  return <div className="rounded-lg border border-border/75 bg-background/45 p-2.5"><p className="text-[10px] uppercase tracking-wide text-muted">{label}</p><p className="mt-1 text-[12px] font-medium text-white">{value}</p></div>
}

export function NetworkTraceDetails({ trace, session, onViewCanvas, onOpenAgent }: {
  trace: NetworkTraceRecord
  session: NetworkSession
  onViewCanvas: (trace: NetworkTraceRecord) => void
  onOpenAgent: (nodeId: AgentNodeId) => void
}) {
  const agents = invocationCount(trace.execution.root)
  const tools = toolCount(trace.execution.root)
  const sources = sourceCount(trace.execution.root)
  const routeEvents = trace.events.filter((event) => event.type.startsWith('network.route.'))
  const running = trace.status === 'running'
  const completed = trace.status === 'success'
  const StatusIcon = running ? CircleDot : completed ? CheckCircle2 : XCircle
  const statusLabel = running ? 'Running' : completed ? 'Completed' : 'Failed'
  const statusSurface = running
    ? 'border-blue-500/25 bg-blue-500/10'
    : completed
      ? 'border-emerald-500/25 bg-emerald-500/10'
      : 'border-red-500/25 bg-red-500/10'
  const statusText = running ? 'text-blue-300' : completed ? 'text-emerald-300' : 'text-red-300'
  const totalTokens = trace.usage.total_tokens ?? ((trace.usage.input_tokens ?? 0) + (trace.usage.output_tokens ?? 0))

  return (
    <div className="space-y-3 p-4">
      <div className="flex items-start gap-3">
        <div className={cn('flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border', statusSurface)}>
          <StatusIcon className={cn('h-4 w-4', statusText, running && 'animate-pulse')} />
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="text-[13px] font-semibold text-white">Trace Detail</h3>
            <span className={cn('rounded-full border px-2 py-0.5 text-[10px] font-medium', statusSurface, statusText)}>{statusLabel}</span>
            <span className="rounded-md border border-border bg-background px-1.5 py-0.5 font-mono text-[10px] text-muted">{formatLatency(trace.durationMs)}</span>
          </div>
          <p className="mt-1 text-[10px] text-muted">{session.title} · {trace.networkVersion}</p>
        </div>
        <button type="button" onClick={() => onViewCanvas(trace)} className="inline-flex items-center gap-1 rounded-lg border border-primary/25 bg-primary/10 px-2.5 py-1.5 text-[10px] text-primary-light hover:text-white"><Play className="h-3 w-3" />View on Canvas</button>
      </div>

      <div className="grid grid-cols-4 gap-1.5">
        <Metric label="Agents" value={String(agents)} />
        <Metric label="Tools" value={String(tools)} />
        <Metric label="Sources" value={String(sources)} />
        <Metric label="Hops" value={String(trace.execution.path.length)} />
      </div>

      <div className="rounded-lg border border-border/75 bg-background/45 p-3">
        <p className="text-[10px] uppercase tracking-wide text-muted">Usage</p>
        <p className="mt-1 text-[11px] text-slate-200">Input {formatTokens(trace.usage.input_tokens)} · Output {formatTokens(trace.usage.output_tokens)} · Total {formatTokens(totalTokens)} · {formatCurrency(trace.costUsd)}</p>
      </div>

      <div className="rounded-lg border border-border/75 bg-background/45 p-3">
        <p className="text-[10px] font-medium uppercase tracking-wide text-muted">User Message</p>
        <p className="mt-1.5 whitespace-pre-wrap text-[11px] leading-5 text-white">{trace.userMessage}</p>
      </div>

      <div className="rounded-lg border border-border/75 bg-background/45 p-3">
        <p className="text-[10px] font-medium uppercase tracking-wide text-muted">Final Response</p>
        <p className="mt-1.5 whitespace-pre-wrap text-[11px] leading-5 text-slate-200">{trace.answer}</p>
      </div>

      {trace.outputParseError ? (
        <div className="rounded-lg border border-red-500/30 bg-red-500/5 p-3">
          <p className="text-[11px] font-medium text-red-300">Output Parse Error</p>
          <p className="mt-1 break-all text-[10px] text-muted">{trace.outputParseError}</p>
        </div>
      ) : null}

      <div className="rounded-xl border border-border/80 bg-background/30 px-3">
        <CollapsibleSection title="Execution" badge={`${agents} Agents`} defaultOpen>
          <NetworkTraceInvocation invocation={trace.execution.root} trace={trace} depth={0} onOpenAgent={onOpenAgent} />
        </CollapsibleSection>
        <CollapsibleSection title="Routing Decisions" badge={String(routeEvents.length)}>
          <div className="space-y-2">{routeEvents.map((event) => <div key={event.id} className="rounded-lg border border-border bg-background/55 p-2.5"><div className="flex items-center gap-1.5"><GitBranch className="h-3.5 w-3.5 text-primary-light" /><code className="text-[10px] text-white">{event.type}</code></div><p className="mt-1 text-[10px] text-muted">{event.label}</p><JsonCodeBlock value={event.payload} maxHeight={128} className="mt-2" /></div>)}</div>
        </CollapsibleSection>
        {trace.parsedOutput ? <CollapsibleSection title="Structured Output"><JsonCodeBlock value={trace.parsedOutput} maxHeight={160} /></CollapsibleSection> : null}
        <CollapsibleSection title="Session Composition" badge={`${trace.agentContexts.length} contexts`}>
          <NetworkSessionComposition contexts={trace.agentContexts} />
        </CollapsibleSection>
        <CollapsibleSection title="Composition Snapshot">
          <JsonCodeBlock value={{ environment: trace.environment, network_version: trace.networkVersion, composition_hash: trace.compositionHash, agents: trace.agentContexts.map((context) => ({ node_id: context.nodeId, agent_id: context.agentId, source: context.source, version: context.version, session_mode: context.sessionMode })) }} maxHeight={220} />
        </CollapsibleSection>
        <CollapsibleSection title="Events" badge={String(trace.events.length)}>
          <div className="space-y-1.5">{trace.events.map((event) => <div key={event.id} className="rounded-lg border border-border bg-background/55 px-3 py-2"><div className="flex items-center justify-between gap-2"><code className="truncate text-[10px] text-white">{event.type}</code><span className="text-[9px] text-muted">#{event.sequence}</span></div><p className="mt-1 text-[10px] text-muted">{event.label}</p><JsonCodeBlock value={event.payload} maxHeight={112} className="mt-2" /></div>)}</div>
        </CollapsibleSection>
        <CollapsibleSection title="Raw"><JsonCodeBlock value={trace} maxHeight={280} /></CollapsibleSection>
      </div>

      <div className="space-y-1 border-t border-border pt-3">
        <CopyableIdRow label="trace" value={trace.traceId} />
        <CopyableIdRow label="network session" value={trace.networkSessionId} />
        <CopyableIdRow label="network" value={session.networkId} />
        <CopyableIdRow label="project" value={session.projectId} />
      </div>
    </div>
  )
}
