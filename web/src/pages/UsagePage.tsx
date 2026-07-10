import { useMemo, useState } from 'react'
import { useParams } from 'react-router-dom'
import { BarChart3, FileText, MessageSquare } from 'lucide-react'

import { ErrorState } from '@/components/common/ErrorState'
import { LoadingState } from '@/components/common/LoadingState'
import {
  ResourceEmptyState,
  ResourcePage,
  ResourceSectionHeader,
  ResourceTabs,
  ResourceToolbar,
} from '@/components/common/ResourcePage'
import { useProjectUsage } from '@/features/usage/hooks'
import type { DailyUsage } from '@/features/usage/types'
import { formatMoney } from '@/lib/formatters/money'

type UsageRange = '7d' | '30d' | '90d' | 'all'

function formatNumber(value: number) {
  return value.toLocaleString()
}

function formatDay(value: string) {
  const [year, month, day] = value.split('-').map(Number)
  return new Date(year, month - 1, day).toLocaleDateString()
}

function dateOnly(value: string) {
  const [year, month, day] = value.split('-').map(Number)
  return new Date(year, month - 1, day)
}

function filterByRange(items: DailyUsage[], range: UsageRange) {
  if (range === 'all') return items
  const days = range === '7d' ? 7 : range === '30d' ? 30 : 90
  const cutoff = new Date()
  cutoff.setHours(0, 0, 0, 0)
  cutoff.setDate(cutoff.getDate() - (days - 1))
  return items.filter((item) => dateOnly(item.day) >= cutoff)
}

function MetricCard({ label, value, description, icon: Icon }: { label: string; value: string; description: string; icon: typeof MessageSquare }) {
  return (
    <div className="rounded-xl border border-border/90 bg-surface/70 p-4">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-muted">{label}</p>
          <p className="mt-2 truncate text-2xl font-semibold tracking-tight text-white">{value}</p>
          <p className="mt-1 truncate text-xs text-muted" title={description}>{description}</p>
        </div>
        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-primary/25 bg-primary/10 text-primary-light">
          <Icon className="h-4 w-4" />
        </div>
      </div>
    </div>
  )
}

function DailyUsageTrend({ usage }: { usage: DailyUsage[] }) {
  const maxRequests = Math.max(...usage.map((item) => item.requests), 1)

  return (
    <section className="rounded-xl border border-border/90 bg-surface/70 p-4">
      <div className="mb-4">
        <h2 className="text-sm font-semibold text-white">Daily usage trend</h2>
        <p className="mt-1 text-xs text-muted">Request volume by day.</p>
      </div>

      <div className="space-y-3">
        {usage.map((item) => {
          const width = `${Math.max((item.requests / maxRequests) * 100, item.requests > 0 ? 6 : 0)}%`
          return (
            <div key={item.day} className="grid gap-3 md:grid-cols-[120px_minmax(0,1fr)_96px] md:items-center">
              <span className="text-xs text-muted">{formatDay(item.day)}</span>
              <div className="h-2 overflow-hidden rounded-full bg-background">
                <div className="h-full rounded-full bg-primary/70" style={{ width }} />
              </div>
              <span className="text-left text-xs font-medium text-white md:text-right">{formatNumber(item.requests)}</span>
            </div>
          )
        })}
      </div>
    </section>
  )
}

function DailyUsageRows({ usage }: { usage: DailyUsage[] }) {
  return (
    <section className="overflow-hidden rounded-xl border border-border/90 bg-surface/70">
      <div className="border-b border-border px-4 py-3">
        <h2 className="text-sm font-semibold text-white">Daily usage</h2>
        <p className="mt-1 text-xs text-muted">Requests, token volume and estimated cost.</p>
      </div>
      <div className="divide-y divide-border/80">
        {usage.map((item) => {
          const totalTokens = item.input_tokens + item.output_tokens
          return (
            <div key={item.day} className="grid gap-3 px-4 py-3 text-sm xl:grid-cols-[1fr_repeat(4,minmax(110px,auto))] xl:items-center">
              <div>
                <p className="font-medium text-white">{formatDay(item.day)}</p>
                <p className="mt-1 text-xs text-muted">{totalTokens.toLocaleString()} total tokens</p>
              </div>
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 xl:contents">
                <div>
                  <p className="text-[10px] uppercase tracking-wider text-muted">Requests</p>
                  <p className="mt-1 font-medium text-white">{formatNumber(item.requests)}</p>
                </div>
                <div>
                  <p className="text-[10px] uppercase tracking-wider text-muted">Input</p>
                  <p className="mt-1 font-medium text-white">{formatNumber(item.input_tokens)}</p>
                </div>
                <div>
                  <p className="text-[10px] uppercase tracking-wider text-muted">Output</p>
                  <p className="mt-1 font-medium text-white">{formatNumber(item.output_tokens)}</p>
                </div>
                <div>
                  <p className="text-[10px] uppercase tracking-wider text-muted">Cost</p>
                  <p className="mt-1 font-medium text-white">{formatMoney(item.cost_usd)}</p>
                </div>
              </div>
            </div>
          )
        })}
      </div>
    </section>
  )
}

export default function UsagePage() {
  const { projectId } = useParams<{ projectId: string }>()
  const { data: usage, isLoading, isError, error, refetch } = useProjectUsage(projectId)
  const [range, setRange] = useState<UsageRange>('30d')

  const items = usage ?? []
  const visibleUsage = useMemo(() => filterByRange(items, range), [items, range])
  const totalRequests = visibleUsage.reduce((sum: number, item: DailyUsage) => sum + item.requests, 0)
  const totalInput = visibleUsage.reduce((sum: number, item: DailyUsage) => sum + item.input_tokens, 0)
  const totalOutput = visibleUsage.reduce((sum: number, item: DailyUsage) => sum + item.output_tokens, 0)
  const totalCost = visibleUsage.reduce((sum: number, item: DailyUsage) => sum + item.cost_usd, 0)
  const totalTokens = totalInput + totalOutput
  const averageTokensPerRequest = totalRequests > 0 ? Math.round(totalTokens / totalRequests) : 0
  const averageCostPerRequest = totalRequests > 0 ? totalCost / totalRequests : 0

  return (
    <ResourcePage
      title="Usage"
      description="Track runtime volume, token usage and estimated cost for this Project."
    >
      <ResourceToolbar>
        <ResourceTabs
          value={range}
          onChange={setRange}
          label="Usage period"
          tabs={[
            { value: '7d', label: 'Last 7 days' },
            { value: '30d', label: 'Last 30 days' },
            { value: '90d', label: 'Last 90 days' },
            { value: 'all', label: 'All time' },
          ]}
        />
      </ResourceToolbar>

      <section>
        <ResourceSectionHeader
          title="Usage overview"
          description="Aggregated runtime consumption for the selected period."
          count={`${visibleUsage.length} day${visibleUsage.length === 1 ? '' : 's'}`}
        />

        {isLoading ? (
          <LoadingState message="Loading Usage" variant="panel" layout="metrics" />
        ) : isError ? (
          <ErrorState error={error} onRetry={refetch} className="rounded-xl border border-border/80 bg-surface/40 py-10" />
        ) : visibleUsage.length === 0 ? (
          <ResourceEmptyState
            icon={<BarChart3 className="h-4 w-4" />}
            title={items.length === 0 ? 'No Usage data' : 'No Usage in this period'}
            description={items.length === 0
              ? 'Usage appears after Agents begin receiving runtime requests.'
              : 'Choose a wider period to inspect earlier runtime activity.'}
          />
        ) : (
          <div className="space-y-4">
            <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
              <MetricCard icon={MessageSquare} label="Requests" value={formatNumber(totalRequests)} description="Runtime requests" />
              <MetricCard icon={FileText} label="Tokens" value={formatNumber(totalTokens)} description={`${formatNumber(totalInput)} input · ${formatNumber(totalOutput)} output`} />
              <MetricCard icon={BarChart3} label="Cost" value={formatMoney(totalCost)} description="Estimated total cost" />
              <MetricCard icon={BarChart3} label="Efficiency" value={formatNumber(averageTokensPerRequest)} description={`${formatMoney(averageCostPerRequest)} per request`} />
            </div>

            <DailyUsageTrend usage={visibleUsage} />
            <DailyUsageRows usage={visibleUsage} />
          </div>
        )}
      </section>
    </ResourcePage>
  )
}

