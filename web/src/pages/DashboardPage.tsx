import { useEffect, useMemo, useState } from 'react'
import type { ChangeEvent, KeyboardEvent, ReactNode } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { useQueryClient } from '@tanstack/react-query'
import type { LucideIcon } from 'lucide-react'
import {
  Activity,
  AlertCircle,
  AlertTriangle,
  ArrowRight,
  Bot,
  CheckCircle2,
  Database,
  FileText,
  GitBranch,
  Layers3,
  Network,
  RefreshCw,
  Sparkles,
  Workflow,
  Wrench,
  XCircle,
} from 'lucide-react'
import {
  adaptProjectOverview,
  formatCost,
  formatPercent,
  rangeLabel,
} from '@/features/dashboard/adapters'
import type {
  DashboardAgentReleaseRow,
  DashboardMetric,
  DashboardNetworkReleaseRow,
  DashboardReliabilityGroup,
  DashboardRunRow,
  DashboardViewModel,
} from '@/features/dashboard/adapters'
import { useProjectOverview } from '@/features/dashboard/hooks'
import type { DashboardEnvironment, DashboardRangePreset } from '@/features/dashboard/types'
import { orgProjectPath } from '@/lib/constants/routes'

const ENVIRONMENTS: Array<{ value: DashboardEnvironment; label: string; tone: string; dot: string }> = [
  { value: 'all', label: 'All', tone: 'border-slate-600/70 bg-slate-800/60 text-slate-100', dot: 'bg-slate-300' },
  { value: 'draft', label: 'Draft', tone: 'border-blue-500/35 bg-blue-500/10 text-blue-300', dot: 'bg-blue-400' },
  { value: 'staging', label: 'Staging', tone: 'border-amber-500/35 bg-amber-500/10 text-amber-300', dot: 'bg-amber-400' },
  { value: 'production', label: 'Production', tone: 'border-emerald-500/35 bg-emerald-500/10 text-emerald-300', dot: 'bg-emerald-400' },
]

const RANGES: DashboardRangePreset[] = ['24h', '7d', '30d']
const CHART_WIDTH = 760
const CHART_HEIGHT = 170
const CHART_PADDING = 20

function Panel({ children, className = '' }: { children: ReactNode; className?: string }) {
  return <section className={`rounded-xl border border-border/90 bg-surface/70 shadow-lg shadow-black/5 ${className}`}>{children}</section>
}

function PanelHeader({ title, subtitle, action }: { title: string; subtitle?: string; action?: ReactNode }) {
  return (
    <div className="flex items-start justify-between gap-3 px-5 pb-3 pt-4">
      <div className="min-w-0">
        <div className="flex items-center gap-1.5">
          <h2 className="truncate text-sm font-semibold text-white">{title}</h2>
          <AlertCircle className="h-3.5 w-3.5 shrink-0 text-muted" />
        </div>
        {subtitle && <p className="mt-1 text-xs text-muted">{subtitle}</p>}
      </div>
      {action}
    </div>
  )
}

function StorySectionHeader({ title, description }: { title: string; description: string }) {
  return (
    <div className="flex flex-col gap-1 pt-2 sm:flex-row sm:items-end sm:justify-between">
      <div>
        <h2 className="text-sm font-semibold text-white">{title}</h2>
        <p className="mt-1 text-xs text-muted">{description}</p>
      </div>
    </div>
  )
}

function MiniLink({ label, onClick }: { label: string; onClick?: () => void }) {
  return (
    <button type="button" onClick={onClick} className="inline-flex items-center gap-1 text-xs font-medium text-primary-light transition-colors hover:text-white">
      {label}<ArrowRight className="h-3 w-3" />
    </button>
  )
}

function MetricCard({ metric }: { metric: DashboardMetric }) {
  const Icon = metric.icon
  const detailTone = metric.direction === 'up' ? 'text-emerald-300' : metric.direction === 'down' ? 'text-red-300' : 'text-muted'
  return (
    <Panel className="min-h-[128px] p-4">
      <div className="flex h-full flex-col justify-between gap-5">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <p className="truncate text-xs font-medium uppercase tracking-[0.14em] text-muted">{metric.label}</p>
            <p className="mt-3 text-2xl font-semibold leading-none tracking-tight text-white">{metric.value}</p>
          </div>
          <div className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-border bg-background/70 ${metric.tone}`}><Icon className="h-5 w-5" /></div>
        </div>
        <p className={`min-h-4 text-xs leading-5 ${detailTone}`}>{metric.detail ?? 'No terminal Runs in this interval'}</p>
      </div>
    </Panel>
  )
}

function SkeletonPanel({ className = '' }: { className?: string }) {
  return <Panel className={`animate-pulse p-5 ${className}`}><div className="h-3 w-28 rounded-full bg-white/[0.07]" /><div className="mt-5 h-20 rounded-xl bg-white/[0.05]" /></Panel>
}

export function DashboardLoadingState() {
  return (
    <div aria-label="Loading project overview" className="space-y-4">
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-6">{Array.from({ length: 6 }, (_, index) => <SkeletonPanel key={index} className="min-h-[128px]" />)}</div>
      <div className="grid grid-cols-1 gap-4 xl:grid-cols-12"><SkeletonPanel className="min-h-[330px] xl:col-span-8" /><SkeletonPanel className="min-h-[330px] xl:col-span-4" /></div>
      <div className="grid grid-cols-1 gap-4 xl:grid-cols-2"><SkeletonPanel className="min-h-[260px]" /><SkeletonPanel className="min-h-[260px]" /></div>
      <div className="grid grid-cols-1 gap-4 xl:grid-cols-3"><SkeletonPanel className="min-h-[250px]" /><SkeletonPanel className="min-h-[250px]" /><SkeletonPanel className="min-h-[250px]" /></div>
    </div>
  )
}

export function DashboardErrorState({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <Panel className="flex min-h-[280px] flex-col items-center justify-center p-8 text-center">
      <XCircle className="h-10 w-10 text-red-300" />
      <h2 className="mt-3 text-base font-semibold text-white">Overview unavailable</h2>
      <p className="mt-1 max-w-lg text-sm text-muted">{message}</p>
      <button type="button" onClick={onRetry} className="mt-5 inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-primary-dark"><RefreshCw className="h-4 w-4" />Retry</button>
    </Panel>
  )
}

function EmptyExecutionState() {
  return (
    <Panel className="flex min-h-[220px] flex-col items-center justify-center p-7 text-center">
      <Activity className="h-9 w-9 text-muted" />
      <h2 className="mt-3 text-sm font-semibold text-white">No Agent Runs or Network Runs in this interval</h2>
      <p className="mt-1 max-w-lg text-xs leading-5 text-muted">The selected environment and time range returned no runtime activity. Changes and current Project state remain available below.</p>
    </Panel>
  )
}

function sum(values: number[]) {
  return values.reduce((total, value) => total + value, 0)
}

function getTickIndexes(length: number, maxTicks = 5): number[] {
  if (length <= 0) return []
  if (length <= maxTicks) return Array.from({ length }, (_, index) => index)
  return Array.from(new Set(Array.from({ length: maxTicks }, (_, index) => Math.round((index * (length - 1)) / (maxTicks - 1)))))
}

function pointX(index: number, length: number): number {
  if (length <= 1) return CHART_WIDTH / 2
  return CHART_PADDING + (index / (length - 1)) * (CHART_WIDTH - CHART_PADDING * 2)
}

function pointY(value: number, maxValue: number): number {
  return CHART_HEIGHT - CHART_PADDING - (value / Math.max(maxValue, 1)) * (CHART_HEIGHT - CHART_PADDING * 2)
}

function buildPath(values: number[], maxValue: number): string {
  if (values.length === 0) return ''
  return values.map((value, index) => `${index === 0 ? 'M' : 'L'} ${pointX(index, values.length).toFixed(2)} ${pointY(value, maxValue).toFixed(2)}`).join(' ')
}

function ChartTicks({ model }: { model: DashboardViewModel }) {
  const ticks = getTickIndexes(model.series.length)
  return (
    <div className="absolute bottom-0 left-0 right-0 flex justify-between overflow-hidden text-[10px] text-muted">
      {ticks.map((index) => <span key={`${model.series[index]?.label}-${index}`} className="max-w-[92px] truncate">{model.series[index]?.label}</span>)}
    </div>
  )
}

function ChartGrid() {
  return <div className="absolute bottom-7 left-0 right-0 top-0 flex flex-col justify-between">{[0, 1, 2, 3].map((line) => <div key={line} className="border-t border-border/70" />)}</div>
}

function RunActivityChart({ model }: { model: DashboardViewModel }) {
  const [activeIndex, setActiveIndex] = useState(() => Math.max(model.series.length - 1, 0))
  const agentValues = model.series.map((point) => point.agentRuns)
  const networkValues = model.series.map((point) => point.networkRuns)
  const maxValue = Math.max(...agentValues, ...networkValues, 1)
  const agentPath = buildPath(agentValues, maxValue)
  const networkPath = buildPath(networkValues, maxValue)
  const activePoint = model.series[activeIndex] ?? null

  useEffect(() => {
    setActiveIndex(Math.max(model.series.length - 1, 0))
  }, [model.series.length])

  return (
    <Panel className="h-full min-h-[330px]">
      <PanelHeader
        title="Run Activity"
        subtitle="When the selected Project activity happened"
        action={<span className="rounded-full border border-border bg-background/70 px-2.5 py-1 text-xs text-muted">{sum(agentValues).toLocaleString()} Agent · {sum(networkValues).toLocaleString()} Network</span>}
      />
      <div className="px-5 pb-5">
        <div className="mb-3 flex flex-wrap items-center gap-4 text-xs text-muted">
          <span className="flex items-center gap-1.5"><span className="h-0.5 w-4 rounded bg-blue-500" />Agent Runs</span>
          <span className="flex items-center gap-1.5"><span className="h-0.5 w-4 rounded bg-violet-500" />Network Runs</span>
          <span className="flex items-center gap-1.5"><span className="h-2 w-2 rounded-full bg-red-400" />Errors in bucket</span>
        </div>
        <div className="relative h-[190px]">
          <ChartGrid />
          <svg className="absolute inset-x-0 top-0 h-[166px] w-full" viewBox={`0 0 ${CHART_WIDTH} ${CHART_HEIGHT}`} preserveAspectRatio="none" aria-label="Agent Run and Network Run activity">
            {agentPath && <path d={agentPath} fill="none" stroke="#3b82f6" strokeWidth="2" vectorEffect="non-scaling-stroke" />}
            {networkPath && <path d={networkPath} fill="none" stroke="#8b5cf6" strokeWidth="2" strokeDasharray="5 4" vectorEffect="non-scaling-stroke" />}
            {model.series.map((point, index) => {
              const x = pointX(index, model.series.length)
              const hasErrors = point.agentErrors + point.networkErrors > 0
              return (
                <g key={point.bucketStart} onMouseEnter={() => setActiveIndex(index)} onClick={() => setActiveIndex(index)} className="cursor-pointer">
                  <rect x={Math.max(x - 11, 0)} y={0} width={22} height={CHART_HEIGHT} fill="transparent" />
                  {activeIndex === index && <line x1={x} x2={x} y1={CHART_PADDING} y2={CHART_HEIGHT - CHART_PADDING} stroke="#64748b" strokeDasharray="3 4" strokeWidth="1" />}
                  <circle cx={x} cy={pointY(point.agentRuns, maxValue)} r={activeIndex === index ? 4 : 2.5} fill="#3b82f6" />
                  <circle cx={x} cy={pointY(point.networkRuns, maxValue)} r={activeIndex === index ? 4 : 2.5} fill="#8b5cf6" />
                  {hasErrors && <circle cx={x} cy={CHART_HEIGHT - 8} r={3} fill="#f87171" />}
                </g>
              )
            })}
          </svg>
          <ChartTicks model={model} />
        </div>
        {activePoint && (
          <div className="grid gap-2 rounded-xl border border-border/80 bg-background/45 p-3 sm:grid-cols-2">
            <div>
              <p className="text-[10px] font-medium uppercase tracking-wide text-muted">{activePoint.label} · Agent Runs</p>
              <div className="mt-2 grid grid-cols-4 gap-2 text-xs"><span><b className="block text-white">{activePoint.agentRuns}</b><span className="text-muted">Runs</span></span><span><b className="block text-emerald-300">{activePoint.agentSuccess}</b><span className="text-muted">Success</span></span><span><b className="block text-red-300">{activePoint.agentErrors}</b><span className="text-muted">Errors</span></span><span><b className="block text-white">{formatCost(activePoint.costUsd, activePoint.costUsd !== null)}</b><span className="text-muted">Cost</span></span></div>
            </div>
            <div>
              <p className="text-[10px] font-medium uppercase tracking-wide text-muted">{activePoint.label} · Network Runs</p>
              <div className="mt-2 grid grid-cols-4 gap-2 text-xs"><span><b className="block text-white">{activePoint.networkRuns}</b><span className="text-muted">Runs</span></span><span><b className="block text-emerald-300">{activePoint.networkSuccess}</b><span className="text-muted">Success</span></span><span><b className="block text-red-300">{activePoint.networkErrors}</b><span className="text-muted">Errors</span></span><span><b className="block text-white">{formatPercent(activePoint.networkSuccessRate)}</b><span className="text-muted">Success rate</span></span></div>
            </div>
          </div>
        )}
      </div>
    </Panel>
  )
}

function ReliabilityDistribution({ group }: { group: DashboardReliabilityGroup }) {
  const denominator = Math.max(group.terminalRuns, 1)
  const errors = group.failed + group.timedOut + group.uncertain
  const segments = [
    { key: 'success', value: group.successful, className: 'bg-emerald-500', label: 'Completed' },
    { key: 'issues', value: group.completedWithIssues, className: 'bg-amber-400', label: 'With issues' },
    { key: 'errors', value: errors, className: 'bg-red-500', label: 'Errors' },
    { key: 'cancelled', value: group.cancelled, className: 'bg-slate-500', label: 'Cancelled' },
  ]
  return (
    <div>
      <div className="flex h-2.5 overflow-hidden rounded-full bg-background ring-1 ring-border/80">
        {group.terminalRuns === 0 ? <span className="h-full w-full bg-muted/20" /> : segments.filter((segment) => segment.value > 0).map((segment) => <span key={segment.key} title={`${segment.label}: ${segment.value}`} className={segment.className} style={{ width: `${(segment.value / denominator) * 100}%` }} />)}
      </div>
      <div className="mt-2 flex flex-wrap gap-x-3 gap-y-1 text-[10px] text-muted">{segments.map((segment) => <span key={segment.key} className="flex items-center gap-1"><span className={`h-1.5 w-1.5 rounded-full ${segment.className}`} />{segment.label} {segment.value}</span>)}</div>
    </div>
  )
}

function ReliabilityGroupView({ group }: { group: DashboardReliabilityGroup }) {
  const errors = group.failed + group.timedOut + group.uncertain
  return (
    <div className="rounded-xl border border-border/80 bg-background/45 p-3">
      <div className="flex items-start justify-between gap-3">
        <div><p className="text-xs font-semibold text-white">{group.label}</p><p className="mt-1 text-[10px] text-muted">{group.terminalRuns} terminal · {group.running} running</p></div>
        <div className="text-right"><p className={`text-lg font-semibold ${group.successRate !== null && group.successRate >= 99 ? 'text-emerald-300' : errors > 0 ? 'text-amber-300' : 'text-white'}`}>{formatPercent(group.successRate)}</p><p className="text-[10px] text-muted">success</p></div>
      </div>
      <div className="mt-3"><ReliabilityDistribution group={group} /></div>
      <div className="mt-3 grid grid-cols-2 gap-x-4 gap-y-2 text-xs">
        <span className="flex justify-between gap-2 text-muted">Errors <b className="text-red-300">{errors}</b></span>
        <span className="flex justify-between gap-2 text-muted">Error rate <b className="text-white">{formatPercent(group.errorRate)}</b></span>
        <span className="flex justify-between gap-2 text-muted">Average <b className="text-white">{group.averageDurationLabel}</b></span>
        <span className="flex justify-between gap-2 text-muted">p95 <b className="text-white">{group.p95DurationLabel}</b></span>
      </div>
    </div>
  )
}

function ReliabilityPanel({ model }: { model: DashboardViewModel }) {
  return (
    <Panel className="h-full min-h-[330px]">
      <PanelHeader title="Reliability & Performance" subtitle="Whether the Runs in this period completed correctly" />
      <div className="space-y-3 px-5 pb-5"><ReliabilityGroupView group={model.reliability.agent} /><ReliabilityGroupView group={model.reliability.network} /></div>
    </Panel>
  )
}

function OperationalIssues({ model }: { model: DashboardViewModel }) {
  if (!model.issues.hasIssues) return null
  return (
    <Panel className="border-red-500/20 bg-red-500/[0.025]">
      <PanelHeader title="Operational Issues" subtitle="Errors detected in the selected period" action={<AlertTriangle className="h-4 w-4 text-red-300" />} />
      <div className="grid gap-4 px-5 pb-5 xl:grid-cols-12">
        <div className="xl:col-span-4">
          <p className="text-[10px] font-medium uppercase tracking-wide text-muted">What happened</p>
          <div className="mt-2 space-y-2">{model.issues.summary.map((item) => <div key={item} className="rounded-lg border border-red-500/15 bg-background/45 px-3 py-2 text-xs text-red-200">{item}</div>)}</div>
          {model.issues.peakLabel && <p className="mt-3 text-xs text-muted">Failure peak: <span className="font-medium text-white">{model.issues.peakLabel}</span> · {model.issues.peakCount} errors</p>}
        </div>
        <div className="xl:col-span-3">
          <p className="text-[10px] font-medium uppercase tracking-wide text-muted">Most affected Agents</p>
          <div className="mt-2 space-y-2">{model.issues.topAgents.length === 0 ? <p className="text-xs text-muted">No Agent failures.</p> : model.issues.topAgents.map((item) => <div key={`${item.entity_id}-${item.name}`} className="flex items-center justify-between gap-3 rounded-lg border border-border/70 bg-background/45 px-3 py-2 text-xs"><span className="truncate text-slate-200">{item.name}</span><b className="text-red-300">{item.failure_count}</b></div>)}</div>
        </div>
        <div className="xl:col-span-3">
          <p className="text-[10px] font-medium uppercase tracking-wide text-muted">Most affected Networks</p>
          <div className="mt-2 space-y-2">{model.issues.topNetworks.length === 0 ? <p className="text-xs text-muted">No Network failures.</p> : model.issues.topNetworks.map((item) => <div key={`${item.entity_id}-${item.name}`} className="flex items-center justify-between gap-3 rounded-lg border border-border/70 bg-background/45 px-3 py-2 text-xs"><span className="truncate text-slate-200">{item.name}</span><b className="text-red-300">{item.failure_count}</b></div>)}</div>
        </div>
        <div className="xl:col-span-2">
          <p className="text-[10px] font-medium uppercase tracking-wide text-muted">Failure codes</p>
          <div className="mt-2 space-y-2">{model.issues.topCodes.map((item) => <div key={item.code} className="rounded-lg border border-border/70 bg-background/45 px-3 py-2"><p className="truncate font-mono text-[10px] text-slate-200">{item.code}</p><p className="mt-1 text-xs font-semibold text-red-300">{item.failure_count}</p></div>)}</div>
        </div>
      </div>
    </Panel>
  )
}

function EnvironmentBadge({ value }: { value: string }) {
  const normalized = value.toLowerCase()
  const classes = normalized === 'production' ? 'border-emerald-500/40 bg-emerald-500/10 text-emerald-300' : normalized === 'staging' ? 'border-amber-500/40 bg-amber-500/10 text-amber-300' : 'border-blue-500/40 bg-blue-500/10 text-blue-300'
  return <span className={`inline-flex rounded-md border px-2 py-0.5 text-xs font-medium ${classes}`}>{value}</span>
}

function StatusBadge({ value }: { value: string }) {
  const classes = value === 'Completed' ? 'border-emerald-500/40 bg-emerald-500/10 text-emerald-300' : value === 'Running' || value === 'Queued' ? 'border-blue-500/40 bg-blue-500/10 text-blue-300' : value === 'Completed with issues' || value === 'Uncertain' ? 'border-amber-500/40 bg-amber-500/10 text-amber-300' : 'border-red-500/40 bg-red-500/10 text-red-300'
  return <span className={`inline-flex rounded-md border px-2 py-0.5 text-xs font-medium ${classes}`}>{value}</span>
}

function AgentReleaseItem({ release, onOpen }: { release: DashboardAgentReleaseRow; onOpen: () => void }) {
  return (
    <button type="button" onClick={onOpen} className="w-full rounded-xl border border-border/80 bg-background/45 p-3 text-left transition-colors hover:border-primary/25 hover:bg-background/75">
      <div className="flex items-start gap-3"><span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl border border-border bg-surface text-primary-light"><Bot className="h-4 w-4" /></span><span className="min-w-0 flex-1"><span className="flex flex-wrap items-center gap-2"><b className="truncate text-sm text-white">{release.agent_name}</b><EnvironmentBadge value={release.environmentLabel} /></span><span className="mt-1 block text-xs text-muted">Version {release.version} · {release.occurredLabel}</span><span className="mt-2 block line-clamp-2 text-xs leading-5 text-slate-300">{release.description}</span></span></div>
    </button>
  )
}

function NetworkReleaseItem({ release, onOpen }: { release: DashboardNetworkReleaseRow; onOpen: () => void }) {
  return (
    <button type="button" onClick={onOpen} className="w-full rounded-xl border border-border/80 bg-background/45 p-3 text-left transition-colors hover:border-primary/25 hover:bg-background/75">
      <div className="flex items-start gap-3"><span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl border border-border bg-surface text-violet-300"><Network className="h-4 w-4" /></span><span className="min-w-0 flex-1"><span className="flex flex-wrap items-center gap-2"><b className="truncate text-sm text-white">{release.network_name}</b><EnvironmentBadge value={release.environmentLabel} /></span><span className="mt-1 block text-xs text-muted">Version {release.version} · {release.agent_count} Agents · {release.occurredLabel}</span><span className="mt-2 block line-clamp-2 text-xs leading-5 text-slate-300">{release.description}</span>{release.activationLabel && <span className="mt-2 inline-flex rounded-md border border-border bg-surface px-2 py-0.5 text-[10px] text-muted">{release.activationLabel}</span>}</span></div>
    </button>
  )
}

function ChangesInPeriod({ model, environment, onNavigate }: { model: DashboardViewModel; environment: DashboardEnvironment; onNavigate: (segment: string) => void }) {
  const draftMessage = environment === 'draft' ? 'Draft changes are mutable and are not presented as releases.' : 'No releases in this period.'
  return (
    <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
      <Panel className="min-h-[250px]">
        <PanelHeader title="Agent Releases" subtitle="Immutable Agent changes in the selected period" />
        <div className="space-y-2 px-5 pb-5">{model.agentReleases.length === 0 ? <p className="py-8 text-center text-sm text-muted">{draftMessage}</p> : model.agentReleases.map((release) => <AgentReleaseItem key={release.id} release={release} onOpen={() => onNavigate('agents')} />)}<MiniLink label="View all Agent releases" onClick={() => onNavigate('agents')} /></div>
      </Panel>
      <Panel className="min-h-[250px]">
        <PanelHeader title="Network Releases" subtitle="Immutable Network changes in the selected period" />
        <div className="space-y-2 px-5 pb-5">{model.networkReleases.length === 0 ? <p className="py-8 text-center text-sm text-muted">{draftMessage}</p> : model.networkReleases.map((release) => <NetworkReleaseItem key={release.id} release={release} onOpen={() => onNavigate(`networks/${release.network_id}`)} />)}<MiniLink label="View all Networks" onClick={() => onNavigate('networks')} /></div>
      </Panel>
    </div>
  )
}

function RuntimeAssets({ model }: { model: DashboardViewModel }) {
  const rows = [
    ['Active Agents', model.assets.activeAgents],
    ['Draft Agents', model.assets.draftAgents],
    ['Staging Agents', model.assets.stagingAgents],
    ['Production Agents', model.assets.productionAgents],
    ['Networks', model.assets.networks],
    ['Networks in Staging', model.assets.stagingNetworks],
    ['Networks in Production', model.assets.productionNetworks],
  ]
  return (
    <Panel className="h-full min-h-[250px]">
      <PanelHeader title="Runtime Assets" subtitle="Current deployable state" />
      <div className="space-y-1 px-5 pb-5">{rows.map(([label, value]) => <div key={label} className="flex items-center justify-between rounded-lg px-1 py-2 text-sm"><span className="text-slate-200">{label}</span><span className="font-semibold text-white">{value}</span></div>)}</div>
    </Panel>
  )
}

function KnowledgeBase({ model, onOpen }: { model: DashboardViewModel; onOpen: () => void }) {
  const entries: Array<{ label: string; value: string; icon: LucideIcon; tone: string }> = [
    { label: 'Collections', value: model.knowledge.collections, icon: Layers3, tone: 'text-blue-300' },
    { label: 'Documents', value: model.knowledge.documents, icon: FileText, tone: 'text-blue-300' },
    { label: 'Indexed', value: model.knowledge.indexed, icon: CheckCircle2, tone: 'text-emerald-300' },
    { label: 'Pending', value: model.knowledge.pending, icon: Sparkles, tone: 'text-amber-300' },
    { label: 'Failed', value: model.knowledge.failed, icon: XCircle, tone: 'text-red-300' },
    { label: 'Storage', value: model.knowledge.storage, icon: Database, tone: 'text-violet-300' },
  ]
  return (
    <Panel className="h-full min-h-[250px]">
      <PanelHeader title="Knowledge" subtitle="Current Project-wide state" />
      <div className="grid grid-cols-2 gap-2 px-5 pb-5">{entries.map((entry) => { const Icon = entry.icon; return <div key={entry.label} className="rounded-xl border border-border/80 bg-background/50 p-3"><div className="flex items-center gap-2"><Icon className={`h-4 w-4 ${entry.tone}`} /><p className="truncate text-xs text-muted">{entry.label}</p></div><p className={`mt-2 text-lg font-semibold ${entry.tone}`}>{entry.value}</p></div> })}<div className="col-span-2 pt-1"><MiniLink label="Open Knowledge" onClick={onOpen} /></div></div>
    </Panel>
  )
}

function ToolsIntegrations({ model, onOpen }: { model: DashboardViewModel; onOpen: () => void }) {
  const items = [
    { label: 'Tools', value: model.tools.total, icon: Wrench, tone: 'text-blue-300' },
    { label: 'Active', value: model.tools.active, icon: CheckCircle2, tone: 'text-emerald-300' },
    { label: 'Inactive', value: model.tools.inactive, icon: Workflow, tone: 'text-slate-300' },
    { label: 'Recent failures', value: String(model.tools.recentFailures), icon: XCircle, tone: model.tools.recentFailures > 0 ? 'text-red-300' : 'text-slate-300' },
  ]
  return (
    <Panel className="h-full min-h-[250px]">
      <PanelHeader title="Tools" subtitle="Current Project-wide state" />
      <div className="space-y-1 px-5 pb-5">{items.map((item) => { const Icon = item.icon; return <div key={item.label} className="flex items-center justify-between gap-3 rounded-lg px-1 py-2.5 text-sm"><span className="flex items-center gap-2 text-slate-200"><Icon className={`h-4 w-4 ${item.tone}`} />{item.label}</span><span className={`font-semibold ${item.tone}`}>{item.value}</span></div> })}<div className="pt-2"><MiniLink label="Manage Tools" onClick={onOpen} /></div></div>
    </Panel>
  )
}

function keyboardActivate(event: KeyboardEvent<HTMLElement>, action: () => void) {
  if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); action() }
}

function RecentRuns({ model, onOpen }: { model: DashboardViewModel; onOpen: (run: DashboardRunRow) => void }) {
  return (
    <Panel className="overflow-hidden">
      <PanelHeader title="Recent Runs" subtitle="The three latest primary executions in the selected period" />
      <div className="px-5 pb-5">
        {model.runs.length === 0 ? <p className="py-8 text-center text-sm text-muted">No Runs in this interval.</p> : (
          <div className="space-y-2">
            <div className="hidden grid-cols-[110px_minmax(220px,1fr)_100px_125px_165px_90px_155px] gap-3 px-3 text-[10px] font-medium uppercase tracking-wide text-muted xl:grid"><span>Type</span><span>Name</span><span>Environment</span><span>Status</span><span>Started</span><span className="text-right">Duration</span><span className="text-right">Cost</span></div>
            {model.runs.map((run) => {
              const open = () => onOpen(run)
              return (
                <div key={`${run.kind}-${run.id}`} role="link" tabIndex={0} onClick={open} onKeyDown={(event) => keyboardActivate(event, open)} className="grid cursor-pointer gap-3 rounded-xl border border-border/80 bg-background/45 p-3 outline-none transition-colors hover:border-primary/25 hover:bg-background/75 focus:ring-1 focus:ring-primary/60 xl:grid-cols-[110px_minmax(220px,1fr)_100px_125px_165px_90px_155px] xl:items-center">
                  <div><span className="rounded-md border border-border bg-surface px-2 py-0.5 text-xs font-medium text-slate-200">{run.typeLabel}</span></div>
                  <div className="min-w-0"><p className="truncate text-sm font-semibold text-white">{run.title}</p><p className="mt-1 truncate text-xs text-muted">{run.sourceLabel}</p></div>
                  <div><EnvironmentBadge value={run.environmentLabel} /></div>
                  <div><StatusBadge value={run.statusLabel} /></div>
                  <p className="text-xs text-muted">{run.timeLabel}</p>
                  <p className="text-xs font-medium text-white xl:text-right">{run.durationLabel}</p>
                  <div className="min-w-0 xl:text-right"><p className="truncate text-xs font-medium text-white">{run.costLabel}</p>{run.costDetail && <p className="mt-1 truncate text-[10px] text-amber-300" title={run.costDetail}>{run.costDetail}</p>}</div>
                </div>
              )
            })}
          </div>
        )}
      </div>
    </Panel>
  )
}

export function DashboardDataState({ model, environment = 'all', onNavigate, onOpenRun }: { model: DashboardViewModel; environment?: DashboardEnvironment; onNavigate: (segment: string) => void; onOpenRun: (run: DashboardRunRow) => void }) {
  return (
    <div className="space-y-5">
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-6">{model.metrics.map((metric) => <MetricCard key={metric.label} metric={metric} />)}</div>

      <StorySectionHeader title="What happened" description="Volume, reliability, performance, and cost in the selected period." />
      {model.isExecutionEmpty ? <EmptyExecutionState /> : <div className="grid grid-cols-1 gap-4 xl:grid-cols-12"><div className="xl:col-span-8"><RunActivityChart model={model} /></div><div className="xl:col-span-4"><ReliabilityPanel model={model} /></div></div>}
      <OperationalIssues model={model} />

      <StorySectionHeader title="Changes in this period" description="Immutable Agent and Network releases that may explain changes in runtime behavior." />
      <ChangesInPeriod model={model} environment={environment} onNavigate={onNavigate} />

      <StorySectionHeader title="Current Project State" description="Current deployable resources. Knowledge and Tools are Project-wide, not historical environment snapshots." />
      <div className="grid grid-cols-1 gap-4 xl:grid-cols-3"><RuntimeAssets model={model} /><KnowledgeBase model={model} onOpen={() => onNavigate('knowledge')} /><ToolsIntegrations model={model} onOpen={() => onNavigate('tools')} /></div>

      <StorySectionHeader title="Latest executions" description="A compact operational handoff to the detailed Agent or Network workspace." />
      <RecentRuns model={model} onOpen={onOpenRun} />
    </div>
  )
}

export default function DashboardPage() {
  const { organizationId, projectId } = useParams<{ organizationId: string; projectId: string }>()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [environment, setEnvironment] = useState<DashboardEnvironment>('all')
  const [range, setRange] = useState<DashboardRangePreset>('24h')
  const [windowAnchor, setWindowAnchor] = useState(() => new Date())
  const query = useProjectOverview({ projectId, environment, range, now: windowAnchor })
  const model = useMemo(() => query.data ? adaptProjectOverview(query.data) : null, [query.data])

  useEffect(() => { const interval = window.setInterval(() => setWindowAnchor(new Date()), 60_000); return () => window.clearInterval(interval) }, [])
  useEffect(() => queryClient.getMutationCache().subscribe((event: any) => { if (event.type === 'updated' && event.mutation.state.status === 'success') setWindowAnchor(new Date()) }), [queryClient])

  const goTo = (segment: string) => {
    if (!projectId) return
    const parts = segment.split('/').filter(Boolean)
    navigate(orgProjectPath(organizationId, projectId, ...parts))
  }

  const openRun = (run: DashboardRunRow) => {
    if (!projectId) return
    if (run.kind === 'network' && run.networkId) {
      navigate(`${orgProjectPath(organizationId, projectId, 'networks', run.networkId)}?run=${encodeURIComponent(run.id)}`)
      return
    }
    if (run.agentId) {
      navigate(`${orgProjectPath(organizationId, projectId, 'agents', run.agentId, 'playground')}?run=${encodeURIComponent(run.id)}`)
      return
    }
    goTo('traces')
  }

  return (
    <div className="h-full overflow-y-auto scrollbar-thin">
      <div className="min-w-0 space-y-5 pb-6 pr-1">
        <header className="rounded-xl border border-border/80 bg-surface/50 p-5">
          <div className="flex flex-col gap-5 xl:flex-row xl:items-start xl:justify-between">
            <div className="min-w-0">
              <div className="flex items-center gap-2"><GitBranch className="h-4 w-4 text-primary-light" /><h1 className="text-2xl font-semibold tracking-tight text-white">Project Overview</h1></div>
              <p className="mt-2 max-w-4xl text-sm leading-6 text-slate-300" aria-live="polite">{model?.narrative ?? 'Operational health across Agent Runs, Network Runs, releases, Knowledge, and Tools.'}</p>
              {model && <p className="mt-2 text-xs text-muted">Interval: {model.intervalLabel} · {model.timezoneLabel} · Last refreshed {model.generatedAtLabel}</p>}
            </div>
            <div className="flex flex-col gap-3 lg:flex-row lg:items-center xl:justify-end">
              <label className="sr-only" htmlFor="dashboard-range">Dashboard range</label>
              <select id="dashboard-range" value={range} onChange={(event: ChangeEvent<HTMLSelectElement>) => setRange(event.target.value as DashboardRangePreset)} className="h-9 rounded-lg border border-border bg-background/70 px-3 text-sm text-slate-300 outline-none transition-colors focus:ring-1 focus:ring-primary/60">{RANGES.map((item) => <option key={item} value={item}>{rangeLabel(item)}</option>)}</select>
              <div className="flex max-w-full overflow-x-auto rounded-lg border border-border bg-background/50 p-1 scrollbar-thin">{ENVIRONMENTS.map((item) => <button type="button" key={item.value} onClick={() => setEnvironment(item.value)} aria-pressed={environment === item.value} className={`flex h-7 items-center gap-1.5 whitespace-nowrap rounded-md border px-3 text-xs font-medium transition-colors ${environment === item.value ? item.tone : 'border-transparent text-muted hover:bg-surface hover:text-white'}`}><span className={`h-1.5 w-1.5 rounded-full ${item.dot}`} />{item.label}</button>)}</div>
              <button type="button" onClick={() => setWindowAnchor(new Date())} disabled={query.isFetching} className="inline-flex h-9 items-center justify-center gap-1.5 rounded-lg border border-border bg-background/70 px-3 text-sm font-medium text-slate-300 transition-colors hover:border-primary/35 hover:text-white disabled:opacity-50"><RefreshCw className={`h-3.5 w-3.5 ${query.isFetching ? 'animate-spin' : ''}`} />Refresh</button>
            </div>
          </div>
        </header>
        {!projectId ? <DashboardErrorState message="Project identifier is missing from the route." onRetry={() => window.location.reload()} /> : query.isPending ? <DashboardLoadingState /> : query.isError ? <DashboardErrorState message={query.error instanceof Error ? query.error.message : 'Unable to load project overview.'} onRetry={() => query.refetch()} /> : model ? <DashboardDataState model={model} environment={environment} onNavigate={goTo} onOpenRun={openRun} /> : <DashboardErrorState message="The overview endpoint returned no data." onRetry={() => query.refetch()} />}
      </div>
    </div>
  )
}
