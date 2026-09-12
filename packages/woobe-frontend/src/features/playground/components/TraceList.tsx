import { ChevronRight, Filter, RefreshCw, AlertCircle, Activity } from 'lucide-react'
import { EmptyStatePanel, TechnicalListItem } from '@woobe/ui'
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
  completed: 'bg-emerald-400',
  success: 'bg-emerald-400',
  running: 'bg-blue-400',
  processing: 'bg-blue-400',
  failed: 'bg-red-400',
  error: 'bg-red-400',
  warning: 'bg-amber-400',
  pending: 'bg-slate-400',
  queued: 'bg-slate-400',
  cancelled: 'bg-slate-400',
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
    return <div className="p-3"><EmptyStatePanel compact icon={<RefreshCw className="h-4 w-4 animate-spin" />} title="Loading Agent Runs" /></div>
  }

  if (isError) {
    return <div className="p-3"><EmptyStatePanel compact icon={<AlertCircle className="h-4 w-4 text-red-300" />} title="Failed to load Agent Runs" description={errorMessage || 'The Runs list could not be loaded.'} action={onRetry ? <button type="button" onClick={onRetry} className="inline-flex h-[27px] items-center gap-1.5 rounded-control border border-border bg-control/35 px-2.5 font-mono text-[8px] text-slate-200"><RefreshCw className="h-3 w-3" />Retry</button> : undefined} /></div>
  }

  if (traces.length === 0) {
    return <div className="p-3"><EmptyStatePanel compact icon={<Activity className="h-4 w-4" />} title="No Agent Runs yet" description="Send a message to create an Agent Run." /></div>
  }

  const grouped = traces.reduce<Record<string, TraceItem[]>>((acc, trace) => {
    const group = getDateGroup(trace.timestamp)
    if (!acc[group]) acc[group] = []
    acc[group].push(trace)
    return acc
  }, {})
  const groupOrder = ['Today', 'Yesterday', 'This Week', 'Older']

  return (
    <div className="p-3">
      <div className="mb-3 flex items-center justify-between gap-3 border-b border-border/70 pb-2.5">
        <div>
          <h3 className="font-mono text-[10px] font-semibold text-slate-50">Agent Runs</h3>
          <p className="mt-0.5 font-sans text-[9px] leading-4 text-muted-foreground">One Run for each Agent execution.</p>
        </div>
        <button type="button" className="inline-flex h-[27px] items-center gap-1 rounded-control border border-transparent px-2 font-mono text-[8px] text-muted-foreground transition-colors hover:border-border hover:bg-control hover:text-slate-50"><Filter className="h-3 w-3" />Filter</button>
      </div>

      <div className="space-y-3">
        {groupOrder.map((group) => {
          const items = grouped[group]
          if (!items?.length) return null
          return (
            <div key={group}>
              <p className="mb-1.5 font-mono text-[8px] uppercase tracking-[0.08em] text-muted-foreground">{group}</p>
              <div className="space-y-1.5">
                {items.map((trace) => (
                  <TechnicalListItem
                    key={trace.id}
                    selected={selectedTraceId === trace.id}
                    onClick={() => onSelectTrace(trace.id)}
                    label={`Agent Run · ${trace.status}`}
                    leading={<span className={cn('h-2 w-2 rounded-full', statusDot[trace.status] || 'bg-slate-400')} />}
                    meta={<span>{formatDateTime(trace.timestamp)}</span>}
                    trailing={<span className="flex items-center gap-2"><span className="font-mono text-[8px] text-muted-foreground">{formatLatency(trace.latency_ms)}</span><ChevronRight className={cn('h-3 w-3', selectedTraceId === trace.id ? 'text-primary-light' : 'text-muted-foreground')} /></span>}
                  />
                ))}
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
