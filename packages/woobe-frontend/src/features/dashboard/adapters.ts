import type { LucideIcon } from 'lucide-react'
import {
  Activity,
  CheckCircle2,
  CircleDollarSign,
  Clock3,
  ShieldCheck,
  Workflow,
} from 'lucide-react'
import type {
  DashboardEnvironment,
  DashboardRangePreset,
  OverviewChangeAction,
  OverviewRunSource,
  ProjectOverview,
  ProjectOverviewNetworkRelease,
  ProjectOverviewNetworkRun,
  ProjectOverviewRelease,
  ProjectOverviewTrace,
} from './types'

const OVERVIEW_RECENT_ROW_LIMIT = 3
const OVERVIEW_CHANGE_ROW_LIMIT = 5

export interface DashboardMetricComparisonItem {
  label: string
  value: string
  detail: string
  tone: string
}

export interface DashboardMetric {
  label: string
  value: string
  detail: string | null
  direction: 'up' | 'down' | 'neutral'
  icon: LucideIcon
  tone: string
  comparison?: {
    agent: DashboardMetricComparisonItem
    network: DashboardMetricComparisonItem
  }
}

export interface DashboardSeriesPoint {
  label: string
  bucketStart: string
  agentRuns: number
  agentSuccess: number
  agentErrors: number
  agentRunning: number
  agentSuccessRate: number | null
  networkRuns: number
  networkSuccess: number
  networkErrors: number
  networkRunning: number
  networkSuccessRate: number | null
  agentDurationMs: number | null
  networkDurationMs: number | null
  costUsd: number | null
}

export interface DashboardEnvironmentSlice {
  key: Exclude<DashboardEnvironment, 'all'>
  label: string
  value: number
  percent: number
  color: string
}

export interface DashboardAgentReleaseRow extends ProjectOverviewRelease {
  environmentLabel: string
  occurredLabel: string
  description: string
}

export interface DashboardNetworkReleaseRow extends ProjectOverviewNetworkRelease {
  environmentLabel: string
  occurredLabel: string
  description: string
  activationLabel: string | null
}

export interface DashboardChangeRow {
  id: string
  resourceType: 'agent' | 'network'
  resourceId: string
  resourceName: string
  resourceLabel: string
  environmentLabel: string
  actionLabel: string
  versionLabel: string | null
  description: string
  occurredLabel: string
  occurredAt: string
  immutable: boolean
}

export type DashboardRunKind = 'agent' | 'network'

export interface DashboardRunRow {
  id: string
  kind: DashboardRunKind
  title: string
  typeLabel: string
  agentId: string | null
  networkId: string | null
  environmentLabel: string
  sourceLabel: string
  statusLabel: string
  timeLabel: string
  durationLabel: string
  costLabel: string
  costDetail: string | null
  startedAt: string | null
}

export interface DashboardReliabilityGroup {
  label: string
  successRate: number | null
  errorRate: number | null
  totalRuns: number
  terminalRuns: number
  successful: number
  completedWithIssues: number
  failed: number
  timedOut: number
  uncertain: number
  cancelled: number
  running: number
  averageDurationLabel: string
  p95DurationLabel: string
}

export interface DashboardOperationalIssues {
  hasIssues: boolean
  totalAgentErrors: number
  totalNetworkErrors: number
  summary: string[]
  topAgents: ProjectOverview['operational_issues']['top_agent_failures']
  topNetworks: ProjectOverview['operational_issues']['top_network_failures']
  topCodes: ProjectOverview['operational_issues']['top_failure_codes']
  peakLabel: string | null
  peakCount: number
}

export interface DashboardViewModel {
  narrative: string
  metrics: DashboardMetric[]
  series: DashboardSeriesPoint[]
  reliability: {
    agent: DashboardReliabilityGroup
    network: DashboardReliabilityGroup
  }
  issues: DashboardOperationalIssues
  environments: DashboardEnvironmentSlice[]
  environmentTotal: number
  agentReleases: DashboardAgentReleaseRow[]
  networkReleases: DashboardNetworkReleaseRow[]
  changes: DashboardChangeRow[]
  runs: DashboardRunRow[]
  assets: {
    activeAgents: string
    draftAgents: string
    stagingAgents: string
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
  if (['warning', 'partial'].includes(normalized)) return 'Completed with issues'
  if (normalized === 'uncertain') return 'Uncertain'
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
  return 'Runtime API'
}

function periodNarrativeLabel(overview: ProjectOverview): string {
  const durationMs = new Date(overview.to).getTime() - new Date(overview.from).getTime()
  const hours = durationMs / 3_600_000
  const period = hours <= 25 ? 'In the last 24 hours' : hours <= 24 * 7.1 ? 'In the last 7 days' : 'In the last 30 days'
  const environment = overview.environment === 'all'
    ? 'across all environments'
    : `in ${environmentLabel(overview.environment)}`
  return `${period} ${environment}`
}

function buildNarrative(overview: ProjectOverview): string {
  const summary = overview.summary
  const prefix = periodNarrativeLabel(overview)
  if (summary.agent_runs === 0 && summary.network_runs === 0) {
    return `${prefix}, this Project had no Agent Runs or Network Runs.`
  }

  const volume = `${formatInteger(summary.agent_runs)} Agent Runs — ${formatInteger(summary.direct_agent_runs)} direct and ${formatInteger(summary.network_agent_runs)} inside Networks — plus ${formatInteger(summary.network_runs)} Network Runs.`
  const cost = summary.agent_run_cost_usd === null
    ? 'Runtime cost is not fully known.'
    : `Recorded runtime cost was ${formatCost(summary.agent_run_cost_usd)}.`
  const reliability: string[] = []
  if (summary.agent_run_success_rate !== null) reliability.push(`Agent success ${formatPercent(summary.agent_run_success_rate)}`)
  if (summary.network_run_success_rate !== null) reliability.push(`Network success ${formatPercent(summary.network_run_success_rate)}`)
  const totalErrors = summary.failed_agent_runs
    + summary.timed_out_agent_runs
    + summary.failed_network_runs
    + summary.timed_out_network_runs
    + summary.uncertain_network_runs
  const health = reliability.length === 0
    ? 'There are no terminal Runs yet.'
    : `${reliability.join(' · ')} · ${totalErrors === 0 ? 'no execution errors' : `${formatInteger(totalErrors)} operational errors`}.`
  return `${prefix}, this Project executed ${volume} ${cost} ${health}`
}

function agentRunRow(trace: ProjectOverviewTrace): DashboardRunRow {
  return {
    id: trace.id,
    kind: 'agent',
    title: trace.agent_name ?? 'Unknown Agent',
    typeLabel: 'Agent Run',
    agentId: trace.agent_id,
    networkId: null,
    environmentLabel: environmentLabel(trace.environment),
    sourceLabel: sourceLabel(trace.source, trace.environment),
    statusLabel: statusLabel(trace.status),
    timeLabel: safeDateLabel(trace.started_at),
    durationLabel: formatLatency(trace.latency_ms),
    costLabel: formatCost(trace.cost_usd, trace.cost_known),
    costDetail: null,
    startedAt: trace.started_at,
  }
}

function networkRunRow(run: ProjectOverviewNetworkRun): DashboardRunRow {
  const hasKnownSubtotal = run.cost_usd !== null
  const costDetail = run.unknown_cost_count > 0
    ? hasKnownSubtotal
      ? `Partial · ${formatInteger(run.priced_agent_runs)}/${formatInteger(run.total_agent_runs)} Agent Runs priced`
      : 'Cost unavailable'
    : run.total_agent_runs === 0
      ? 'No Agent Runs recorded'
      : null
  return {
    id: run.id,
    kind: 'network',
    title: run.network_name,
    typeLabel: 'Network Run',
    agentId: null,
    networkId: run.network_id,
    environmentLabel: environmentLabel(run.environment),
    sourceLabel: 'Network',
    statusLabel: statusLabel(run.status),
    timeLabel: safeDateLabel(run.started_at),
    durationLabel: formatLatency(run.duration_ms),
    costLabel: formatCost(run.cost_usd, hasKnownSubtotal),
    costDetail,
    startedAt: run.started_at,
  }
}

function reliabilityTone(rate: number | null): string {
  if (rate === null) return 'bg-slate-500/10 text-slate-300'
  if (rate >= 99) return 'bg-emerald-500/10 text-emerald-400'
  if (rate >= 95) return 'bg-amber-500/10 text-amber-300'
  return 'bg-red-500/10 text-red-300'
}

function actionLabel(action: OverviewChangeAction): string {
  if (action === 'draft_updated') return 'Draft updated'
  if (action === 'staged') return 'Published to Staging'
  if (action === 'released') return 'Released to Production'
  if (action === 'rolled_back') return 'Rolled back'
  return 'Reactivated'
}

export function adaptProjectOverview(overview: ProjectOverview): DashboardViewModel {
  const summary = overview.summary
  const runChange = changeDetail(summary.agent_run_change_percent)
  const totalAgentErrors = summary.failed_agent_runs + summary.timed_out_agent_runs
  const totalNetworkErrors = summary.failed_network_runs + summary.timed_out_network_runs + summary.uncertain_network_runs
  const pricedPercent = summary.terminal_agent_runs > 0
    ? (summary.priced_agent_runs / summary.terminal_agent_runs) * 100
    : null

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
      detail: `${formatInteger(summary.successful_network_runs)} completed · ${formatInteger(summary.running_network_runs)} running · ${formatInteger(totalNetworkErrors)} errors`,
      direction: totalNetworkErrors > 0 ? 'down' : 'neutral',
      icon: Workflow,
      tone: 'bg-violet-500/10 text-violet-300',
    },
    {
      label: 'Runtime Cost',
      value: formatCost(summary.agent_run_cost_usd, summary.agent_run_cost_usd !== null),
      detail: pricedPercent === null
        ? 'No terminal Agent Runs'
        : summary.unknown_agent_run_cost_count > 0
          ? `${formatPercent(pricedPercent)} priced · ${formatInteger(summary.unknown_agent_run_cost_count)} without cost data`
          : 'All terminal Agent Runs priced',
      direction: 'neutral',
      icon: CircleDollarSign,
      tone: summary.unknown_agent_run_cost_count > 0 ? 'bg-amber-500/10 text-amber-300' : 'bg-blue-500/10 text-blue-400',
    },
    {
      label: 'Agent Run Success',
      value: formatPercent(summary.agent_run_success_rate),
      detail: summary.terminal_agent_runs === 0
        ? 'No terminal Agent Runs'
        : `${formatInteger(summary.successful_agent_runs)} successful · ${formatInteger(totalAgentErrors)} errors · ${formatInteger(summary.cancelled_agent_runs)} cancelled`,
      direction: totalAgentErrors > 0 ? 'down' : 'neutral',
      icon: ShieldCheck,
      tone: reliabilityTone(summary.agent_run_success_rate),
    },
    {
      label: 'Network Run Success',
      value: formatPercent(summary.network_run_success_rate),
      detail: summary.terminal_network_runs === 0
        ? 'No terminal Network Runs'
        : `${formatInteger(summary.successful_network_runs)} successful · ${formatInteger(totalNetworkErrors)} errors · ${formatInteger(summary.cancelled_network_runs)} cancelled`,
      direction: totalNetworkErrors > 0 ? 'down' : 'neutral',
      icon: CheckCircle2,
      tone: reliabilityTone(summary.network_run_success_rate),
    },
    {
      label: 'Average Run Time',
      value: '',
      detail: 'p95 is the duration not exceeded by 95% of terminal Runs',
      direction: 'neutral',
      icon: Clock3,
      tone: 'bg-slate-500/10 text-slate-300',
      comparison: {
        agent: {
          label: 'Agent Run',
          value: formatLatency(summary.avg_agent_run_duration_ms),
          detail: `p95 ${formatLatency(summary.p95_agent_run_duration_ms)}`,
          tone: 'text-blue-300',
        },
        network: {
          label: 'Network Run',
          value: formatLatency(summary.avg_network_run_duration_ms),
          detail: `p95 ${formatLatency(summary.p95_network_run_duration_ms)}`,
          tone: 'text-violet-300',
        },
      },
    },
  ]

  const series = overview.timeseries.map((point) => ({
    label: chartLabelFormatter.format(new Date(point.bucket_start)),
    bucketStart: point.bucket_start,
    agentRuns: point.agent_runs,
    agentSuccess: point.agent_run_success,
    agentErrors: point.agent_run_failed + point.agent_run_timed_out,
    agentRunning: point.agent_run_running,
    agentSuccessRate: point.agent_run_success_rate,
    networkRuns: point.network_runs,
    networkSuccess: point.network_run_success,
    networkErrors: point.network_run_failed + point.network_run_timed_out + point.network_run_uncertain,
    networkRunning: point.network_run_running,
    networkSuccessRate: point.network_run_success_rate,
    agentDurationMs: point.avg_agent_run_duration_ms,
    networkDurationMs: point.avg_network_run_duration_ms,
    costUsd: point.cost_usd,
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

  const agentReleases = overview.recent_releases.slice(0, 3).map((release) => ({
    ...release,
    environmentLabel: environmentLabel(release.environment),
    occurredLabel: safeDateLabel(release.promoted_at ?? release.created_at),
    description: release.release_notes?.trim() || 'No release description provided.',
  }))

  const networkReleases = overview.recent_network_releases.slice(0, 3).map((release) => ({
    ...release,
    environmentLabel: environmentLabel(release.environment),
    occurredLabel: safeDateLabel(release.created_at),
    description: release.change_description?.trim() || 'No release description provided.',
    activationLabel: release.activation_kind
      ? release.activation_kind[0].toUpperCase() + release.activation_kind.slice(1)
      : null,
  }))

  const changes = (overview.recent_changes ?? [])
    .slice(0, OVERVIEW_CHANGE_ROW_LIMIT)
    .map((change): DashboardChangeRow => ({
      id: change.id,
      resourceType: change.resource_type,
      resourceId: change.resource_id,
      resourceName: change.resource_name,
      resourceLabel: change.resource_type === 'agent' ? 'Agent' : 'Network',
      environmentLabel: environmentLabel(change.environment),
      actionLabel: actionLabel(change.action),
      versionLabel: change.revision !== null
        ? `Draft revision ${formatInteger(change.revision)}`
        : change.version
          ? `Version ${change.version}`
          : null,
      description: change.description?.trim() || (change.immutable ? 'No change description provided.' : 'Mutable Draft state updated.'),
      occurredLabel: safeDateLabel(change.occurred_at),
      occurredAt: change.occurred_at,
      immutable: change.immutable,
    }))

  const runs = [
    ...overview.recent_traces.map(agentRunRow),
    ...overview.recent_network_runs.map(networkRunRow),
  ]
    .sort((left, right) => new Date(right.startedAt ?? 0).getTime() - new Date(left.startedAt ?? 0).getTime())
    .slice(0, OVERVIEW_RECENT_ROW_LIMIT)

  const issueSummary = [
    summary.failed_agent_runs > 0 ? `${formatInteger(summary.failed_agent_runs)} Agent Runs failed` : null,
    summary.timed_out_agent_runs > 0 ? `${formatInteger(summary.timed_out_agent_runs)} Agent Runs timed out` : null,
    summary.failed_network_runs > 0 ? `${formatInteger(summary.failed_network_runs)} Network Runs failed` : null,
    summary.timed_out_network_runs > 0 ? `${formatInteger(summary.timed_out_network_runs)} Network Runs timed out` : null,
    summary.uncertain_network_runs > 0 ? `${formatInteger(summary.uncertain_network_runs)} Network Runs remain uncertain` : null,
  ].filter((value): value is string => Boolean(value))

  return {
    narrative: buildNarrative(overview),
    metrics,
    series,
    reliability: {
      agent: {
        label: 'Agent Runs',
        successRate: summary.agent_run_success_rate,
        errorRate: summary.agent_run_error_rate,
        totalRuns: summary.agent_runs,
        terminalRuns: summary.terminal_agent_runs,
        successful: summary.successful_agent_runs,
        completedWithIssues: summary.completed_with_issues_agent_runs,
        failed: summary.failed_agent_runs,
        timedOut: summary.timed_out_agent_runs,
        uncertain: 0,
        cancelled: summary.cancelled_agent_runs,
        running: summary.running_agent_runs,
        averageDurationLabel: formatLatency(summary.avg_agent_run_duration_ms),
        p95DurationLabel: formatLatency(summary.p95_agent_run_duration_ms),
      },
      network: {
        label: 'Network Runs',
        successRate: summary.network_run_success_rate,
        errorRate: summary.network_run_error_rate,
        totalRuns: summary.network_runs,
        terminalRuns: summary.terminal_network_runs,
        successful: summary.successful_network_runs,
        completedWithIssues: summary.completed_with_issues_network_runs,
        failed: summary.failed_network_runs,
        timedOut: summary.timed_out_network_runs,
        uncertain: summary.uncertain_network_runs,
        cancelled: summary.cancelled_network_runs,
        running: summary.running_network_runs,
        averageDurationLabel: formatLatency(summary.avg_network_run_duration_ms),
        p95DurationLabel: formatLatency(summary.p95_network_run_duration_ms),
      },
    },
    issues: {
      hasIssues: totalAgentErrors + totalNetworkErrors > 0,
      totalAgentErrors,
      totalNetworkErrors,
      summary: issueSummary,
      topAgents: overview.operational_issues.top_agent_failures,
      topNetworks: overview.operational_issues.top_network_failures,
      topCodes: overview.operational_issues.top_failure_codes,
      peakLabel: overview.operational_issues.failure_peak
        ? safeDateLabel(overview.operational_issues.failure_peak.bucket_start)
        : null,
      peakCount: overview.operational_issues.failure_peak?.failure_count ?? 0,
    },
    environments,
    environmentTotal,
    agentReleases,
    networkReleases,
    changes,
    runs,
    assets: {
      activeAgents: formatInteger(summary.active_agents),
      draftAgents: formatInteger(distribution.draft),
      stagingAgents: formatInteger(distribution.staging),
      productionAgents: formatInteger(distribution.production),
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
