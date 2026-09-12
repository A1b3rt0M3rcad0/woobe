import { useState } from 'react'
import { operationGroups, operationLabel } from '@/features/skills/operations'
import { CheckCircle, ChevronDown, ChevronRight, Loader2, Puzzle, Wrench, XCircle } from 'lucide-react'

import { JsonCodeBlock } from '@/components/ui/JsonCodeBlock'
import type { ToolCallInfo } from '@/features/playground/types'
import { formatLatency } from '@/lib/formatters/number'
import { cn } from '@/lib/utils'

interface ToolCallsCollapsibleProps {
  toolCalls: ToolCallInfo[]
  variant?: 'playground' | 'network'
}

function isRunningTool(toolCall: ToolCallInfo): boolean {
  if (isFailedTool(toolCall)) return false
  return toolCall.status === 'running' || (toolCall.success == null && toolCall.status !== 'error')
}

function isFailedTool(toolCall: ToolCallInfo): boolean {
  return toolCall.success === false || toolCall.status === 'error' || toolCall.status === 'failed'
}

function summaryLabel(toolCalls: ToolCallInfo[], label: string): string {
  const running = toolCalls.filter(isRunningTool).length
  const failed = toolCalls.filter(isFailedTool).length
  const completed = toolCalls.length - running - failed
  const parts = [`${label} (${toolCalls.length})`]
  if (running) parts.push(`${running} running`)
  if (completed) parts.push(`${completed} completed`)
  if (failed) parts.push(`${failed} failed`)
  return parts.join(' · ')
}

function OperationGroup({ toolCalls, variant = 'playground', label, kind }: ToolCallsCollapsibleProps & { label: string; kind: 'skill' | 'tool' }) {
  const [open, setOpen] = useState(false)
  const compact = variant === 'network'
  const hasRunningTool = toolCalls.some(isRunningTool)
  const hasFailedTool = toolCalls.some(isFailedTool)

  if (!toolCalls.length) return null

  return (
    <div className="overflow-hidden rounded-container border border-border/70 bg-background/20">
      <button
        type="button"
        onClick={() => setOpen(!open)}
        aria-expanded={open}
        className={cn('flex min-h-[34px] w-full items-center gap-1.5 px-2.5 py-2 font-mono text-[8px] transition-colors hover:bg-control/25', hasFailedTool ? 'text-red-300' : 'text-muted-foreground hover:text-slate-50')}
      >
        {open ? <ChevronDown className="h-3 w-3 shrink-0" /> : <ChevronRight className="h-3 w-3 shrink-0" />}
        {hasRunningTool ? <Loader2 className="h-3 w-3 shrink-0 animate-spin" /> : hasFailedTool ? <XCircle className="h-3 w-3 shrink-0" /> : kind === 'skill' ? <Puzzle className="h-3 w-3 shrink-0 text-primary-light" /> : <Wrench className="h-3 w-3 shrink-0 text-primary-light" />}
        <span className="truncate font-semibold">{summaryLabel(toolCalls, label)}</span>
      </button>

      {open ? (
        <div className="border-t border-border/60">
          {toolCalls.map((toolCall, index) => {
            const isRunning = isRunningTool(toolCall)
            const isSuccess = !isRunning && !isFailedTool(toolCall)
            const failureLabel = toolCall.error_code || toolCall.error
            return (
              <div key={toolCall.tool_call_id ?? index} className="border-t border-border/50 px-2.5 py-2.5 first:border-t-0">
                <div className="flex items-center justify-between gap-2">
                  <div className="flex min-w-0 flex-1 items-center gap-1.5">
                    {isRunning ? <Loader2 className="h-3 w-3 shrink-0 animate-spin text-muted-foreground" /> : isSuccess ? <CheckCircle className="h-3 w-3 shrink-0 text-emerald-400" /> : <XCircle className="h-3 w-3 shrink-0 text-red-400" />}
                    <span className="truncate font-mono text-[8px] font-semibold text-slate-200">{operationLabel(toolCall)}</span>
                  </div>
                  <div className="flex shrink-0 items-center gap-2 font-mono text-[8px]">
                    {isRunning ? <span className="text-muted-foreground">running</span> : null}
                    {!isSuccess && !isRunning && failureLabel ? <span className="max-w-[120px] truncate text-red-300" title={toolCall.error || toolCall.error_code || undefined}>{failureLabel}</span> : null}
                    {toolCall.duration_ms != null ? <span className="text-muted-foreground">{formatLatency(toolCall.duration_ms)}</span> : null}
                  </div>
                </div>

                {(toolCall.input != null || toolCall.output != null || (toolCall.error && !isSuccess && !isRunning)) ? (
                  <div className={cn('mt-2 space-y-1.5', compact && 'space-y-1')}>
                    {toolCall.input != null ? <JsonCodeBlock title="Input" value={toolCall.input as Record<string, unknown>} maxHeight={compact ? 84 : 120} /> : null}
                    {toolCall.output != null ? <JsonCodeBlock title="Output" value={toolCall.output as Record<string, unknown>} maxHeight={compact ? 84 : 120} /> : null}
                    {toolCall.error && !isSuccess && !isRunning ? <div className="rounded-container border border-red-500/20 bg-background/25 px-2.5 py-2 font-mono text-[8px] leading-4 text-red-300">{toolCall.error_code ? `${toolCall.error_code}: ` : ''}{toolCall.error}</div> : null}
                  </div>
                ) : null}
              </div>
            )
          })}
        </div>
      ) : null}
    </div>
  )
}

export function ToolCallsCollapsible({ toolCalls, variant }: ToolCallsCollapsibleProps) {
  return <div className="space-y-1.5">{operationGroups(toolCalls ?? []).map(group => <OperationGroup key={group.kind} toolCalls={group.calls} variant={variant} label={group.label} kind={group.kind} />)}</div>
}
