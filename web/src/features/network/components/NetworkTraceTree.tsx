import { useState } from 'react'
import {
  Bot,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  CircleDot,
  Copy,
  Database,
  GitBranch,
  XCircle,
} from 'lucide-react'

import { JsonCodeBlock } from '@/components/ui/JsonCodeBlock'
import { ToolCallsCollapsible } from '@/features/playground/components/ToolCallsCollapsible'
import { formatLatency, formatNumber } from '@/lib/formatters/number'
import { cn } from '@/lib/utils'

import type { NetworkAgentInvocation } from './networkChatExecution'
import type { AgentNodeId } from './networkWorkspaceTypes'
import type { NetworkTraceEvent, NetworkTraceRecord } from './networkObservabilityTypes'
import { Badge } from './NetworkOperationsRail'

const surface = 'rounded-xl border border-border/75 bg-background/35'

function copyText(value: string) {
  void navigator.clipboard.writeText(value)
}

function SourcesList({ invocation }: { invocation: NetworkAgentInvocation }) {
  if (!invocation.sources.length) return null
  return (
    <div className="space-y-1.5">
      {invocation.sources.map((source, index) => (
        <div key={source.chunk_id || `${source.document_id || 'source'}-${index}`} className="rounded-lg border border-border/70 bg-background/45 p-2.5">
          <div className="flex items-center gap-2">
            <Database className="h-3.5 w-3.5 shrink-0 text-violet-300" />
            <span className="min-w-0 flex-1 truncate text-[10px] text-white">{source.document_title || 'Untitled source'}</span>
            {source.page_number != null ? <span className="text-[9px] text-muted">p. {source.page_number}</span> : null}
            {source.score != null ? <span className="text-[9px] text-muted">{formatNumber(source.score * 100, 0)}%</span> : null}
          </div>
          {source.content_preview ? <p className="mt-1 line-clamp-3 text-[10px] leading-4 text-muted">{source.content_preview}</p> : null}
        </div>
      ))}
    </div>
  )
}

function RoutingDecision({ event }: { event: NetworkTraceEvent | undefined }) {
  if (!event) return null
  const selectedNode = String(event.payload.selected_node ?? event.payload.candidate_node ?? 'unknown')
  const confidence = typeof event.payload.confidence === 'number' ? event.payload.confidence : null
  return (
    <div className="rounded-lg border border-primary/20 bg-primary/5 p-2.5">
      <div className="flex items-center gap-1.5 text-[10px] font-medium text-primary-light"><GitBranch className="h-3.5 w-3.5" />Routing decision</div>
      <div className="mt-1.5 flex flex-wrap items-center gap-x-2 gap-y-1 text-[9px] text-muted">
        <span>Selected {selectedNode}</span>
        {confidence != null ? <span>Confidence {confidence.toFixed(2)}</span> : null}
      </div>
      {typeof event.payload.reason === 'string' ? <p className="mt-1 text-[9px] leading-4 text-slate-300">{event.payload.reason}</p> : null}
    </div>
  )
}

function ContextSummary({ invocation }: { invocation: NetworkAgentInvocation }) {
  const label = invocation.contextState === 'stateless'
    ? 'Stateless invocation'
    : invocation.contextState === 'created'
      ? 'Stateful context · created now'
      : `Stateful context · reused after ${invocation.previousInvocationCount} invocation${invocation.previousInvocationCount === 1 ? '' : 's'}`
  return (
    <div className="rounded-lg border border-border/70 bg-background/45 p-2.5">
      <div className="flex items-center gap-2">
        <span className={cn('h-2 w-2 rounded-full', invocation.contextState === 'stateless' ? 'bg-slate-400' : invocation.contextState === 'created' ? 'bg-blue-400' : 'bg-emerald-400')} />
        <p className="min-w-0 flex-1 text-[10px] text-slate-200">{label}</p>
      </div>
      {invocation.agentSessionId ? <div className="mt-2 flex items-center gap-2"><code className="min-w-0 flex-1 truncate text-[9px] text-primary-light">agent session {invocation.agentSessionId}</code><button type="button" onClick={() => copyText(invocation.agentSessionId!)} className="text-muted hover:text-white" aria-label="Copy Agent Session ID"><Copy className="h-3 w-3" /></button></div> : null}
      {invocation.childTraceId ? <div className="mt-1 flex items-center gap-2"><code className="min-w-0 flex-1 truncate text-[9px] text-muted">child trace {invocation.childTraceId}</code><button type="button" onClick={() => copyText(invocation.childTraceId!)} className="text-muted hover:text-white" aria-label="Copy child trace ID"><Copy className="h-3 w-3" /></button></div> : null}
    </div>
  )
}

export function NetworkTraceInvocation({ invocation, trace, depth, onOpenAgent }: {
  invocation: NetworkAgentInvocation
  trace: NetworkTraceRecord
  depth: number
  onOpenAgent: (nodeId: AgentNodeId) => void
}) {
  const [open, setOpen] = useState(false)
  const routingEvent = trace.events.find((event) => event.type === 'network.route.selected' && event.spanId === invocation.spanId)
  const statusIcon = invocation.status === 'error'
    ? <XCircle className="h-3.5 w-3.5 text-red-400" />
    : invocation.status === 'cancelled'
      ? <XCircle className="h-3.5 w-3.5 text-slate-400" />
      : invocation.status === 'running'
        ? <CircleDot className="h-3.5 w-3.5 animate-pulse text-blue-400" />
        : <CheckCircle2 className="h-3.5 w-3.5 text-emerald-400" />

  return (
    <div className={cn(depth > 0 && 'border-l border-border/80 pl-2.5')}>
      <article className={cn(surface, invocation.status === 'error' && 'border-red-500/30')}>
        <div className="flex items-start gap-2.5 p-2.5">
          <div className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-lg border border-border bg-surface">{statusIcon}</div>
          <div className="min-w-0 flex-1">
            <div className="flex min-w-0 flex-wrap items-center gap-1.5">
              <p className="truncate text-[11px] font-medium text-white">{invocation.agentName}</p>
              <Badge tone={invocation.source === 'release' ? 'production' : invocation.source}>{invocation.source}</Badge>
            </div>
            <p className="mt-1 truncate font-mono text-[9px] text-muted">{invocation.provider || '—'}/{invocation.model || '—'} · {invocation.version}</p>
            <div className="mt-1 flex flex-wrap gap-x-2 gap-y-1 text-[9px] text-muted">
              {invocation.durationMs != null ? <span>{formatLatency(invocation.durationMs)}</span> : null}
              {invocation.usage ? <span>{formatNumber(invocation.usage.input_tokens, 0)} in / {formatNumber(invocation.usage.output_tokens, 0)} out</span> : null}
              {invocation.costUsd != null ? <span>${invocation.costUsd.toFixed(3)}</span> : null}
            </div>
          </div>
          {invocation.nodeId ? <button type="button" onClick={() => onOpenAgent(invocation.nodeId!)} className="rounded-md border border-border/80 px-2 py-1 text-[9px] text-muted hover:border-primary/30 hover:text-white">Open Agent</button> : null}
          <button type="button" onClick={() => setOpen((value) => !value)} className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md text-muted hover:bg-surface hover:text-white" aria-label={open ? 'Collapse invocation' : 'Expand invocation'} aria-expanded={open}>
            {open ? <ChevronDown className="h-3.5 w-3.5" /> : <ChevronRight className="h-3.5 w-3.5" />}
          </button>
        </div>
        {open ? (
          <div className="space-y-2 border-t border-border/70 p-2.5">
            <ContextSummary invocation={invocation} />
            {invocation.failure ? (
              <div className="rounded-lg border border-red-500/30 bg-red-500/5 p-2.5">
                <p className="text-[10px] font-medium text-red-300">{invocation.failure.message}</p>
                <p className="mt-1 font-mono text-[9px] text-muted">{invocation.failure.code} · {invocation.failure.stage}{invocation.failure.retryable ? ' · retryable' : ''}</p>
              </div>
            ) : null}
            {invocation.input !== undefined ? <div><p className="mb-1.5 text-[9px] font-medium uppercase tracking-wide text-muted">Input</p><JsonCodeBlock value={invocation.input} maxHeight={128} /></div> : null}
            {invocation.output ? <div className="rounded-lg border border-border/70 bg-surface/45 p-2.5"><p className="text-[9px] uppercase tracking-wide text-muted">Output</p><p className="mt-1 whitespace-pre-wrap text-[10px] leading-4 text-slate-200">{invocation.output}</p></div> : null}
            {invocation.parsedOutput ? <JsonCodeBlock value={invocation.parsedOutput} maxHeight={128} /> : null}
            <RoutingDecision event={routingEvent} />
            {invocation.tools.length ? <ToolCallsCollapsible toolCalls={invocation.tools} variant="network" /> : null}
            <SourcesList invocation={invocation} />
            {invocation.children.length ? (
              <div className="space-y-2">
                <div className="flex items-center gap-1.5 text-[9px] font-medium uppercase tracking-wide text-muted"><Bot className="h-3 w-3" />Agents called ({invocation.children.length})</div>
                {invocation.children.map((child) => <NetworkTraceInvocation key={child.spanId} invocation={child} trace={trace} depth={Math.min(depth + 1, 3)} onOpenAgent={onOpenAgent} />)}
              </div>
            ) : null}
            <JsonCodeBlock value={{ span_id: invocation.spanId, parent_span_id: invocation.parentSpanId, agent_id: invocation.agentId, agent_session_id: invocation.agentSessionId, child_trace_id: invocation.childTraceId, node_id: invocation.nodeId }} maxHeight={112} />
          </div>
        ) : null}
      </article>
    </div>
  )
}
