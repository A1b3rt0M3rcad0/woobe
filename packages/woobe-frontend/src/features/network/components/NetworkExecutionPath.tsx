import { isSkillOperation, operationCountsLabel } from '@/features/skills/operations'
import {
  CheckCircle2,
  CircleDot,
  CornerDownRight,
  Wrench,
  Puzzle,
  XCircle,
} from 'lucide-react'

import { formatLatency, formatNumber } from '@/lib/formatters/number'
import { cn } from '@/lib/utils'

import { operationalTools, type NetworkAgentInvocation } from './networkChatExecution'
import {
  flattenNetworkInvocationPath,
  summarizeInvocationTools,
} from './networkRunInspector'

function StatusIcon({ status }: { status: NetworkAgentInvocation['status'] }) {
  if (status === 'error') return <XCircle className="h-3.5 w-3.5 text-red-400" />
  if (status === 'cancelled') return <XCircle className="h-3.5 w-3.5 text-slate-400" />
  if (status === 'running' || status === 'pending') return <CircleDot className="h-3.5 w-3.5 animate-pulse text-blue-400" />
  return <CheckCircle2 className="h-3.5 w-3.5 text-emerald-400" />
}

function toolSummaryLabel(invocation: NetworkAgentInvocation) {
  const summary = summarizeInvocationTools(invocation)
  if (!summary.total) return null
  const states = [
    summary.running ? `${summary.running} running` : null,
    summary.completed ? `${summary.completed} completed` : null,
    summary.failed ? `${summary.failed} failed` : null,
  ].filter(Boolean)
  return `${operationCountsLabel(operationalTools(invocation.tools))}${states.length ? ` · ${states.join(' · ')}` : ''}`
}

export function NetworkExecutionPath({
  root,
  limit,
  selectedSpanId,
  onSelect,
  onViewAll,
}: {
  root: NetworkAgentInvocation
  limit?: number
  selectedSpanId?: string | null
  onSelect: (invocation: NetworkAgentInvocation) => void
  onViewAll?: () => void
}) {
  const items = flattenNetworkInvocationPath(root)
  const visible = limit ? items.slice(0, limit) : items
  const hiddenCount = items.length - visible.length

  return (
    <div className="space-y-ui-xs">
      {visible.map(({ invocation, depth, role }) => {
        const toolSummary = toolSummaryLabel(invocation)
        const toolSummaryState = summarizeInvocationTools(invocation)
        return (
          <button
            key={invocation.spanId}
            type="button"
            onClick={() => onSelect(invocation)}
            className={cn(
              'group relative w-full rounded-control px-ui-sm py-ui-sm text-left transition-colors hover:bg-background/55',
              selectedSpanId === invocation.spanId && 'bg-primary/10',
            )}
            style={{ paddingLeft: `${10 + Math.min(depth, 4) * 16}px` }}
          >
            {depth > 0 ? <CornerDownRight className="absolute left-1 top-2.5 h-3 w-3 text-muted-foreground/55" style={{ marginLeft: `${Math.min(depth - 1, 3) * 16}px` }} /> : null}
            <div className="flex items-start gap-ui-sm">
              <span className="mt-ui-hairline shrink-0"><StatusIcon status={invocation.status} /></span>
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-ui-sm">
                  <p className="truncate font-sans text-product-small font-medium text-white">{invocation.agentName}</p>
                  <span className="shrink-0 font-mono text-system-meta uppercase tracking-ui-label text-muted-foreground">{role === 'entry' ? 'Entry' : 'Delegated'}</span>
                  {invocation.durationMs != null ? <span className="ml-auto shrink-0 font-mono text-system-meta text-muted-foreground">{formatLatency(invocation.durationMs)}</span> : null}
                </div>
                <div className="mt-ui-hairline flex min-w-0 items-center gap-ui-sm font-mono text-system-meta text-muted-foreground">
                  <span className="truncate">{invocation.source} · {invocation.version}</span>
                  {invocation.usage ? <span className="ml-auto shrink-0">{formatNumber(invocation.usage.input_tokens, 0)} / {formatNumber(invocation.usage.output_tokens, 0)} tokens</span> : null}
                </div>
                {toolSummary ? <p className={cn('mt-ui-xs inline-flex items-center gap-ui-xs font-mono text-system-meta', toolSummaryState.failed ? 'text-red-300' : toolSummaryState.running ? 'text-blue-300' : 'text-muted-foreground')}>{invocation.tools.some(isSkillOperation) ? <Puzzle className="h-3 w-3" /> : <Wrench className="h-3 w-3" />}{toolSummary}</p> : null}
              </div>
            </div>
          </button>
        )
      })}
      {hiddenCount > 0 && onViewAll ? (
        <button type="button" onClick={onViewAll} className="w-full rounded-control border border-dashed border-border/80 px-ui-md py-ui-sm font-mono text-system-micro text-muted-foreground transition-colors hover:border-primary/30 hover:text-white">
          View {hiddenCount} more Agent Run{hiddenCount === 1 ? '' : 's'}
        </button>
      ) : null}
    </div>
  )
}
