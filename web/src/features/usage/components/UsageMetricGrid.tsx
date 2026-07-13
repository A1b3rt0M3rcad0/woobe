import type { ReactNode } from 'react'
import {
  Activity,
  BadgeDollarSign,
  Braces,
  CircleGauge,
  Coins,
  Workflow,
  type LucideIcon,
} from 'lucide-react'

import type { ProjectUsageSummary } from '../types'
import { formatKnownMoney, formatMoney } from '@/lib/formatters/money'

function formatNumber(value: number | null, maximumFractionDigits = 0) {
  if (value === null) return '—'
  return new Intl.NumberFormat('en-US', {
    notation: Math.abs(value) >= 10_000 ? 'compact' : 'standard',
    maximumFractionDigits,
  }).format(value)
}

function Change({ value, inverse = false }: { value: number | null; inverse?: boolean }) {
  if (value === null) return <span className="text-muted">No previous baseline</span>
  const sign = value > 0 ? '+' : ''
  const positive = inverse ? value < 0 : value > 0
  const negative = inverse ? value > 0 : value < 0
  return (
    <span className={positive ? 'text-emerald-300' : negative ? 'text-amber-300' : 'text-muted'}>
      {sign}{value.toFixed(1)}% vs previous
    </span>
  )
}

interface MetricCardProps {
  label: string
  value: string
  description: ReactNode
  icon: LucideIcon
  warning?: boolean
}

function MetricCard({ label, value, description, icon: Icon, warning }: MetricCardProps) {
  return (
    <div className="min-h-[118px] rounded-xl border border-border/90 bg-surface/70 p-4">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-muted">{label}</p>
          <p className="mt-2 truncate text-2xl font-semibold tracking-tight text-white" title={value}>{value}</p>
          <div className={warning ? 'mt-1 text-xs text-amber-300' : 'mt-1 text-xs text-muted'}>{description}</div>
        </div>
        <div className={warning
          ? 'flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-amber-400/25 bg-amber-400/10 text-amber-300'
          : 'flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-primary/25 bg-primary/10 text-primary-light'}
        >
          <Icon className="h-4 w-4" />
        </div>
      </div>
    </div>
  )
}

export function UsageMetricGrid({ summary }: { summary: ProjectUsageSummary }) {
  const generationTokens = summary.input_tokens + summary.output_tokens
  const partial = summary.partial_cost_requests > 0 || summary.unpriced_requests > 0
  const successRate = summary.runtime_requests
    ? (summary.successful_requests / summary.runtime_requests) * 100
    : 0
  const callsPerRequest = summary.runtime_requests
    ? summary.llm_calls / summary.runtime_requests
    : 0

  return (
    <div className="space-y-3">
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 2xl:grid-cols-4">
        <MetricCard
          icon={BadgeDollarSign}
          label="Known provider spend"
          value={formatKnownMoney(summary.known_cost_usd)}
          warning={partial}
          description={partial
            ? `${summary.partial_cost_requests} partial · ${summary.unpriced_requests} unpriced`
            : <Change value={summary.cost_change_percent} inverse />}
        />
        <MetricCard
          icon={Activity}
          label="Runtime requests"
          value={formatNumber(summary.runtime_requests)}
          description={<Change value={summary.request_change_percent} />}
        />
        <MetricCard
          icon={Coins}
          label="Cost per priced request"
          value={formatKnownMoney(summary.cost_per_priced_request)}
          warning={partial}
          description={`${summary.cost_coverage_percent === null ? '—' : summary.cost_coverage_percent.toFixed(1)}% pricing coverage`}
        />
        <MetricCard
          icon={CircleGauge}
          label="Runtime success rate"
          value={`${successRate.toFixed(1)}%`}
          description={`${formatNumber(summary.failed_requests + summary.cancelled_requests)} failed or cancelled`}
        />
      </div>

      <div className="grid gap-3 rounded-xl border border-border/80 bg-surface/45 p-3 sm:grid-cols-2 xl:grid-cols-4">
        <div className="flex items-center gap-3 rounded-lg border border-border/60 bg-background/20 p-3">
          <Workflow className="h-4 w-4 text-primary-light" />
          <div>
            <p className="text-[10px] font-semibold uppercase tracking-wider text-muted">LLM calls</p>
            <p className="mt-1 text-sm font-semibold text-white">{formatNumber(summary.llm_calls)}</p>
            <p className="mt-0.5 text-[10px] text-muted">{callsPerRequest.toFixed(2)} per request</p>
          </div>
        </div>
        <div className="flex items-center gap-3 rounded-lg border border-border/60 bg-background/20 p-3">
          <Braces className="h-4 w-4 text-primary-light" />
          <div>
            <p className="text-[10px] font-semibold uppercase tracking-wider text-muted">Generation tokens</p>
            <p className="mt-1 text-sm font-semibold text-white">{formatNumber(generationTokens)}</p>
            <p className="mt-0.5 text-[10px] text-muted">{formatNumber(summary.tokens_per_request, 1)} per request</p>
          </div>
        </div>
        <div className="rounded-lg border border-border/60 bg-background/20 p-3">
          <p className="text-[10px] font-semibold uppercase tracking-wider text-muted">Failed spend</p>
          <p className="mt-1 text-sm font-semibold text-white">{formatMoney(summary.failed_spend_usd)}</p>
          <p className="mt-0.5 text-[10px] text-muted">Known spend on failed or cancelled runs</p>
        </div>
        <div className="rounded-lg border border-border/60 bg-background/20 p-3">
          <p className="text-[10px] font-semibold uppercase tracking-wider text-muted">Priced requests</p>
          <p className="mt-1 text-sm font-semibold text-white">{formatNumber(summary.priced_requests)}</p>
          <p className="mt-0.5 text-[10px] text-muted">{summary.cost_coverage_percent === null ? 'No coverage baseline' : `${summary.cost_coverage_percent.toFixed(1)}% of runtime requests`}</p>
        </div>
      </div>
    </div>
  )
}
