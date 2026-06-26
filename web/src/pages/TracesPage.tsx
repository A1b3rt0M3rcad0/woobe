import { useMemo, useState, type ReactNode } from 'react'
import { useParams } from 'react-router-dom'
import { useTraces, useTraceDetail } from '@/features/traces/hooks'
import { LoadingState } from '@/components/common/LoadingState'
import { ErrorState } from '@/components/common/ErrorState'
import { StatusBadge } from '@/components/common/StatusBadge'
import { Dialog } from '@/components/ui/Dialog'
import { Input } from '@/components/ui/Input'
import { Select } from '@/components/ui/Select'
import { JsonCodeBlock } from '@/components/ui/JsonCodeBlock'
import { formatDateTime } from '@/lib/formatters/date'
import { formatMoney } from '@/lib/formatters/money'
import { formatLatency } from '@/lib/formatters/number'
import { Activity, Search } from 'lucide-react'
import type { Trace } from '@/features/traces/types'

type StatusFilter = 'all' | 'running' | 'completed' | 'failed' | 'cancelled'

const STATUS_OPTIONS: Array<{ value: StatusFilter; label: string }> = [
  { value: 'all', label: 'All statuses' },
  { value: 'running', label: 'Running' },
  { value: 'completed', label: 'Completed' },
  { value: 'failed', label: 'Failed' },
  { value: 'cancelled', label: 'Cancelled' },
]

function MinimalShell({ title, description, children }: { title: string; description: string; children: ReactNode }) {
  return (
    <div className="mx-auto w-full max-w-[1500px] space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight text-white">{title}</h1>
        <p className="mt-2 max-w-3xl text-sm text-muted">{description}</p>
      </div>
      {children}
    </div>
  )
}

function Pill({ children, tone = 'default' }: { children: ReactNode; tone?: 'default' | 'primary' | 'danger' }) {
  const toneClass = tone === 'primary'
    ? 'border-primary/30 bg-primary/10 text-primary-light'
    : tone === 'danger'
      ? 'border-red-500/30 bg-red-500/10 text-red-200'
      : 'border-border/80 bg-background/70 text-muted'
  return <span className={`rounded-full border px-2.5 py-1 text-xs ${toneClass}`}>{children}</span>
}

function compactId(id: string) {
  return `${id.slice(0, 8)}...`
}

function matchesStatus(trace: Trace, statusFilter: StatusFilter) {
  if (statusFilter === 'all') return true
  const status = trace.status.toLowerCase()
  return status === statusFilter || (statusFilter === 'failed' && status === 'error')
}

function EmptyTraces({ hasFilters }: { hasFilters: boolean }) {
  return (
    <div className="rounded-xl border border-border/80 bg-surface/50 px-5 py-8 text-center">
      <Activity className="mx-auto h-10 w-10 text-muted" />
      <h2 className="mt-4 text-sm font-semibold text-white">No traces found</h2>
      <p className="mt-1 text-sm text-muted">
        {hasFilters ? 'Adjust the search or status filter.' : 'Traces appear when agents are invoked.'}
      </p>
    </div>
  )
}

function TraceRow({ trace, onClick }: { trace: Trace; onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="grid w-full gap-4 border-b border-border/80 px-5 py-4 text-left transition-colors hover:bg-background/50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/30 md:grid-cols-[minmax(0,1.25fr)_minmax(0,1fr)_120px_120px_170px] md:items-center"
    >
      <div className="min-w-0">
        <div className="flex flex-wrap items-center gap-2">
          <code className="font-mono text-xs text-white">{compactId(trace.id)}</code>
          {trace.fallback_used && <Pill tone="primary">Fallback</Pill>}
          {trace.error && <Pill tone="danger">Error</Pill>}
        </div>
        <p className="mt-1 truncate text-xs text-muted">{trace.session_id || trace.agent_id || 'Project trace'}</p>
      </div>

      <div className="min-w-0">
        <p className="truncate text-sm font-medium text-white">{trace.model || 'Model not recorded'}</p>
        <p className="mt-1 truncate text-xs text-muted">{trace.provider || 'Provider not recorded'}</p>
      </div>

      <StatusBadge status={trace.status} />

      <div>
        <p className="text-xs text-muted">Latency</p>
        <p className="mt-1 text-sm font-medium text-white">{formatLatency(trace.total_latency_ms)}</p>
      </div>

      <div className="md:text-right">
        <p className="text-xs text-muted">Cost · Time</p>
        <p className="mt-1 text-sm font-medium text-white">{trace.total_cost_usd ? formatMoney(trace.total_cost_usd) : '—'}</p>
        <p className="mt-1 text-xs text-muted">{trace.created_at ? formatDateTime(trace.created_at) : '—'}</p>
      </div>
    </button>
  )
}

export default function TracesPage() {
  const { projectId } = useParams<{ projectId: string }>()
  const { data: traces, isLoading, isError, error, refetch } = useTraces(projectId)
  const [selectedTraceId, setSelectedTraceId] = useState<string | null>(null)
  const [query, setQuery] = useState('')
  const [statusFilter, setStatusFilter] = useState<StatusFilter>('all')
  const { data: traceDetail } = useTraceDetail(selectedTraceId || undefined)

  const items = traces ?? []
  const visibleTraces = useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase()
    return items.filter((trace) => {
      const matchesQuery = !normalizedQuery
        || trace.id.toLowerCase().includes(normalizedQuery)
        || trace.status.toLowerCase().includes(normalizedQuery)
        || trace.provider?.toLowerCase().includes(normalizedQuery)
        || trace.model?.toLowerCase().includes(normalizedQuery)
        || trace.session_id?.toLowerCase().includes(normalizedQuery)
        || trace.agent_id?.toLowerCase().includes(normalizedQuery)
      return matchesStatus(trace, statusFilter) && matchesQuery
    })
  }, [items, query, statusFilter])

  if (isLoading) return <LoadingState />
  if (isError) return <ErrorState error={error} onRetry={refetch} />

  const hasFilters = query.trim().length > 0 || statusFilter !== 'all'

  return (
    <MinimalShell title="Traces" description="Request-level observability for agent executions.">
      <div className="grid gap-3 lg:grid-cols-[minmax(0,1fr)_220px]">
        <div className="relative">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted" />
          <Input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Search traces..."
            className="h-11 pl-9"
          />
        </div>
        <Select
          value={statusFilter}
          onChange={(event) => setStatusFilter(event.target.value as StatusFilter)}
          options={STATUS_OPTIONS}
          className="h-11"
        />
      </div>

      {visibleTraces.length > 0 ? (
        <section className="overflow-hidden rounded-xl border border-border/90 bg-surface/70">
          <div className="border-b border-border px-5 py-4">
            <h2 className="text-sm font-semibold text-white">Trace stream</h2>
            <p className="mt-1 text-xs text-muted">Auto-refreshing execution records for this project.</p>
          </div>
          {visibleTraces.map((trace) => <TraceRow key={trace.id} trace={trace} onClick={() => setSelectedTraceId(trace.id)} />)}
        </section>
      ) : (
        <EmptyTraces hasFilters={hasFilters} />
      )}

      <Dialog open={!!selectedTraceId} onClose={() => setSelectedTraceId(null)} title="Trace detail" className="max-h-[90vh] max-w-5xl overflow-hidden">
        {traceDetail ? (
          <div className="max-h-[calc(90vh-96px)] overflow-y-auto pr-1">
            <div className="grid gap-6 lg:grid-cols-[280px_minmax(0,1fr)]">
              <aside className="space-y-4 lg:sticky lg:top-0 lg:self-start">
                <div className="rounded-xl border border-border/90 bg-surface/70 p-4">
                  <div className="flex h-11 w-11 items-center justify-center rounded-xl border border-border bg-background text-primary-light">
                    <Activity className="h-5 w-5" />
                  </div>
                  <div className="mt-5 min-w-0">
                    <code className="block truncate font-mono text-xs text-white">{traceDetail.id}</code>
                    <p className="mt-2 truncate text-sm text-muted">{traceDetail.model || 'Model not recorded'}</p>
                  </div>
                  <div className="mt-5 flex flex-wrap gap-2">
                    <StatusBadge status={traceDetail.status} />
                    {traceDetail.fallback_used && <Pill tone="primary">Fallback</Pill>}
                    {traceDetail.error && <Pill tone="danger">Error</Pill>}
                  </div>
                </div>

                <div className="grid gap-3">
                  <div className="rounded-xl border border-border/80 bg-background/60 p-3">
                    <p className="text-xs text-muted">Provider</p>
                    <p className="mt-2 text-sm font-medium text-white">{traceDetail.provider || '—'}</p>
                  </div>
                  <div className="rounded-xl border border-border/80 bg-background/60 p-3">
                    <p className="text-xs text-muted">Latency</p>
                    <p className="mt-2 text-sm font-medium text-white">{formatLatency(traceDetail.total_latency_ms)}</p>
                  </div>
                  <div className="rounded-xl border border-border/80 bg-background/60 p-3">
                    <p className="text-xs text-muted">Cost</p>
                    <p className="mt-2 text-sm font-medium text-white">{traceDetail.total_cost_usd ? formatMoney(traceDetail.total_cost_usd) : '—'}</p>
                  </div>
                  <div className="rounded-xl border border-border/80 bg-background/60 p-3">
                    <p className="text-xs text-muted">Created</p>
                    <p className="mt-2 text-sm font-medium text-white">{traceDetail.created_at ? formatDateTime(traceDetail.created_at) : '—'}</p>
                  </div>
                </div>
              </aside>

              <main className="space-y-5">
                {traceDetail.error && (
                  <section className="rounded-xl border border-red-500/35 bg-red-500/10 p-4">
                    <h3 className="text-sm font-semibold text-red-100">Error</h3>
                    <p className="mt-2 text-sm leading-6 text-red-100/90">{traceDetail.error}</p>
                  </section>
                )}

                <section className="rounded-xl border border-border/80 bg-surface/65 p-4">
                  <div className="mb-4 flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
                    <div>
                      <h3 className="text-sm font-semibold text-white">Events</h3>
                      <p className="mt-1 text-xs text-muted">Timeline of recorded trace events.</p>
                    </div>
                    <Pill>{traceDetail.events.length} events</Pill>
                  </div>
                  <div className="space-y-3">
                    {traceDetail.events.length === 0 ? (
                      <div className="rounded-xl border border-border/80 bg-background/60 p-4 text-sm text-muted">No trace events recorded.</div>
                    ) : traceDetail.events.map((event) => (
                      <div key={event.id} className="rounded-xl border border-border/80 bg-background/60 p-4">
                        <div className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
                          <div>
                            <p className="text-sm font-medium text-white">{event.event_type}</p>
                            <p className="mt-1 text-xs text-muted">{event.created_at ? formatDateTime(event.created_at) : 'Time not recorded'}</p>
                          </div>
                          {event.latency_ms != null && <Pill>{formatLatency(event.latency_ms)}</Pill>}
                        </div>
                        {event.payload && <JsonCodeBlock value={event.payload} maxHeight={140} className="mt-3" />}
                      </div>
                    ))}
                  </div>
                </section>
              </main>
            </div>
          </div>
        ) : (
          <LoadingState />
        )}
      </Dialog>
    </MinimalShell>
  )
}
