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
  return (
    <section className={`rounded-xl border border-border/90 bg-surface/70 shadow-lg shadow-black/5 ${className}`}>
      {children}
    </section>
  )
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
      {label}
      <ArrowRight className="h-3 w-3" />
    </button>
  )
}

function metricDetail(metric: DashboardMetric) {
  if (!metric.detail) return null
  return metric.detail.replace('request(s) with unknown cost', 'requests without cost data')
}

function MetricCard({ metric }: { metric: DashboardMetric }) {
  const Icon = metric.icon
  const detail = metricDetail(metric)
  const detailTone = metric.direction === 'up'
    ? 'text-emerald-300'
    : metric.direction === 'down'
      ? 'text-red-300'
      : 'text-muted'

  return (
    <Panel className="min-h-[128px] p-4">
      <div className="flex h-full flex-col justify-between gap-5">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <p className="truncate text-xs font-medium uppercase tracking-[0.14em] text-muted">{metric.label}</p>
            <p className="mt-3 text-2xl font-semibold leading-none tracking-tight text-white">{metric.value}</p>
          </div>
          <div className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-border bg-background/70 ${metric.tone}`}>
            <Icon className="h-5 w-5" />
          </div>
        </div>
        <p className={`min-h-4 text-xs leading-5 ${detailTone}`}>{detail ?? 'Live project state'}</p>
      </div>
    </Panel>
  )
}

function SkeletonPanel({ className = '' }: { className?: string }) {
  return (
    <Panel className={`animate-pulse p-5 ${className}`}>
      <div className="h-3 w-28 rounded-full bg-white/[0.07]" />
      <div className="mt-5 h-20 rounded-xl bg-white/[0.05]" />
    </Panel>
  )
}

export function DashboardLoadingState() {
  return (
    <div aria-label="Loading dashboard" className="space-y-4">
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-6">
        {Array.from({ length: 6 }, (_, index) => <SkeletonPanel key={index} className="min-h-[128px]" />)}
      </div>
      <div className="grid grid-cols-1 gap-4 xl:grid-cols-12">
        <SkeletonPanel className="min-h-[250px] xl:col-span-5" />
        <SkeletonPanel className="min-h-[250px] xl:col-span-4" />
        <SkeletonPanel className="min-h-[250px] xl:col-span-3" />
      </div>
      <div className="grid grid-cols-1 gap-4 xl:grid-cols-12">
        <SkeletonPanel className="min-h-[230px] xl:col-span-5" />
        <SkeletonPanel className="min-h-[230px] xl:col-span-4" />
        <SkeletonPanel className="min-h-[230px] xl:col-span-3" />
      </div>
    </div>
  )
}

export function DashboardErrorState({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <Panel className="flex min-h-[280px] flex-col items-center justify-center p-8 text-center">
      <XCircle className="h-10 w-10 text-red-300" />
      <h2 className="mt-3 text-base font-semibold text-white">Dashboard unavailable</h2>
      <p className="mt-1 max-w-lg text-sm text-muted">{message}</p>
      <button type="button" onClick={onRetry} className="mt-5 inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-primary-dark">
        <RefreshCw className="h-4 w-4" />
        Retry
      </button>
    </Panel>
  )
}

function EmptyExecutionState() {
  return (
    <Panel className="flex min-h-[220px] flex-col items-center justify-center p-7 text-center">
      <Activity className="h-9 w-9 text-muted" />
      <h2 className="mt-3 text-sm font-semibold text-white">No executions in this interval</h2>
      <p className="mt-1 max-w-md text-xs leading-5 text-muted">The selected project, environment, and time range returned no runtime requests. Agent, knowledge, and tool totals remain live.</p>
    </Panel>
  )
}

function sum(values: number[]) {
  return values.reduce((total, value) => total + value, 0)
}

function getTickIndexes(length: number, maxTicks = 5): number[] {
  if (length <= 0) return []
  if (length <= maxTicks) return Array.from({ length }, (_, index) => index)

  const indexes = Array.from({ length: maxTicks }, (_, index) => Math.round((index * (length - 1)) / (maxTicks - 1)))
  return Array.from(new Set(indexes))
}

function buildPath(values: number[], width: number, height: number, padding = CHART_PADDING, zeroBased = true): string {
  if (values.length === 0) return ''
  if (values.length === 1) return `M ${width / 2} ${height / 2}`

  const min = zeroBased ? 0 : Math.min(...values)
  const max = Math.max(...values, 1)
  const range = Math.max(max - min, 1)

  return values.map((value, index) => {
    const x = padding + (index / (values.length - 1)) * (width - padding * 2)
    const y = height - padding - ((value - min) / range) * (height - padding * 2)
    return `${index === 0 ? 'M' : 'L'} ${x.toFixed(2)} ${y.toFixed(2)}`
  }).join(' ')
}

function ChartTicks({ model }: { model: DashboardViewModel }) {
  const ticks = getTickIndexes(model.series.length, 5)
  if (ticks.length === 0) return null

  return (
    <div className="absolute bottom-0 left-0 right-0 flex justify-between overflow-hidden text-[10px] text-muted">
      {ticks.map((index) => (
        <span key={`${model.series[index]?.label}-${index}`} className="max-w-[86px] truncate">
          {model.series[index]?.label}
        </span>
      ))}
    </div>
  )
}

function RuntimeChart({ model }: { model: DashboardViewModel }) {
  const values = model.series.map((point) => point.requests)
  const path = buildPath(values, CHART_WIDTH, CHART_HEIGHT, CHART_PADDING, true)
  const area = path && values.length > 1 ? `${path} L ${CHART_WIDTH - CHART_PADDING} ${CHART_HEIGHT - CHART_PADDING} L ${CHART_PADDING} ${CHART_HEIGHT - CHART_PADDING} Z` : ''
  const total = sum(values)
  const peak = Math.max(...values, 0)

  return (
    <Panel className="h-full min-h-[260px]">
      <PanelHeader
        title="Runtime Requests"
        subtitle="Request volume over the selected interval"
        action={<span className="rounded-full border border-border bg-background/70 px-2.5 py-1 text-xs text-muted">Peak {peak}</span>}
      />
      <div className="px-5 pb-5">
        <div className="mb-4 flex flex-wrap items-center gap-3 text-xs text-muted">
          <span>Total <span className="font-semibold text-white">{total.toLocaleString()}</span></span>
          <span className="flex items-center gap-1.5"><span className="h-0.5 w-4 rounded bg-primary" />Requests</span>
        </div>
        <div className="relative h-[170px]">
          <div className="absolute bottom-7 left-0 right-0 top-0 flex flex-col justify-between">
            {[0, 1, 2, 3].map((line) => <div key={line} className="border-t border-border/70" />)}
          </div>
          <svg className="absolute inset-x-0 top-0 h-[146px] w-full" viewBox={`0 0 ${CHART_WIDTH} ${CHART_HEIGHT}`} preserveAspectRatio="none" aria-label="Runtime requests trend">
            <defs>
              <linearGradient id="request-area-live" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#3b82f6" stopOpacity=".22" />
                <stop offset="100%" stopColor="#3b82f6" stopOpacity="0" />
              </linearGradient>
            </defs>
            {area && <path d={area} fill="url(#request-area-live)" />}
            {path && <path d={path} fill="none" stroke="#3b82f6" strokeWidth="2" vectorEffect="non-scaling-stroke" />}
          </svg>
          <ChartTicks model={model} />
        </div>
      </div>
    </Panel>
  )
}

function LatencyChart({ model }: { model: DashboardViewModel }) {
  const latency = model.series.map((point) => point.latencyMs ?? 0)
  const tokens = model.series.map((point) => point.tokens)
  const path = buildPath(latency, CHART_WIDTH, CHART_HEIGHT, CHART_PADDING, true)
  const maxTokens = Math.max(...tokens, 1)
  const slot = CHART_WIDTH / Math.max(tokens.length, 1)
  const barWidth = Math.max(3, Math.min(14, slot * 0.34))
  const totalTokens = sum(tokens)

  return (
    <Panel className="h-full min-h-[260px]">
      <PanelHeader
        title="Latency & Tokens"
        subtitle="Average latency with token volume"
        action={<span className="rounded-full border border-border bg-background/70 px-2.5 py-1 text-xs text-muted">{totalTokens.toLocaleString()} tokens</span>}
      />
      <div className="px-5 pb-5">
        <div className="mb-4 flex flex-wrap items-center gap-4 text-xs text-muted">
          <span className="flex items-center gap-1.5"><span className="h-0.5 w-4 rounded bg-primary" />Latency</span>
          <span className="flex items-center gap-1.5"><span className="h-2.5 w-2.5 rounded-sm bg-violet-500/75" />Tokens</span>
        </div>
        <div className="relative h-[170px]">
          <div className="absolute bottom-7 left-0 right-0 top-0 flex flex-col justify-between">
            {[0, 1, 2, 3].map((line) => <div key={line} className="border-t border-border/70" />)}
          </div>
          <svg className="absolute inset-x-0 top-0 h-[146px] w-full" viewBox={`0 0 ${CHART_WIDTH} ${CHART_HEIGHT}`} preserveAspectRatio="none" aria-label="Latency and token usage">
            {tokens.map((value, index) => {
              const barHeight = Math.max(0, (value / maxTokens) * (CHART_HEIGHT - CHART_PADDING * 2))
              const x = index * slot + slot / 2 - barWidth / 2
              const y = CHART_HEIGHT - CHART_PADDING - barHeight
              return <rect key={`${value}-${index}`} x={x} y={y} width={barWidth} height={barHeight} rx="2" fill="#8b5cf6" fillOpacity=".7" />
            })}
            {path && <path d={path} fill="none" stroke="#3b82f6" strokeWidth="2" vectorEffect="non-scaling-stroke" />}
          </svg>
          <ChartTicks model={model} />
        </div>
      </div>
    </Panel>
  )
}

function EnvironmentComposition({ model }: { model: DashboardViewModel }) {
  return (
    <Panel className="h-full min-h-[260px]">
      <PanelHeader title="Environment Composition" subtitle="Current agent distribution" />
      <div className="space-y-5 px-5 pb-5">
        <div className="rounded-xl border border-border/80 bg-background/60 p-4">
          <p className="text-xs font-medium uppercase tracking-[0.14em] text-muted">Total agents</p>
          <p className="mt-3 text-3xl font-semibold text-white">{model.environmentTotal}</p>
        </div>
        <div className="h-3 overflow-hidden rounded-full bg-background ring-1 ring-border/80">
          {model.environmentTotal === 0 ? (
            <div className="h-full w-full bg-muted/20" />
          ) : model.environments.filter((slice) => slice.value > 0).map((slice) => (
            <div key={slice.key} className="inline-block h-full" style={{ width: `${slice.percent}%`, backgroundColor: slice.color }} />
          ))}
        </div>
        <div className="space-y-3">
          {model.environments.map((slice) => (
            <div key={slice.key} className="flex items-center justify-between gap-4 text-sm">
              <span className="flex min-w-0 items-center gap-2 text-slate-200">
                <span className="h-2 w-2 shrink-0 rounded-full" style={{ backgroundColor: slice.color }} />
                <span className="truncate">{slice.label}</span>
              </span>
              <span className="shrink-0 text-xs font-medium text-muted">{slice.percent.toFixed(0)}% · {slice.value}</span>
            </div>
          ))}
        </div>
      </div>
    </Panel>
  )
}

function EnvironmentBadge({ value }: { value: string }) {
  const normalized = value.toLowerCase()
  const classes = normalized === 'production'
    ? 'border-emerald-500/40 bg-emerald-500/10 text-emerald-300'
    : normalized === 'staging'
      ? 'border-amber-500/40 bg-amber-500/10 text-amber-300'
      : 'border-blue-500/40 bg-blue-500/10 text-blue-300'
  return <span className={`inline-flex rounded-md border px-2 py-0.5 text-xs font-medium ${classes}`}>{value}</span>
}

function StatusBadge({ value }: { value: string }) {
  const classes = value === 'Success'
    ? 'border-emerald-500/40 bg-emerald-500/10 text-emerald-300'
    : value === 'Warning'
      ? 'border-orange-500/40 bg-orange-500/10 text-orange-300'
      : 'border-red-500/40 bg-red-500/10 text-red-300'
  return <span className={`inline-flex rounded-md border px-2 py-0.5 text-xs font-medium ${classes}`}>{value}</span>
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
    <Panel className="h-full min-h-[250px]">
      <PanelHeader title="Agent Releases" subtitle="Recent promotions and draft changes" />
      <div className="space-y-2 px-5 pb-5">
        {model.releases.length === 0 ? (
          <p className="py-8 text-center text-sm text-muted">No releases in this interval.</p>
        ) : model.releases.map((release) => (
          <div
            key={release.id}
            role="link"
            tabIndex={0}
            onClick={onOpen}
            onKeyDown={(event: KeyboardEvent<HTMLDivElement>) => keyboardActivate(event, onOpen)}
            className="grid cursor-pointer gap-3 rounded-xl border border-border/80 bg-background/50 p-3 outline-none transition-colors hover:border-primary/25 hover:bg-background/80 focus:ring-1 focus:ring-primary/60 md:grid-cols-[minmax(0,1fr)_auto]"
          >
            <div className="flex min-w-0 items-start gap-3">
              <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl border border-border bg-surface text-primary-light"><Bot className="h-4 w-4" /></span>
              <div className="min-w-0">
                <p className="truncate text-sm font-semibold text-white">{release.agent_name}</p>
                <p className="mt-1 truncate text-xs text-muted">Version {release.version} · {release.promotedLabel}</p>
              </div>
            </div>
            <div className="flex items-center md:justify-end"><EnvironmentBadge value={release.environmentLabel} /></div>
          </div>
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
      <div className="grid grid-cols-2 gap-2 px-5 pb-5">
        {entries.map((entry) => {
          const Icon = entry.icon
          return (
            <div key={entry.label} className="rounded-xl border border-border/80 bg-background/50 p-3">
              <div className="flex items-center gap-2">
                <Icon className={`h-4 w-4 ${entry.tone}`} />
                <p className="truncate text-xs text-muted">{entry.label}</p>
              </div>
              <p className={`mt-2 text-lg font-semibold leading-tight ${entry.tone}`}>{entry.value}</p>
            </div>
          )
        })}
        <div className="col-span-2 pt-1"><MiniLink label="Open Knowledge" onClick={onOpen} /></div>
      </div>
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
      <div className="space-y-1 px-5 pb-5">
        {items.map((item) => {
          const Icon = item.icon
          return (
            <div key={item.label} className="flex items-center justify-between gap-3 rounded-lg px-1 py-2.5 text-sm">
              <span className="flex items-center gap-2 text-slate-200"><Icon className={`h-4 w-4 ${item.tone}`} />{item.label}</span>
              <span className={`font-semibold ${item.tone}`}>{item.value}</span>
            </div>
          )
        })}
        <div className="pt-2"><MiniLink label="Manage Tools" onClick={onOpen} /></div>
      </div>
    </Panel>
  )
}

function RecentTraces({ model, onOpen }: { model: DashboardViewModel; onOpen: () => void }) {
  return (
    <Panel className="overflow-hidden">
      <PanelHeader title="Recent Traces" subtitle="Latest runtime executions" />
      <div className="space-y-2 px-5 pb-5">
        {model.traces.length === 0 ? (
          <p className="py-8 text-center text-sm text-muted">No traces in this interval.</p>
        ) : model.traces.map((trace) => (
          <div
            key={trace.id}
            role="link"
            tabIndex={0}
            onClick={onOpen}
            onKeyDown={(event: KeyboardEvent<HTMLDivElement>) => keyboardActivate(event, onOpen)}
            className="grid cursor-pointer gap-3 rounded-xl border border-border/80 bg-background/45 p-3 outline-none transition-colors hover:border-primary/25 hover:bg-background/75 focus:ring-1 focus:ring-primary/60 md:grid-cols-[minmax(0,1fr)_auto] md:items-center"
          >
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-2">
                <StatusBadge value={trace.statusLabel} />
                <span className="truncate text-sm font-semibold text-white">{trace.agentLabel}</span>
                <EnvironmentBadge value={trace.environmentLabel} />
              </div>
              <p className="mt-2 truncate text-xs text-muted">{trace.timeLabel}</p>
            </div>
            <div className="grid grid-cols-3 gap-4 text-xs md:min-w-[280px]">
              <div><p className="text-muted">Latency</p><p className="mt-1 font-medium text-white">{trace.latencyLabel}</p></div>
              <div><p className="text-muted">Tokens</p><p className="mt-1 font-medium text-white">{trace.tokenLabel}</p></div>
              <div><p className="text-muted">Cost</p><p className="mt-1 font-medium text-white">{trace.costLabel}</p></div>
            </div>
          </div>
        ))}
        <MiniLink label="View all traces" onClick={onOpen} />
      </div>
    </Panel>
  )
}

function CapabilityPanel({ title, description, icon: Icon, onOpen }: { title: string; description: string; icon: LucideIcon; onOpen?: () => void }) {
  return (
    <Panel className="flex h-full min-h-[140px] items-center gap-3 p-4">
      <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-border bg-background/70 text-slate-300"><Icon className="h-4 w-4" /></span>
      <div className="min-w-0">
        <h3 className="text-sm font-semibold text-white">{title}</h3>
        <p className="mt-1 text-xs leading-5 text-muted">{description}</p>
        {onOpen && <div className="mt-2"><MiniLink label="Open" onClick={onOpen} /></div>}
      </div>
    </Panel>
  )
}

export function DashboardDataState({ model, onNavigate }: { model: DashboardViewModel; onNavigate: (segment: string) => void }) {
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-6">
        {model.metrics.map((metric) => <MetricCard key={metric.label} metric={metric} />)}
      </div>

      {model.isExecutionEmpty ? (
        <EmptyExecutionState />
      ) : (
        <div className="grid grid-cols-1 gap-4 xl:grid-cols-12">
          <div className="xl:col-span-5"><RuntimeChart model={model} /></div>
          <div className="xl:col-span-4"><LatencyChart model={model} /></div>
          <div className="xl:col-span-3"><EnvironmentComposition model={model} /></div>
        </div>
      )}

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-12">
        <div className="xl:col-span-5"><AgentReleases model={model} onOpen={() => onNavigate(dashboardRowTarget('release'))} /></div>
        <div className="xl:col-span-4"><KnowledgeBase model={model} onOpen={() => onNavigate('knowledge')} /></div>
        <div className="xl:col-span-3"><ToolsIntegrations model={model} onOpen={() => onNavigate('tools')} /></div>
      </div>

      <RecentTraces model={model} onOpen={() => onNavigate(dashboardRowTarget('trace'))} />

      {(model.capabilities.sessions_jobs || model.capabilities.ingestion_pipeline || model.capabilities.activity_feed) && (
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
          {model.capabilities.sessions_jobs && <CapabilityPanel title="Sessions & Jobs" description="This deployment exposes session and job diagnostics in the dedicated runtime view." icon={Users} />}
          {model.capabilities.ingestion_pipeline && <CapabilityPanel title="Ingestion Pipeline" description="Ingestion pipeline diagnostics are available without substituting dashboard data." icon={Workflow} onOpen={() => onNavigate('knowledge')} />}
          {model.capabilities.activity_feed && <CapabilityPanel title="Recent Activity" description="Activity feed capability is enabled for this project." icon={Activity} />}
        </div>
      )}
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
    <div className="h-full overflow-y-auto scrollbar-thin">
      <div className="min-w-0 space-y-5 pb-6 pr-1">
        <header className="rounded-xl border border-border/80 bg-surface/50 p-5">
          <div className="flex flex-col gap-5 xl:flex-row xl:items-start xl:justify-between">
            <div className="min-w-0">
              <h1 className="text-2xl font-semibold tracking-tight text-white">Project Overview</h1>
              <p className="mt-1 max-w-3xl text-sm text-muted">Live runtime health, release state and project operations.</p>
              {model && <p className="mt-2 text-xs text-muted">Interval: {model.intervalLabel} · {model.timezoneLabel} · Last refreshed {model.generatedAtLabel}</p>}
            </div>

            <div className="flex flex-col gap-3 lg:flex-row lg:items-center xl:justify-end">
              <label className="sr-only" htmlFor="dashboard-range">Dashboard range</label>
              <select
                id="dashboard-range"
                value={range}
                onChange={(event: ChangeEvent<HTMLSelectElement>) => setRange(event.target.value as DashboardRangePreset)}
                className="h-9 rounded-lg border border-border bg-background/70 px-3 text-sm text-slate-300 outline-none transition-colors focus:ring-1 focus:ring-primary/60"
              >
                {RANGES.map((item) => <option key={item} value={item}>{rangeLabel(item)}</option>)}
              </select>

              <div className="flex max-w-full overflow-x-auto rounded-lg border border-border bg-background/50 p-1 scrollbar-thin">
                {ENVIRONMENTS.map((item) => (
                  <button
                    type="button"
                    key={item.value}
                    onClick={() => setEnvironment(item.value)}
                    aria-pressed={environment === item.value}
                    className={`flex h-7 items-center gap-1.5 whitespace-nowrap rounded-md border px-3 text-xs font-medium transition-colors ${environment === item.value ? item.tone : 'border-transparent text-muted hover:bg-surface hover:text-white'}`}
                  >
                    <span className={`h-1.5 w-1.5 rounded-full ${item.dot}`} />
                    {item.label}
                  </button>
                ))}
              </div>

              <button
                type="button"
                onClick={() => setWindowAnchor(new Date())}
                disabled={query.isFetching}
                className="inline-flex h-9 items-center justify-center gap-1.5 rounded-lg border border-border bg-background/70 px-3 text-sm font-medium text-slate-300 transition-colors hover:border-primary/35 hover:text-white disabled:opacity-50"
              >
                <RefreshCw className={`h-3.5 w-3.5 ${query.isFetching ? 'animate-spin' : ''}`} />
                Refresh
              </button>
            </div>
          </div>
        </header>

        {!projectId ? (
          <DashboardErrorState message="Project identifier is missing from the route." onRetry={() => window.location.reload()} />
        ) : query.isPending ? (
          <DashboardLoadingState />
        ) : query.isError ? (
          <DashboardErrorState message={query.error instanceof Error ? query.error.message : 'Unable to load project overview.'} onRetry={() => query.refetch()} />
        ) : model ? (
          <DashboardDataState model={model} onNavigate={goTo} />
        ) : (
          <DashboardErrorState message="The overview endpoint returned no data." onRetry={() => query.refetch()} />
        )}
      </div>
    </div>
  )
}
