import { useMemo, useState } from 'react'
import { useParams } from 'react-router-dom'
import { useTraces, useTraceDetail } from '@/features/traces/hooks'
import { LoadingState } from '@/components/common/LoadingState'
import { ErrorState } from '@/components/common/ErrorState'
import { StatusBadge } from '@/components/common/StatusBadge'
import { ResourcePill } from '@/components/common/OperationalResourceCard'
import {
  ResourceEmptyState,
  ResourcePage,
  ResourceSearch,
  ResourceSectionHeader,
  ResourceTabs,
  ResourceToolbar,
} from '@/components/common/ResourcePage'
import { Dialog } from '@/components/ui/Dialog'
import { Button } from '@/components/ui/Button'
import { JsonCodeBlock } from '@/components/ui/JsonCodeBlock'
import { formatDateTime } from '@/lib/formatters/date'
import { formatMoney } from '@/lib/formatters/money'
import { formatLatency } from '@/lib/formatters/number'
import { Activity, ChevronRight } from 'lucide-react'
import type { Trace } from '@/features/traces/types'

type StatusFilter = 'all' | 'running' | 'completed' | 'failed' | 'cancelled'

const panelScrollClass = 'scrollbar-thin scrollbar-track-transparent scrollbar-thumb-border hover:scrollbar-thumb-muted [scrollbar-color:rgb(51_65_85)_transparent] [scrollbar-width:thin] [&::-webkit-scrollbar]:w-2 [&::-webkit-scrollbar-track]:bg-transparent [&::-webkit-scrollbar-thumb]:rounded-full [&::-webkit-scrollbar-thumb]:border-2 [&::-webkit-scrollbar-thumb]:border-transparent [&::-webkit-scrollbar-thumb]:bg-border/70 [&::-webkit-scrollbar-thumb]:bg-clip-padding hover:[&::-webkit-scrollbar-thumb]:bg-muted'

function compactId(id: string) {
  return `${id.slice(0, 8)}...`
}

function matchesStatus(trace: Trace, statusFilter: StatusFilter) {
  if (statusFilter === 'all') return true
  const status = trace.status.toLowerCase()
  if (statusFilter === 'cancelled') return status === 'cancelled' || status === 'canceled'
  return status === statusFilter || (statusFilter === 'failed' && status === 'error')
}

function traceData(trace: Trace): Record<string, unknown> {
  return trace.data ?? {}
}

function stringField(...values: unknown[]): string | null {
  for (const value of values) {
    if (typeof value === 'string' && value.trim()) return value
  }
  return null
}

function providerModelId(trace: Trace) {
  const data = traceData(trace)
  return stringField(trace.provider_model_id, data.provider_model_id)
}

function providerCredentialId(trace: Trace) {
  const data = traceData(trace)
  return stringField(trace.provider_credential_id, data.provider_credential_id)
}

function fallbackProviderModelId(trace: Trace) {
  const data = traceData(trace)
  return stringField(trace.fallback_provider_model_id, data.fallback_provider_model_id)
}

function fallbackCredentialId(trace: Trace) {
  const data = traceData(trace)
  return stringField(trace.fallback_credential_id, data.fallback_credential_id)
}

function TraceRow({ trace, onClick }: { trace: Trace; onClick: () => void }) {
  const modelRef = providerModelId(trace)
  return (
    <button
      type="button"
      onClick={onClick}
      className="group grid w-full gap-4 border-b border-border/80 px-4 py-4 text-left transition-colors last:border-b-0 hover:bg-background/50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/30 xl:grid-cols-[minmax(0,1.25fr)_minmax(0,1fr)_110px_110px_160px_20px] xl:items-center"
    >
      <div className="min-w-0">
        <div className="flex flex-wrap items-center gap-2">
          <code className="font-mono text-xs text-white">{compactId(trace.id)}</code>
          {trace.fallback_used && <ResourcePill tone="primary">Fallback</ResourcePill>}
          {trace.error && <ResourcePill tone="danger">Error</ResourcePill>}
        </div>
        <p className="mt-1 truncate text-xs text-muted">{trace.session_id || trace.agent_id || 'Project trace'}</p>
      </div>

      <div className="min-w-0">
        <p className="truncate text-sm font-medium text-white">{trace.model || 'Model not recorded'}</p>
        <p className="mt-1 truncate text-xs text-muted">{trace.provider || 'Provider not recorded'}</p>
        {modelRef && <p className="mt-1 truncate font-mono text-[11px] text-muted">model ref · {compactId(modelRef)}</p>}
      </div>

      <StatusBadge status={trace.status} size="compact" />

      <div>
        <p className="text-xs text-muted">Latency</p>
        <p className="mt-1 text-sm font-medium text-white">{formatLatency(trace.total_latency_ms)}</p>
      </div>

      <div className="xl:text-right">
        <p className="text-xs text-muted">Cost · Time</p>
        <p className="mt-1 text-sm font-medium text-white">{trace.total_cost_usd ? formatMoney(trace.total_cost_usd) : '—'}</p>
        <p className="mt-1 text-xs text-muted">{trace.created_at ? formatDateTime(trace.created_at) : '—'}</p>
      </div>

      <ChevronRight className="hidden h-4 w-4 text-muted transition-transform group-hover:translate-x-0.5 group-hover:text-primary-light xl:block" aria-hidden="true" />
    </button>
  )
}

function IdCard({ label, value }: { label: string; value?: string | null }) {
  if (!value) return null
  return (
    <div className="rounded-xl border border-border/80 bg-background/60 p-3">
      <p className="text-xs text-muted">{label}</p>
      <code className="mt-2 block truncate text-xs font-medium text-white">{value}</code>
    </div>
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
  const statusCounts = useMemo(() => ({
    all: items.length,
    running: items.filter((trace) => matchesStatus(trace, 'running')).length,
    completed: items.filter((trace) => matchesStatus(trace, 'completed')).length,
    failed: items.filter((trace) => matchesStatus(trace, 'failed')).length,
    cancelled: items.filter((trace) => matchesStatus(trace, 'cancelled')).length,
  }), [items])
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
        || providerModelId(trace)?.toLowerCase().includes(normalizedQuery)
        || providerCredentialId(trace)?.toLowerCase().includes(normalizedQuery)
        || fallbackProviderModelId(trace)?.toLowerCase().includes(normalizedQuery)
        || fallbackCredentialId(trace)?.toLowerCase().includes(normalizedQuery)
      return matchesStatus(trace, statusFilter) && matchesQuery
    })
  }, [items, query, statusFilter])

  if (!projectId) return <ErrorState message="Project not found" />
  const hasFilters = query.trim().length > 0 || statusFilter !== 'all'
  const resultCount = hasFilters ? `${visibleTraces.length} of ${items.length}` : items.length

  return (
    <ResourcePage title="Traces" description="Request-level observability for Agent executions.">
      <ResourceToolbar>
        <ResourceTabs
          value={statusFilter}
          onChange={setStatusFilter}
          label="Filter Traces by status"
          tabs={[
            { value: 'all', label: 'All', count: statusCounts.all },
            { value: 'running', label: 'Running', count: statusCounts.running },
            { value: 'completed', label: 'Completed', count: statusCounts.completed },
            { value: 'failed', label: 'Failed', count: statusCounts.failed },
            { value: 'cancelled', label: 'Cancelled', count: statusCounts.cancelled },
          ]}
        />
        <ResourceSearch
          value={query}
          onChange={setQuery}
          placeholder="Search Traces, sessions, models or bindings..."
          label="Search Traces"
        />
      </ResourceToolbar>

      <section>
        <ResourceSectionHeader
          title="Trace stream"
          description="Auto-refreshing execution records for this Project."
          count={resultCount}
        />

        {isLoading ? (
          <LoadingState message="Loading Traces" variant="panel" layout="resource-list" />
        ) : isError ? (
          <ErrorState error={error} onRetry={refetch} className="rounded-xl border border-border/80 bg-surface/40 py-10" />
        ) : visibleTraces.length > 0 ? (
          <div className="overflow-hidden rounded-xl border border-border/90 bg-surface/70">
            {visibleTraces.map((trace) => <TraceRow key={trace.id} trace={trace} onClick={() => setSelectedTraceId(trace.id)} />)}
          </div>
        ) : (
          <ResourceEmptyState
            icon={<Activity className="h-4 w-4" />}
            title="No Traces found"
            description={hasFilters ? 'Adjust the search or clear the active status filter.' : 'Traces appear when Agents are invoked.'}
            action={hasFilters ? (
              <Button type="button" size="sm" variant="outline" onClick={() => { setQuery(''); setStatusFilter('all') }}>
                Clear filters
              </Button>
            ) : undefined}
          />
        )}
      </section>

      <Dialog open={!!selectedTraceId} onClose={() => setSelectedTraceId(null)} title="Trace detail" className="max-h-[90vh] max-w-5xl overflow-hidden">
        {traceDetail ? (
          <div className={`max-h-[calc(90vh-96px)] overflow-y-auto pr-2 ${panelScrollClass}`}>
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
                    <StatusBadge status={traceDetail.status} size="compact" />
                    {traceDetail.fallback_used && <ResourcePill tone="primary">Fallback</ResourcePill>}
                    {traceDetail.error && <ResourcePill tone="danger">Error</ResourcePill>}
                  </div>
                </div>

                <div className="grid gap-3">
                  <div className="rounded-xl border border-border/80 bg-background/60 p-3">
                    <p className="text-xs text-muted">Provider</p>
                    <p className="mt-2 text-sm font-medium text-white">{traceDetail.provider || '—'}</p>
                  </div>
                  <IdCard label="Provider model" value={providerModelId(traceDetail)} />
                  <IdCard label="Provider credential" value={providerCredentialId(traceDetail)} />
                  <IdCard label="Fallback model" value={fallbackProviderModelId(traceDetail)} />
                  <IdCard label="Fallback credential" value={fallbackCredentialId(traceDetail)} />
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
                    <ResourcePill>{traceDetail.events.length} events</ResourcePill>
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
                          {event.latency_ms != null && <ResourcePill>{formatLatency(event.latency_ms)}</ResourcePill>}
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
    </ResourcePage>
  )
}
