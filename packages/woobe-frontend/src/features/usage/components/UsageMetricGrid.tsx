import type { ReactNode } from 'react'
import {
  Activity,
  BadgeDollarSign,
  CircleGauge,
  Coins,
  Network,
  Route,
  TriangleAlert,
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
  if (value === null) return <span className="text-muted-foreground">No previous baseline</span>
  const sign = value > 0 ? '+' : ''
  const positive = inverse ? value < 0 : value > 0
  const negative = inverse ? value > 0 : value < 0
  return (
    <span className={positive ? 'text-emerald-300' : negative ? 'text-amber-300' : 'text-muted-foreground'}>
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
    <div className="min-h-[104px] rounded-container border border-border bg-surface/[0.92] px-3.5 py-3 shadow-[inset_0_1px_0_rgba(255,255,255,0.014)]">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="font-mono text-[8px] font-semibold uppercase tracking-[0.11em] text-muted-foreground">{label}</p>
          <p className="mt-1.5 truncate font-mono text-xl font-bold tabular-nums tracking-tight text-slate-50" title={value}>{value}</p>
          <div className={warning
            ? 'mt-1 font-mono text-[8px] leading-4 text-amber-300'
            : 'mt-1 font-mono text-[8px] leading-4 text-muted-foreground'}
          >
            {description}
          </div>
        </div>
        <div className={warning
          ? 'flex h-7 w-7 shrink-0 items-center justify-center rounded-control border border-amber-400/25 bg-amber-400/[0.07] text-amber-300'
          : 'flex h-7 w-7 shrink-0 items-center justify-center rounded-control border border-border bg-control text-primary-light'}
        >
          <Icon className="h-3.5 w-3.5" />
        </div>
      </div>
    </div>
  )
}

function SupportingMetric({ label, value, detail, icon: Icon }: {
  label: string
  value: string
  detail: string
  icon: LucideIcon
}) {
  return (
    <div className="flex min-w-0 items-center gap-2.5 border-r border-border/70 px-3 py-2.5 last:border-r-0">
      <Icon className="h-3.5 w-3.5 shrink-0 text-primary-light" />
      <div className="min-w-0">
        <p className="font-mono text-[8px] font-semibold uppercase tracking-[0.1em] text-muted-foreground">{label}</p>
        <p className="mt-0.5 font-mono text-[11px] font-bold tabular-nums text-slate-100">{value}</p>
        <p className="mt-0.5 truncate font-mono text-[8px] leading-4 text-muted-foreground" title={detail}>{detail}</p>
      </div>
    </div>
  )
}

export function UsageMetricGrid({ summary }: { summary: ProjectUsageSummary }) {
  const agentPricingIncomplete = summary.partial_cost_agent_runs > 0 || summary.unpriced_agent_runs > 0
  const networkPricingIncomplete = summary.partial_cost_network_runs > 0 || summary.unpriced_network_runs > 0
  const agentFailures = summary.failed_agent_runs + summary.cancelled_agent_runs
  const networkFailures = summary.failed_network_runs + summary.cancelled_network_runs

  return (
    <div className="space-y-3">
      <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-6">
        <MetricCard
          icon={BadgeDollarSign}
          label="Operational cost"
          value={formatKnownMoney(summary.known_cost_usd)}
          warning={agentPricingIncomplete}
          description={agentPricingIncomplete
            ? `${summary.partial_cost_agent_runs} partial · ${summary.unpriced_agent_runs} unpriced Agent Runs`
            : <Change value={summary.cost_change_percent} inverse />}
        />
        <MetricCard
          icon={Activity}
          label="Agent Runs"
          value={formatNumber(summary.agent_runs)}
          description={<Change value={summary.agent_run_change_percent} />}
        />
        <MetricCard
          icon={Coins}
          label="Cost / Agent Run"
          value={formatKnownMoney(summary.cost_per_priced_agent_run)}
          warning={agentPricingIncomplete}
          description={`Median ${formatKnownMoney(summary.median_agent_run_cost_usd)} · P95 ${formatKnownMoney(summary.p95_agent_run_cost_usd)}`}
        />
        <MetricCard
          icon={Network}
          label="Network Runs"
          value={formatNumber(summary.network_runs)}
          description={<Change value={summary.network_run_change_percent} />}
        />
        <MetricCard
          icon={Route}
          label="Cost / Network Run"
          value={formatKnownMoney(summary.cost_per_priced_network_run)}
          warning={networkPricingIncomplete}
          description={`Median ${formatKnownMoney(summary.median_network_run_cost_usd)} · P95 ${formatKnownMoney(summary.p95_network_run_cost_usd)}`}
        />
        <MetricCard
          icon={TriangleAlert}
          label="Failed cost"
          value={formatMoney(summary.failed_spend_usd)}
          warning={summary.failed_spend_usd > 0}
          description={`${formatNumber(agentFailures)} Agent · ${formatNumber(networkFailures)} Network failures`}
        />
      </div>

      <div className="grid overflow-hidden rounded-container border border-border bg-surface/[0.76] sm:grid-cols-2 xl:grid-cols-6">
        <SupportingMetric
          icon={Activity}
          label="Direct Agent Runs"
          value={formatNumber(summary.direct_agent_runs)}
          detail="Executed outside Networks"
        />
        <SupportingMetric
          icon={Network}
          label="Agent Runs in Networks"
          value={formatNumber(summary.network_agent_runs)}
          detail="Contained by Network Runs"
        />
        <SupportingMetric
          icon={Route}
          label="Runs / Network"
          value={formatNumber(summary.avg_agent_runs_per_network_run, 2)}
          detail="Average effective composition"
        />
        <SupportingMetric
          icon={CircleGauge}
          label="Agent success"
          value={summary.agent_run_success_rate === null ? '—' : `${summary.agent_run_success_rate.toFixed(1)}%`}
          detail="Terminal Agent Runs"
        />
        <SupportingMetric
          icon={CircleGauge}
          label="Network success"
          value={summary.network_run_success_rate === null ? '—' : `${summary.network_run_success_rate.toFixed(1)}%`}
          detail="Terminal Network Runs"
        />
        <SupportingMetric
          icon={BadgeDollarSign}
          label="Pricing coverage"
          value={summary.cost_coverage_percent === null ? '—' : `${summary.cost_coverage_percent.toFixed(1)}%`}
          detail="Fully priced Agent Runs"
        />
      </div>
    </div>
  )
}
