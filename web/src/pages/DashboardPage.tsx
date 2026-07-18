import { useEffect, useMemo, useState } from 'react'
import type { ChangeEvent, KeyboardEvent, ReactNode } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { useQueryClient } from '@tanstack/react-query'
import type { LucideIcon } from 'lucide-react'
import {
  Activity,
  AlertCircle,
  ArrowRight,
  Bot,
  CheckCircle2,
  Database,
  FileText,
  Layers3,
  RefreshCw,
  Sparkles,
  Workflow,
  Wrench,
  XCircle,
} from 'lucide-react'
import { adaptProjectOverview, rangeLabel } from '@/features/dashboard/adapters'
import type { DashboardMetric, DashboardRunRow, DashboardViewModel } from '@/features/dashboard/adapters'
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
const CHART_WIDTH = 640
const CHART_HEIGHT = 152
const CHART_PADDING = 18

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
        <p className={`min-h-4 text-xs leading-5 ${detailTone}`}>{metric.detail ?? 'No completed Runs in this interval'}</p>
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
      <div className="grid grid-cols-1 gap-4 xl:grid-cols-12"><SkeletonPanel className="min-h-[260px] xl:col-span-5" /><SkeletonPanel className="min-h-[260px] xl:col-span-4" /><SkeletonPanel className="min-h-[260px] xl:col-span-3" /></div>
      <SkeletonPanel className="min-h-[280px]" />
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
      <p className="mt-1 max-w-lg text-xs leading-5 text-muted">The selected project, environment, and time range returned no runtime activity. Agent, Network, Knowledge, and Tool state remains available below.</p>
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

function buildPath(values: number[], width: number, height: number): string {
  if (values.length === 0) return ''
  if (values.length === 1) return `M ${width / 2} ${height / 2}`
  const max = Math.max(...values, 1)
  return values.map((value, index) => {
    const x = CHART_PADDING + (index / (values.length - 1)) * (width - CHART_PADDING * 2)
    const y = height - CHART_PADDING - (value / max) * (height - CHART_PADDING * 2)
    return `${index === 0 ? 'M' : 'L'} ${x.toFixed(2)} ${y.toFixed(2)}`
  }).join(' ')
}

function ChartTicks({ model }: { model: DashboardViewModel }) {
  const ticks = getTickIndexes(model.series.length)
  return (
    <div className="absolute bottom-0 left-0 right-0 flex justify-between overflow-hidden text-[10px] text-muted">
      {ticks.map((index) => <span key={`${model.series[index]?.label}-${index}`} className="max-w-[86px] truncate">{model.series[index]?.label}</span>)}
    </div>
  )
}

function ChartGrid() {
  return <div className="absolute bottom-7 left-0 right-0 top-0 flex flex-col justify-between">{[0, 1, 2, 3].map((line) => <div key={line} className="border-t border-border/70" />)}</div>
}

function RunVolumeChart({ model }: { model: DashboardViewModel }) {
  const agentValues = model.series.map((point) => point.agentRuns)
  const networkValues = model.series.map((point) => point.networkRuns)
  const agentPath = buildPath(agentValues, CHART_WIDTH, CHART_HEIGHT)
  const networkPath = buildPath(networkValues, CHART_WIDTH, CHART_HEIGHT)
  return (
    <Panel className="h-full min-h-[260px]">
      <PanelHeader title="Run Volume" subtitle="Agent Runs and Network Runs are independent operational units" action={<span className="rounded-full border border-border bg-background/70 px-2.5 py-1 text-xs text-muted">{sum(agentValues).toLocaleString()} / {sum(networkValues).toLocaleString()}</span>} />
      <div className="px-5 pb-5">
        <div className="mb-4 flex flex-wrap items-center gap-4 text-xs text-muted">
          <span className="flex items-center gap-1.5"><span className="h-0.5 w-4 rounded bg-blue-500" />Agent Runs</span>
          <span className="flex items-center gap-1.5"><span className="h-0.5 w-4 rounded bg-violet-500" />Network Runs</span>
        </div>
        <div className="relative h-[170px]">
          <ChartGrid />
          <svg className="absolute inset-x-0 top-0 h-[146px] w-full" viewBox={`0 0 ${CHART_WIDTH} ${CHART_HEIGHT}`} preserveAspectRatio="none" aria-label="Agent Run and Network Run volume">
            {agentPath && <path d={agentPath} fill="none" stroke="#3b82f6" strokeWidth="2" vectorEffect="non-scaling-stroke" />}
            {networkPath && <path d={networkPath} fill="none" stroke="#8b5cf6" strokeWidth="2" strokeDasharray="5 4" vectorEffect="non-scaling-stroke" />}
          </svg>
          <ChartTicks model={model} />
        </div>
      </div>
    </Panel>
  )
}

function ExecutionTimeChart({ model }: { model: DashboardViewModel }) {
  const agentValues = model.series.map((point) => point.agentDurationMs ?? 0)
  const networkValues = model.series.map((point) => point.networkDurationMs ?? 0)
  const agentPath = buildPath(agentValues, CHART_WIDTH, CHART_HEIGHT)
  const networkPath = buildPath(networkValues, CHART_WIDTH, CHART_HEIGHT)
  return (
    <Panel className="h-full min-h-[260px]">
      <PanelHeader title="Execution Time" subtitle="Average duration by Run type" />
      <div className="px-5 pb-5">
        <div className="mb-4 flex flex-wrap items-center gap-4 text-xs text-muted">
          <span className="flex items-center gap-1.5"><span className="h-0.5 w-4 rounded bg-blue-500" />Agent Run</span>
          <span className="flex items-center gap-1.5"><span className="h-0.5 w-4 rounded bg-violet-500" />Network Run</span>
        </div>
        <div className="relative h-[170px]">
          <ChartGrid />
          <svg className="absolute inset-x-0 top-0 h-[146px] w-full" viewBox={`0 0 ${CHART_WIDTH} ${CHART_HEIGHT}`} preserveAspectRatio="none" aria-label="Average Run execution time">
            {agentPath && <path d={agentPath} fill="none" stroke="#3b82f6" strokeWidth="2" vectorEffect="non-scaling-stroke" />}
            {networkPath && <path d={networkPath} fill="none" stroke="#8b5cf6" strokeWidth="2" strokeDasharray="5 4" vectorEffect="non-scaling-stroke" />}
          </svg>
          <ChartTicks model={model} />
        </div>
      </div>
    </Panel>
  )
}

function RuntimeAssets({ model }: { model: DashboardViewModel }) {
  const rows = [
    ['Active Agents', model.assets.activeAgents],
    ['Agents in Production', model.assets.productionAgents],
    ['Networks', model.assets.networks],
    ['Networks in Production', model.assets.productionNetworks],
    ['Networks in Staging', model.assets.stagingNetworks],
  ]
  return (
    <Panel className="h-full min-h-[260px]">
      <PanelHeader title="Runtime Assets" subtitle="Current deployable state" />
      <div className="space-y-1 px-5 pb-5">{rows.map(([label, value]) => <div key={label} className="flex items-center justify-between rounded-lg px-1 py-2.5 text-sm"><span className="text-slate-200">{label}</span><span className="font-semibold text-white">{value}</span></div>)}</div>
    </Panel>
  )
}

function EnvironmentBadge({ value }: { value: string }) {
  const normalized = value.toLowerCase()
  const classes = normalized === 'production' ? 'border-emerald-500/40 bg-emerald-500/10 text-emerald-300' : normalized === 'staging' ? 'border-amber-500/40 bg-amber-500/10 text-amber-300' : 'border-blue-500/40 bg-blue-500/10 text-blue-300'
  return <span className={`inline-flex rounded-md border px-2 py-0.5 text-xs font-medium ${classes}`}>{value}</span>
}

function StatusBadge({ value }: { value: string }) {
  const classes = value === 'Completed' ? 'border-emerald-500/40 bg-emerald-500/10 text-emerald-300' : value === 'Running' || value === 'Queued' ? 'border-blue-500/40 bg-blue-500/10 text-blue-300' : value === 'Completed with issues' ? 'border-amber-500/40 bg-amber-500/10 text-amber-300' : 'border-red-500/40 bg-red-500/10 text-red-300'
  return <span className={`inline-flex rounded-md border px-2 py-0.5 text-xs font-medium ${classes}`}>{value}</span>
}

function keyboardActivate(event: KeyboardEvent<HTMLElement>, action: () => void) {
  if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); action() }
}

function AgentReleases({ model, onOpen }: { model: DashboardViewModel; onOpen: () => void }) {
  return (
    <Panel className="h-full min-h-[250px]">
      <PanelHeader title="Agent Releases" subtitle="Recent promotions and draft changes" />
      <div className="space-y-2 px-5 pb-5">
        {model.releases.length === 0 ? <p className="py-8 text-center text-sm text-muted">No releases in this interval.</p> : model.releases.map((release) => (
          <button type="button" key={release.id} onClick={onOpen} className="grid w-full gap-3 rounded-xl border border-border/80 bg-background/50 p-3 text-left transition-colors hover:border-primary/25 hover:bg-background/80 md:grid-cols-[minmax(0,1fr)_auto]">
            <span className="flex min-w-0 items-start gap-3"><span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl border border-border bg-surface text-primary-light"><Bot className="h-4 w-4" /></span><span className="min-w-0"><span className="block truncate text-sm font-semibold text-white">{release.agent_name}</span><span className="mt-1 block truncate text-xs text-muted">Version {release.version} · {release.promotedLabel}</span></span></span>
            <span className="flex items-center md:justify-end"><EnvironmentBadge value={release.environmentLabel} /></span>
          </button>
        ))}
        <MiniLink label="View all releases" onClick={onOpen} />
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
    <Panel className="h-full min-h-[250px]">
      <PanelHeader title="Knowledge" subtitle="Retrieval assets and indexing state" />
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
      <PanelHeader title="Tools" subtitle="Integration readiness" />
      <div className="space-y-1 px-5 pb-5">{items.map((item) => { const Icon = item.icon; return <div key={item.label} className="flex items-center justify-between gap-3 rounded-lg px-1 py-2.5 text-sm"><span className="flex items-center gap-2 text-slate-200"><Icon className={`h-4 w-4 ${item.tone}`} />{item.label}</span><span className={`font-semibold ${item.tone}`}>{item.value}</span></div> })}<div className="pt-2"><MiniLink label="Manage Tools" onClick={onOpen} /></div></div>
    </Panel>
  )
}

function RecentRuns({ model, onOpen }: { model: DashboardViewModel; onOpen: (run: DashboardRunRow) => void }) {
  return (
    <Panel className="overflow-hidden">
      <PanelHeader title="Recent Runs" subtitle="Agent Runs and Network Runs with operational context" />
      <div className="space-y-2 px-5 pb-5">
        {model.runs.length === 0 ? <p className="py-8 text-center text-sm text-muted">No Runs in this interval.</p> : model.runs.map((run) => {
          const open = () => onOpen(run)
          return (
            <div key={`${run.kind}-${run.id}`} role="link" tabIndex={0} onClick={open} onKeyDown={(event) => keyboardActivate(event, open)} className="grid cursor-pointer gap-3 rounded-xl border border-border/80 bg-background/45 p-3 outline-none transition-colors hover:border-primary/25 hover:bg-background/75 focus:ring-1 focus:ring-primary/60 md:grid-cols-[minmax(0,1fr)_auto] md:items-center">
              <div className="min-w-0"><div className="flex flex-wrap items-center gap-2"><span className="rounded-md border border-border bg-surface px-2 py-0.5 text-xs font-medium text-slate-200">{run.subtitle}</span><StatusBadge value={run.statusLabel} /><span className="truncate text-sm font-semibold text-white">{run.title}</span><EnvironmentBadge value={run.environmentLabel} /></div><p className="mt-2 truncate text-xs text-muted">{run.sourceLabel} · {run.timeLabel}</p></div>
              <div className="grid grid-cols-3 gap-4 text-xs md:min-w-[330px]"><div><p className="text-muted">Duration</p><p className="mt-1 font-medium text-white">{run.durationLabel}</p></div><div><p className="text-muted">Tokens</p><p className="mt-1 font-medium text-white">{run.tokenLabel}</p></div><div><p className="text-muted">Cost</p><p className="mt-1 truncate font-medium text-white">{run.costLabel}</p></div></div>
            </div>
          )
        })}
      </div>
    </Panel>
  )
}

export function DashboardDataState({ model, onNavigate, onOpenRun }: { model: DashboardViewModel; onNavigate: (segment: string) => void; onOpenRun: (run: DashboardRunRow) => void }) {
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-6">{model.metrics.map((metric) => <MetricCard key={metric.label} metric={metric} />)}</div>
      {model.isExecutionEmpty ? <EmptyExecutionState /> : <div className="grid grid-cols-1 gap-4 xl:grid-cols-12"><div className="xl:col-span-5"><RunVolumeChart model={model} /></div><div className="xl:col-span-4"><ExecutionTimeChart model={model} /></div><div className="xl:col-span-3"><RuntimeAssets model={model} /></div></div>}
      <RecentRuns model={model} onOpen={onOpenRun} />
      <div className="grid grid-cols-1 gap-4 xl:grid-cols-12"><div className="xl:col-span-5"><AgentReleases model={model} onOpen={() => onNavigate('agents')} /></div><div className="xl:col-span-4"><KnowledgeBase model={model} onOpen={() => onNavigate('knowledge')} /></div><div className="xl:col-span-3"><ToolsIntegrations model={model} onOpen={() => onNavigate('tools')} /></div></div>
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
    navigate(orgProjectPath(organizationId, projectId, segment))
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
            <div className="min-w-0"><h1 className="text-2xl font-semibold tracking-tight text-white">Project Overview</h1><p className="mt-1 max-w-3xl text-sm text-muted">Operational health across Agent Runs, Network Runs, releases, Knowledge, and Tools.</p>{model && <p className="mt-2 text-xs text-muted">Interval: {model.intervalLabel} · {model.timezoneLabel} · Last refreshed {model.generatedAtLabel}</p>}</div>
            <div className="flex flex-col gap-3 lg:flex-row lg:items-center xl:justify-end">
              <label className="sr-only" htmlFor="dashboard-range">Dashboard range</label>
              <select id="dashboard-range" value={range} onChange={(event: ChangeEvent<HTMLSelectElement>) => setRange(event.target.value as DashboardRangePreset)} className="h-9 rounded-lg border border-border bg-background/70 px-3 text-sm text-slate-300 outline-none transition-colors focus:ring-1 focus:ring-primary/60">{RANGES.map((item) => <option key={item} value={item}>{rangeLabel(item)}</option>)}</select>
              <div className="flex max-w-full overflow-x-auto rounded-lg border border-border bg-background/50 p-1 scrollbar-thin">{ENVIRONMENTS.map((item) => <button type="button" key={item.value} onClick={() => setEnvironment(item.value)} aria-pressed={environment === item.value} className={`flex h-7 items-center gap-1.5 whitespace-nowrap rounded-md border px-3 text-xs font-medium transition-colors ${environment === item.value ? item.tone : 'border-transparent text-muted hover:bg-surface hover:text-white'}`}><span className={`h-1.5 w-1.5 rounded-full ${item.dot}`} />{item.label}</button>)}</div>
              <button type="button" onClick={() => setWindowAnchor(new Date())} disabled={query.isFetching} className="inline-flex h-9 items-center justify-center gap-1.5 rounded-lg border border-border bg-background/70 px-3 text-sm font-medium text-slate-300 transition-colors hover:border-primary/35 hover:text-white disabled:opacity-50"><RefreshCw className={`h-3.5 w-3.5 ${query.isFetching ? 'animate-spin' : ''}`} />Refresh</button>
            </div>
          </div>
        </header>
        {!projectId ? <DashboardErrorState message="Project identifier is missing from the route." onRetry={() => window.location.reload()} /> : query.isPending ? <DashboardLoadingState /> : query.isError ? <DashboardErrorState message={query.error instanceof Error ? query.error.message : 'Unable to load project overview.'} onRetry={() => query.refetch()} /> : model ? <DashboardDataState model={model} onNavigate={goTo} onOpenRun={openRun} /> : <DashboardErrorState message="The overview endpoint returned no data." onRetry={() => query.refetch()} />}
      </div>
    </div>
  )
}
