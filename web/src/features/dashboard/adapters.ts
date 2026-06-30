import type { LucideIcon } from 'lucide-react'
import {
  Activity,
  CheckCircle2,
  CircleDollarSign,
  Clock3,
  Rocket,
  Users,
} from 'lucide-react'
import type {
  DashboardEnvironment,
  DashboardRangePreset,
  ProjectOverview,
  ProjectOverviewRelease,
  ProjectOverviewTrace,
} from './types'

const OVERVIEW_RECENT_ROW_LIMIT = 3

export interface DashboardMetric {
  label: string
  value: string
  detail: string | null
  direction: 'up' | 'down' | 'neutral'
  icon: LucideIcon
  tone: string
}

export interface DashboardSeriesPoint {
  label: string
  requests: number
  latencyMs: number | null
  tokens: number
}

export interface DashboardEnvironmentSlice {
  key: Exclude<DashboardEnvironment, 'all'>
  label: string
  value: number
  percent: number
  color: string
}

export interface DashboardReleaseRow extends ProjectOverviewRelease {
  environmentLabel: string
  promotedLabel: string
}

export interface DashboardTraceRow extends ProjectOverviewTrace {
  agentLabel: string
  environmentLabel: string
  statusLabel: string
  timeLabel: string
  latencyLabel: string
  tokenLabel: string
  costLabel: string
}

export interface DashboardViewModel {
  metrics: DashboardMetric[]
  series: DashboardSeriesPoint[]
  environments: DashboardEnvironmentSlice[]
  environmentTotal: number
  releases: DashboardReleaseRow[]
  traces: DashboardTraceRow[]
  knowledge: {
    collections: string
    documents: string
    indexed: string
    failed: string
    pending: string
    storage: string
  }
  tools: {
    total: string
    active: string
    inactive: string
    recentFailures: number
  }
  capabilities: ProjectOverview['capabilities']
  generatedAtLabel: string
  intervalLabel: string
  timezoneLabel: string
  isExecutionEmpty: boolean
}

const numberFormatter = new Intl.NumberFormat(undefined, { maximumFractionDigits: 0 })
const compactNumberFormatter = new Intl.NumberFormat(undefined, {
  notation: 'compact',
  maximumFractionDigits: 1,
})
const percentFormatter = new Intl.NumberFormat(undefined, {
  minimumFractionDigits: 0,
  maximumFractionDigits: 2,
})
const currencyFormatter = new Intl.NumberFormat(undefined, {
  style: 'currency',
  currency: 'USD',
  minimumFractionDigits: 2,
  maximumFractionDigits: 4,
})
const dateTimeFormatter = new Intl.DateTimeFormat(undefined, {
  dateStyle: 'medium',
  timeStyle: 'short',
})
const chartLabelFormatter = new Intl.DateTimeFormat(undefined, {
  month: 'short',
  day: 'numeric',
  hour: '2-digit',
  minute: '2-digit',
})

export function formatInteger(value: number): string {
  return numberFormatter.format(value)
}

export function formatCompactInteger(value: number): string {
  return compactNumberFormatter.format(value)
}

export function formatPercent(value: number | null): string {
  return value === null ? '—' : `${percentFormatter.format(value)}%`
}

export function formatLatency(value: number | null): string {
  return value === null ? '—' : `${numberFormatter.format(Math.round(value))} ms`
}

export function formatCost(value: number | null, known = true): string {
  return value === null || !known ? 'Unknown' : currencyFormatter.format(value)
}

export function formatStorage(bytes: number): string {
  if (bytes === 0) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB', 'TB']
  const index = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1)
  const value = bytes / 1024 ** index
  return `${value.toFixed(value >= 10 || index === 0 ? 0 : 1)} ${units[index]}`
}

export function environmentLabel(environment: DashboardEnvironment | null): string {
  if (environment === null || environment === 'all') return 'All'
  return environment[0].toUpperCase() + environment.slice(1)
}

export function rangeLabel(range: DashboardRangePreset): string {
  return range === '24h' ? 'Last 24 hours' : range === '7d' ? 'Last 7 days' : 'Last 30 days'
}

function safeDateLabel(value: string | null, fallback = '—'): string {
  if (!value) return fallback
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? fallback : dateTimeFormatter.format(date)
}

function statusLabel(status: string): string {
  const normalized = status.trim().toLowerCase()
  if (['success', 'succeeded', 'completed'].includes(normalized)) return 'Success'
  if (['warning', 'partial', 'cancelled', 'canceled'].includes(normalized)) return 'Warning'
  if (['error', 'failed', 'failure'].includes(normalized)) return 'Error'
  return status || 'Unknown'
}

function requestChangeDetail(change: number | null): Pick<DashboardMetric, 'detail' | 'direction'> {
  if (change === null) return { detail: null, direction: 'neutral' }
  const direction = change > 0 ? 'up' : change < 0 ? 'down' : 'neutral'
  const prefix = change > 0 ? '+' : ''
  return { detail: `${prefix}${percentFormatter.format(change)}% vs previous window`, direction }
}

function runtimeCostDetail(requests: number, unknownCostCount: number, costUsd: number | null): string | null {
  if (requests === 0) return 'No requests in this period'
  if (unknownCostCount <= 0) return 'All requests priced'
  if (costUsd !== null) {
    const pricedRequests = Math.max(requests - unknownCostCount, 0)
    return `${formatInteger(pricedRequests)} of ${formatInteger(requests)} requests priced`
  }
  return `${formatInteger(unknownCostCount)} request${unknownCostCount === 1 ? '' : 's'} without cost data`
}

export function adaptProjectOverview(overview: ProjectOverview): DashboardViewModel {
  const requestChange = requestChangeDetail(overview.summary.request_change_percent)
  const unknownCostCount = overview.summary.unknown_cost_count ?? 0
  const costHasValue = overview.summary.cost_usd !== null
  const metrics: DashboardMetric[] = [
    {
      label: 'Active Agents',
      value: formatInteger(overview.summary.active_agents),
      detail: null,
      direction: 'neutral',
      icon: Users,
      tone: 'bg-blue-500/10 text-blue-400',
    },
    {
      label: 'Production Agents',
      value: formatInteger(overview.summary.production_agents),
      detail: null,
      direction: 'neutral',
      icon: Rocket,
      tone: 'bg-blue-500/10 text-blue-400',
    },
    {
      label: 'Runtime Requests',
      value: formatInteger(overview.summary.requests),
      ...requestChange,
      icon: Activity,
      tone: 'bg-blue-500/10 text-blue-400',
    },
    {
      label: 'Avg Latency',
      value: formatLatency(overview.summary.avg_latency_ms),
      detail: overview.summary.p95_latency_ms === null
        ? null
        : `p95 ${formatLatency(overview.summary.p95_latency_ms)}`,
      direction: 'neutral',
      icon: Clock3,
      tone: 'bg-blue-500/10 text-blue-400',
    },
    {
      label: 'Success Rate',
      value: formatPercent(overview.summary.success_rate),
      detail: `${formatInteger(overview.summary.failed_requests)} failed`,
      direction: 'neutral',
      icon: CheckCircle2,
      tone: 'bg-emerald-500/10 text-emerald-400',
    },
    {
      label: 'Runtime Cost',
      value: formatCost(overview.summary.cost_usd, costHasValue),
      detail: runtimeCostDetail(
        overview.summary.requests,
        unknownCostCount,
        overview.summary.cost_usd,
      ),
      direction: 'neutral',
      icon: CircleDollarSign,
      tone: unknownCostCount > 0 ? 'bg-amber-500/10 text-amber-300' : 'bg-blue-500/10 text-blue-400',
    },
  ]

  const series = overview.timeseries.map((point) => ({
    label: chartLabelFormatter.format(new Date(point.bucket_start)),
    requests: point.requests,
    latencyMs: point.avg_latency_ms,
    tokens: point.input_tokens + point.output_tokens,
  }))

  const distribution = overview.environment_distribution
  const environmentTotal = distribution.draft + distribution.staging + distribution.production
  const environmentSlices: DashboardEnvironmentSlice[] = [
    { key: 'production', label: 'Production', value: distribution.production, percent: 0, color: '#22c55e' },
    { key: 'staging', label: 'Staging', value: distribution.staging, percent: 0, color: '#fbbf24' },
    { key: 'draft', label: 'Draft', value: distribution.draft, percent: 0, color: '#3b82f6' },
  ]
  const environments: DashboardEnvironmentSlice[] = environmentSlices.map((slice) => ({
    ...slice,
    percent: environmentTotal === 0 ? 0 : (slice.value / environmentTotal) * 100,
  }))

  const releases = overview.recent_releases.slice(0, OVERVIEW_RECENT_ROW_LIMIT).map((release) => ({
    ...release,
    environmentLabel: environmentLabel(release.environment),
    promotedLabel: safeDateLabel(release.promoted_at ?? release.created_at),
  }))

  const traces = overview.recent_traces.slice(0, OVERVIEW_RECENT_ROW_LIMIT).map((trace) => ({
    ...trace,
    agentLabel: trace.agent_name ?? 'Unknown agent',
    environmentLabel: environmentLabel(trace.environment),
    statusLabel: statusLabel(trace.status),
    timeLabel: safeDateLabel(trace.started_at),
    latencyLabel: formatLatency(trace.latency_ms),
    tokenLabel: trace.total_tokens === null ? '—' : formatInteger(trace.total_tokens),
    costLabel: formatCost(trace.cost_usd, trace.cost_known),
  }))

  return {
    metrics,
    series,
    environments,
    environmentTotal,
    releases,
    traces,
    knowledge: {
      collections: formatInteger(overview.knowledge_summary.collections),
      documents: formatInteger(overview.knowledge_summary.documents),
      indexed: formatInteger(overview.knowledge_summary.indexed_documents),
      failed: formatInteger(overview.knowledge_summary.failed_documents),
      pending: formatInteger(overview.knowledge_summary.pending_documents),
      storage: formatStorage(overview.knowledge_summary.storage_bytes),
    },
    tools: {
      total: formatInteger(overview.tools_summary.total),
      active: formatInteger(overview.tools_summary.active),
      inactive: formatInteger(overview.tools_summary.inactive),
      recentFailures: overview.tools_summary.recent_failures.length,
    },
    capabilities: overview.capabilities,
    generatedAtLabel: safeDateLabel(overview.generated_at),
    intervalLabel: `${safeDateLabel(overview.from)} – ${safeDateLabel(overview.to)}`,
    timezoneLabel: Intl.DateTimeFormat().resolvedOptions().timeZone || 'Local time',
    isExecutionEmpty: overview.summary.requests === 0 && overview.timeseries.every((point) => point.requests === 0),
  }
}
