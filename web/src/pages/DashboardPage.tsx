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
  CircleDollarSign,
  Clock3,
  Database,
  FileText,
  Layers3,
  RefreshCw,
  Rocket,
  Sparkles,
  Users,
  Workflow,
  Wrench,
  XCircle,
} from 'lucide-react'
import { adaptProjectOverview, rangeLabel } from '@/features/dashboard/adapters'
import type { DashboardMetric, DashboardViewModel } from '@/features/dashboard/adapters'
import { useProjectOverview } from '@/features/dashboard/hooks'
import type { DashboardEnvironment, DashboardRangePreset } from '@/features/dashboard/types'
import { orgProjectPath } from '@/lib/constants/routes'

const ENVIRONMENTS: Array<{ value: DashboardEnvironment; label: string; tone: string; dot: string }> = [
  { value: 'all', label: 'All', tone: 'bg-slate-700/40 text-slate-200 ring-slate-600', dot: 'bg-slate-300' },
  { value: 'draft', label: 'Draft', tone: 'bg-blue-500/10 text-blue-400 ring-blue-500/35', dot: 'bg-blue-400' },
  { value: 'staging', label: 'Staging', tone: 'bg-amber-500/10 text-amber-400 ring-amber-500/35', dot: 'bg-amber-400' },
  { value: 'production', label: 'Production', tone: 'bg-emerald-500/10 text-emerald-400 ring-emerald-500/35', dot: 'bg-emerald-400' },
]

const RANGES: DashboardRangePreset[] = ['24h', '7d', '30d']

function Panel({ children, className = '' }: { children: ReactNode; className?: string }) {
  return <section className={`rounded-xl border border-slate-800/90 bg-[#081321] shadow-[0_14px_35px_rgba(0,0,0,.18)] ${className}`}>{children}</section>
}

function PanelHeader({ title, subtitle, action }: { title: string; subtitle?: string; action?: ReactNode }) {
  return (
    <div className="flex items-start justify-between gap-3 px-4 pb-2 pt-3.5">
      <div>
        <div className="flex items-center gap-1.5"><h2 className="text-[13px] font-semibold text-slate-100">{title}</h2><AlertCircle className="h-3 w-3 text-slate-500" /></div>
        {subtitle && <p className="mt-0.5 text-[10px] text-slate-500">{subtitle}</p>}
      </div>
      {action}
    </div>
  )
}

function MiniLink({ label, onClick }: { label: string; onClick?: () => void }) {
  return <button type="button" onClick={onClick} className="flex items-center gap-1 text-[10px] font-medium text-blue-400 hover:text-blue-300">{label}<ArrowRight className="h-3 w-3" /></button>
}

function MetricCard({ metric }: { metric: DashboardMetric }) {
  const Icon = metric.icon
  const detailTone = metric.direction === 'up'
    ? 'text-emerald-400'
    : metric.direction === 'down'
      ? 'text-red-400'
      : 'text-slate-500'
  return (
    <Panel className="min-h-[104px] p-3.5">
      <div className="flex items-start gap-3">
        <div className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-xl ${metric.tone}`}><Icon className="h-4 w-4" /></div>
        <div className="min-w-0">
          <p className="truncate text-[11px] font-medium text-slate-300">{metric.label}</p>
          <p className="mt-1 text-[22px] font-semibold leading-none tracking-tight text-white">{metric.value}</p>
          <p className={`mt-2 min-h-4 text-[10px] ${detailTone}`}>{metric.detail ?? ' '}</p>
        </div>
      </div>
    </Panel>
  )
}

function SkeletonPanel({ className = '' }: { className?: string }) {
  return <Panel className={`animate-pulse p-4 ${className}`}><div className="h-3 w-28 rounded bg-slate-800" /><div className="mt-5 h-20 rounded-lg bg-slate-900/80" /></Panel>
}

export function DashboardLoadingState() {
  return (
    <div aria-label="Loading dashboard" className="space-y-2.5">
      <div className="grid grid-cols-1 gap-2.5 sm:grid-cols-2 lg:grid-cols-3 2xl:grid-cols-6">{Array.from({ length: 6 }, (_, index) => <SkeletonPanel key={index} className="min-h-[104px]" />)}</div>
      <div className="grid grid-cols-1 gap-2.5 xl:grid-cols-3">{Array.from({ length: 3 }, (_, index) => <SkeletonPanel key={index} className="min-h-[230px]" />)}</div>
      <div className="grid grid-cols-1 gap-2.5 xl:grid-cols-3">{Array.from({ length: 3 }, (_, index) => <SkeletonPanel key={index} className="min-h-[190px]" />)}</div>
    </div>
  )
}

export function DashboardErrorState({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <Panel className="flex min-h-[260px] flex-col items-center justify-center p-8 text-center">
      <XCircle className="h-10 w-10 text-red-400" />
      <h2 className="mt-3 text-base font-semibold text-white">Dashboard unavailable</h2>
      <p className="mt-1 max-w-lg text-sm text-slate-400">{message}</p>
      <button type="button" onClick={onRetry} className="mt-5 inline-flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-500"><RefreshCw className="h-4 w-4" />Retry</button>
    </Panel>
  )
}

function EmptyExecutionState() {
  return (
    <Panel className="flex min-h-[190px] flex-col items-center justify-center p-7 text-center">
      <Activity className="h-9 w-9 text-slate-600" />
      <h2 className="mt-3 text-sm font-semibold text-slate-100">No executions in this interval</h2>
      <p className="mt-1 max-w-md text-xs text-slate-500">The selected project, environment, and time range returned no runtime requests. Agent, knowledge, and tool totals remain live.</p>
    </Panel>
  )
}

function buildPath(values: number[], width: number, height: number, padding = 12): string {
  if (values.length === 0) return ''
  if (values.length === 1) return `M ${width / 2} ${height / 2}`
  const min = Math.min(...values)
  const max = Math.max(...values)
  const range = max - min || 1
  return values.map((value, index) => {
    const x = padding + (index / (values.length - 1)) * (width - padding * 2)
    const y = height - padding - ((value - min) / range) * (height - padding * 2)
    return `${index === 0 ? 'M' : 'L'} ${x.toFixed(2)} ${y.toFixed(2)}`
  }).join(' ')
}

function RuntimeChart({ model }: { model: DashboardViewModel }) {
  const width = 420
  const height = 118
  const values = model.series.map((point) => point.requests)
  const path = buildPath(values, width, height, 13)
  const area = path && values.length > 1 ? `${path} L ${width - 13} ${height - 13} L 13 ${height - 13} Z` : ''
  return (
    <Panel className="h-full">
      <PanelHeader title="Runtime Requests" subtitle="Requests by selected bucket" />
      <div className="px-3 pb-3">
        <div className="relative h-[150px]">
          <div className="absolute bottom-7 left-8 right-0 top-2 flex flex-col justify-between">{[0, 1, 2, 3].map((line) => <div key={line} className="border-t border-slate-800/80" />)}</div>
          <svg className="absolute left-8 right-0 top-0 h-[118px]" viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="none" aria-label="Runtime requests trend">
            <defs><linearGradient id="request-area-live" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#3b82f6" stopOpacity=".24" /><stop offset="100%" stopColor="#3b82f6" stopOpacity="0" /></linearGradient></defs>
            {area && <path d={area} fill="url(#request-area-live)" />}
            {path && <path d={path} fill="none" stroke="#3b82f6" strokeWidth="2.1" vectorEffect="non-scaling-stroke" />}
          </svg>
          <div className="absolute bottom-0 left-8 right-0 flex justify-between overflow-hidden text-[9px] text-slate-500">{model.series.map((point, index) => <span key={`${point.label}-${index}`} className="truncate">{point.label}</span>)}</div>
        </div>
      </div>
    </Panel>
  )
}

function LatencyChart({ model }: { model: DashboardViewModel }) {
  const width = 420
  const height = 104
  const latency = model.series.map((point) => point.latencyMs ?? 0)
  const tokens = model.series.map((point) => point.tokens)
  const path = buildPath(latency, width, height, 12)
  const maxTokens = Math.max(...tokens, 1)
  return (
    <Panel className="h-full">
      <PanelHeader title="Latency & Token Usage" subtitle="Average latency and total tokens" />
      <div className="px-3 pb-3">
        <div className="mb-1.5 flex items-center gap-4 pl-8 text-[9px] text-slate-400"><span className="flex items-center gap-1.5"><span className="h-0.5 w-3 rounded bg-blue-500" />Latency</span><span className="flex items-center gap-1.5"><span className="h-2.5 w-2.5 rounded-sm bg-violet-500/80" />Tokens</span></div>
        <div className="relative h-[126px]">
          <div className="absolute bottom-6 left-7 right-7 top-1 flex flex-col justify-between">{[0, 1, 2, 3].map((line) => <div key={line} className="border-t border-slate-800/80" />)}</div>
          <svg className="absolute left-7 right-7 top-0 h-[104px]" viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="none" aria-label="Latency and token usage">
            {tokens.map((value, index) => { const slot = width / Math.max(tokens.length, 1); const barHeight = (value / maxTokens) * 74; return <rect key={`${value}-${index}`} x={index * slot + slot * .37} y={height - 11 - barHeight} width={slot * .26} height={barHeight} rx="1" fill="#8b5cf6" fillOpacity=".72" /> })}
            {path && <path d={path} fill="none" stroke="#3b82f6" strokeWidth="2.1" vectorEffect="non-scaling-stroke" />}
          </svg>
          <div className="absolute bottom-0 left-7 right-7 flex justify-between overflow-hidden text-[9px] text-slate-500">{model.series.map((point, index) => <span key={`${point.label}-${index}`} className="truncate">{point.label}</span>)}</div>
        </div>
      </div>
    </Panel>
  )
}

function EnvironmentDistribution({ model }: { model: DashboardViewModel }) {
  const productionEnd = model.environments[0]?.percent ?? 0
  const stagingEnd = productionEnd + (model.environments[1]?.percent ?? 0)
  const gradient = model.environmentTotal === 0
    ? 'conic-gradient(#1e293b 0 100%)'
    : `conic-gradient(#22c55e 0 ${productionEnd}%, #fbbf24 ${productionEnd}% ${stagingEnd}%, #3b82f6 ${stagingEnd}% 100%)`
  return (
    <Panel className="h-full"><PanelHeader title="Environment Distribution" subtitle="Current agent distribution" />
      <div className="grid min-h-[178px] grid-cols-1 items-center gap-4 px-5 pb-4 sm:grid-cols-[150px_1fr]">
        <div className="relative mx-auto h-32 w-32 rounded-full" style={{ background: gradient }}><div className="absolute inset-[18px] flex flex-col items-center justify-center rounded-full bg-[#081321] shadow-[inset_0_0_0_1px_rgba(51,65,85,.6)]"><span className="text-2xl font-semibold text-white">{model.environmentTotal}</span><span className="text-[10px] text-slate-500">Agents</span></div></div>
        <div className="space-y-4">{model.environments.map((slice) => <div key={slice.key} className="flex items-center justify-between gap-5 text-[11px]"><span className="flex items-center gap-2 text-slate-200"><span className="h-2 w-2 rounded-full" style={{ backgroundColor: slice.color }} />{slice.label}</span><span className="font-medium text-slate-300">{slice.percent.toFixed(0)}% ({slice.value})</span></div>)}</div>
      </div>
    </Panel>
  )
}

function EnvironmentBadge({ value }: { value: string }) {
  const normalized = value.toLowerCase()
  const classes = normalized === 'production'
    ? 'border-emerald-500/40 bg-emerald-500/10 text-emerald-400'
    : normalized === 'staging'
      ? 'border-amber-500/40 bg-amber-500/10 text-amber-400'
      : 'border-blue-500/40 bg-blue-500/10 text-blue-400'
  return <span className={`inline-flex rounded border px-1.5 py-0.5 text-[9px] font-medium ${classes}`}>{value}</span>
}

function StatusBadge({ value }: { value: string }) {
  const classes = value === 'Success'
    ? 'border-emerald-500/40 bg-emerald-500/10 text-emerald-400'
    : value === 'Warning'
      ? 'border-orange-500/40 bg-orange-500/10 text-orange-400'
      : 'border-red-500/40 bg-red-500/10 text-red-400'
  return <span className={`inline-flex rounded border px-1.5 py-0.5 text-[9px] font-medium ${classes}`}>{value}</span>
}

function keyboardActivate(event: KeyboardEvent<HTMLElement>, action: () => void) {
  if (event.key === 'Enter' || event.key === ' ') {
    event.preventDefault()
    action()
  }
}

export function dashboardRowTarget(kind: 'release' | 'trace'): 'agents' | 'traces' {
  return kind === 'release' ? 'agents' : 'traces'
}

function AgentReleases({ model, onOpen }: { model: DashboardViewModel; onOpen: () => void }) {
  return (
    <Panel className="h-full"><PanelHeader title="Agent Releases" /><div className="px-3 pb-3">
      {model.releases.length === 0 ? <p className="py-8 text-center text-xs text-slate-500">No releases in this interval.</p> : <>
        <div className="grid grid-cols-[1.55fr_1fr_.8fr_1.2fr] border-b border-slate-800 px-1 pb-1.5 text-[9px] text-slate-500"><span>Agent</span><span>Environment</span><span>Version</span><span>Promoted</span></div>
        {model.releases.map((release, index) => <div key={release.id} role="link" tabIndex={0} onClick={onOpen} onKeyDown={(event: KeyboardEvent<HTMLDivElement>) => keyboardActivate(event, onOpen)} className={`grid cursor-pointer grid-cols-[1.55fr_1fr_.8fr_1.2fr] items-center px-1 py-2 text-[10px] outline-none hover:bg-slate-900/50 focus:ring-1 focus:ring-blue-500/60 ${index !== model.releases.length - 1 ? 'border-b border-slate-800/80' : ''}`}><span className="flex min-w-0 items-center gap-2 font-medium text-slate-200"><span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-md bg-blue-500/15 text-blue-400"><Bot className="h-3 w-3" /></span><span className="truncate">{release.agent_name}</span></span><span><EnvironmentBadge value={release.environmentLabel} /></span><span className="text-slate-300">{release.version}</span><span className="truncate text-slate-400">{release.promotedLabel}</span></div>)}
      </>}
      <div className="pt-2"><MiniLink label="View all releases" onClick={onOpen} /></div>
    </div></Panel>
  )
}

function KnowledgeBase({ model, onOpen }: { model: DashboardViewModel; onOpen: () => void }) {
  const entries: Array<{ label: string; value: string; icon: LucideIcon; tone: string }> = [
    { label: 'Collections', value: model.knowledge.collections, icon: Layers3, tone: 'text-blue-400' },
    { label: 'Documents', value: model.knowledge.documents, icon: FileText, tone: 'text-blue-400' },
    { label: 'Indexed', value: model.knowledge.indexed, icon: CheckCircle2, tone: 'text-emerald-400' },
    { label: 'Pending', value: model.knowledge.pending, icon: Sparkles, tone: 'text-amber-400' },
    { label: 'Failed', value: model.knowledge.failed, icon: XCircle, tone: 'text-red-400' },
    { label: 'Storage', value: model.knowledge.storage, icon: Database, tone: 'text-violet-400' },
  ]
  return <Panel className="h-full"><PanelHeader title="Knowledge Base" /><div className="grid grid-cols-2 gap-2 px-3 pb-3">{entries.map((entry) => { const Icon = entry.icon; return <div key={entry.label} className="flex items-center gap-2.5 rounded-lg border border-slate-800 bg-slate-950/20 p-2.5"><div className="flex h-7 w-7 items-center justify-center rounded-lg bg-slate-800/60"><Icon className={`h-4 w-4 ${entry.tone}`} /></div><div><p className="text-[9px] text-slate-500">{entry.label}</p><p className={`text-[15px] font-semibold leading-tight ${entry.tone}`}>{entry.value}</p></div></div> })}<div className="col-span-2 pt-0.5"><MiniLink label="Open Knowledge" onClick={onOpen} /></div></div></Panel>
}

function ToolsIntegrations({ model, onOpen }: { model: DashboardViewModel; onOpen: () => void }) {
  const items = [
    { label: 'Tools', value: model.tools.total, icon: Wrench, tone: 'text-blue-400' },
    { label: 'Active', value: model.tools.active, icon: CheckCircle2, tone: 'text-emerald-400' },
    { label: 'Inactive', value: model.tools.inactive, icon: Workflow, tone: 'text-slate-300' },
    { label: 'Recent Failures', value: String(model.tools.recentFailures), icon: XCircle, tone: model.tools.recentFailures > 0 ? 'text-red-400' : 'text-slate-300' },
  ]
  return <Panel className="h-full"><PanelHeader title="Tools & Integrations" /><div className="px-3 pb-3">{items.map((item, index) => { const Icon = item.icon; return <div key={item.label} className={`flex items-center justify-between py-2.5 text-[10px] ${index !== items.length - 1 ? 'border-b border-slate-800/80' : ''}`}><span className="flex items-center gap-2 text-slate-200"><Icon className={`h-3.5 w-3.5 ${item.tone}`} />{item.label}</span><span className={`font-semibold ${item.tone}`}>{item.value}</span></div> })}<div className="pt-2"><MiniLink label="Manage Tools" onClick={onOpen} /></div></div></Panel>
}

function RecentTraces({ model, onOpen }: { model: DashboardViewModel; onOpen: () => void }) {
  return <Panel className="h-full overflow-hidden"><PanelHeader title="Recent Traces" /><div className="overflow-x-auto px-3 pb-3 scrollbar-thin"><div className="min-w-[640px]">{model.traces.length === 0 ? <p className="py-8 text-center text-xs text-slate-500">No traces in this interval.</p> : <><div className="grid grid-cols-[1.2fr_1.25fr_1.05fr_.95fr_.85fr_.75fr_.75fr] border-b border-slate-800 pb-1.5 text-[9px] text-slate-500"><span>Time</span><span>Agent</span><span>Environment</span><span>Status</span><span>Latency</span><span>Tokens</span><span>Cost</span></div>{model.traces.map((trace, index) => <div key={trace.id} role="link" tabIndex={0} onClick={onOpen} onKeyDown={(event: KeyboardEvent<HTMLDivElement>) => keyboardActivate(event, onOpen)} className={`grid cursor-pointer grid-cols-[1.2fr_1.25fr_1.05fr_.95fr_.85fr_.75fr_.75fr] items-center py-1.5 text-[9px] outline-none hover:bg-slate-900/50 focus:ring-1 focus:ring-blue-500/60 ${index !== model.traces.length - 1 ? 'border-b border-slate-800/70' : ''}`}><span className="truncate text-slate-400">{trace.timeLabel}</span><span className="truncate font-medium text-slate-200">{trace.agentLabel}</span><span><EnvironmentBadge value={trace.environmentLabel} /></span><span><StatusBadge value={trace.statusLabel} /></span><span className="text-slate-300">{trace.latencyLabel}</span><span className="text-slate-300">{trace.tokenLabel}</span><span className="text-slate-300">{trace.costLabel}</span></div>)}</>}<div className="pt-2"><MiniLink label="View all traces" onClick={onOpen} /></div></div></div></Panel>
}

function CapabilityPanel({ title, description, icon: Icon, onOpen }: { title: string; description: string; icon: LucideIcon; onOpen?: () => void }) {
  return <Panel className="flex h-full min-h-[130px] items-center gap-3 p-4"><span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-slate-800/60 text-slate-300"><Icon className="h-4 w-4" /></span><div><h3 className="text-xs font-semibold text-slate-100">{title}</h3><p className="mt-1 text-[10px] leading-4 text-slate-500">{description}</p>{onOpen && <div className="mt-2"><MiniLink label="Open" onClick={onOpen} /></div>}</div></Panel>
}

export function DashboardDataState({ model, onNavigate }: { model: DashboardViewModel; onNavigate: (segment: string) => void }) {
  return (
    <div className="space-y-2.5">
      <div className="grid grid-cols-1 gap-2.5 sm:grid-cols-2 lg:grid-cols-3 2xl:grid-cols-6">{model.metrics.map((metric) => <MetricCard key={metric.label} metric={metric} />)}</div>
      {model.isExecutionEmpty ? <EmptyExecutionState /> : <div className="grid grid-cols-1 gap-2.5 xl:grid-cols-12"><div className="xl:col-span-4"><RuntimeChart model={model} /></div><div className="xl:col-span-4"><LatencyChart model={model} /></div><div className="xl:col-span-4"><EnvironmentDistribution model={model} /></div></div>}
      <div className="grid grid-cols-1 gap-2.5 xl:grid-cols-12"><div className="xl:col-span-4"><AgentReleases model={model} onOpen={() => onNavigate(dashboardRowTarget('release'))} /></div><div className="xl:col-span-4"><KnowledgeBase model={model} onOpen={() => onNavigate('knowledge')} /></div><div className="xl:col-span-4"><ToolsIntegrations model={model} onOpen={() => onNavigate('tools')} /></div></div>
      <RecentTraces model={model} onOpen={() => onNavigate(dashboardRowTarget('trace'))} />
      {(model.capabilities.sessions_jobs || model.capabilities.ingestion_pipeline || model.capabilities.activity_feed) && <div className="grid grid-cols-1 gap-2.5 lg:grid-cols-3">
        {model.capabilities.sessions_jobs && <CapabilityPanel title="Sessions & Jobs" description="This deployment exposes session and job diagnostics in the dedicated runtime view." icon={Users} />}
        {model.capabilities.ingestion_pipeline && <CapabilityPanel title="Ingestion Pipeline" description="Ingestion pipeline diagnostics are available without substituting dashboard data." icon={Workflow} onOpen={() => onNavigate('knowledge')} />}
        {model.capabilities.activity_feed && <CapabilityPanel title="Recent Activity" description="Activity feed capability is enabled for this project." icon={Activity} />}
      </div>}
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

  useEffect(() => {
    const interval = window.setInterval(() => setWindowAnchor(new Date()), 60_000)
    return () => window.clearInterval(interval)
  }, [])

  useEffect(() => queryClient.getMutationCache().subscribe((event: any) => {
    if (event.type === 'updated' && event.mutation.state.status === 'success') {
      setWindowAnchor(new Date())
    }
  }), [queryClient])

  const goTo = (segment: string) => {
    if (!projectId) return
    navigate(orgProjectPath(organizationId, projectId, segment))
  }

  return (
    <div className="h-full overflow-y-auto pr-1 scrollbar-thin">
      <div className="mx-auto min-w-0 max-w-[1720px] space-y-2.5 pb-6">
        <header className="flex flex-col gap-3 border-b border-slate-800/70 pb-3 xl:flex-row xl:items-start xl:justify-between">
          <div><h1 className="text-[22px] font-semibold tracking-tight text-white">Project Overview</h1><p className="mt-0.5 text-[11px] text-slate-500">Live, tenant-scoped runtime and project data</p>{model && <p className="mt-1 text-[9px] text-slate-600">Interval: {model.intervalLabel} · {model.timezoneLabel} · Last refreshed {model.generatedAtLabel}</p>}</div>
          <div className="flex flex-col gap-2 lg:flex-row lg:items-center">
            <label className="sr-only" htmlFor="dashboard-range">Dashboard range</label>
            <select id="dashboard-range" value={range} onChange={(event: ChangeEvent<HTMLSelectElement>) => setRange(event.target.value as DashboardRangePreset)} className="rounded-lg border border-slate-800 bg-slate-950/50 px-3 py-2 text-[10px] text-slate-300 outline-none focus:ring-1 focus:ring-blue-500/60">{RANGES.map((item) => <option key={item} value={item}>{rangeLabel(item)}</option>)}</select>
            <div className="flex overflow-x-auto rounded-lg border border-slate-800 bg-slate-950/30 p-0.5">{ENVIRONMENTS.map((item) => <button type="button" key={item.value} onClick={() => setEnvironment(item.value)} aria-pressed={environment === item.value} className={`flex items-center gap-1.5 whitespace-nowrap rounded-md px-3 py-1.5 text-[10px] font-medium transition ${environment === item.value ? `${item.tone} ring-1` : 'text-slate-500 hover:text-slate-300'}`}><span className={`h-1.5 w-1.5 rounded-full ${item.dot}`} />{item.label}</button>)}</div>
            <button type="button" onClick={() => setWindowAnchor(new Date())} disabled={query.isFetching} className="inline-flex items-center justify-center gap-1.5 rounded-lg border border-slate-800 bg-slate-950/30 px-3 py-2 text-[10px] font-medium text-slate-300 hover:border-slate-700 hover:text-white disabled:opacity-50"><RefreshCw className={`h-3.5 w-3.5 ${query.isFetching ? 'animate-spin' : ''}`} />Refresh</button>
          </div>
        </header>

        {!projectId ? <DashboardErrorState message="Project identifier is missing from the route." onRetry={() => window.location.reload()} /> : query.isPending ? <DashboardLoadingState /> : query.isError ? <DashboardErrorState message={query.error instanceof Error ? query.error.message : 'Unable to load project overview.'} onRetry={() => query.refetch()} /> : model ? <DashboardDataState model={model} onNavigate={goTo} /> : <DashboardErrorState message="The overview endpoint returned no data." onRetry={() => query.refetch()} />}
      </div>
    </div>
  )
}
