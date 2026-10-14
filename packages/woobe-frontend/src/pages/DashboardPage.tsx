import { ProjectConfigurationNotice } from '@/features/projects/components/ProjectConfigurationNotice'
import { useMemo, useState } from 'react'
import type { ChangeEvent, KeyboardEvent, ReactNode } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import type { LucideIcon } from 'lucide-react'
import { Card, Dialog, PanelHeader as TechnicalPanelHeader } from '@woobe/ui'
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
  DashboardViewModel,
} from '@/features/dashboard/adapters'
import { RunActivityChart } from '@/features/dashboard/components/RunActivityChart'
import { useProjectOverview } from '@/features/dashboard/hooks'
import type { DashboardEnvironment, DashboardRangePreset } from '@/features/dashboard/types'
import { workspaceProjectPath } from '@/lib/constants/routes'

const ENVIRONMENTS: Array<{ value: DashboardEnvironment; label: string; tone: string; dot: string }> = [
  { value: 'all', label: 'All', tone: 'border-primary bg-primary text-primary-foreground', dot: 'bg-current' },
  { value: 'draft', label: 'Draft', tone: 'border-border bg-control text-foreground', dot: 'bg-slate-500' },
  { value: 'staging', label: 'Staging', tone: 'border-primary/30 bg-primary/10 text-primary-light', dot: 'bg-primary' },
  { value: 'production', label: 'Production', tone: 'border-emerald-500/35 bg-emerald-500/10 text-success', dot: 'bg-emerald-400' },
]

const RANGES: DashboardRangePreset[] = ['24h', '7d', '30d']
function Panel({ children, className = '' }: { children: ReactNode; className?: string }) {
  return <Card className={className}>{children}</Card>
}

function PanelHeader({ title, subtitle, action }: { title: string; subtitle?: string; action?: ReactNode }) {
  return <TechnicalPanelHeader title={title} description={subtitle} actions={action} hierarchy="section" className="border-0 bg-transparent [&_h2]:text-product-label" />
}

function StorySectionHeader({ title, description }: { title: string; description: string }) {
  return (
    <div className="pt-ui-sm">
      <h2 className="font-serif text-editorial-section font-normal text-foreground">{title}</h2>
      <p className="mt-ui-xs max-w-3xl text-product-caption text-muted-foreground">{description}</p>
    </div>
  )
}

function MiniLink({ label, onClick }: { label: string; onClick?: () => void }) {
  return (
    <button type="button" onClick={onClick} className="inline-flex items-center gap-1 text-xs font-medium text-primary-light transition-colors hover:text-foreground">
      {label}<ArrowRight className="h-3 w-3" />
    </button>
  )
}

function MetricCard({ metric, onReviewPricing, onNavigate }: { metric: DashboardMetric; onReviewPricing: () => void; onNavigate: (segment: string) => void }) {
  const [helpOpen, setHelpOpen] = useState(false)
  const destination = metric.label === 'Runtime Cost' ? 'usage' : 'traces'
  return <Panel className="flex min-w-0 flex-col p-ui-panel-inset">
    <div className="flex items-center justify-between gap-ui-sm">
      <h2 className="font-sans text-product-label font-medium text-foreground">
        <button type="button" onClick={() => onNavigate(destination)} title={destination === 'usage' ? 'Open Usage' : 'Open Run ledger'} className="inline-flex items-center gap-ui-xs rounded-control text-left hover:text-primary-light">
          {metric.label}<ArrowRight className="h-3 w-3 text-muted-foreground" aria-hidden="true" />
        </button>
      </h2>
      {metric.costHelp && <button type="button" aria-label="Runtime cost details" onClick={() => setHelpOpen(true)} className="flex h-control-xs w-control-xs shrink-0 items-center justify-center rounded-technical text-warning"><AlertCircle className="h-icon w-icon" aria-hidden="true" /></button>}
    </div>
    <p className="my-ui-sm break-words font-mono text-metric font-normal tabular-nums text-foreground">{metric.value}</p>
    <p className="text-product-caption text-muted-foreground">{metric.detail ?? 'No terminal Runs in this interval'}</p>
    {metric.change && <p className="mt-ui-xs text-product-caption text-foreground">{metric.change}</p>}
    {metric.costHelp && <Dialog open={helpOpen} onClose={() => setHelpOpen(false)} title="Runtime cost coverage" className="max-w-md">
      <p className="font-sans text-sm leading-6 text-muted-foreground">{metric.costHelp.description}</p>
      {metric.costHelp.reviewPricing && <div className="mt-4 space-y-3">
        <p className="font-sans text-xs leading-5 text-muted-foreground">For future Runs, configure both USD rates in Models, save the Agent Draft, then capture and deploy a new Candidate/Release for Staging or Production.</p>
        <MiniLink label="Review Model pricing" onClick={() => { setHelpOpen(false); onReviewPricing() }} />
      </div>}
    </Dialog>}
  </Panel>
}

function SkeletonPanel({ className = '' }: { className?: string }) {
  return <Panel className={`animate-pulse p-5 ${className}`}><div className="h-3 w-28 rounded-full bg-muted/15" /><div className="mt-5 h-20 rounded-xl bg-muted/15" /></Panel>
}

export function DashboardLoadingState() {
  return (
    <div aria-label="Loading project overview" className="space-y-4">
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">{Array.from({ length: 4 }, (_, index) => <SkeletonPanel key={index} className="min-h-[128px]" />)}</div>
      <div className="grid grid-cols-1 gap-4 xl:grid-cols-12"><SkeletonPanel className="min-h-[330px] xl:col-span-8" /><SkeletonPanel className="min-h-[330px] xl:col-span-4" /></div>
      <SkeletonPanel className="min-h-[120px]" />
      <div className="grid grid-cols-1 gap-4 xl:grid-cols-3"><SkeletonPanel className="min-h-[250px]" /><SkeletonPanel className="min-h-[250px]" /><SkeletonPanel className="min-h-[250px]" /></div>
    </div>
  )
}

export function DashboardErrorState({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <Panel className="flex min-h-[280px] flex-col items-center justify-center p-8 text-center">
      <XCircle className="h-10 w-10 text-error" />
      <h2 className="mt-3 text-base font-medium text-foreground">Overview unavailable</h2>
      <p className="mt-1 max-w-lg text-sm text-muted">{message}</p>
      <button type="button" onClick={onRetry} className="mt-5 inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary-dark"><RefreshCw className="h-4 w-4" />Retry</button>
    </Panel>
  )
}

function EmptyExecutionState() {
  return (
    <Panel className="flex min-h-[180px] flex-col items-center justify-center p-7 text-center">
      <Activity className="h-9 w-9 text-muted" />
      <h2 className="mt-3 text-sm font-medium text-foreground">No Agent Runs or Network Runs in this interval</h2>
      <p className="mt-1 max-w-lg text-xs leading-5 text-muted">The selected environment and time range returned no runtime activity.</p>
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
      <div className="flex h-1 overflow-hidden rounded-technical bg-background ring-1 ring-border/80">
        {group.terminalRuns === 0 ? <span className="h-full w-full bg-muted/20" /> : activeSegments.map((segment) => <span key={segment.key} title={`${segment.label}: ${segment.value}`} className={segment.className} style={{ width: `${(segment.value / denominator) * 100}%` }} />)}
      </div>
      {activeSegments.length > 1 && <div className="mt-2 flex flex-wrap gap-x-3 gap-y-1 text-system-meta text-muted">{activeSegments.map((segment) => <span key={segment.key} className="flex items-center gap-1"><span className={`h-1.5 w-1.5 rounded-full ${segment.className}`} />{segment.label} {segment.value}</span>)}</div>}
    </div>
  )
}

function ReliabilityGroupView({ group }: { group: DashboardReliabilityGroup }) {
  const errors = group.failed + group.timedOut + group.uncertain
  return <section className="space-y-ui-sm" aria-label={`${group.label} reliability`}>
    <div className="flex items-start justify-between gap-ui-md">
      <div><h3 className="text-product-label font-medium">{group.label === 'Network Runs' ? 'Network Run Success' : 'Agent Run Success'}</h3>
        <p className="mt-ui-xs text-product-caption text-muted-foreground"><span className="font-mono text-foreground">{group.successful} / {group.terminalRuns}</span> terminal Runs successful</p>
      </div>
      <p className={`font-mono text-xl font-normal ${errors > 0 ? 'text-warning' : 'text-foreground'}`}>{formatPercent(group.successRate)}</p>
    </div>
    <ReliabilityDistribution group={group} />
    <p className="text-product-caption text-muted-foreground">{group.running} running or queued · {group.cancelled} cancelled{group.completedWithIssues > 0 ? ` · ${group.completedWithIssues} completed with issues` : ''}</p>
    <dl className="grid grid-cols-3 gap-ui-sm">
      {[
        ['Error rate', formatPercent(group.errorRate)],
        ['Average duration', group.averageDurationLabel],
        ['p95 duration', group.p95DurationLabel],
      ].map(([label, value]) => <div key={label}><dt className="text-product-caption text-muted-foreground">{label}</dt><dd className="mt-ui-xs font-mono text-product-caption text-foreground">{value}</dd></div>)}
    </dl>
    {errors > 0 && <p className="text-product-caption text-error">{group.failed} failed · {group.timedOut} timed out · {group.uncertain} uncertain</p>}
  </section>
}

function ReliabilityPanel({ model }: { model: DashboardViewModel }) {
  return <Panel className="h-full">
    <PanelHeader title="Reliability & Performance" />
    <div className="space-y-ui-xl px-ui-panel-inset pb-ui-panel-inset">
      <ReliabilityGroupView group={model.reliability.agent} />
      <ReliabilityGroupView group={model.reliability.network} />
      <p className="text-product-caption text-muted-foreground">Success is completed / terminal Runs. Running Runs are excluded. Average Run Time and p95 describe recorded terminal durations; p95 is the duration not exceeded by 95% of those measurements.</p>
    </div>
  </Panel>
}

function OperationalIssues({ model, onNavigate, onOpenRun }: { model: DashboardViewModel; onNavigate: (segment: string) => void; onOpenRun: (run: DashboardRunRow) => void }) {
  if (!model.issues.hasIssues) return model.isExecutionEmpty ? null : <p className="text-product-small text-muted-foreground">No failed, timed out or uncertain Runs recorded in this interval.</p>
  const recentError = model.runs.find(run => ['Failed', 'Timed out', 'Uncertain'].includes(run.statusLabel))
  return <Panel className="border-error/30 p-ui-md">
    <div className="flex flex-wrap items-start justify-between gap-ui-md">
      <div className="flex min-w-0 items-start gap-ui-sm">
        <AlertTriangle className="mt-0.5 h-icon w-icon shrink-0 text-error" aria-hidden="true" />
        <div><h3 className="text-product-label font-medium">Execution errors</h3><p className="mt-ui-xs text-product-small text-error">{model.issues.summary.join(' · ')}</p></div>
      </div>
      <div className="flex flex-wrap gap-ui-md">
        {recentError && <MiniLink label="Open recent error Run" onClick={() => onOpenRun(recentError)} />}
        <MiniLink label="Open Run ledger" onClick={() => onNavigate('traces')} />
      </div>
    </div>
    <div className="mt-ui-md flex flex-wrap gap-x-ui-xl gap-y-ui-sm text-product-caption">
      {([...model.issues.topAgents.map(item => ({ ...item, kind: 'agent' })), ...model.issues.topNetworks.map(item => ({ ...item, kind: 'network' }))]).map(item =>
        <span key={`${item.kind}-${item.entity_id}-${item.name}`} className="inline-flex flex-wrap items-center gap-ui-xs">
          <span className="text-muted-foreground">{item.kind === 'agent' ? 'Agent' : 'Network'}</span>
          {item.entity_id ? <MiniLink label={item.name} onClick={() => onNavigate(item.kind === 'agent' ? `agents/${item.entity_id}/playground` : `networks/${item.entity_id}`)} /> : <span>{item.name}</span>}
          <span className="font-mono text-error">{item.failure_count}</span>
        </span>)}
      {model.issues.topCodes.map(item => <span key={item.code} className="min-w-0 break-words"><span className="font-mono text-error">{item.code}</span> <span className="font-mono">({item.failure_count})</span></span>)}
      {model.issues.peakLabel && <span className="text-muted-foreground">Peak interval starts <span className="font-mono text-foreground">{model.issues.peakLabel}</span> · {model.issues.peakCount} errors</span>}
    </div>
  </Panel>
}

function EnvironmentBadge({ value }: { value: string }) {
  const normalized = value.toLowerCase()
  const classes = normalized === 'production' ? 'border-emerald-500/40 bg-emerald-500/10 text-success' : normalized === 'staging' ? 'border-amber-500/40 bg-amber-500/10 text-warning' : 'border-blue-500/40 bg-blue-500/10 text-primary-light'
  return <span className={`inline-flex rounded-md border px-2 py-0.5 text-xs font-medium ${classes}`}>{value}</span>
}

function StatusBadge({ value }: { value: string }) {
  const classes = value === 'Completed' ? 'border-emerald-500/40 bg-emerald-500/10 text-success' : value === 'Running' || value === 'Queued' ? 'border-blue-500/40 bg-blue-500/10 text-primary-light' : value === 'Completed with issues' || value === 'Uncertain' ? 'border-amber-500/40 bg-amber-500/10 text-warning' : 'border-red-500/40 bg-red-500/10 text-error'
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
      <span className={`flex h-9 w-9 items-center justify-center rounded-xl border border-border bg-surface ${change.resourceType === 'agent' ? 'text-primary-light' : 'text-network'}`}><Icon className="h-4 w-4" /></span>
      <span className="min-w-0"><span className="flex flex-wrap items-center gap-2"><b className="truncate text-sm text-foreground">{change.resourceName}</b><span className="rounded-md border border-border bg-surface px-2 py-0.5 text-system-meta text-slate-300">{change.resourceLabel}</span><EnvironmentBadge value={change.environmentLabel} /></span><span className="mt-1 block text-xs text-slate-300">{change.actionLabel}{change.versionLabel ? ` · ${change.versionLabel}` : ''}</span><span className="mt-1 block truncate text-xs text-muted">{change.description}</span></span>
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
      <div className="grid flex-1 grid-cols-1 sm:grid-cols-2">
        {rows.map(([label, value], index) => {
          const isLast = index === rows.length - 1
          return (
            <div
              key={label}
              className={`flex min-h-10 items-center justify-between gap-3 border-b border-border/60 px-4 py-2.5 ${!isLast && index % 2 === 0 ? 'sm:border-r' : ''} ${isLast ? 'sm:col-span-2' : ''}`}
            >
              <span className="min-w-0 truncate font-sans text-product-caption text-muted-foreground">{label}</span>
              <span className="shrink-0 font-mono text-xs font-medium tabular-nums text-slate-50">{value}</span>
            </div>
          )
        })}
      </div>
    </Panel>
  )
}

function KnowledgeBase({ model, onOpen }: { model: DashboardViewModel; onOpen: () => void }) {
  const entries: Array<{ label: string; value: string; icon: LucideIcon; tone: string }> = [
    { label: 'Collections', value: model.knowledge.collections, icon: Layers3, tone: 'text-primary-light' },
    { label: 'Documents', value: model.knowledge.documents, icon: FileText, tone: 'text-primary-light' },
    { label: 'Indexed', value: model.knowledge.indexed, icon: CheckCircle2, tone: 'text-success' },
    { label: 'Pending', value: model.knowledge.pending, icon: Sparkles, tone: 'text-warning' },
    { label: 'Failed', value: model.knowledge.failed, icon: XCircle, tone: 'text-error' },
    { label: 'Storage', value: model.knowledge.storage, icon: Database, tone: 'text-network' },
  ]
  return (
    <Panel className="flex h-full min-h-[230px] flex-col overflow-hidden">
      <PanelHeader title="Knowledge" />
      <div className="grid flex-1 grid-cols-2">
        {entries.map((entry, index) => {
          const Icon = entry.icon
          return (
            <div key={entry.label} className={`min-h-[62px] border-b border-border/60 px-4 py-3 ${index % 2 === 0 ? 'border-r' : ''}`}>
              <div className="flex min-w-0 items-center gap-2">
                <Icon className={`h-3.5 w-3.5 shrink-0 ${entry.tone}`} />
                <p className="truncate font-sans text-product-caption text-muted-foreground">{entry.label}</p>
              </div>
              <p className={`mt-1.5 truncate font-mono text-base font-medium leading-none tabular-nums ${entry.tone}`}>{entry.value}</p>
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
    { label: 'Tools', value: model.tools.total, icon: Wrench, tone: 'text-primary-light' },
    { label: 'Active', value: model.tools.active, icon: CheckCircle2, tone: 'text-success' },
    { label: 'Inactive', value: model.tools.inactive, icon: Workflow, tone: 'text-slate-400' },
    { label: 'Recent failures', value: String(model.tools.recentFailures), icon: XCircle, tone: model.tools.recentFailures > 0 ? 'text-error' : 'text-slate-400' },
  ]
  return (
    <Panel className="flex h-full min-h-[230px] flex-col overflow-hidden">
      <PanelHeader title="Tools" />
      <div className="flex-1">
        {items.map((item) => {
          const Icon = item.icon
          return (
            <div key={item.label} className="flex min-h-10 items-center justify-between gap-3 border-b border-border/60 px-4 py-2.5">
              <span className="flex min-w-0 items-center gap-2 font-sans text-product-caption text-muted-foreground">
                <Icon className={`h-3.5 w-3.5 shrink-0 ${item.tone}`} />
                <span className="truncate">{item.label}</span>
              </span>
              <span className={`shrink-0 font-mono text-xs font-medium tabular-nums ${item.tone}`}>{item.value}</span>
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
    <Panel className="overflow-hidden" >
      <PanelHeader title="Recent Runs" action={<MiniLink label="View all Runs" onClick={onViewAll} />} />
      <div className="px-5 pb-5">
        {model.runs.length === 0 ? <p className="py-6 text-center text-sm text-muted">No Runs in this interval.</p> : (
          <div className="space-y-2">
            <div className="hidden grid-cols-[104px_minmax(120px,1fr)_110px_110px_180px_75px_100px] gap-3 px-3 text-system-meta font-medium uppercase tracking-wide text-muted xl:grid"><span>Type</span><span>Name</span><span>Environment</span><span>Status</span><span>Started</span><span className="text-right">Duration</span><span className="text-right">Cost</span></div>
            {model.runs.map((run) => {
              const open = () => onOpen(run)
              return (
                <div key={`${run.kind}-${run.id}`} role="link" tabIndex={0} onClick={open} onKeyDown={(event) => keyboardActivate(event, open)} className="grid cursor-pointer gap-3 rounded-xl border border-border/80 bg-background/45 p-3 outline-none transition-colors hover:border-primary/25 hover:bg-background/75 focus:ring-1 focus:ring-primary/60 xl:grid-cols-[104px_minmax(120px,1fr)_110px_110px_180px_75px_100px] xl:items-center">
                  <div><span className="inline-flex whitespace-nowrap rounded-md border border-border bg-surface px-2 py-0.5 text-xs font-medium text-slate-200">{run.typeLabel}</span></div>
                  <div className="min-w-0"><p className="font-mono truncate text-sm font-medium text-foreground">{run.title}</p><p className="mt-1 truncate text-xs text-muted">{run.sourceLabel}</p></div>
                  <div><EnvironmentBadge value={run.environmentLabel} /></div>
                  <div><StatusBadge value={run.statusLabel} /></div>
                  <p className="font-mono text-xs text-muted">{run.timeLabel}</p>
                  <p className="font-mono text-xs font-medium text-foreground xl:text-right">{run.durationLabel}</p>
                  <div className="min-w-0 xl:text-right"><p className="font-mono truncate text-xs font-medium text-foreground">{run.costLabel}</p>{run.costDetail && <p className="font-mono mt-1 truncate text-system-meta text-warning" title={run.costDetail}>{run.costDetail}</p>}</div>
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
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">{model.metrics.map((metric) => <MetricCard key={metric.label} metric={metric} onReviewPricing={() => onNavigate('models')} onNavigate={onNavigate} />)}</div>

      <StorySectionHeader title="What happened" description="Volume, reliability, performance, and cost in the selected period." />
      <OperationalIssues model={model} onNavigate={onNavigate} onOpenRun={onOpenRun} />
      <div className="grid grid-cols-1 items-start gap-4 xl:grid-cols-12"><div className="xl:col-span-8">{model.isExecutionEmpty ? <EmptyExecutionState /> : <RunActivityChart model={model} />}</div><div className="xl:col-span-4"><ReliabilityPanel model={model} /></div></div>
      <RecentRuns model={model} onOpen={onOpenRun} onViewAll={() => onNavigate('traces')} />

      <StorySectionHeader title="What changed" description="Configuration and release activity for the selected environment and period." />
      <ChangesInPeriod model={model} environment={environment} onNavigate={onNavigate} />

      <StorySectionHeader title="Current Project State" description="Current deployable resources. Knowledge and Tools are Project-wide, not historical environment snapshots." />
      <div className="grid grid-cols-1 items-stretch gap-4 xl:grid-cols-3"><RuntimeAssets model={model} /><KnowledgeBase model={model} onOpen={() => onNavigate('knowledge')} /><ToolsIntegrations model={model} onOpen={() => onNavigate('tools')} /></div>

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
    <div className="min-h-full">
      <div className="min-w-0 space-y-ui-lg pb-ui-xxl" aria-busy={isUpdating}>
        <header className="relative pb-ui-sm">
          {isUpdating && <div className="absolute inset-x-0 top-0 h-0.5 animate-pulse bg-primary/70" />}
          <div className="flex flex-col gap-5 xl:flex-row xl:items-start xl:justify-between">
            <div className="min-w-0">
              <div className="flex items-center gap-2"><h1 className="font-serif text-page-title font-normal text-foreground">Project Overview</h1>{isUpdating && <span className="rounded-full border border-primary/20 bg-primary/5 px-2 py-0.5 text-system-meta text-primary-light">Updating {environmentLabel(environment)} overview…</span>}</div>
              {model && <p className="mt-ui-sm text-product-caption text-muted">Interval: {model.intervalLabel} · {model.timezoneLabel} · Last refreshed {model.generatedAtLabel}</p>}
            </div>
            <div className="flex flex-col gap-3 md:flex-row md:flex-wrap md:items-center xl:flex-nowrap xl:justify-end">
              <label className="sr-only" htmlFor="dashboard-range">Dashboard range</label>
              <select id="dashboard-range" value={range} onChange={(event: ChangeEvent<HTMLSelectElement>) => setRange(event.target.value as DashboardRangePreset)} className="h-9 rounded-lg border border-border bg-background/70 px-3 text-sm text-slate-300 outline-none transition-colors focus:ring-1 focus:ring-primary/60">{RANGES.map((item) => <option key={item} value={item}>{rangeLabel(item)}</option>)}</select>
              <div className="flex max-w-full overflow-x-auto rounded-lg border border-border bg-background/50 p-1 scrollbar-thin">{ENVIRONMENTS.map((item) => <button type="button" key={item.value} onClick={() => setEnvironment(item.value)} aria-pressed={environment === item.value} className={`flex h-7 items-center gap-1.5 whitespace-nowrap rounded-md border px-3 text-xs font-medium transition-colors ${environment === item.value ? item.tone : 'border-transparent text-muted hover:bg-surface hover:text-foreground'}`}><span className={`h-1.5 w-1.5 rounded-full ${item.dot}`} />{item.label}</button>)}</div>
              <button type="button" onClick={() => void query.refetch()} disabled={query.isFetching} className="inline-flex h-9 items-center justify-center gap-1.5 rounded-lg border border-border bg-background/70 px-3 text-sm font-medium text-slate-300 transition-colors hover:border-primary/35 hover:text-foreground disabled:opacity-50"><RefreshCw className={`h-3.5 w-3.5 ${query.isFetching ? 'animate-spin' : ''}`} />Refresh</button>
            </div>
          </div>
        </header>

        {projectId && <ProjectConfigurationNotice key={projectId} projectId={projectId} workspaceId={workspaceId} environment={environment === 'all' ? undefined : environment} />}

        {query.isError && model && <div className="rounded-lg border border-amber-500/20 bg-amber-500/5 px-4 py-2 text-xs text-warning">The latest refresh failed. Showing the last available Overview data.</div>}

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
