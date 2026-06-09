import { ChevronRight, Circle, Filter, RefreshCw, AlertCircle } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { TraceItem } from '@/features/playground/types'

interface TraceListProps {
  traces: TraceItem[]
  selectedTraceId: string | null
  onSelectTrace: (id: string) => void
  isLoading?: boolean
  isError?: boolean
  errorMessage?: string
  onRetry?: () => void
  hasSessionId?: boolean
}

const statusColor: Record<string, string> = {
  success: 'text-emerald-400',
  error: 'text-red-400',
  warning: 'text-yellow-400',
}

function formatTime(ts: string): string {
  const d = new Date(ts)
  return d.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

export function TraceList({ traces, selectedTraceId, onSelectTrace, isLoading, isError, errorMessage, onRetry, hasSessionId }: TraceListProps) {
  if (isLoading) {
    return (
      <div className="p-4 text-center">
        <RefreshCw className="h-5 w-5 animate-spin text-muted mx-auto mb-2" />
        <p className="text-sm text-muted">Loading traces...</p>
      </div>
    )
  }

  if (isError) {
    return (
      <div className="p-4 text-center">
        <AlertCircle className="h-5 w-5 text-red-400 mx-auto mb-2" />
        <p className="text-sm text-red-400">Failed to load traces</p>
        {errorMessage && (
          <p className="text-xs text-muted mt-1 line-clamp-2">{errorMessage}</p>
        )}
        {onRetry && (
          <button
            onClick={onRetry}
            className="mt-3 text-xs text-primary hover:underline inline-flex items-center gap-1"
          >
            <RefreshCw className="h-3 w-3" />
            Retry
          </button>
        )}
      </div>
    )
  }

  if (traces.length === 0) {
    return (
      <div className="p-4 text-center">
        <p className="text-sm text-muted">
          {hasSessionId
            ? 'No traces for this session yet'
            : 'No traces for this agent yet'}
        </p>
        <p className="text-xs text-muted mt-1">Send a message to see traces.</p>
      </div>
    )
  }

  return (
    <div className="p-4">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-medium text-white">Traces</h3>
        <button className="flex items-center gap-1 text-xs text-muted hover:text-white transition-colors">
          <Filter className="h-3.5 w-3.5" />
          Filter
        </button>
      </div>

      <div className="space-y-0.5">
        <p className="text-[11px] font-medium text-muted uppercase tracking-wider mb-2">Today</p>
        {traces.map((trace) => (
          <button
            key={trace.id}
            onClick={() => onSelectTrace(trace.id)}
            className={cn(
              'w-full text-left rounded-lg border px-3 py-2.5 transition-colors',
              selectedTraceId === trace.id
                ? 'border-primary/30 bg-primary/5'
                : 'border-transparent hover:bg-accent',
            )}
          >
            <div className="flex items-center gap-2">
              <Circle className={cn('h-2 w-2 shrink-0 fill-current', statusColor[trace.status] || 'text-muted')} />
              <div className="flex-1 min-w-0">
                <p className="text-xs text-white truncate">{trace.title}</p>
              </div>
              <span className="text-[11px] text-muted shrink-0">
                {trace.latency_ms != null ? `${Math.round(trace.latency_ms)}ms` : '—'}
              </span>
              <ChevronRight className="h-3.5 w-3.5 text-muted shrink-0" />
            </div>
            <p className="text-[11px] text-muted mt-0.5 ml-4">{formatTime(trace.timestamp)}</p>
          </button>
        ))}
      </div>
    </div>
  )
}
