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

export function ToolCallsCollapsible({
  toolCalls,
  variant = 'playground',
}: ToolCallsCollapsibleProps) {
  const [open, setOpen] = useState(false)
  const compact = variant === 'network'

  if (!toolCalls || toolCalls.length === 0) return null

  const completedCount = toolCalls.filter((toolCall) => toolCall.status !== 'running' && toolCall.success != null).length
  const successCount = toolCalls.filter((toolCall) => toolCall.success === true).length

  return (
    <div className={cn('space-y-1.5', compact ? 'mt-1.5' : 'mt-2')}>
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className={cn(
          'flex items-center gap-1.5 text-primary hover:underline',
          compact ? 'text-[9px]' : 'text-xs',
        )}
      >
        {open ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
        <Wrench className="h-3 w-3" />
        Tool calls ({successCount}/{completedCount || toolCalls.length})
      </button>
      {open && (
        <div className="space-y-1.5">
          {toolCalls.map((toolCall, index) => {
            const isRunning = toolCall.status === 'running' || toolCall.success == null
            const isSuccess = toolCall.success !== false
            return (
              <div
                key={toolCall.tool_call_id ?? index}
                className={cn(
                  'space-y-1.5 rounded-lg border',
                  compact ? 'p-2' : 'p-2.5',
                  isSuccess ? 'border-border bg-background' : 'border-red-500/20 bg-red-500/5',
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
                    {!isSuccess && toolCall.error && (
                      <span
                        className={cn('truncate text-red-400', compact ? 'max-w-[90px] text-[8px]' : 'max-w-[120px] text-[10px]')}
                        title={toolCall.error}
                      >
                        {toolCall.error}
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
                {toolCall.error && isSuccess === false && (
                  <div className="rounded bg-red-500/10 px-2 py-1">
                    <p className={cn('break-all font-mono text-red-300', compact ? 'text-[8px]' : 'text-[10px]')}>
                      {toolCall.error}
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
