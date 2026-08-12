import { useState } from 'react'
import { CheckCircle, ChevronDown, ChevronRight, Loader2, Wrench, XCircle } from 'lucide-react'

import { JsonCodeBlock } from '@/components/ui/JsonCodeBlock'
import type { ToolCallInfo } from '@/features/playground/types'
import { formatLatency } from '@/lib/formatters/number'
import { cn } from '@/lib/utils'

interface ToolCallsCollapsibleProps {
  toolCalls: ToolCallInfo[]
  variant?: 'playground' | 'network'
}

function isRunningTool(toolCall: ToolCallInfo): boolean {
  return toolCall.status === 'running'
    || (toolCall.success == null && toolCall.status !== 'error')
}

function isFailedTool(toolCall: ToolCallInfo): boolean {
  return toolCall.success === false || toolCall.status === 'error'
}

function summaryLabel(toolCalls: ToolCallInfo[]): string {
  const running = toolCalls.filter(isRunningTool).length
  const failed = toolCalls.filter(isFailedTool).length
  const completed = toolCalls.length - running - failed
  const parts = [`Tool calls (${toolCalls.length})`]
  if (running) parts.push(`${running} running`)
  if (completed) parts.push(`${completed} completed`)
  if (failed) parts.push(`${failed} failed`)
  return parts.join(' · ')
}

export function ToolCallsCollapsible({
  toolCalls,
  variant = 'playground',
}: ToolCallsCollapsibleProps) {
  const [open, setOpen] = useState(false)
  const compact = variant === 'network'
  const hasRunningTool = toolCalls.some(isRunningTool)
  const hasFailedTool = toolCalls.some(isFailedTool)

  if (!toolCalls || toolCalls.length === 0) return null

  return (
    <div className={cn('space-y-1.5', compact ? 'mt-1.5' : 'mt-2')}>
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className={cn(
          'flex max-w-full items-center gap-1.5 transition-colors hover:text-white',
          compact ? 'text-[9px]' : 'text-xs',
          hasFailedTool ? 'text-red-300' : 'text-primary',
        )}
      >
        {open ? <ChevronDown className="h-3 w-3 shrink-0" /> : <ChevronRight className="h-3 w-3 shrink-0" />}
        {hasRunningTool
          ? <Loader2 className="h-3 w-3 shrink-0 animate-spin" />
          : hasFailedTool
            ? <XCircle className="h-3 w-3 shrink-0" />
            : <Wrench className="h-3 w-3 shrink-0" />}
        <span className="truncate">{summaryLabel(toolCalls)}</span>
      </button>
      {open && (
        <div className="space-y-1.5">
          {toolCalls.map((toolCall, index) => {
            const isRunning = isRunningTool(toolCall)
            const isSuccess = !isRunning && !isFailedTool(toolCall)
            const failureLabel = toolCall.error_code || toolCall.error
            return (
              <div
                key={toolCall.tool_call_id ?? index}
                className={cn(
                  'space-y-1.5 rounded-lg border',
                  compact ? 'p-2' : 'p-2.5',
                  isSuccess || isRunning ? 'border-border bg-background' : 'border-red-500/20 bg-red-500/5',
                )}
              >
                <div className="flex items-center justify-between gap-2">
                  <div className="flex min-w-0 flex-1 items-center gap-1.5">
                    {isRunning ? (
                      <Loader2 className={cn('shrink-0 animate-spin text-muted', compact ? 'h-3 w-3' : 'h-3.5 w-3.5')} />
                    ) : isSuccess ? (
                      <CheckCircle className={cn('shrink-0 text-emerald-400', compact ? 'h-3 w-3' : 'h-3.5 w-3.5')} />
                    ) : (
                      <XCircle className={cn('shrink-0 text-red-400', compact ? 'h-3 w-3' : 'h-3.5 w-3.5')} />
                    )}
                    <span className={cn('truncate font-medium text-white', compact ? 'text-[9px]' : 'text-xs')}>
                      {toolCall.tool_name}
                    </span>
                  </div>
                  <div className="flex shrink-0 items-center gap-2">
                    {isRunning && <span className={cn('text-muted', compact ? 'text-[8px]' : 'text-[10px]')}>running</span>}
                    {!isSuccess && !isRunning && failureLabel && (
                      <span
                        className={cn('truncate text-red-400', compact ? 'max-w-[90px] text-[8px]' : 'max-w-[120px] text-[10px]')}
                        title={toolCall.error || toolCall.error_code || undefined}
                      >
                        {failureLabel}
                      </span>
                    )}
                    {toolCall.duration_ms != null && (
                      <span className={cn('font-mono text-muted', compact ? 'text-[8px]' : 'text-[10px]')}>
                        {formatLatency(toolCall.duration_ms)}
                      </span>
                    )}
                  </div>
                </div>
                {toolCall.input != null && (
                  <div>
                    <p className={cn('mb-0.5 text-muted', compact ? 'text-[8px]' : 'text-[10px]')}>Input</p>
                    <JsonCodeBlock value={toolCall.input as Record<string, unknown>} maxHeight={compact ? 84 : 100} />
                  </div>
                )}
                {toolCall.output != null && (
                  <div>
                    <p className={cn('mb-0.5 text-muted', compact ? 'text-[8px]' : 'text-[10px]')}>Output</p>
                    <JsonCodeBlock value={toolCall.output as Record<string, unknown>} maxHeight={compact ? 84 : 100} />
                  </div>
                )}
                {toolCall.error && !isSuccess && !isRunning && (
                  <div className="rounded bg-red-500/10 px-2 py-1">
                    <p className={cn('break-all font-mono text-red-300', compact ? 'text-[8px]' : 'text-[10px]')}>
                      {toolCall.error_code ? `${toolCall.error_code}: ` : ''}{toolCall.error}
                    </p>
                  </div>
                )}
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
