import type { LucideIcon } from 'lucide-react'
import {
  Activity,
  CheckCircle2,
  CircleDollarSign,
  Clock3,
  Network,
  Workflow,
} from 'lucide-react'
import type {
  DashboardEnvironment,
  DashboardRangePreset,
  OverviewRunSource,
  ProjectOverview,
  ProjectOverviewNetworkRun,
  ProjectOverviewRelease,
  ProjectOverviewTrace,
} from './types'

const OVERVIEW_RECENT_ROW_LIMIT = 6

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
  agentRuns: number
  networkRuns: number
  agentDurationMs: number | null
  networkDurationMs: number | null
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

export type DashboardRunKind = 'agent' | 'network'

export interface DashboardRunRow {
  id: string
  kind: DashboardRunKind
  title: string
  subtitle: string
  agentId: string | null
  networkId: string | null
  environmentLabel: string
  sourceLabel: string
  statusLabel: string
  timeLabel: string
  durationLabel: string
  tokenLabel: string
  costLabel: string
  startedAt: string | null
}

export interface DashboardViewModel {
  metrics: DashboardMetric[]
  series: DashboardSeriesPoint[]
  environments: DashboardEnvironmentSlice[]
  environmentTotal: number
  releases: DashboardReleaseRow[]
  runs: DashboardRunRow[]
  assets: {
    activeAgents: string
    productionAgents: string
    networks: string
    productionNetworks: string
    stagingNetworks: string
  }
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
const decimalFormatter = new Intl.NumberFormat(undefined, { maximumFractionDigits: 2 })
const percentFormatter = new Intl.NumberFormat(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 2 })
const currencyFormatter = new Intl.NumberFormat(undefined, {
  style: 'currency',
  currency: 'USD',
  minimumFractionDigits: 2,
  maximumFractionDigits: 4,
})
const dateTimeFormatter = new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeStyle: 'short' })
const chartLabelFormatter = new Intl.DateTimeFormat(undefined, {
  month: 'short',
  day: 'numeric',
  hour: '2-digit',
  minute: '2-digit',
})

export function formatInteger(value: number): string {
  return numberFormatter.format(value)
}

export function formatPercent(value: number | null): string {
  return value === null ? '—' : `${percentFormatter.format(value)}%`
}

export function formatLatency(value: number | null): string {
  if (value === null) return '—'
  if (value >= 1000) return `${decimalFormatter.format(value / 1000)} s`
  return `${numberFormatter.format(Math.round(value))} ms`
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

export function environmentLabel(environment: DashboardEnvironment | 'playground' | null): string {
  if (environment === null || environment === 'all') return 'All'
  if (environment === 'playground') return 'Draft'
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
  if (['success', 'succeeded', 'completed'].includes(normalized)) return 'Completed'
  if (['warning', 'partial', 'uncertain'].includes(normalized)) return 'Completed with issues'
  if (['running', 'processing'].includes(normalized)) return 'Running'
  if (['pending', 'queued', 'cancel_requested'].includes(normalized)) return 'Queued'
  if (['cancelled', 'canceled'].includes(normalized)) return 'Cancelled'
  if (['timed_out', 'timeout'].includes(normalized)) return 'Timed out'
  if (['error', 'failed', 'failure'].includes(normalized)) return 'Failed'
  return status || 'Unknown'
}

function changeDetail(change: number | null): Pick<DashboardMetric, 'detail' | 'direction'> {
  if (change === null) return { detail: null, direction: 'neutral' }
  const direction = change > 0 ? 'up' : change < 0 ? 'down' : 'neutral'
  const prefix = change > 0 ? '+' : ''
  return { detail: `${prefix}${percentFormatter.format(change)}% vs previous window`, direction }
}

function sourceLabel(source: OverviewRunSource | undefined, environment: ProjectOverviewTrace['environment']): string {
  if (environment === 'playground') return 'Playground'
  const value = source ?? 'unknown'
  if (value === 'network') return 'Network'
  if (value === 'playground') return 'Playground'
  if (value === 'job') return 'Job'
  if (value === 'event') return 'Event'
  if (value === 'schedule') return 'Schedule'
  if (value === 'api') return 'API'
  return 'Runtime API'
}

function agentRunRow(trace: ProjectOverviewTrace): DashboardRunRow {
  return {
    id: trace.id,
    kind: 'agent',
    title: trace.agent_name ?? 'Unknown Agent',
    subtitle: 'Agent Run',
    agentId: trace.agent_id,
    networkId: null,
    environmentLabel: environmentLabel(trace.environment),
    sourceLabel: sourceLabel(trace.source, trace.environment),
    statusLabel: statusLabel(trace.status),
    timeLabel: safeDateLabel(trace.started_at),
    durationLabel: formatLatency(trace.latency_ms),
    tokenLabel: trace.total_tokens === null ? '—' : formatInteger(trace.total_tokens),
    costLabel: formatCost(trace.cost_usd, trace.cost_known),
    startedAt: trace.started_at,
  }
}

function networkRunRow(run: ProjectOverviewNetworkRun): DashboardRunRow {
  return {
    id: run.id,
    kind: 'network',
    title: run.network_name,
    subtitle: 'Network Run',
    agentId: null,
    networkId: run.network_id,
    environmentLabel: environmentLabel(run.environment),
    sourceLabel: 'Network',
    statusLabel: statusLabel(run.status),
    timeLabel: safeDateLabel(run.started_at),
    durationLabel: formatLatency(run.duration_ms),
    tokenLabel: '—',
    costLabel: 'Aggregated from Agent Runs',
    startedAt: run.started_at,
  }
}

export function adaptProjectOverview(overview: ProjectOverview): DashboardViewModel {
  const summary = overview.summary
  const runChange = changeDetail(summary.agent_run_change_percent)
  const unknownCosts = summary.unknown_agent_run_cost_count ?? 0
  const metrics: DashboardMetric[] = [
    {
      label: 'Agent Runs',
      value: formatInteger(summary.agent_runs),
      detail: `${formatInteger(summary.direct_agent_runs)} direct · ${formatInteger(summary.network_agent_runs)} from Networks${runChange.detail ? ` · ${runChange.detail}` : ''}`,
      direction: runChange.direction,
      icon: Activity,
      tone: 'bg-blue-500/10 text-blue-400',
    },
    {
      label: 'Network Runs',
      value: formatInteger(summary.network_runs),
      detail: `${formatInteger(summary.running_network_runs)} running · ${formatInteger(summary.failed_network_runs)} failed${summary.avg_agent_runs_per_network_run === null ? '' : ` · ${decimalFormatter.format(summary.avg_agent_runs_per_network_run)} Agent Runs avg`}`,
      direction: 'neutral',
      icon: Workflow,
      tone: 'bg-violet-500/10 text-violet-300',
    },
    {
      label: 'Runtime Cost',
      value: formatCost(summary.agent_run_cost_usd, summary.agent_run_cost_usd !== null),
      detail: unknownCosts > 0 ? `${formatInteger(unknownCosts)} Agent Runs without consolidated cost` : 'All Agent Runs priced',
      direction: 'neutral',
      icon: CircleDollarSign,
      tone: unknownCosts > 0 ? 'bg-amber-500/10 text-amber-300' : 'bg-blue-500/10 text-blue-400',
    },
    {
      label: 'Avg Agent Run',
      value: formatLatency(summary.avg_agent_run_duration_ms),
      detail: summary.p95_agent_run_duration_ms === null ? null : `p95 ${formatLatency(summary.p95_agent_run_duration_ms)}`,
      direction: 'neutral',
      icon: Clock3,
      tone: 'bg-blue-500/10 text-blue-400',
    },
    {
      label: 'Avg Network Run',
      value: formatLatency(summary.avg_network_run_duration_ms),
      detail: summary.p95_network_run_duration_ms === null ? null : `p95 ${formatLatency(summary.p95_network_run_duration_ms)}`,
      direction: 'neutral',
      icon: Network,
      tone: 'bg-violet-500/10 text-violet-300',
    },
    {
      label: 'Run Health',
      value: formatPercent(summary.agent_run_success_rate),
      detail: `Agent Runs · Network Runs ${formatPercent(summary.network_run_success_rate)}`,
      direction: 'neutral',
      icon: CheckCircle2,
      tone: 'bg-emerald-500/10 text-emerald-400',
    },
  ]

  const series = overview.timeseries.map((point) => ({
    label: chartLabelFormatter.format(new Date(point.bucket_start)),
    agentRuns: point.agent_runs,
    networkRuns: point.network_runs,
    agentDurationMs: point.avg_agent_run_duration_ms,
    networkDurationMs: point.avg_network_run_duration_ms,
  }))

  const distribution = overview.environment_distribution
  const environmentTotal = distribution.draft + distribution.staging + distribution.production
  const slices: DashboardEnvironmentSlice[] = [
    { key: 'production', label: 'Production', value: distribution.production, percent: 0, color: '#22c55e' },
    { key: 'staging', label: 'Staging', value: distribution.staging, percent: 0, color: '#fbbf24' },
    { key: 'draft', label: 'Draft', value: distribution.draft, percent: 0, color: '#3b82f6' },
  ]
  const environments = slices.map((slice) => ({
    ...slice,
    percent: environmentTotal === 0 ? 0 : (slice.value / environmentTotal) * 100,
  }))

  const releases = overview.recent_releases.slice(0, 3).map((release) => ({
    ...release,
    environmentLabel: environmentLabel(release.environment),
    promotedLabel: safeDateLabel(release.promoted_at ?? release.created_at),
  }))

  const runs = [
    ...overview.recent_traces.map(agentRunRow),
    ...(overview.recent_network_runs ?? []).map(networkRunRow),
  ]
    .sort((left, right) => new Date(right.startedAt ?? 0).getTime() - new Date(left.startedAt ?? 0).getTime())
    .slice(0, OVERVIEW_RECENT_ROW_LIMIT)

  return {
    metrics,
    series,
    environments,
    environmentTotal,
    releases,
    runs,
    assets: {
      activeAgents: formatInteger(summary.active_agents),
      productionAgents: formatInteger(summary.production_agents),
      networks: formatInteger(summary.network_count),
      productionNetworks: formatInteger(summary.production_networks),
      stagingNetworks: formatInteger(summary.staging_networks),
    },
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
    isExecutionEmpty: summary.agent_runs === 0 && summary.network_runs === 0,
  }
}
