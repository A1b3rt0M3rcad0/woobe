import { useMemo, useState } from 'react'
import { BarChart3, RefreshCw } from 'lucide-react'
import { useParams } from 'react-router-dom'

import { ErrorState } from '@/components/common/ErrorState'
import { LoadingState } from '@/components/common/LoadingState'
import {
  ResourceEmptyState,
  ResourcePage,
  ResourceSectionHeader,
  ResourceTabs,
  ResourceToolbar,
} from '@/components/common/ResourcePage'
import { Select } from '@/components/ui/Select'
import { resolveUsageWindow, useProjectUsage } from '@/features/usage/hooks'
import { UsageMetricGrid } from '@/features/usage/components/UsageMetricGrid'
import { UsageOperations } from '@/features/usage/components/UsageOperations'
import { UsageTrendChart, type UsageTrendMode } from '@/features/usage/components/UsageTrendChart'
import type { UsageEnvironment, UsageGroupBy, UsageRange } from '@/features/usage/types'
import { formatKnownMoney } from '@/lib/formatters/money'

function formatDateTime(value: string | null) {
  if (!value) return 'No completed runtime data'
  return new Intl.DateTimeFormat('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    timeZoneName: 'short',
  }).format(new Date(value))
}

function formatBucket(value: string, bucket: 'hour' | 'day') {
  return new Intl.DateTimeFormat('en-US', bucket === 'hour'
    ? { month: 'short', day: 'numeric', hour: '2-digit' }
    : { month: 'short', day: 'numeric', year: 'numeric' }).format(new Date(value))
}

function formatNumber(value: number) {
  return new Intl.NumberFormat('en-US').format(value)
}

export default function UsagePage() {
  const { organizationId, projectId } = useParams<{ organizationId: string; projectId: string }>()
  const [range, setRange] = useState<UsageRange>('30d')
  const [environment, setEnvironment] = useState<UsageEnvironment>('all')
  const [groupBy, setGroupBy] = useState<UsageGroupBy>('agent')
  const [trendMode, setTrendMode] = useState<UsageTrendMode>('cost')
  const [anchor, setAnchor] = useState(() => new Date())

  const params = useMemo(() => {
    if (!projectId) return undefined
    const window = resolveUsageWindow(range, anchor)
    return {
      projectId,
      ...window,
      environment,
      group_by: groupBy,
      top_limit: 10,
    }
  }, [anchor, environment, groupBy, projectId, range])

  const usageQuery = useProjectUsage(params)
  const usage = usageQuery.data
  const hasUsage = Boolean(usage && usage.summary.runtime_requests > 0)

  const refresh = () => {
    setAnchor(new Date())
    void usageQuery.refetch()
  }

  return (
    <ResourcePage
      title="Usage"
      description="Understand runtime consumption, estimated provider spend and cost drivers for this Project."
      className="max-w-[1600px]"
      action={(
        <button
          type="button"
          onClick={refresh}
          disabled={usageQuery.isFetching}
          className="inline-flex h-9 items-center gap-2 rounded-lg border border-border bg-surface/60 px-3 text-xs font-medium text-white transition-colors hover:bg-surface disabled:opacity-50"
        >
          <RefreshCw className={usageQuery.isFetching ? 'h-3.5 w-3.5 animate-spin' : 'h-3.5 w-3.5'} />
          Refresh
        </button>
      )}
    >
      <div className="-mt-2 text-xs text-muted">
        Data through <span className="text-white">{formatDateTime(usage?.data_through ?? null)}</span>
        {usage?.data_quality.aggregation_lag_seconds !== null && usage?.data_quality.aggregation_lag_seconds !== undefined
          ? ` · ${usage.data_quality.aggregation_lag_seconds}s freshness`
          : ''}
      </div>

      <ResourceToolbar>
        <div className="flex flex-col gap-4 xl:flex-row xl:items-center xl:justify-between">
          <ResourceTabs
            value={range}
            onChange={(value) => { setRange(value); setAnchor(new Date()) }}
            label="Usage period"
            tabs={[
              { value: '24h', label: 'Last 24 hours' },
              { value: '7d', label: 'Last 7 days' },
              { value: '30d', label: 'Last 30 days' },
              { value: '90d', label: 'Last 90 days' },
            ]}
          />
          <ResourceTabs
            value={environment}
            onChange={(value) => { setEnvironment(value); setAnchor(new Date()) }}
            label="Runtime environment"
            tabs={[
              { value: 'all', label: 'All environments' },
              { value: 'draft', label: 'Draft' },
              { value: 'staging', label: 'Staging' },
              { value: 'production', label: 'Production' },
            ]}
          />
        </div>
        <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-end">
          <label htmlFor="usage-group-by" className="text-xs font-medium text-muted">Group cost drivers by</label>
          <Select
            id="usage-group-by"
            value={groupBy}
            onChange={(event) => setGroupBy(event.target.value as UsageGroupBy)}
            className="min-w-[180px] bg-background/35"
            options={[
              { value: 'agent', label: 'Agent' },
              { value: 'model', label: 'Model' },
              { value: 'provider', label: 'Provider' },
              { value: 'environment', label: 'Environment' },
              { value: 'release', label: 'Release' },
            ]}
          />
        </div>
      </ResourceToolbar>

      {usageQuery.isLoading ? (
        <LoadingState message="Loading Usage analytics" variant="panel" layout="metrics" />
      ) : usageQuery.isError ? (
        <ErrorState
          error={usageQuery.error}
          onRetry={refresh}
          className="rounded-xl border border-border/80 bg-surface/40 py-10"
        />
      ) : !usage || !hasUsage ? (
        <ResourceEmptyState
          icon={<BarChart3 className="h-4 w-4" />}
          title="No runtime usage in this period"
          description="Usage appears after an Agent reaches a terminal runtime state. Select a wider period or another environment if executions already exist."
        />
      ) : (
        <div className="space-y-4">
          <section>
            <ResourceSectionHeader
              title="Usage overview"
              description="Consumption and estimated provider spend for the exact selected window."
              count={`${formatNumber(usage.summary.runtime_requests)} runtime requests`}
            />
            <UsageMetricGrid summary={usage.summary} />
          </section>

          <UsageTrendChart points={usage.timeseries} mode={trendMode} onModeChange={setTrendMode} />

          <UsageOperations
            breakdown={usage.breakdown}
            composition={usage.composition}
            quality={usage.data_quality}
            executions={usage.top_executions}
            groupBy={usage.group_by}
            organizationId={organizationId ?? ''}
            projectId={projectId ?? ''}
          />

          <section className="overflow-hidden rounded-xl border border-border/90 bg-surface/70">
            <div className="border-b border-border px-4 py-3">
              <h2 className="text-sm font-semibold text-white">Period breakdown</h2>
              <p className="mt-1 text-xs text-muted">Requests, LLM calls, tokens and known spend per {usage.bucket} bucket.</p>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full min-w-[920px] text-left text-xs">
                <thead className="border-b border-border/80 bg-background/20 text-[10px] uppercase tracking-wider text-muted">
                  <tr>
                    <th className="px-4 py-3 font-medium">Period</th>
                    <th className="px-3 py-3 text-right font-medium">Requests</th>
                    <th className="px-3 py-3 text-right font-medium">Success</th>
                    <th className="px-3 py-3 text-right font-medium">Failed</th>
                    <th className="px-3 py-3 text-right font-medium">LLM calls</th>
                    <th className="px-3 py-3 text-right font-medium">Input</th>
                    <th className="px-3 py-3 text-right font-medium">Output</th>
                    <th className="px-4 py-3 text-right font-medium">Known spend</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border/70">
                  {[...usage.timeseries].reverse().map((point) => (
                    <tr key={point.bucket_start} className="transition-colors hover:bg-background/25">
                      <td className="px-4 py-3 font-medium text-white">{formatBucket(point.bucket_start, usage.bucket)}</td>
                      <td className="px-3 py-3 text-right text-white">{formatNumber(point.runtime_requests)}</td>
                      <td className="px-3 py-3 text-right text-emerald-300">{formatNumber(point.successful_requests)}</td>
                      <td className="px-3 py-3 text-right text-amber-300">{formatNumber(point.failed_requests)}</td>
                      <td className="px-3 py-3 text-right text-white">{formatNumber(point.llm_calls)}</td>
                      <td className="px-3 py-3 text-right text-white">{formatNumber(point.input_tokens)}</td>
                      <td className="px-3 py-3 text-right text-white">{formatNumber(point.output_tokens)}</td>
                      <td className={point.partial_cost_requests || point.unpriced_requests ? 'px-4 py-3 text-right text-amber-300' : 'px-4 py-3 text-right text-white'}>{formatKnownMoney(point.known_cost_usd)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        </div>
      )}
    </ResourcePage>
  )
}
