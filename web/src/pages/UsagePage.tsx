import { type ReactNode } from 'react'
import { useParams } from 'react-router-dom'
import { useProjectUsage } from '@/features/usage/hooks'
import { LoadingState } from '@/components/common/LoadingState'
import { ErrorState } from '@/components/common/ErrorState'
import { formatMoney } from '@/lib/formatters/money'
import { BarChart3, FileText, MessageSquare } from 'lucide-react'
import type { DailyUsage } from '@/features/usage/types'

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

function formatNumber(value: number) {
  return value.toLocaleString()
}

function formatDay(value: string) {
  return new Date(`${value}T00:00:00`).toLocaleDateString()
}

function MetricCard({ label, value, description, icon: Icon }: { label: string; value: string; description: string; icon: typeof MessageSquare }) {
  return (
    <div className="rounded-xl border border-border/90 bg-surface/70 p-5">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-xs font-medium uppercase tracking-[0.18em] text-muted">{label}</p>
          <p className="mt-3 text-2xl font-semibold tracking-tight text-white">{value}</p>
          <p className="mt-2 text-xs leading-5 text-muted">{description}</p>
        </div>
        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-border bg-background text-primary-light">
          <Icon className="h-5 w-5" />
        </div>
      </div>
    </div>
  )
}

function EmptyUsage() {
  return (
    <div className="rounded-xl border border-border/80 bg-surface/50 px-5 py-8 text-center">
      <BarChart3 className="mx-auto h-10 w-10 text-muted" />
      <h2 className="mt-4 text-sm font-semibold text-white">No usage data</h2>
      <p className="mt-1 text-sm text-muted">Usage appears once agents start receiving runtime requests.</p>
    </div>
  )
}

function DailyUsageTrend({ usage }: { usage: DailyUsage[] }) {
  const maxRequests = Math.max(...usage.map((item) => item.requests), 1)

  return (
    <section className="rounded-xl border border-border/90 bg-surface/70 p-5">
      <div className="mb-5 flex items-center justify-between gap-3">
        <div>
          <h2 className="text-sm font-semibold text-white">Daily usage trend</h2>
          <p className="mt-1 text-xs text-muted">Request volume by day.</p>
        </div>
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
              <span className="text-right text-xs font-medium text-white">{formatNumber(item.requests)}</span>
            </div>
          )
        })}
      </div>
    </section>
  )
}

function DailyUsageRows({ usage }: { usage: DailyUsage[] }) {
  return (
    <section className="rounded-xl border border-border/90 bg-surface/70">
      <div className="border-b border-border px-5 py-4">
        <h2 className="text-sm font-semibold text-white">Daily usage</h2>
        <p className="mt-1 text-xs text-muted">Requests, token volume and estimated cost.</p>
      </div>
      <div className="divide-y divide-border/80">
        {usage.map((item) => {
          const totalTokens = item.input_tokens + item.output_tokens
          return (
            <div key={item.day} className="grid gap-3 px-5 py-4 text-sm md:grid-cols-[1fr_repeat(4,minmax(110px,auto))] md:items-center">
              <div>
                <p className="font-medium text-white">{formatDay(item.day)}</p>
                <p className="mt-1 text-xs text-muted">{totalTokens.toLocaleString()} total tokens</p>
              </div>
              <div>
                <p className="text-xs text-muted">Requests</p>
                <p className="mt-1 font-medium text-white">{formatNumber(item.requests)}</p>
              </div>
              <div>
                <p className="text-xs text-muted">Input</p>
                <p className="mt-1 font-medium text-white">{formatNumber(item.input_tokens)}</p>
              </div>
              <div>
                <p className="text-xs text-muted">Output</p>
                <p className="mt-1 font-medium text-white">{formatNumber(item.output_tokens)}</p>
              </div>
              <div>
                <p className="text-xs text-muted">Cost</p>
                <p className="mt-1 font-medium text-white">{formatMoney(item.cost_usd)}</p>
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

  if (isLoading) return <LoadingState />
  if (isError) return <ErrorState error={error} onRetry={refetch} />

  const items = usage ?? []
  const totalRequests = items.reduce((sum: number, item: DailyUsage) => sum + item.requests, 0)
  const totalInput = items.reduce((sum: number, item: DailyUsage) => sum + item.input_tokens, 0)
  const totalOutput = items.reduce((sum: number, item: DailyUsage) => sum + item.output_tokens, 0)
  const totalCost = items.reduce((sum: number, item: DailyUsage) => sum + item.cost_usd, 0)
  const totalTokens = totalInput + totalOutput
  const averageTokensPerRequest = totalRequests > 0 ? Math.round(totalTokens / totalRequests) : 0
  const averageCostPerRequest = totalRequests > 0 ? totalCost / totalRequests : 0

  return (
    <MinimalShell
      title="Usage"
      description="Track runtime volume, token usage and estimated cost for this project."
    >
      {items.length === 0 ? (
        <EmptyUsage />
      ) : (
        <>
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
            <MetricCard icon={MessageSquare} label="Requests" value={formatNumber(totalRequests)} description="Total runtime requests in the current dataset." />
            <MetricCard icon={FileText} label="Tokens" value={formatNumber(totalTokens)} description={`${formatNumber(totalInput)} input · ${formatNumber(totalOutput)} output`} />
            <MetricCard icon={BarChart3} label="Cost" value={formatMoney(totalCost)} description="Estimated total cost across recorded usage." />
            <MetricCard icon={BarChart3} label="Efficiency" value={formatNumber(averageTokensPerRequest)} description={`${formatMoney(averageCostPerRequest)} average cost per request`} />
          </div>

          <DailyUsageTrend usage={items} />
          <DailyUsageRows usage={items} />
        </>
      )}
    </MinimalShell>
  )
}
