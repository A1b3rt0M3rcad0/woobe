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
    <div className="space-y-1">
      {visible.map(({ invocation, depth, role }) => {
        const toolSummary = toolSummaryLabel(invocation)
        return (
          <button
            key={invocation.spanId}
            type="button"
            onClick={() => onSelect(invocation)}
            className={cn(
              'group relative w-full rounded-lg px-2.5 py-2 text-left transition-colors hover:bg-background/55',
              selectedSpanId === invocation.spanId && 'bg-primary/10',
            )}
            style={{ paddingLeft: `${10 + Math.min(depth, 4) * 16}px` }}
          >
            {depth > 0 ? <CornerDownRight className="absolute left-1 top-2.5 h-3 w-3 text-muted/55" style={{ marginLeft: `${Math.min(depth - 1, 3) * 16}px` }} /> : null}
            <div className="flex items-start gap-2">
              <span className="mt-0.5 shrink-0"><StatusIcon status={invocation.status} /></span>
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2">
                  <p className="truncate text-[11px] font-medium text-white">{invocation.agentName}</p>
                  <span className="shrink-0 text-[8px] uppercase tracking-wide text-muted">{role === 'entry' ? 'Entry' : 'Delegated'}</span>
                  {invocation.durationMs != null ? <span className="ml-auto shrink-0 text-[9px] text-muted">{formatLatency(invocation.durationMs)}</span> : null}
                </div>
                <div className="mt-0.5 flex min-w-0 items-center gap-2 text-[9px] text-muted">
                  <span className="truncate">{invocation.source} · {invocation.version}</span>
                  {invocation.usage ? <span className="ml-auto shrink-0">{formatNumber(invocation.usage.input_tokens, 0)} / {formatNumber(invocation.usage.output_tokens, 0)} tokens</span> : null}
                </div>
                {toolSummary ? <p className={cn('mt-1 inline-flex items-center gap-1 text-[9px]', summarizeInvocationTools(invocation).failed ? 'text-red-300' : summarizeInvocationTools(invocation).running ? 'text-blue-300' : 'text-muted')}>{invocation.tools.some(isSkillOperation) ? <Puzzle className="h-3 w-3" /> : <Wrench className="h-3 w-3" />}{toolSummary}</p> : null}
              </div>
            </div>
          </button>
        )
      })}
      {hiddenCount > 0 && onViewAll ? (
        <button type="button" onClick={onViewAll} className="w-full rounded-lg border border-dashed border-border/80 px-3 py-2 text-[9px] text-muted hover:border-primary/30 hover:text-white">
          View {hiddenCount} more Agent Run{hiddenCount === 1 ? '' : 's'}
        </button>
      ) : null}
    </div>
  )
}
