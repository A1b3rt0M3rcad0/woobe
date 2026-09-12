import { useEffect, useMemo, useState } from 'react'
import type { ChangeEvent, KeyboardEvent, ReactNode } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
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
  environmentLabel,
  formatCost,
  formatPercent,
  rangeLabel,
} from '@/features/dashboard/adapters'
import type {
  DashboardChangeRow,
  DashboardMetric,
  DashboardReliabilityGroup,
  DashboardRunRow,
  DashboardSeriesPoint,
  DashboardViewModel,
} from '@/features/dashboard/adapters'
import { useProjectOverview } from '@/features/dashboard/hooks'
import type { DashboardEnvironment, DashboardRangePreset } from '@/features/dashboard/types'
import { workspaceProjectPath } from '@/lib/constants/routes'

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

function PanelHeader({ title, subtitle: _subtitle, action }: { title: string; subtitle?: string; action?: ReactNode }) {
  return (
    <div className="flex items-start justify-between gap-3 px-5 pb-3 pt-4">
      <div className="min-w-0">
        <div className="flex items-center gap-1.5">
          <h2 className="truncate text-sm font-semibold text-white">{title}</h2>
          <AlertCircle className="h-3.5 w-3.5 shrink-0 text-muted" />
        </div>
      </div>
      {action}
    </div>
  )
}

function StorySectionHeader({ title, description: _description }: { title: string; description: string }) {
  return (
    <div className="pt-2">
      <h2 className="text-sm font-semibold text-white">{title}</h2>
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
      <div className="flex h-full flex-col justify-between gap-4">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0 flex-1">
            <p className="truncate text-xs font-medium uppercase tracking-[0.14em] text-muted">{metric.label}</p>
            {metric.comparison ? (
              <div className="mt-3 grid grid-cols-2 gap-3">
                {[metric.comparison.agent, metric.comparison.network].map((item) => (
                  <div key={item.label} className="min-w-0 border-l border-border/80 pl-2 first:border-l-0 first:pl-0">
                    <p className={`truncate text-[10px] font-medium uppercase tracking-wide ${item.tone}`}>{item.label}</p>
                    <p className="mt-1 truncate text-lg font-semibold text-white">{item.value}</p>
                    <p className="mt-1 text-[10px] text-muted">{item.detail}</p>
                  </div>
                ))}
              </div>
            ) : <p className="mt-3 text-2xl font-semibold leading-none tracking-tight text-white">{metric.value}</p>}
          </div>
          <div className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-border bg-background/70 ${metric.tone}`}><Icon className="h-5 w-5" /></div>
        </div>
        <p className={`min-h-4 text-[11px] leading-4 ${detailTone}`} title={metric.comparison ? metric.detail ?? undefined : undefined}>{metric.detail ?? 'No terminal Runs in this interval'}</p>
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
      <SkeletonPanel className="min-h-[120px]" />
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
    <Panel className="flex min-h-[180px] flex-col items-center justify-center p-7 text-center">
      <Activity className="h-9 w-9 text-muted" />
      <h2 className="mt-3 text-sm font-semibold text-white">No Agent Runs or Network Runs in this interval</h2>
      <p className="mt-1 max-w-lg text-xs leading-5 text-muted">The selected environment and time range returned no runtime activity.</p>
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

type ChartPoint = { x: number; y: number }

function chartPoints(values: number[], maxValue: number): ChartPoint[] {
  return values.map((value, index) => ({
    x: pointX(index, values.length),
    y: pointY(value, maxValue),
  }))
}

function buildSmoothPath(values: number[], maxValue: number): string {
  const points = chartPoints(values, maxValue)
  if (points.length === 0) return ''
  if (points.length === 1) return `M ${points[0].x.toFixed(2)} ${points[0].y.toFixed(2)}`

  return points.slice(1).reduce((path, current, index) => {
    const previous = points[index]
    const distance = current.x - previous.x
    const controlOffset = Math.min(distance * 0.42, 24)
    return `${path} C ${(previous.x + controlOffset).toFixed(2)} ${previous.y.toFixed(2)} ${(current.x - controlOffset).toFixed(2)} ${current.y.toFixed(2)} ${current.x.toFixed(2)} ${current.y.toFixed(2)}`
  }, `M ${points[0].x.toFixed(2)} ${points[0].y.toFixed(2)}`)
}

function buildAreaPath(values: number[], maxValue: number): string {
  if (values.length === 0) return ''
  const baseline = CHART_HEIGHT - CHART_PADDING
  const line = buildSmoothPath(values, maxValue)
  return `${line} L ${pointX(values.length - 1, values.length).toFixed(2)} ${baseline} L ${pointX(0, values.length).toFixed(2)} ${baseline} Z`
}

function latestActivityIndex(series: DashboardSeriesPoint[]): number {
  for (let index = series.length - 1; index >= 0; index -= 1) {
    const point = series[index]
    if (point && point.agentRuns + point.networkRuns + point.agentErrors + point.networkErrors > 0) return index
  }
  return Math.max(series.length - 1, 0)
}

function ChartTicks({ model }: { model: DashboardViewModel }) {
  const ticks = getTickIndexes(model.series.length)
  return (
    <div className="absolute bottom-0 left-0 right-0 flex justify-between overflow-hidden font-mono text-[9px] text-muted">
      {ticks.map((index) => <span key={`${model.series[index]?.label}-${index}`} className="max-w-[108px] truncate">{model.series[index]?.label}</span>)}
    </div>
  )
}

function ChartGrid() {
  return <div className="absolute bottom-7 left-0 right-0 top-0 flex flex-col justify-between">{[0, 1, 2, 3].map((line) => <div key={line} className="border-t border-border/55" />)}</div>
}

function RunActivityChart({ model }: { model: DashboardViewModel }) {
  const [selectedIndex, setSelectedIndex] = useState(() => latestActivityIndex(model.series))
  const [hoverIndex, setHoverIndex] = useState<number | null>(null)
  const activeIndex = hoverIndex ?? selectedIndex
  const agentValues = model.series.map((point) => point.agentRuns)
  const networkValues = model.series.map((point) => point.networkRuns)
  const maxValue = Math.max(...agentValues, ...networkValues, 1)
  const agentPath = buildSmoothPath(agentValues, maxValue)
  const agentAreaPath = buildAreaPath(agentValues, maxValue)
  const hasAgentActivity = agentValues.some((value) => value > 0)
  const hasNetworkActivity = networkValues.some((value) => value > 0)
  const activePoint = model.series[activeIndex] ?? null
  const activeX = activePoint ? pointX(activeIndex, model.series.length) : null
  const bucketWidth = model.series.length > 1 ? (CHART_WIDTH - CHART_PADDING * 2) / (model.series.length - 1) : CHART_WIDTH - CHART_PADDING * 2
  const networkBarWidth = Math.min(Math.max(bucketWidth * 0.18, 3), 7)
  const hitWidth = Math.max(bucketWidth, 20)

  useEffect(() => {
    setSelectedIndex(latestActivityIndex(model.series))
    setHoverIndex(null)
  }, [model.series])

  return (
    <Panel className="h-full min-h-[330px]">
      <PanelHeader
        title="Run Activity"
        action={<div className="rounded-md border border-border bg-background/55 px-3 py-1.5 text-right font-mono text-[9px] text-muted"><span className="block uppercase tracking-[0.08em]">Period total</span><b className="mt-0.5 block text-[10px] font-medium text-slate-200">{sum(agentValues).toLocaleString()} Agent Runs · {sum(networkValues).toLocaleString()} Network Runs</b></div>}
      />
      <div className="px-5 pb-5">
        <div className="mb-3 flex flex-wrap items-center gap-4 font-mono text-[9px] text-muted">
          {hasAgentActivity && <span className="flex items-center gap-1.5"><span className="h-0.5 w-4 rounded bg-blue-500" />Agent Runs</span>}
          {hasNetworkActivity && <span className="flex items-center gap-1.5"><span className="h-3 w-1 rounded-sm bg-violet-500/80" />Network Runs</span>}
          <span className="flex items-center gap-1.5"><span className="h-1.5 w-1.5 rounded-full bg-red-400" />Errors</span>
        </div>
        <div className="relative h-[190px]">
          <ChartGrid />
          <svg
            onMouseLeave={() => setHoverIndex(null)}
            className="absolute inset-x-0 top-0 h-[166px] w-full"
            viewBox={`0 0 ${CHART_WIDTH} ${CHART_HEIGHT}`}
            preserveAspectRatio="none"
            aria-label="Agent Run area and Network Run bars by time bucket"
          >
            <defs>
              <linearGradient id="agent-run-area" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#3b82f6" stopOpacity="0.28" />
                <stop offset="55%" stopColor="#3b82f6" stopOpacity="0.10" />
                <stop offset="95%" stopColor="#3b82f6" stopOpacity="0.01" />
              </linearGradient>
              <linearGradient id="network-run-bar" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#a78bfa" stopOpacity="0.9" />
                <stop offset="100%" stopColor="#7c3aed" stopOpacity="0.45" />
              </linearGradient>
            </defs>

            {activeX !== null && (
              <line
                x1={activeX}
                x2={activeX}
                y1={CHART_PADDING - 2}
                y2={CHART_HEIGHT - CHART_PADDING}
                stroke="#334155"
                strokeWidth="1"
                strokeDasharray="3 5"
                opacity="0.8"
                vectorEffect="non-scaling-stroke"
              />
            )}

            {hasAgentActivity && agentAreaPath && <path d={agentAreaPath} fill="url(#agent-run-area)" />}

            {hasNetworkActivity && model.series.map((point, index) => {
              if (point.networkRuns <= 0) return null
              const x = pointX(index, model.series.length)
              const y = pointY(point.networkRuns, maxValue)
              const baseline = CHART_HEIGHT - CHART_PADDING
              return (
                <rect
                  key={`network-bar-${point.bucketStart}`}
                  x={x - networkBarWidth / 2}
                  y={y}
                  width={networkBarWidth}
                  height={Math.max(baseline - y, 2)}
                  rx={Math.min(networkBarWidth / 2, 3)}
                  fill="url(#network-run-bar)"
                />
              )
            })}

            {hasAgentActivity && agentPath && (
              <path
                d={agentPath}
                fill="none"
                stroke="#3b82f6"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
                vectorEffect="non-scaling-stroke"
              />
            )}

            {model.series.map((point, index) => {
              const x = pointX(index, model.series.length)
              const hasErrors = point.agentErrors + point.networkErrors > 0
              const isActive = activeIndex === index
              const agentY = pointY(point.agentRuns, maxValue)
              const left = Math.max(x - hitWidth / 2, 0)
              const width = Math.min(hitWidth, CHART_WIDTH - left)
              return (
                <g key={point.bucketStart} onMouseEnter={() => setHoverIndex(index)} onClick={() => setSelectedIndex(index)} className="cursor-pointer">
                  <rect x={left} y={0} width={width} height={CHART_HEIGHT} fill="transparent" />
                  {isActive && (
                    <>
                      <circle cx={x} cy={agentY} r="5" fill="#020817" stroke="#60a5fa" strokeWidth="2" vectorEffect="non-scaling-stroke" />
                      <circle cx={x} cy={agentY} r="1.5" fill="#93c5fd" />
                    </>
                  )}
                  {hasErrors && <circle cx={x} cy={CHART_HEIGHT - 8} r="3" fill="#f87171" />}
                </g>
              )
            })}
          </svg>
          <ChartTicks model={model} />
        </div>
        {activePoint && (
          <div className="flex flex-col gap-3 rounded-md border border-border/80 bg-background/45 px-4 py-3 lg:flex-row lg:items-center lg:justify-between">
            <div className="min-w-[150px]"><p className="font-mono text-[9px] font-medium uppercase tracking-[0.08em] text-muted">Selected interval</p><p className="mt-1 font-mono text-[10px] font-medium text-white">{activePoint.label}</p></div>
            <div className="grid flex-1 grid-cols-2 gap-3 sm:grid-cols-5">
              <div><p className="font-mono text-[9px] text-muted">Agent Runs</p><p className="mt-1 font-mono text-sm font-semibold text-blue-300">{activePoint.agentRuns}</p></div>
              <div><p className="font-mono text-[9px] text-muted">Network Runs</p><p className="mt-1 font-mono text-sm font-semibold text-violet-300">{activePoint.networkRuns}</p></div>
              <div><p className="font-mono text-[9px] text-muted">Successful</p><p className="mt-1 font-mono text-sm font-semibold text-emerald-300">{activePoint.agentSuccess + activePoint.networkSuccess}</p></div>
              <div><p className="font-mono text-[9px] text-muted">Errors</p><p className="mt-1 font-mono text-sm font-semibold text-red-300">{activePoint.agentErrors + activePoint.networkErrors}</p></div>
              <div><p className="font-mono text-[9px] text-muted">Runtime cost</p><p className="mt-1 font-mono text-sm font-semibold text-white">{formatCost(activePoint.costUsd, activePoint.costUsd !== null)}</p></div>
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
  const activeSegments = segments.filter((segment) => segment.value > 0)
  return (
    <div>
      <div className="flex h-2.5 overflow-hidden rounded-full bg-background ring-1 ring-border/80">
        {group.terminalRuns === 0 ? <span className="h-full w-full bg-muted/20" /> : activeSegments.map((segment) => <span key={segment.key} title={`${segment.label}: ${segment.value}`} className={segment.className} style={{ width: `${(segment.value / denominator) * 100}%` }} />)}
      </div>
      {activeSegments.length > 1 && <div className="mt-2 flex flex-wrap gap-x-3 gap-y-1 text-[10px] text-muted">{activeSegments.map((segment) => <span key={segment.key} className="flex items-center gap-1"><span className={`h-1.5 w-1.5 rounded-full ${segment.className}`} />{segment.label} {segment.value}</span>)}</div>}
    </div>
  )
}

function ReliabilityGroupView({ group }: { group: DashboardReliabilityGroup }) {
  const errors = group.failed + group.timedOut + group.uncertain
  return (
    <div className="rounded-xl border border-border/80 bg-background/45 p-3">
      <div className="flex items-start justify-between gap-3">
        <div><p className="text-xs font-semibold text-white">{group.label}</p><p className="mt-1 text-[11px] text-slate-400">{group.successful} successful · {errors} errors · {group.running} running</p></div>
        <div className="text-right"><p className={`text-lg font-semibold ${group.successRate !== null && group.successRate >= 99 ? 'text-emerald-300' : errors > 0 ? 'text-amber-300' : 'text-white'}`}>{formatPercent(group.successRate)}</p><p className="text-[10px] text-muted">success</p></div>
      </div>
      <div className="mt-3"><ReliabilityDistribution group={group} /></div>
      <div className="mt-3 grid grid-cols-3 gap-x-3 text-xs">
        <span className="text-muted">Error rate <b className="mt-1 block text-white">{formatPercent(group.errorRate)}</b></span>
        <span className="text-muted">Average <b className="mt-1 block text-white">{group.averageDurationLabel}</b></span>
        <span className="text-muted" title="95% of terminal Runs completed within this duration">p95 <b className="mt-1 block text-white">{group.p95DurationLabel}</b></span>
      </div>
    </div>
  )
}

function ReliabilityPanel({ model }: { model: DashboardViewModel }) {
  return (
    <Panel className="h-full min-h-[330px]">
      <PanelHeader title="Reliability & Performance" />
      <div className="space-y-3 px-5 pb-5"><ReliabilityGroupView group={model.reliability.agent} /><ReliabilityGroupView group={model.reliability.network} /></div>
    </Panel>
  )
}

function OperationalIssues({ model }: { model: DashboardViewModel }) {
  if (!model.issues.hasIssues) return null
  const totalIssues = model.issues.totalAgentErrors + model.issues.totalNetworkErrors
  const firstEntity = model.issues.topAgents[0] ?? model.issues.topNetworks[0]
  const firstCode = model.issues.topCodes[0]

  if (totalIssues <= 2) {
    return (
      <Panel className="border-red-500/15 bg-red-500/[0.018] px-4 py-3">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
          <div className="flex items-start gap-3"><AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-red-300" /><div><p className="text-sm font-semibold text-white">{totalIssues} operational {totalIssues === 1 ? 'issue' : 'issues'} in this period</p><p className="mt-1 text-xs text-slate-400">{model.issues.summary.join(' · ')}</p></div></div>
          <div className="flex flex-wrap gap-x-6 gap-y-2 text-xs"><span className="text-muted">Affected <b className="ml-1 text-white">{firstEntity?.name ?? 'Unknown'}</b></span><span className="text-muted">Failure code <b className="ml-1 font-mono text-red-200">{firstCode?.code ?? 'unknown'}</b></span>{model.issues.peakLabel && <span className="text-muted">Occurred <b className="ml-1 text-white">{model.issues.peakLabel}</b></span>}</div>
        </div>
      </Panel>
    )
  }

  return (
    <Panel className="border-red-500/20 bg-red-500/[0.025]">
      <PanelHeader title="Operational Issues" action={<AlertTriangle className="h-4 w-4 text-red-300" />} />
      <div className="grid gap-4 px-5 pb-5 xl:grid-cols-12">
        <div className="xl:col-span-4"><p className="text-[10px] font-medium uppercase tracking-wide text-muted">What happened</p><div className="mt-2 space-y-2">{model.issues.summary.map((item) => <div key={item} className="rounded-lg border border-red-500/15 bg-background/45 px-3 py-2 text-xs text-red-200">{item}</div>)}</div>{model.issues.peakLabel && <p className="mt-3 text-xs text-muted">Failure peak: <span className="font-medium text-white">{model.issues.peakLabel}</span> · {model.issues.peakCount} errors</p>}</div>
        <div className="xl:col-span-3"><p className="text-[10px] font-medium uppercase tracking-wide text-muted">Most affected Agents</p><div className="mt-2 space-y-2">{model.issues.topAgents.length === 0 ? <p className="text-xs text-muted">No Agent failures.</p> : model.issues.topAgents.map((item) => <div key={`${item.entity_id}-${item.name}`} className="flex items-center justify-between gap-3 rounded-lg border border-border/70 bg-background/45 px-3 py-2 text-xs"><span className="truncate text-slate-200">{item.name}</span><b className="text-red-300">{item.failure_count}</b></div>)}</div></div>
        <div className="xl:col-span-3"><p className="text-[10px] font-medium uppercase tracking-wide text-muted">Most affected Networks</p><div className="mt-2 space-y-2">{model.issues.topNetworks.length === 0 ? <p className="text-xs text-muted">No Network failures.</p> : model.issues.topNetworks.map((item) => <div key={`${item.entity_id}-${item.name}`} className="flex items-center justify-between gap-3 rounded-lg border border-border/70 bg-background/45 px-3 py-2 text-xs"><span className="truncate text-slate-200">{item.name}</span><b className="text-red-300">{item.failure_count}</b></div>)}</div></div>
        <div className="xl:col-span-2"><p className="text-[10px] font-medium uppercase tracking-wide text-muted">Failure codes</p><div className="mt-2 space-y-2">{model.issues.topCodes.map((item) => <div key={item.code} className="rounded-lg border border-border/70 bg-background/45 px-3 py-2"><p className="truncate font-mono text-[10px] text-slate-200">{item.code}</p><p className="mt-1 text-xs font-semibold text-red-300">{item.failure_count}</p></div>)}</div></div>
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

function changeContext(environment: DashboardEnvironment) {
  if (environment === 'draft') return { title: 'Draft activity', description: 'Mutable Agent and Network Draft updates in the selected period.', empty: 'No Draft changes in the selected period.' }
  if (environment === 'staging') return { title: 'Staging changes', description: 'Agent and Network versions published to Staging in the selected period.', empty: 'No Staging changes in the selected period.' }
  if (environment === 'production') return { title: 'Production releases', description: 'Immutable releases, rollbacks, and reactivations in the selected period.', empty: 'No Production releases in the selected period.' }
  return { title: 'Changes across all environments', description: 'Draft updates, Staging versions, and Production releases in chronological order.', empty: 'No changes recorded in the selected period.' }
}

function ChangeItem({ change, onOpen }: { change: DashboardChangeRow; onOpen: () => void }) {
  const Icon = change.resourceType === 'agent' ? Bot : Network
  return (
    <button type="button" onClick={onOpen} className="grid w-full gap-3 rounded-xl border border-border/80 bg-background/45 p-3 text-left transition-colors hover:border-primary/25 hover:bg-background/75 md:grid-cols-[40px_minmax(0,1fr)_auto] md:items-center">
      <span className={`flex h-9 w-9 items-center justify-center rounded-xl border border-border bg-surface ${change.resourceType === 'agent' ? 'text-blue-300' : 'text-violet-300'}`}><Icon className="h-4 w-4" /></span>
      <span className="min-w-0"><span className="flex flex-wrap items-center gap-2"><b className="truncate text-sm text-white">{change.resourceName}</b><span className="rounded-md border border-border bg-surface px-2 py-0.5 text-[10px] text-slate-300">{change.resourceLabel}</span><EnvironmentBadge value={change.environmentLabel} /></span><span className="mt-1 block text-xs text-slate-300">{change.actionLabel}{change.versionLabel ? ` · ${change.versionLabel}` : ''}</span><span className="mt-1 block truncate text-xs text-muted">{change.description}</span></span>
      <span className="text-xs text-muted md:text-right">{change.occurredLabel}</span>
    </button>
  )
}

function ChangesInPeriod({ model, environment, onNavigate }: { model: DashboardViewModel; environment: DashboardEnvironment; onNavigate: (segment: string) => void }) {
  const context = changeContext(environment)
  return (
    <Panel>
      <PanelHeader title={context.title} />
      <div className="space-y-2 px-5 pb-4">
        {model.changes.length === 0 ? <div className="rounded-xl border border-dashed border-border/80 bg-background/25 px-4 py-5 text-center text-sm text-muted">{context.empty}</div> : model.changes.map((change) => <ChangeItem key={`${change.resourceType}-${change.id}`} change={change} onOpen={() => onNavigate(change.resourceType === 'agent' ? `agents/${change.resourceId}` : `networks/${change.resourceId}`)} />)}
        <div className="flex flex-wrap gap-4 pt-2"><MiniLink label="View Agent history" onClick={() => onNavigate('agents')} /><MiniLink label="View Network history" onClick={() => onNavigate('networks')} /></div>
      </div>
    </Panel>
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
    <Panel className="flex h-full min-h-[230px] flex-col overflow-hidden">
      <PanelHeader title="Runtime Assets" />
      <div className="grid flex-1 grid-cols-1 border-t border-border/70 sm:grid-cols-2">
        {rows.map(([label, value], index) => {
          const isLast = index === rows.length - 1
          return (
            <div
              key={label}
              className={`flex min-h-10 items-center justify-between gap-3 border-b border-border/60 px-4 py-2.5 ${!isLast && index % 2 === 0 ? 'sm:border-r' : ''} ${isLast ? 'sm:col-span-2' : ''}`}
            >
              <span className="min-w-0 truncate font-mono text-[9px] text-muted-foreground">{label}</span>
              <span className="shrink-0 font-mono text-xs font-semibold tabular-nums text-slate-50">{value}</span>
            </div>
          )
        })}
      </div>
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
    <Panel className="flex h-full min-h-[230px] flex-col overflow-hidden">
      <PanelHeader title="Knowledge" />
      <div className="grid flex-1 grid-cols-2 border-t border-border/70">
        {entries.map((entry, index) => {
          const Icon = entry.icon
          return (
            <div key={entry.label} className={`min-h-[62px] border-b border-border/60 px-4 py-3 ${index % 2 === 0 ? 'border-r' : ''}`}>
              <div className="flex min-w-0 items-center gap-2">
                <Icon className={`h-3.5 w-3.5 shrink-0 ${entry.tone}`} />
                <p className="truncate font-mono text-[9px] text-muted-foreground">{entry.label}</p>
              </div>
              <p className={`mt-1.5 truncate font-mono text-base font-semibold leading-none tabular-nums ${entry.tone}`}>{entry.value}</p>
            </div>
          )
        })}
      </div>
      <div className="border-t border-border/70 px-4 py-3">
        <MiniLink label="Open Knowledge" onClick={onOpen} />
      </div>
    </Panel>
  )
}

function ToolsIntegrations({ model, onOpen }: { model: DashboardViewModel; onOpen: () => void }) {
  const items = [
    { label: 'Tools', value: model.tools.total, icon: Wrench, tone: 'text-blue-300' },
    { label: 'Active', value: model.tools.active, icon: CheckCircle2, tone: 'text-emerald-300' },
    { label: 'Inactive', value: model.tools.inactive, icon: Workflow, tone: 'text-slate-400' },
    { label: 'Recent failures', value: String(model.tools.recentFailures), icon: XCircle, tone: model.tools.recentFailures > 0 ? 'text-red-300' : 'text-slate-400' },
  ]
  return (
    <Panel className="flex h-full min-h-[230px] flex-col overflow-hidden">
      <PanelHeader title="Tools" />
      <div className="flex-1 border-t border-border/70">
        {items.map((item) => {
          const Icon = item.icon
          return (
            <div key={item.label} className="flex min-h-10 items-center justify-between gap-3 border-b border-border/60 px-4 py-2.5">
              <span className="flex min-w-0 items-center gap-2 font-mono text-[9px] text-muted-foreground">
                <Icon className={`h-3.5 w-3.5 shrink-0 ${item.tone}`} />
                <span className="truncate">{item.label}</span>
              </span>
              <span className={`shrink-0 font-mono text-xs font-semibold tabular-nums ${item.tone}`}>{item.value}</span>
            </div>
          )
        })}
      </div>
      <div className="border-t border-border/70 px-4 py-3">
        <MiniLink label="Manage Tools" onClick={onOpen} />
      </div>
    </Panel>
  )
}

function keyboardActivate(event: KeyboardEvent<HTMLElement>, action: () => void) {
  if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); action() }
}

function RecentRuns({ model, onOpen, onViewAll }: { model: DashboardViewModel; onOpen: (run: DashboardRunRow) => void; onViewAll: () => void }) {
  return (
    <Panel className="overflow-hidden">
      <PanelHeader title="Recent Runs" action={<MiniLink label="View all Runs" onClick={onViewAll} />} />
      <div className="px-5 pb-5">
        {model.runs.length === 0 ? <p className="py-6 text-center text-sm text-muted">No Runs in this interval.</p> : (
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

      <StorySectionHeader title="What changed" description="Configuration and release activity for the selected environment and period." />
      <ChangesInPeriod model={model} environment={environment} onNavigate={onNavigate} />

      <StorySectionHeader title="Current Project State" description="Current deployable resources. Knowledge and Tools are Project-wide, not historical environment snapshots." />
      <div className="grid grid-cols-1 items-stretch gap-4 xl:grid-cols-3"><RuntimeAssets model={model} /><KnowledgeBase model={model} onOpen={() => onNavigate('knowledge')} /><ToolsIntegrations model={model} onOpen={() => onNavigate('tools')} /></div>

      <StorySectionHeader title="Latest executions" description="A compact operational handoff to the detailed Agent or Network workspace." />
      <RecentRuns model={model} onOpen={onOpenRun} onViewAll={() => onNavigate('traces')} />
    </div>
  )
}

export default function DashboardPage() {
  const { workspaceId, projectId } = useParams<{ workspaceId: string; projectId: string }>()
  const navigate = useNavigate()
  const [environment, setEnvironment] = useState<DashboardEnvironment>('all')
  const [range, setRange] = useState<DashboardRangePreset>('24h')
  const query = useProjectOverview({ projectId, environment, range })
  const model = useMemo(() => query.data ? adaptProjectOverview(query.data) : null, [query.data])
  const isInitialLoading = query.isPending && !query.data
  const isUpdating = query.isFetching && Boolean(query.data)

  const goTo = (segment: string) => {
    if (!projectId) return
    const parts = segment.split('/').filter(Boolean)
    navigate(workspaceProjectPath(workspaceId, projectId, ...parts))
  }

  const openRun = (run: DashboardRunRow) => {
    if (!projectId) return
    if (run.kind === 'network' && run.networkId) {
      navigate(`${workspaceProjectPath(workspaceId, projectId, 'networks', run.networkId)}?run=${encodeURIComponent(run.id)}`)
      return
    }
    if (run.agentId) {
      navigate(`${workspaceProjectPath(workspaceId, projectId, 'agents', run.agentId, 'playground')}?run=${encodeURIComponent(run.id)}`)
      return
    }
    goTo('traces')
  }

  return (
    <div className="h-full overflow-y-auto scrollbar-thin">
      <div className="min-w-0 space-y-5 pb-6 pr-1" aria-busy={isUpdating}>
        <header className="relative overflow-hidden rounded-xl border border-border/80 bg-surface/50 p-5">
          {isUpdating && <div className="absolute inset-x-0 top-0 h-0.5 animate-pulse bg-primary/70" />}
          <div className="flex flex-col gap-5 xl:flex-row xl:items-start xl:justify-between">
            <div className="min-w-0">
              <div className="flex items-center gap-2"><GitBranch className="h-4 w-4 text-primary-light" /><h1 className="text-2xl font-semibold tracking-tight text-white">Project Overview</h1>{isUpdating && <span className="rounded-full border border-primary/20 bg-primary/5 px-2 py-0.5 text-[10px] text-primary-light">Updating {environmentLabel(environment)} overview…</span>}</div>
              {model && <p className="mt-2 text-xs text-muted">Interval: {model.intervalLabel} · {model.timezoneLabel} · Last refreshed {model.generatedAtLabel}</p>}
            </div>
            <div className="flex flex-col gap-3 lg:flex-row lg:items-center xl:justify-end">
              <label className="sr-only" htmlFor="dashboard-range">Dashboard range</label>
              <select id="dashboard-range" value={range} onChange={(event: ChangeEvent<HTMLSelectElement>) => setRange(event.target.value as DashboardRangePreset)} className="h-9 rounded-lg border border-border bg-background/70 px-3 text-sm text-slate-300 outline-none transition-colors focus:ring-1 focus:ring-primary/60">{RANGES.map((item) => <option key={item} value={item}>{rangeLabel(item)}</option>)}</select>
              <div className="flex max-w-full overflow-x-auto rounded-lg border border-border bg-background/50 p-1 scrollbar-thin">{ENVIRONMENTS.map((item) => <button type="button" key={item.value} onClick={() => setEnvironment(item.value)} aria-pressed={environment === item.value} className={`flex h-7 items-center gap-1.5 whitespace-nowrap rounded-md border px-3 text-xs font-medium transition-colors ${environment === item.value ? item.tone : 'border-transparent text-muted hover:bg-surface hover:text-white'}`}><span className={`h-1.5 w-1.5 rounded-full ${item.dot}`} />{item.label}</button>)}</div>
              <button type="button" onClick={() => void query.refetch()} disabled={query.isFetching} className="inline-flex h-9 items-center justify-center gap-1.5 rounded-lg border border-border bg-background/70 px-3 text-sm font-medium text-slate-300 transition-colors hover:border-primary/35 hover:text-white disabled:opacity-50"><RefreshCw className={`h-3.5 w-3.5 ${query.isFetching ? 'animate-spin' : ''}`} />Refresh</button>
            </div>
          </div>
        </header>

        {query.isError && model && <div className="rounded-lg border border-amber-500/20 bg-amber-500/5 px-4 py-2 text-xs text-amber-200">The latest refresh failed. Showing the last available Overview data.</div>}

        {!projectId
          ? <DashboardErrorState message="Project identifier is missing from the route." onRetry={() => window.location.reload()} />
          : isInitialLoading
            ? <DashboardLoadingState />
            : !model && query.isError
              ? <DashboardErrorState message={query.error instanceof Error ? query.error.message : 'Unable to load project overview.'} onRetry={() => query.refetch()} />
              : model
                ? <DashboardDataState model={model} environment={environment} onNavigate={goTo} onOpenRun={openRun} />
                : <DashboardErrorState message="The overview endpoint returned no data." onRetry={() => query.refetch()} />}
      </div>
    </div>
  )
}
