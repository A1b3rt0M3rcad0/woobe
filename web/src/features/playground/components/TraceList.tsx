import { ChevronRight, Filter, RefreshCw, AlertCircle, Activity } from 'lucide-react'
import { cn } from '@/lib/utils'
import { formatLatency, formatDateTime } from '@/lib/formatters/number'
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

const statusDot: Record<string, string> = {
  completed: 'bg-emerald-400 shadow-[0_0_4px_rgba(52,211,153,0.5)]',
  success: 'bg-emerald-400 shadow-[0_0_4px_rgba(52,211,153,0.5)]',
  running: 'bg-blue-400 shadow-[0_0_4px_rgba(96,165,250,0.5)]',
  processing: 'bg-blue-400 shadow-[0_0_4px_rgba(96,165,250,0.5)]',
  failed: 'bg-red-400 shadow-[0_0_4px_rgba(248,113,113,0.5)]',
  error: 'bg-red-400 shadow-[0_0_4px_rgba(248,113,113,0.5)]',
  warning: 'bg-yellow-400',
  pending: 'bg-gray-400',
  queued: 'bg-gray-400',
  cancelled: 'bg-gray-400',
}

function getDateGroup(dateStr: string): string {
  const d = new Date(dateStr)
  const now = new Date()
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate())
  const yesterday = new Date(today)
  yesterday.setDate(yesterday.getDate() - 1)
  const weekStart = new Date(today)
  weekStart.setDate(weekStart.getDate() - today.getDay())

  if (d >= today) return 'Today'
  if (d >= yesterday) return 'Yesterday'
  if (d >= weekStart) return 'This Week'
  return 'Older'
}

export function TraceList({ traces, selectedTraceId, onSelectTrace, isLoading, isError, errorMessage, onRetry }: TraceListProps) {
  if (isLoading) {
    return <div className="p-4 text-center"><RefreshCw className="h-5 w-5 animate-spin text-muted mx-auto mb-2" /><p className="text-sm text-muted">Loading Agent Runs...</p></div>
  }

  if (isError) {
    return (
      <div className="p-4 text-center">
        <AlertCircle className="h-5 w-5 text-red-400 mx-auto mb-2" />
        <p className="text-sm text-red-400">Failed to load Agent Runs</p>
        {errorMessage && <p className="text-xs text-muted mt-1 line-clamp-2">{errorMessage}</p>}
        {onRetry && <button type="button" onClick={onRetry} className="mt-3 text-xs text-primary hover:underline inline-flex items-center gap-1"><RefreshCw className="h-3 w-3" />Retry</button>}
      </div>
    )
  }

  if (traces.length === 0) {
    return (
      <div className="p-4 text-center">
        <Activity className="h-8 w-8 text-muted mx-auto mb-2 opacity-40" />
        <p className="text-sm text-muted">No Agent Runs yet</p>
        <p className="text-xs text-muted mt-1">Send a message to create an Agent Run. Stateless Agents do not require a Session.</p>
      </div>
    )
  }

  const grouped = traces.reduce<Record<string, TraceItem[]>>((acc, trace) => {
    const group = getDateGroup(trace.timestamp)
    if (!acc[group]) acc[group] = []
    acc[group].push(trace)
    return acc
  }, {})
  const groupOrder = ['Today', 'Yesterday', 'This Week', 'Older']

  return (
    <div className="p-4">
      <div className="flex items-center justify-between mb-3">
        <div><h3 className="text-sm font-medium text-white">Agent Runs</h3><p className="mt-0.5 text-[10px] text-muted">One Run for each Agent execution</p></div>
        <button type="button" className="flex items-center gap-1 text-xs text-muted hover:text-white transition-colors"><Filter className="h-3.5 w-3.5" />Filter</button>
      </div>
      <div className="space-y-3">
        {groupOrder.map((group) => {
          const items = grouped[group]
          if (!items?.length) return null
          return (
            <div key={group}>
              <p className="text-[11px] font-medium text-muted uppercase tracking-wider mb-1.5">{group}</p>
              <div className="space-y-0.5">
                {items.map((trace) => (
                  <button
                    type="button"
                    key={trace.id}
                    onClick={() => onSelectTrace(trace.id)}
                    className={cn('w-full text-left rounded-lg border px-3 py-2.5 transition-colors group', selectedTraceId === trace.id ? 'border-primary/30 bg-primary/5' : 'border-transparent hover:bg-accent')}
                  >
                    <div className="flex items-center gap-2.5">
                      <span className={cn('h-2 w-2 shrink-0 rounded-full', statusDot[trace.status] || 'bg-gray-400')} />
                      <div className="flex-1 min-w-0"><p className={cn('text-xs truncate', selectedTraceId === trace.id ? 'text-white font-medium' : 'text-muted group-hover:text-white')}>Agent Run · {trace.status}</p></div>
                      <span className="text-[11px] text-muted shrink-0 font-mono">{formatLatency(trace.latency_ms)}</span>
                      <ChevronRight className={cn('h-3.5 w-3.5 shrink-0 transition-colors', selectedTraceId === trace.id ? 'text-primary' : 'text-muted/40 group-hover:text-muted')} />
                    </div>
                    <p className="text-[11px] text-muted mt-0.5 ml-4">{formatDateTime(trace.timestamp)}</p>
                  </button>
                ))}
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
