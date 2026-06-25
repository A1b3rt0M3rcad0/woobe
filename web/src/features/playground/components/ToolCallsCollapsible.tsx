import { useState } from 'react'
import { ChevronDown, ChevronRight, Wrench, CheckCircle, XCircle, Loader2 } from 'lucide-react'
import { formatLatency } from '@/lib/formatters/number'
import { JsonCodeBlock } from '@/components/ui/JsonCodeBlock'
import type { ToolCallInfo } from '@/features/playground/types'

interface ToolCallsCollapsibleProps {
  toolCalls: ToolCallInfo[]
}

export function ToolCallsCollapsible({ toolCalls }: ToolCallsCollapsibleProps) {
  const [open, setOpen] = useState(false)

  if (!toolCalls || toolCalls.length === 0) return null

  const completedCount = toolCalls.filter(tc => tc.status !== 'running' && tc.success != null).length
  const successCount = toolCalls.filter(tc => tc.success === true).length

  return (
    <div className="mt-2 space-y-1.5">
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-1.5 text-xs text-primary hover:underline"
      >
        {open ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
        <Wrench className="h-3 w-3" />
        Tool calls ({successCount}/{completedCount || toolCalls.length})
      </button>
      {open && (
        <div className="space-y-1.5">
          {toolCalls.map((tc, i) => {
            const isRunning = tc.status === 'running' || tc.success == null
            const isSuccess = tc.success !== false
            return (
            <div key={tc.tool_call_id ?? i} className={`rounded-lg border p-2.5 space-y-1.5 ${isSuccess ? 'border-border bg-background' : 'border-red-500/20 bg-red-500/5'}`}>
              <div className="flex items-center justify-between gap-2">
                <div className="flex items-center gap-1.5 min-w-0 flex-1">
                  {isRunning ? (
                    <Loader2 className="h-3.5 w-3.5 text-muted animate-spin shrink-0" />
                  ) : isSuccess ? (
                    <CheckCircle className="h-3.5 w-3.5 text-emerald-400 shrink-0" />
                  ) : (
                    <XCircle className="h-3.5 w-3.5 text-red-400 shrink-0" />
                  )}
                  <span className="text-xs font-medium text-white truncate">{tc.tool_name}</span>
                </div>
                <div className="flex items-center gap-2 shrink-0">
                  {isRunning && (
                    <span className="text-[10px] text-muted">running</span>
                  )}
                  {!isSuccess && tc.error && (
                    <span className="text-[10px] text-red-400 truncate max-w-[120px]" title={tc.error}>
                      {tc.error}
                    </span>
                  )}
                  {tc.duration_ms != null && (
                    <span className="text-[10px] text-muted font-mono">{formatLatency(tc.duration_ms)}</span>
                  )}
                </div>
              </div>
              {tc.input != null && (
                <div>
                  <p className="text-[10px] text-muted mb-0.5">Input:</p>
                  <JsonCodeBlock value={tc.input as Record<string, unknown>} maxHeight={100} />
                </div>
              )}
              {tc.output != null && (
                <div>
                  <p className="text-[10px] text-muted mb-0.5">Output:</p>
                  <JsonCodeBlock value={tc.output as Record<string, unknown>} maxHeight={100} />
                </div>
              )}
              {tc.error && isSuccess === false && (
                <div className="rounded bg-red-500/10 px-2 py-1">
                  <p className="text-[10px] text-red-300 font-mono break-all">{tc.error}</p>
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
