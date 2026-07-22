import { ArrowLeft, Activity, Bot, Network, Wrench } from 'lucide-react'
import { useNavigate, useParams } from 'react-router-dom'

import { ErrorState } from '@/components/common/ErrorState'
import { LoadingState } from '@/components/common/LoadingState'
import { ResourcePage, ResourceSectionHeader } from '@/components/common/ResourcePage'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { JsonCodeBlock } from '@/components/ui/JsonCodeBlock'
import { useTraceDetail } from '@/features/traces/hooks'
import { formatDateTime } from '@/lib/formatters/date'
import { formatMoney } from '@/lib/formatters/money'
import { formatLatency } from '@/lib/formatters/number'

function statusClass(value?: string | null) {
  const status = String(value || '').toLowerCase()
  if (status === 'completed' || status === 'success') return 'border-emerald-500/30 bg-emerald-500/10 text-emerald-300'
  if (status === 'failed' || status === 'error') return 'border-red-500/30 bg-red-500/10 text-red-300'
  if (status === 'running' || status === 'pending') return 'border-primary/30 bg-primary/10 text-primary-light'
  return 'border-border text-muted'
}

export default function TraceDetailPage() {
  const navigate = useNavigate()
  const { traceId } = useParams<{ traceId: string }>()
  const query = useTraceDetail(traceId)
  const trace = query.data

  if (!traceId) return <ErrorState title="Trace required" description="No Trace ID was provided." />
  if (query.isLoading) return <LoadingState message="Loading Trace evidence" />
  if (query.isError || !trace) return <ErrorState title="Unable to load Trace" description="The Trace may be unavailable or outside the current Project." />

  const traceStartedAt = trace.started_at ?? trace.created_at

  return (
    <ResourcePage
      title="Trace evidence"
      description="Canonical Agent Run evidence linked from an Evaluation Trial."
      action={<Button variant="outline" onClick={() => navigate(-1)}><ArrowLeft className="mr-2 h-4 w-4" />Back</Button>}
      className="max-w-[1500px]"
    >
      <section className="rounded-xl border border-border/80 bg-surface/45 p-5">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <Badge variant="outline" className={statusClass(trace.status)}>{trace.status}</Badge>
              <span className="font-mono text-xs text-muted">{trace.id}</span>
            </div>
            <div className="mt-4 flex flex-wrap items-center gap-4 text-xs text-muted">
              {trace.agent_id ? <span className="flex items-center gap-2"><Bot className="h-3.5 w-3.5" />Agent {trace.agent_id}</span> : null}
              {trace.network_execution_id ? <span className="flex items-center gap-2"><Network className="h-3.5 w-3.5" />Network Run {trace.network_execution_id}</span> : null}
              <span>{traceStartedAt ? formatDateTime(traceStartedAt) : '—'}</span>
            </div>
          </div>
          <div className="grid grid-cols-2 gap-5 sm:grid-cols-3">
            <div><p className="text-[9px] uppercase text-muted">Latency</p><p className="mt-1 text-sm font-semibold text-white">{trace.total_latency_ms == null ? '—' : formatLatency(trace.total_latency_ms)}</p></div>
            <div><p className="text-[9px] uppercase text-muted">Cost</p><p className="mt-1 text-sm font-semibold text-white">{trace.total_cost_usd == null ? 'Unknown' : formatMoney(trace.total_cost_usd)}</p></div>
            <div><p className="text-[9px] uppercase text-muted">Events</p><p className="mt-1 text-sm font-semibold text-white">{trace.events.length}</p></div>
          </div>
        </div>
      </section>

      <section>
        <ResourceSectionHeader title="Execution payload" description="Trace metadata, runtime dimensions and final status." />
        <JsonCodeBlock title="Trace" value={trace} maxHeight={440} />
      </section>

      <section>
        <ResourceSectionHeader title="Timeline" description="Ordered evidence emitted during the Agent Run." count={trace.events.length} />
        <div className="space-y-2">
          {trace.events.map((event) => (
            <article key={event.id} className="rounded-xl border border-border/80 bg-surface/40 p-4">
              <div className="flex items-start justify-between gap-4">
                <div className="flex min-w-0 gap-3">
                  <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border border-border bg-background text-primary-light">{event.event_type.includes('tool') ? <Wrench className="h-3.5 w-3.5" /> : <Activity className="h-3.5 w-3.5" />}</div>
                  <div><p className="text-xs font-semibold text-white">{event.event_type}</p><p className="mt-1 text-[10px] text-muted">{event.created_at ? formatDateTime(event.created_at) : '—'}</p></div>
                </div>
                <div className="text-right text-[10px] text-muted">{event.latency_ms == null ? '—' : formatLatency(event.latency_ms)}</div>
              </div>
              {event.payload ? <div className="mt-3"><JsonCodeBlock title="Evidence" value={event.payload} maxHeight={260} /></div> : null}
            </article>
          ))}
        </div>
      </section>
    </ResourcePage>
  )
}
