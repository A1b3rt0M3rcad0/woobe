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

const surface = 'rounded-container border border-border/75 bg-background/35'

function copyText(value: string) {
  void navigator.clipboard.writeText(value)
}

function SourcesList({ invocation }: { invocation: NetworkAgentInvocation }) {
  if (!invocation.sources.length) return null
  return (
    <div className="space-y-ui-sm">
      {invocation.sources.map((source, index) => (
        <div key={source.chunk_id || `${source.document_id || 'source'}-${index}`} className="rounded-control border border-border/70 bg-background/45 p-ui-sm">
          <div className="flex items-center gap-ui-sm">
            <Database className="h-3.5 w-3.5 shrink-0 text-violet-300" />
            <span className="min-w-0 flex-1 truncate font-sans text-product-small text-white">{source.document_title || 'Untitled source'}</span>
            {source.page_number != null ? <span className="font-mono text-system-meta text-muted-foreground">p. {source.page_number}</span> : null}
            {source.score != null ? <span className="font-mono text-system-meta text-muted-foreground">{formatNumber(source.score * 100, 0)}%</span> : null}
          </div>
          {source.content_preview ? <p className="mt-ui-xs line-clamp-3 font-sans text-product-caption leading-4 text-muted-foreground">{source.content_preview}</p> : null}
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
    <div className="rounded-control border border-primary/20 bg-primary/5 p-ui-sm">
      <div className="flex items-center gap-ui-xs font-mono text-system-control font-medium text-primary-light"><GitBranch className="h-3.5 w-3.5" />Routing decision</div>
      <div className="mt-ui-sm flex flex-wrap items-center gap-x-ui-sm gap-y-ui-xs font-mono text-system-meta text-muted-foreground">
        <span>Selected {selectedNode}</span>
        {confidence != null ? <span>Confidence {confidence.toFixed(2)}</span> : null}
      </div>
      {typeof event.payload.reason === 'string' ? <p className="mt-ui-xs font-sans text-product-caption leading-4 text-slate-300">{event.payload.reason}</p> : null}
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
    <div className="rounded-control border border-border/70 bg-background/45 p-ui-sm">
      <div className="flex items-center gap-ui-sm">
        <span className={cn('h-2 w-2 rounded-full', invocation.contextState === 'stateless' ? 'bg-slate-400' : invocation.contextState === 'created' ? 'bg-blue-400' : 'bg-emerald-400')} />
        <p className="min-w-0 flex-1 font-sans text-product-caption text-slate-200">{label}</p>
      </div>
      {invocation.agentSessionId ? <div className="mt-ui-sm flex items-center gap-ui-sm"><code className="min-w-0 flex-1 truncate font-mono text-system-meta text-primary-light">agent session {invocation.agentSessionId}</code><button type="button" onClick={() => copyText(invocation.agentSessionId!)} className="text-muted-foreground transition-colors hover:text-white" aria-label="Copy Agent Session ID"><Copy className="h-3 w-3" /></button></div> : null}
      {invocation.childTraceId ? <div className="mt-ui-xs flex items-center gap-ui-sm"><code className="min-w-0 flex-1 truncate font-mono text-system-meta text-muted-foreground">child trace {invocation.childTraceId}</code><button type="button" onClick={() => copyText(invocation.childTraceId!)} className="text-muted-foreground transition-colors hover:text-white" aria-label="Copy child trace ID"><Copy className="h-3 w-3" /></button></div> : null}
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
    <div className={cn(depth > 0 && 'border-l border-border/80 pl-ui-sm')}>
      <article className={cn(surface, invocation.status === 'error' && 'border-red-500/30')}>
        <div className="flex items-start gap-ui-sm p-ui-sm">
          <div className="mt-ui-hairline flex h-control-sm w-control-sm shrink-0 items-center justify-center rounded-control border border-border bg-surface">{statusIcon}</div>
          <div className="min-w-0 flex-1">
            <div className="flex min-w-0 flex-wrap items-center gap-ui-xs">
              <p className="truncate font-sans text-product-small font-medium text-white">{invocation.agentName}</p>
              <Badge tone={invocation.source === 'release' ? 'production' : invocation.source}>{invocation.source}</Badge>
            </div>
            <p className="mt-ui-xs truncate font-mono text-system-meta text-muted-foreground">{invocation.provider || '—'}/{invocation.model || '—'} · {invocation.version}</p>
            <div className="mt-ui-xs flex flex-wrap gap-x-ui-sm gap-y-ui-xs font-mono text-system-meta text-muted-foreground">
              {invocation.durationMs != null ? <span>{formatLatency(invocation.durationMs)}</span> : null}
              {invocation.usage ? <span>{formatNumber(invocation.usage.input_tokens, 0)} in / {formatNumber(invocation.usage.output_tokens, 0)} out</span> : null}
              {invocation.costUsd != null ? <span>${invocation.costUsd.toFixed(3)}</span> : null}
            </div>
          </div>
          {invocation.nodeId ? <button type="button" onClick={() => onOpenAgent(invocation.nodeId!)} className="h-control-segment rounded-control border border-border/80 px-ui-sm font-mono text-system-micro text-muted-foreground transition-colors hover:border-primary/30 hover:text-white">Open Agent</button> : null}
          <button type="button" onClick={() => setOpen((value) => !value)} className="flex h-control-segment w-control-segment shrink-0 items-center justify-center rounded-control text-muted-foreground transition-colors hover:bg-surface hover:text-white" aria-label={open ? 'Collapse invocation' : 'Expand invocation'} aria-expanded={open}>
            {open ? <ChevronDown className="h-3.5 w-3.5" /> : <ChevronRight className="h-3.5 w-3.5" />}
          </button>
        </div>
        {open ? (
          <div className="space-y-ui-sm border-t border-border/70 p-ui-sm">
            <ContextSummary invocation={invocation} />
            {invocation.failure ? (
              <div className="rounded-control border border-red-500/30 bg-red-500/5 p-ui-sm">
                <p className="font-sans text-product-caption font-medium text-red-300">{invocation.failure.message}</p>
                <p className="mt-ui-xs font-mono text-system-meta text-muted-foreground">{invocation.failure.code} · {invocation.failure.stage}{invocation.failure.retryable ? ' · retryable' : ''}</p>
              </div>
            ) : null}
            {invocation.input !== undefined ? <div><p className="mb-ui-sm font-mono text-system-meta font-medium uppercase tracking-ui-label text-muted-foreground">Input</p><JsonCodeBlock value={invocation.input} maxHeight={128} /></div> : null}
            {invocation.output ? <div className="rounded-control border border-border/70 bg-surface/45 p-ui-sm"><p className="font-mono text-system-meta uppercase tracking-ui-label text-muted-foreground">Output</p><p className="mt-ui-xs whitespace-pre-wrap font-sans text-product-caption leading-4 text-slate-200">{invocation.output}</p></div> : null}
            {invocation.parsedOutput ? <JsonCodeBlock value={invocation.parsedOutput} maxHeight={128} /> : null}
            <RoutingDecision event={routingEvent} />
            {invocation.tools.length ? <ToolCallsCollapsible toolCalls={invocation.tools} variant="network" /> : null}
            <SourcesList invocation={invocation} />
            {invocation.children.length ? (
              <div className="space-y-ui-sm">
                <div className="flex items-center gap-ui-xs font-mono text-system-meta font-medium uppercase tracking-ui-label text-muted-foreground"><Bot className="h-3 w-3" />Agents called ({invocation.children.length})</div>
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
