import { useState } from 'react'
import { useParams } from 'react-router-dom'
import { useTraces, useTraceDetail } from '@/features/traces/hooks'
import { PageHeader } from '@/components/common/PageHeader'
import { LoadingState } from '@/components/common/LoadingState'
import { ErrorState } from '@/components/common/ErrorState'
import { EmptyState } from '@/components/common/EmptyState'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card'
import { Table } from '@/components/ui/Table'
import { Badge } from '@/components/ui/Badge'
import { StatusBadge } from '@/components/common/StatusBadge'
import { Dialog } from '@/components/ui/Dialog'
import { formatDateTime } from '@/lib/formatters/date'
import { formatMoney } from '@/lib/formatters/money'
import { Activity } from 'lucide-react'
import type { Trace } from '@/features/traces/types'

export default function TracesPage() {
  const { projectId } = useParams<{ projectId: string }>()
  const { data: traces, isLoading, isError, error, refetch } = useTraces(projectId)
  const [selectedTraceId, setSelectedTraceId] = useState<string | null>(null)
  const { data: traceDetail } = useTraceDetail(selectedTraceId || undefined)

  if (isLoading) return <LoadingState />
  if (isError) return <ErrorState error={error} onRetry={refetch} />

  const columns = [
    { key: 'id', header: 'Trace ID', render: (t: Trace) => <code className="text-xs">{t.id.slice(0, 8)}...</code> },
    { key: 'status', header: 'Status', render: (t: Trace) => <StatusBadge status={t.status} /> },
    { key: 'provider', header: 'Provider', render: (t: Trace) => t.provider || '—' },
    { key: 'model', header: 'Model', render: (t: Trace) => t.model || '—' },
    { key: 'total_latency_ms', header: 'Latency', render: (t: Trace) => t.total_latency_ms ? `${t.total_latency_ms.toFixed(0)}ms` : '—' },
    { key: 'total_cost_usd', header: 'Cost', render: (t: Trace) => t.total_cost_usd ? formatMoney(t.total_cost_usd) : '—' },
    { key: 'created_at', header: 'Time', render: (t: Trace) => t.created_at ? formatDateTime(t.created_at) : '—' },
  ]

  return (
    <div>
      <PageHeader title="Traces" description="Request-level observability and debugging" />

      {traces && traces.length > 0 ? (
        <Card>
          <CardContent className="p-0">
            <Table
              columns={columns}
              data={traces}
              keyExtractor={(t) => t.id}
              onRowClick={(t) => setSelectedTraceId(t.id)}
            />
          </CardContent>
        </Card>
      ) : (
        <EmptyState icon={<Activity className="h-12 w-12" />} title="No traces" description="Traces will appear when agents are invoked." />
      )}

      <Dialog open={!!selectedTraceId} onClose={() => setSelectedTraceId(null)} title="Trace Detail" className="max-w-2xl">
        {traceDetail ? (
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-4 text-sm">
              <div>
                <p className="text-muted text-xs">Status</p>
                <StatusBadge status={traceDetail.trace.status} />
              </div>
              <div>
                <p className="text-muted text-xs">Provider</p>
                <p>{traceDetail.trace.provider || '—'}</p>
              </div>
              <div>
                <p className="text-muted text-xs">Model</p>
                <p>{traceDetail.trace.model || '—'}</p>
              </div>
              <div>
                <p className="text-muted text-xs">Latency</p>
                <p>{traceDetail.trace.total_latency_ms ? `${traceDetail.trace.total_latency_ms.toFixed(0)}ms` : '—'}</p>
              </div>
              <div>
                <p className="text-muted text-xs">Cost</p>
                <p>{traceDetail.trace.total_cost_usd ? formatMoney(traceDetail.trace.total_cost_usd) : '—'}</p>
              </div>
              <div>
                <p className="text-muted text-xs">Fallback Used</p>
                <p>{traceDetail.trace.fallback_used ? 'Yes' : 'No'}</p>
              </div>
            </div>

            {traceDetail.trace.error && (
              <div className="rounded-lg border border-red-500/50 bg-red-500/10 p-3 text-sm text-red-400">
                {traceDetail.trace.error}
              </div>
            )}

            {traceDetail.events.length > 0 && (
              <div>
                <p className="text-sm font-medium text-white mb-2">Events ({traceDetail.events.length})</p>
                <div className="space-y-2">
                  {traceDetail.events.map((evt) => (
                    <div key={evt.id} className="rounded-lg border border-border p-3 text-sm">
                      <div className="flex items-center justify-between">
                        <Badge variant="outline">{evt.event_type}</Badge>
                        <span className="text-xs text-muted">{evt.latency_ms ? `${evt.latency_ms}ms` : ''}</span>
                      </div>
                      {evt.payload && (
                        <pre className="mt-2 text-xs text-muted overflow-x-auto">{JSON.stringify(evt.payload, null, 2)}</pre>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        ) : (
          <LoadingState />
        )}
      </Dialog>
    </div>
  )
}
