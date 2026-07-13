import type { ReactNode } from 'react'
import { Activity, BadgeDollarSign, Braces, CircleGauge, Coins, Workflow, type LucideIcon } from 'lucide-react'

import type { ProjectUsageSummary } from '../types'
import { formatKnownMoney, formatMoney } from '@/lib/formatters/money'

function formatNumber(value: number | null, maximumFractionDigits = 0) {
  if (value === null) return '—'
  return new Intl.NumberFormat('en-US', {
    notation: Math.abs(value) >= 10_000 ? 'compact' : 'standard',
    maximumFractionDigits,
  }).format(value)
}

function Change({ value }: { value: number | null }) {
  if (value === null) return <span className="text-muted">No previous baseline</span>
  const sign = value > 0 ? '+' : ''
  return <span className={value > 0 ? 'text-amber-300' : value < 0 ? 'text-emerald-300' : 'text-muted'}>{sign}{value.toFixed(1)}% vs previous</span>
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
    <div className="min-h-[116px] rounded-xl border border-border/90 bg-surface/70 p-4">
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
  return (
    <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-6">
      <MetricCard
        icon={BadgeDollarSign}
        label="Estimated provider spend"
        value={formatKnownMoney(summary.known_cost_usd)}
        warning={partial}
        description={partial
          ? `${summary.partial_cost_requests} partial · ${summary.unpriced_requests} unpriced`
          : <Change value={summary.cost_change_percent} />}
      />
      <MetricCard
        icon={Activity}
        label="Runtime requests"
        value={formatNumber(summary.runtime_requests)}
        description={<Change value={summary.request_change_percent} />}
      />
      <MetricCard
        icon={Workflow}
        label="LLM calls"
        value={formatNumber(summary.llm_calls)}
        description={`${summary.runtime_requests ? (summary.llm_calls / summary.runtime_requests).toFixed(2) : '0.00'} calls per request`}
      />
      <MetricCard
        icon={Braces}
        label="Generation tokens"
        value={formatNumber(generationTokens)}
        description={`${formatNumber(summary.input_tokens)} input · ${formatNumber(summary.output_tokens)} output`}
      />
      <MetricCard
        icon={Coins}
        label="Cost per priced request"
        value={summary.cost_per_priced_request === null ? 'Unknown' : formatMoney(summary.cost_per_priced_request)}
        description={`${formatMoney(summary.failed_spend_usd)} failed spend`}
      />
      <MetricCard
        icon={CircleGauge}
        label="Cost coverage"
        value={summary.cost_coverage_percent === null ? '—' : `${summary.cost_coverage_percent.toFixed(2)}%`}
        warning={partial}
        description={`${formatNumber(summary.priced_requests)} fully priced requests`}
      />
    </div>
  )
}
