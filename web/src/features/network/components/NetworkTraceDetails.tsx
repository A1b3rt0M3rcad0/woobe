import { Copy, GitBranch, Play } from 'lucide-react'

import { formatLatency } from '@/lib/formatters/number'
import { cn } from '@/lib/utils'

import { invocationCount, sourceCount, toolCount } from './networkChatExecution'
import type { AgentNodeId } from './networkWorkspaceTypes'
import type { NetworkTraceRecord } from './networkObservabilityTypes'
import { Badge } from './NetworkOperationsRail'
import { NetworkTraceInvocation } from './NetworkTraceTree'

const surface = 'rounded-xl border border-border/75 bg-background/35'

function copyText(value: string) {
  void navigator.clipboard.writeText(value)
}

function Metric({ label, value }: { label: string; value: string }) {
  return <div className="rounded-lg border border-border/70 bg-background/45 p-2.5"><p className="text-[8px] uppercase tracking-wide text-muted">{label}</p><p className="mt-1 text-[11px] font-medium text-white">{value}</p></div>
}

export function NetworkTraceDetails({ trace, onViewCanvas, onOpenAgent }: {
  trace: NetworkTraceRecord
  onViewCanvas: (trace: NetworkTraceRecord) => void
  onOpenAgent: (nodeId: AgentNodeId) => void
}) {
  const agents = invocationCount(trace.execution.root)
  const tools = toolCount(trace.execution.root)
  const sources = sourceCount(trace.execution.root)
  return (
    <div className="space-y-3 p-3">
      <div className="flex items-start gap-2">
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <Badge tone={trace.status === 'error' ? 'danger' : trace.status === 'running' ? 'warning' : 'production'}>{trace.status}</Badge>
            <Badge tone={trace.environment}>{trace.environment}</Badge>
          </div>
          <h3 className="mt-2 text-xs font-semibold text-white">{trace.title}</h3>
          <p className="mt-1 line-clamp-2 text-[9px] leading-4 text-muted">{trace.userMessage}</p>
        </div>
        <button type="button" onClick={() => onViewCanvas(trace)} className="inline-flex items-center gap-1 rounded-lg border border-primary/25 bg-primary/10 px-2.5 py-1.5 text-[9px] text-primary-light hover:text-white"><Play className="h-3 w-3" />View on Canvas</button>
      </div>
      <div className="grid grid-cols-4 gap-1.5">
        <Metric label="Agents" value={String(agents)} /><Metric label="Tools" value={String(tools)} /><Metric label="Sources" value={String(sources)} /><Metric label="Hops" value={String(trace.execution.path.length)} />
      </div>
      <div className={cn(surface, 'p-3')}>
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-[9px] text-muted"><span>{trace.networkVersion}</span><span>{formatLatency(trace.durationMs)}</span><span>${trace.costUsd.toFixed(3)}</span></div>
        <div className="mt-2 flex items-center gap-2"><code className="min-w-0 flex-1 truncate text-[8px] text-primary-light">trace {trace.traceId}</code><button type="button" onClick={() => copyText(trace.traceId)} className="text-muted hover:text-white" title="Copy trace ID"><Copy className="h-3 w-3" /></button></div>
        <p className="mt-1 truncate font-mono text-[8px] text-muted">composition {trace.compositionHash}</p>
      </div>
      <div>
        <div className="mb-2 flex items-center gap-1.5 text-[9px] font-medium uppercase tracking-wide text-muted"><GitBranch className="h-3 w-3" />Causal execution</div>
        <NetworkTraceInvocation invocation={trace.execution.root} trace={trace} depth={0} onOpenAgent={onOpenAgent} />
      </div>
    </div>
  )
}
