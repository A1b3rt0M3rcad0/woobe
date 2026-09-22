import { operationCountsLabel, operationEventLabel } from '@/features/skills/operations'
import { ToolCallsCollapsible } from '@/features/playground/components/ToolCallsCollapsible'
import { useMemo, useState } from 'react'
import { useParams } from 'react-router-dom'
import {
  Activity,
  Bot,
  ChevronDown,
  ChevronRight,
  Clock3,
  Cpu,
  Database,
  Network,
  Route,
  TriangleAlert,
} from 'lucide-react'
import { Button, Select } from '@woobe/ui'

import { ErrorState } from '@/components/common/ErrorState'
import { LoadingState } from '@/components/common/LoadingState'
import { ResourcePill } from '@/components/common/OperationalResourceCard'
import {
  ResourceEmptyState,
  ResourcePage,
  ResourceSearch,
  ResourceSectionHeader,
  ResourceTabs,
  ResourceToolbar,
} from '@/components/common/ResourcePage'
import { JsonCodeBlock } from '@/components/ui/JsonCodeBlock'
import { useAgents } from '@/features/agents/hooks'
import { useNetworks } from '@/features/network/hooks'
import { useOptionalTraceDetail, useProjectRuns } from '@/features/traces/hooks'
import type {
  ProjectAgentRunRecord,
  ProjectNetworkRunRecord,
  Trace,
  TraceDetail,
  TraceEvent,
} from '@/features/traces/types'
import { formatDateTime } from '@/lib/formatters/date'
import { formatMoney } from '@/lib/formatters/money'
import { formatLatency, formatTokens } from '@/lib/formatters/number'
import { cn } from '@/lib/utils'

type RunTypeFilter = 'all' | 'network' | 'agent'
type StatusFilter = 'all' | 'running' | 'completed' | 'failed' | 'cancelled'
type RunStatus = 'pending' | 'running' | 'completed' | 'completed_with_issues' | 'failed' | 'cancelled'
type InspectorTone = 'default' | 'focus' | 'muted'

type TimelineItem = {
  id: string
  label: string
  phase: string
  status: string
  startedAt: number
  endedAt: number
  durationMs: number
  payload: Record<string, unknown>
}

type NetworkRunGroup = {
  id: string
  networkId: string | null
  networkName: string
  traces: Trace[]
  status: RunStatus
  startedAt: string | null
  endedAt: string | null
  durationMs: number | null
  costUsd: number | null
  environment: string | null
  versionLabel: string | null
  inputPreview: string | null
}

type RunEntry =
  | { key: string; kind: 'network'; group: NetworkRunGroup; sortAt: number }
  | { key: string; kind: 'agent'; trace: Trace; sortAt: number }

const panelScrollClass = 'scrollbar-thin scrollbar-track-transparent scrollbar-thumb-border hover:scrollbar-thumb-muted [scrollbar-color:rgb(51_65_85)_transparent] [scrollbar-width:thin] [&::-webkit-scrollbar]:w-2 [&::-webkit-scrollbar-track]:bg-transparent [&::-webkit-scrollbar-thumb]:rounded-sm [&::-webkit-scrollbar-thumb]:border-2 [&::-webkit-scrollbar-thumb]:border-transparent [&::-webkit-scrollbar-thumb]:bg-border/70 [&::-webkit-scrollbar-thumb]:bg-clip-padding hover:[&::-webkit-scrollbar-thumb]:bg-muted'
const runRowGridClass = 'xl:grid-cols-[32px_minmax(0,1.45fr)_minmax(0,.9fr)_140px_145px_20px]'

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : {}
}

function asString(value: unknown): string | null {
  return typeof value === 'string' && value.trim() ? value : null
}

function asNumber(value: unknown): number | null {
  if (typeof value === 'number' && Number.isFinite(value)) return value
  if (typeof value === 'string' && value.trim()) {
    const parsed = Number(value)
    return Number.isFinite(parsed) ? parsed : null
  }
  return null
}

function compactId(value: string) {
  return value.length > 12 ? `${value.slice(0, 8)}…` : value
}

function traceData(trace: Trace): Record<string, unknown> {
  return asRecord(trace.data)
}

function runDurationMs(run: ProjectAgentRunRecord): number | null {
  const start = timestamp(run.started_at ?? run.created_at)
  const end = timestamp(run.completed_at)
  if (start && end && end >= start) return end - start
  const diagnostics = asRecord(asRecord(run.result).diagnostics)
  return asNumber(
    diagnostics.agent_runtime_latency_ms
      ?? diagnostics.total_latency_ms
      ?? asRecord(run.result).latency_ms,
  )
}

function agentRunToTrace(
  run: ProjectAgentRunRecord,
  network?: ProjectNetworkRunRecord,
): Trace {
  const result = asRecord(run.result)
  const usage = asRecord(run.usage ?? result.usage)
  return {
    id: run.trace_id,
    project_id: run.project_id,
    agent_id: run.agent_id,
    session_id: run.session_id ?? undefined,
    network_id: network?.network_id ?? null,
    network_execution_id: run.network_execution_id,
    network_session_id: network?.network_session_id ?? null,
    network_version_id: network?.network_version_id ?? null,
    status: run.status,
    provider: asString(result.provider) ?? undefined,
    model: asString(result.model) ?? undefined,
    fallback_used: Boolean(asRecord(result.diagnostics).fallback_used ?? result.fallback_used),
    total_latency_ms: runDurationMs(run) ?? undefined,
    total_cost_usd: asNumber(usage.cost_usd ?? result.cost_usd),
    error: run.failure_detail ?? run.failure_code ?? undefined,
    data: {
      ...result,
      agent_run_id: run.id,
      input_message: run.input_message,
      execution_context: run.environment,
      input_tokens: asNumber(usage.input_tokens),
      output_tokens: asNumber(usage.output_tokens),
      total_tokens: asNumber(usage.total_tokens),
      cost_usd: asNumber(usage.cost_usd ?? result.cost_usd),
    },
    started_at: run.started_at,
    ended_at: run.completed_at,
    created_at: run.created_at ?? run.started_at ?? undefined,
  }
}

function traceStartedAt(trace: Trace): string | null {
  const raw = trace as Trace & { started_at?: string | null }
  return raw.started_at ?? trace.created_at ?? null
}

function traceEndedAt(trace: Trace): string | null {
  const raw = trace as Trace & { ended_at?: string | null }
  return raw.ended_at ?? null
}

function timestamp(value: string | null | undefined): number {
  if (!value) return 0
  const parsed = new Date(value).getTime()
  return Number.isFinite(parsed) ? parsed : 0
}

function normalizedStatus(status: string): RunStatus {
  const value = status.toLowerCase()
  if (value === 'running' || value === 'processing') return 'running'
  if (value === 'pending' || value === 'queued') return 'pending'
  if (value === 'failed' || value === 'error' || value === 'timed_out' || value === 'uncertain') return 'failed'
  if (value === 'cancelled' || value === 'canceled') return 'cancelled'
  return 'completed'
}

function statusMatches(status: RunStatus, filter: StatusFilter) {
  if (filter === 'all') return true
  if (filter === 'running') return status === 'running' || status === 'pending'
  if (filter === 'completed') return status === 'completed' || status === 'completed_with_issues'
  return status === filter
}

function environmentLabel(trace: Trace): string | null {
  const data = traceData(trace)
  return asString(data.execution_context) ?? asString(data.environment)
}

function versionLabel(trace: Trace): string | null {
  const data = traceData(trace)
  const agentVersion = asString(data.agent_release_version)
  if (agentVersion) return `Agent ${agentVersion}`
  if (trace.network_version_id) return `Network ${compactId(trace.network_version_id)}`
  const draftRevision = asNumber(data.draft_revision)
  return draftRevision == null ? null : `Draft r${draftRevision}`
}

function inputPreview(trace: Trace): string | null {
  const data = traceData(trace)
  return asString(data.message_preview)
    ?? asString(data.message)
    ?? asString(data.input_preview)
    ?? asString(data.input_message)
}

function traceSearchText(trace: Trace, agentName?: string | null, networkName?: string | null) {
  const data = traceData(trace)
  return [
    trace.id,
    trace.status,
    trace.agent_id,
    trace.session_id,
    trace.network_id,
    trace.network_execution_id,
    trace.network_session_id,
    trace.network_version_id,
    trace.provider,
    trace.model,
    agentName,
    networkName,
    inputPreview(trace),
    asString(data.agent_release_version),
    asString(data.execution_context),
  ].filter(Boolean).join(' ').toLowerCase()
}

function knownCostSum(traces: Trace[]): number | null {
  if (!traces.length || traces.some((trace) => trace.total_cost_usd == null)) return null
  return traces.reduce((total, trace) => total + (trace.total_cost_usd ?? 0), 0)
}

function statusMeta(status: RunStatus) {
  if (status === 'running' || status === 'pending') return { label: status === 'pending' ? 'Queued' : 'Running', className: 'border-blue-500/30 bg-blue-500/[0.08] text-blue-300', dot: 'bg-blue-400 animate-pulse', accent: 'border-l-blue-400' }
  if (status === 'failed') return { label: 'Failed', className: 'border-red-500/25 bg-red-500/[0.06] text-red-300', dot: 'bg-red-400', accent: 'border-l-red-400' }
  if (status === 'completed_with_issues') return { label: 'Completed with issues', className: 'border-amber-500/25 bg-amber-500/[0.06] text-amber-200', dot: 'bg-amber-400', accent: 'border-l-amber-400' }
  if (status === 'cancelled') return { label: 'Cancelled', className: 'border-border bg-control/60 text-muted-foreground', dot: 'bg-slate-400', accent: 'border-l-slate-500' }
  return { label: 'Completed', className: 'border-emerald-500/25 bg-emerald-500/[0.06] text-emerald-300', dot: 'bg-emerald-400', accent: 'border-l-emerald-400' }
}

function RunStatusBadge({ status }: { status: RunStatus }) {
  const meta = statusMeta(status)
  return (
    <span className={cn('inline-flex h-[22px] items-center gap-1.5 rounded-technical border px-2 font-mono text-[8px] font-medium', meta.className)}>
      <span className={cn('h-1.5 w-1.5 rounded-full', meta.dot)} />
      {meta.label}
    </span>
  )
}

function MetricCard({ label, value, detail }: { label: string; value: string; detail: string }) {
  return (
    <div className="border border-border bg-surface/[0.9] px-3.5 py-3 shadow-[inset_0_1px_0_rgba(255,255,255,0.012)]">
      <p className="font-mono text-[8px] font-semibold uppercase tracking-[0.11em] text-muted-foreground">{label}</p>
      <p className="mt-1.5 font-mono text-lg font-bold tabular-nums tracking-tight text-slate-50">{value}</p>
      <p className="mt-1 font-mono text-[8px] leading-4 text-muted-foreground">{detail}</p>
    </div>
  )
}

function RunTreeSlot({ nested, isLastNested }: { nested: boolean; isLastNested: boolean }) {
  return (
    <span aria-hidden className="relative hidden h-full min-h-10 w-8 xl:block">
      {nested ? (
        <>
          <span className={cn('absolute left-1/2 top-0 w-px -translate-x-1/2 bg-border/70', isLastNested ? 'h-1/2' : 'h-full')} />
          <span className="absolute left-1/2 top-1/2 h-px w-1/2 bg-border/70" />
        </>
      ) : null}
    </span>
  )
}

function AgentRunRow({ trace, agentName, networkName, selected, nested = false, isLastNested = false, onSelect }: {
  trace: Trace
  agentName: string
  networkName?: string | null
  selected: boolean
  nested?: boolean
  isLastNested?: boolean
  onSelect: () => void
}) {
  const data = traceData(trace)
  const llmCalls = asNumber(data.llm_call_count ?? asRecord(data.diagnostics).llm_call_count)
  const toolCalls = asNumber(data.tool_call_count ?? asRecord(data.diagnostics).tool_call_count)
  const status = normalizedStatus(trace.status)
  const preview = inputPreview(trace)
  const environment = environmentLabel(trace)
  const version = versionLabel(trace)

  return (
    <button
      type="button"
      onClick={onSelect}
      className={cn(
        'group grid w-full gap-3 border-b border-border/70 px-3.5 py-3 text-left transition-colors last:border-b-0 hover:bg-control/35 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-primary/35 xl:items-center',
        runRowGridClass,
        nested && 'bg-background/20',
        selected && 'bg-primary/[0.08] hover:bg-primary/[0.08]',
      )}
    >
      <RunTreeSlot nested={nested} isLastNested={isLastNested} />
      <div className="min-w-0">
        <div className="flex flex-wrap items-center gap-2">
          <Bot className="h-3.5 w-3.5 text-primary-light" />
          <span className="truncate font-mono text-[10px] font-medium text-slate-100">{agentName}</span>
          <ResourcePill>Agent Run</ResourcePill>
          {!nested && networkName ? <ResourcePill tone="primary">{networkName}</ResourcePill> : null}
          {trace.fallback_used ? <ResourcePill tone="primary">Fallback</ResourcePill> : null}
        </div>
        <p className="mt-1 truncate font-sans text-[10px] text-muted-foreground">{preview ?? `Run ${compactId(trace.id)}`}</p>
      </div>
      <div className="min-w-0 font-mono text-[9px] leading-4 text-muted-foreground">
        <p className="truncate text-slate-300">{environment ?? 'Environment not recorded'}{version ? ` · ${version}` : ''}</p>
        <p className="truncate">{trace.provider || 'Provider unknown'} / {trace.model || 'Model unknown'}</p>
        {(llmCalls != null || toolCalls != null) ? <p>{llmCalls ?? 0} LLM · {toolCalls ?? 0} Tool/Skill operations</p> : null}
      </div>
      <RunStatusBadge status={status} />
      <div className="font-mono xl:text-right">
        <p className="text-[10px] font-medium text-slate-100">{formatLatency(trace.total_latency_ms)}</p>
        <p className="mt-0.5 text-[8px] text-muted-foreground">{trace.total_cost_usd == null ? 'Cost unknown' : formatMoney(trace.total_cost_usd)}</p>
        <p className="mt-0.5 text-[8px] text-muted-foreground">{traceStartedAt(trace) ? formatDateTime(traceStartedAt(trace)!) : '—'}</p>
      </div>
      <ChevronRight className={cn('hidden h-3.5 w-3.5 text-muted-foreground transition-transform group-hover:translate-x-0.5 group-hover:text-primary-light xl:block', selected && 'text-primary-light')} />
    </button>
  )
}

function NetworkRunRow({ group, agentNames, selectedKey, expanded, onToggle, onSelectNetwork, onSelectAgent }: {
  group: NetworkRunGroup
  agentNames: Map<string, string>
  selectedKey: string | null
  expanded: boolean
  onToggle: () => void
  onSelectNetwork: () => void
  onSelectAgent: (trace: Trace) => void
}) {
  const failedChildren = group.traces.filter((trace) => normalizedStatus(trace.status) === 'failed').length
  const toolCalls = group.traces.reduce((total, trace) => total + (asNumber(traceData(trace).tool_call_count ?? asRecord(traceData(trace).diagnostics).tool_call_count) ?? 0), 0)
  const sortedTraces = group.traces.slice().sort((left, right) => timestamp(traceStartedAt(left)) - timestamp(traceStartedAt(right)))

  return (
    <div className="border-b border-border/75 last:border-b-0">
      <div className={cn('grid gap-3 px-3.5 py-3 transition-colors hover:bg-control/35 xl:items-center', runRowGridClass, selectedKey === `network:${group.id}` && 'bg-primary/[0.08] hover:bg-primary/[0.08]')}>
        <button type="button" onClick={onToggle} className="flex h-7 w-7 items-center justify-center rounded-control border border-border bg-control/70 text-muted-foreground hover:border-slate-600 hover:text-slate-100" aria-label={expanded ? 'Collapse Network Run' : 'Expand Network Run'} aria-expanded={expanded}>
          {expanded ? <ChevronDown className="h-3.5 w-3.5" /> : <ChevronRight className="h-3.5 w-3.5" />}
        </button>
        <button type="button" onClick={onSelectNetwork} className="min-w-0 text-left focus-visible:outline-none">
          <div className="flex flex-wrap items-center gap-2"><Network className="h-3.5 w-3.5 text-violet-300" /><span className="truncate font-mono text-[10px] font-medium text-slate-100">{group.networkName}</span><ResourcePill tone="primary">Network Run</ResourcePill></div>
          <p className="mt-1 truncate font-sans text-[10px] text-muted-foreground">{group.inputPreview ?? `Execution ${compactId(group.id)}`}</p>
        </button>
        <button type="button" onClick={onSelectNetwork} className="min-w-0 text-left font-mono text-[9px] leading-4 text-muted-foreground focus-visible:outline-none">
          <p className="truncate text-slate-300">{group.environment ?? 'Environment not recorded'}{group.versionLabel ? ` · ${group.versionLabel}` : ''}</p>
          <p>{group.traces.length} Agent Run{group.traces.length === 1 ? '' : 's'} · {toolCalls} Tool/Skill operations</p>
          {failedChildren > 0 ? <p className="text-amber-300">{failedChildren} child failure{failedChildren === 1 ? '' : 's'}</p> : null}
        </button>
        <button type="button" onClick={onSelectNetwork} className="text-left focus-visible:outline-none"><RunStatusBadge status={group.status} /></button>
        <button type="button" onClick={onSelectNetwork} className="font-mono text-left focus-visible:outline-none xl:text-right"><p className="text-[10px] font-medium text-slate-100">{formatLatency(group.durationMs)}</p><p className="mt-0.5 text-[8px] text-muted-foreground">{group.costUsd == null ? 'Cost partial/unknown' : formatMoney(group.costUsd)}</p><p className="mt-0.5 text-[8px] text-muted-foreground">{group.startedAt ? formatDateTime(group.startedAt) : '—'}</p></button>
        <button type="button" onClick={onSelectNetwork} className="hidden text-muted-foreground hover:text-primary-light xl:block" aria-label="Inspect Network Run"><ChevronRight className="h-3.5 w-3.5" /></button>
      </div>
      {expanded ? <div className="border-t border-border/60 bg-background/15">{sortedTraces.map((trace, index) => <AgentRunRow key={trace.id} trace={trace} agentName={trace.agent_id ? agentNames.get(trace.agent_id) ?? `Agent ${compactId(trace.agent_id)}` : 'Agent Run'} nested isLastNested={index === sortedTraces.length - 1} selected={selectedKey === `agent:${trace.id}`} onSelect={() => onSelectAgent(trace)} />)}</div> : null}
    </div>
  )
}

function parseTimeline(detail: Trace): TimelineItem[] {
  const data = traceData(detail)
  const rawItems = Array.isArray(data.execution_events) ? data.execution_events : []
  return rawItems.flatMap((raw, index) => {
    const event = asRecord(raw)
    const attributes = asRecord(event.attributes)
    const started = timestamp(asString(event.started_at) ?? asString(event.occurred_at))
    const ended = timestamp(asString(event.ended_at) ?? asString(event.occurred_at))
    const duration = asNumber(event.duration_ms) ?? Math.max(0, ended - started)
    if (!started) return []
    return [{ id: asString(event.event_id) ?? `${index}`, label: (asString(event.event_type) ?? 'runtime.event').replaceAll('.', ' '), phase: asString(event.phase) ?? 'runtime', status: asString(event.status) ?? 'unknown', startedAt: started, endedAt: ended || started + duration, durationMs: duration, payload: attributes }]
  })
}

function Timeline({ items }: { items: TimelineItem[] }) {
  if (!items.length) {
    return (
      <div className="flex min-h-[40px] items-center gap-2.5 border border-dashed border-border bg-control/15 px-3 py-2">
        <Clock3 className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
        <p className="font-mono text-[8px] text-muted-foreground"><span className="text-slate-300">Timeline unavailable</span> · detailed execution events were not recorded for this Run.</p>
      </div>
    )
  }
  const min = Math.min(...items.map((item) => item.startedAt))
  const max = Math.max(...items.map((item) => Math.max(item.endedAt, item.startedAt + item.durationMs)))
  const range = Math.max(1, max - min)
  return (
    <div className="divide-y divide-border/60 border border-border bg-background/20">
      {items.map((item) => {
        const left = ((item.startedAt - min) / range) * 100
        const width = Math.max(2, (Math.max(item.durationMs, item.endedAt - item.startedAt) / range) * 100)
        const failed = item.status === 'error' || item.status === 'failed'
        return (
          <div key={item.id} className="grid gap-2 px-3 py-2 md:grid-cols-[150px_minmax(0,1fr)_68px] md:items-center">
            <div className="min-w-0"><p className="truncate font-mono text-[8px] font-medium capitalize text-slate-200">{item.label}</p><p className="font-mono text-[7px] uppercase tracking-wide text-muted-foreground">{item.phase}</p></div>
            <div className="relative h-4 overflow-hidden border border-border/60 bg-control/40"><div className={cn('absolute top-1/2 h-2 -translate-y-1/2 rounded-technical', failed ? 'bg-red-400/80' : item.status === 'running' ? 'bg-blue-400/80' : 'bg-primary/80')} style={{ left: `${left}%`, width: `${Math.min(100 - left, width)}%` }} /></div>
            <p className="text-right font-mono text-[8px] text-muted-foreground">{formatLatency(item.durationMs)}</p>
          </div>
        )
      })}
    </div>
  )
}

function InspectorSection({ title, description, children, tone = 'default' }: { title: string; description?: string; children: React.ReactNode; tone?: InspectorTone }) {
  return (
    <section className={cn(
      'rounded-container border p-4',
      tone === 'focus' && 'border-primary/25 bg-surface/[0.92] shadow-[inset_2px_0_0_rgba(59,130,246,0.55)]',
      tone === 'default' && 'border-border bg-surface/[0.82]',
      tone === 'muted' && 'border-border/70 bg-surface/[0.48]',
    )}>
      <div className="mb-3 flex items-start gap-2">
        {tone === 'focus' ? <span className="mt-1 h-1.5 w-1.5 shrink-0 bg-primary" /> : null}
        <div className="min-w-0">
          <h3 className="font-mono text-[9px] font-bold text-slate-50">{title}</h3>
          {description ? <p className="mt-1 font-sans text-[9px] leading-4 text-muted-foreground">{description}</p> : null}
        </div>
      </div>
      {children}
    </section>
  )
}

function RunHeader({ title, subtitle, status, icon, metrics }: { title: string; subtitle: string; status: RunStatus; icon: React.ReactNode; metrics: Array<{ label: string; value: string }> }) {
  const meta = statusMeta(status)
  return (
    <section className={cn('rounded-container border border-border border-l-2 bg-surface/[0.96]', meta.accent)}>
      <div className="flex items-start gap-3 px-4 py-3">
        <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-control border border-border bg-control text-primary-light">{icon}</div>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2"><h2 className="truncate font-mono text-[11px] font-bold text-slate-50">{title}</h2><RunStatusBadge status={status} /></div>
          <p className="mt-1 font-mono text-[8px] text-muted-foreground">{subtitle}</p>
        </div>
      </div>
      <div className="grid border-t border-border/70 sm:grid-cols-2 xl:grid-cols-4">
        {metrics.map((metric, index) => (
          <div key={metric.label} className={cn('px-4 py-2.5', index > 0 && 'sm:border-l sm:border-border/70')}>
            <p className="font-mono text-[7px] uppercase tracking-[0.1em] text-muted-foreground">{metric.label}</p>
            <p className="mt-1 font-mono text-[9px] font-semibold text-slate-100">{metric.value}</p>
          </div>
        ))}
      </div>
    </section>
  )
}

function AgentRunInspector({ trace, detail, agentName, networkName }: { trace: Trace; detail?: TraceDetail; agentName: string; networkName?: string | null }) {
  const source = detail ?? trace
  const data = traceData(source)
  const diagnostics = asRecord(data.diagnostics)
  const timeline = parseTimeline(detail ?? trace)
  const llmCalls = Array.isArray(data.llm_calls) ? data.llm_calls.map(asRecord) : []
  const toolCalls = Array.isArray(data.tool_calls) ? data.tool_calls.map(asRecord) : []
  const sources = Array.isArray(data.sources) ? data.sources.map(asRecord) : []
  const totalTokens = asNumber(data.total_tokens)
  const status = normalizedStatus(source.status)
  const preview = inputPreview(source)
  const output = asString(data.answer) ?? asString(data.output_preview)
  const operationSummary = `${llmCalls.length || asNumber(diagnostics.llm_call_count) || 0} LLM · ${toolCalls.length ? operationCountsLabel(toolCalls) : `${asNumber(diagnostics.tool_call_count) || 0} Tool/Skill operations`}`

  return (
    <div className="space-y-3">
      <RunHeader
        title={agentName}
        subtitle={`Agent Run${networkName ? ` in ${networkName}` : ' · direct execution'}`}
        status={status}
        icon={<Bot className="h-4 w-4" />}
        metrics={[
          { label: 'Duration', value: formatLatency(source.total_latency_ms) },
          { label: 'Tokens', value: totalTokens == null ? 'Unknown' : formatTokens(totalTokens) },
          { label: 'Cost', value: source.total_cost_usd == null ? 'Unknown' : formatMoney(source.total_cost_usd) },
          { label: 'Operations', value: operationSummary },
        ]}
      />

      {source.error ? <section className="rounded-container border border-red-500/25 border-l-2 border-l-red-400 bg-surface/[0.86] p-3"><div className="flex items-center gap-2 text-red-200"><TriangleAlert className="h-3.5 w-3.5" /><h3 className="font-mono text-[9px] font-semibold">Run failure</h3></div><p className="mt-1.5 font-sans text-[10px] leading-5 text-red-100/85">{source.error}</p></section> : null}

      <InspectorSection title="Execution timeline" description="What happened, in execution order." tone="focus"><Timeline items={timeline} /></InspectorSection>

      {(llmCalls.length || toolCalls.length || sources.length) ? (
        <InspectorSection title="Operations" description="Models, Tools, Skills and Knowledge used by this Run." tone="focus">
          <div className="space-y-3">
            {llmCalls.length ? (
              <div>
                <div className="mb-1.5 flex items-center gap-2 font-mono text-[8px] font-medium text-slate-300"><Cpu className="h-3.5 w-3.5 text-primary-light" />LLM calls <span className="text-muted-foreground">{llmCalls.length}</span></div>
                <div className="divide-y divide-border/60 border border-border bg-background/20">
                  {llmCalls.map((call, index) => (
                    <div key={asString(call.call_id) ?? `${index}`} className="grid gap-2 px-3 py-2 sm:grid-cols-[minmax(0,1fr)_80px_80px] sm:items-center">
                      <div className="min-w-0"><p className="truncate font-mono text-[8px] font-medium text-slate-100">{asString(call.provider) ?? 'Provider unknown'} / {asString(call.model) ?? 'Model unknown'}</p><p className="font-mono text-[7px] text-muted-foreground">{asString(call.phase) ?? 'inference'} · {asString(call.status) ?? 'unknown'}</p></div>
                      <p className="font-mono text-[8px] text-muted-foreground sm:text-right">{formatLatency(asNumber(call.latency_ms))}</p>
                      <p className="font-mono text-[8px] text-muted-foreground sm:text-right">{asNumber(call.cost_usd) == null ? 'Cost unknown' : formatMoney(asNumber(call.cost_usd)!)}</p>
                    </div>
                  ))}
                </div>
              </div>
            ) : null}
            {toolCalls.length ? <ToolCallsCollapsible toolCalls={toolCalls.map(call => ({ ...call, tool_name: asString(call.tool_name) ?? 'Unknown Tool', duration_ms: asNumber(call.duration_ms) ?? undefined, status: asString(call.status), success: typeof call.success === 'boolean' ? call.success : null }))} /> : null}
            {sources.length ? (
              <div>
                <div className="mb-1.5 flex items-center gap-2 font-mono text-[8px] font-medium text-slate-300"><Database className="h-3.5 w-3.5 text-violet-300" />Knowledge sources <span className="text-muted-foreground">{sources.length}</span></div>
                <div className="divide-y divide-border/60 border border-border bg-background/20">{sources.map((item, index) => <div key={asString(item.chunk_id) ?? asString(item.document_id) ?? `${index}`} className="px-3 py-2"><p className="truncate font-mono text-[8px] font-medium text-slate-100">{asString(item.document_title) ?? 'Knowledge source'}</p><p className="mt-0.5 line-clamp-2 font-sans text-[9px] leading-4 text-muted-foreground">{asString(item.content_preview) ?? 'No content preview recorded.'}</p></div>)}</div>
              </div>
            ) : null}
          </div>
        </InspectorSection>
      ) : null}

      {(preview || output) ? (
        <InspectorSection title="Request and result" description="Business input and observable output for this Run.">
          <div className="grid gap-2">
            {preview ? <div className="border border-border/70 bg-control/20 p-3"><p className="font-mono text-[7px] uppercase tracking-wide text-muted-foreground">Request</p><p className="mt-1.5 whitespace-pre-wrap font-sans text-[10px] leading-5 text-slate-200">{preview}</p></div> : null}
            {output ? <div className="border border-border/70 bg-control/20 p-3"><p className="font-mono text-[7px] uppercase tracking-wide text-muted-foreground">Result</p><p className="mt-1.5 whitespace-pre-wrap font-sans text-[10px] leading-5 text-slate-200">{output}</p></div> : null}
          </div>
        </InspectorSection>
      ) : null}

      <InspectorSection title="Trace evidence" description="Identifiers and raw evidence for audit or incident analysis." tone="muted">
        <div className="space-y-2">
          <div className="grid border border-border/60 bg-background/15 sm:grid-cols-2">
            <div className="px-3 py-2 sm:border-r sm:border-border/60"><p className="font-mono text-[7px] uppercase tracking-wide text-muted-foreground">Trace ID</p><code className="mt-1 block truncate font-mono text-[8px] text-slate-300">{source.id}</code></div>
            <div className="px-3 py-2"><p className="font-mono text-[7px] uppercase tracking-wide text-muted-foreground">Agent ID</p><code className="mt-1 block truncate font-mono text-[8px] text-slate-300">{source.agent_id ?? '—'}</code></div>
          </div>
          {detail?.events?.length ? <details className="border border-border/60 bg-background/15 px-3 py-2"><summary className="cursor-pointer font-mono text-[8px] font-medium text-slate-300">Recorded events · {detail.events.length}</summary><div className="mt-2 space-y-2">{detail.events.map((event: TraceEvent) => <div key={event.id} className="border border-border/50 bg-background/40 p-2.5"><div className="flex items-center justify-between gap-3"><code className="truncate font-mono text-[8px] text-slate-300">{operationEventLabel(event.event_type, event.payload)}</code><span className="font-mono text-[7px] text-muted-foreground">{event.created_at ? formatDateTime(event.created_at) : '—'}</span></div>{event.payload ? <JsonCodeBlock value={event.payload} maxHeight={150} className="mt-2" /> : null}</div>)}</div></details> : null}
          <details className="border border-border/60 bg-background/15 px-3 py-2"><summary className="cursor-pointer font-mono text-[8px] font-medium text-slate-300">Raw Trace</summary><JsonCodeBlock value={detail ?? trace} maxHeight={320} className="mt-2" /></details>
        </div>
      </InspectorSection>
    </div>
  )
}

function NetworkRunInspector({ group, agentNames, onSelectAgent }: { group: NetworkRunGroup; agentNames: Map<string, string>; onSelectAgent: (trace: Trace) => void }) {
  const failed = group.traces.filter((trace) => normalizedStatus(trace.status) === 'failed')
  const totalTools = group.traces.reduce((total, trace) => total + (asNumber(traceData(trace).tool_call_count ?? asRecord(traceData(trace).diagnostics).tool_call_count) ?? 0), 0)
  const totalTokens = group.traces.reduce((total, trace) => total + (asNumber(traceData(trace).total_tokens) ?? 0), 0)
  const sorted = group.traces.slice().sort((left, right) => timestamp(traceStartedAt(left)) - timestamp(traceStartedAt(right)))
  const starts = sorted.map((trace) => timestamp(traceStartedAt(trace))).filter(Boolean)
  const min = starts.length ? Math.min(...starts) : 0
  const maxCandidates = sorted.map((trace) => timestamp(traceEndedAt(trace)) || timestamp(traceStartedAt(trace)) + (trace.total_latency_ms ?? 0)).filter(Boolean)
  const max = maxCandidates.length ? Math.max(...maxCandidates) : min + 1
  const range = Math.max(1, max - min)

  return (
    <div className="space-y-3">
      <RunHeader
        title={group.networkName}
        subtitle={`Network Run · ${group.environment ?? 'environment unknown'}${group.versionLabel ? ` · ${group.versionLabel}` : ''}`}
        status={group.status}
        icon={<Network className="h-4 w-4 text-violet-300" />}
        metrics={[
          { label: 'Duration', value: formatLatency(group.durationMs) },
          { label: 'Agent Runs', value: String(group.traces.length) },
          { label: 'Tokens', value: totalTokens ? formatTokens(totalTokens) : 'Unknown' },
          { label: 'Cost / ops', value: `${group.costUsd == null ? 'Partial/unknown' : formatMoney(group.costUsd)} · ${totalTools} ops` },
        ]}
      />

      {failed.length ? <section className="rounded-container border border-amber-500/25 border-l-2 border-l-amber-400 bg-surface/[0.86] p-3"><div className="flex items-center gap-2 text-amber-100"><TriangleAlert className="h-3.5 w-3.5" /><h3 className="font-mono text-[9px] font-semibold">{failed.length} Agent Run failure{failed.length === 1 ? '' : 's'} inside this Network Run</h3></div><p className="mt-1.5 font-sans text-[9px] leading-4 text-amber-100/80">Inspect the execution path to distinguish handled child failures from the root cause.</p></section> : null}

      <InspectorSection title="Execution path" description="Agent Runs in execution order. Open a row to inspect that Agent Run." tone="focus">
        <div className="divide-y divide-border/60 border border-border bg-background/20">
          {sorted.map((trace, index) => {
            const agentName = trace.agent_id ? agentNames.get(trace.agent_id) ?? `Agent ${compactId(trace.agent_id)}` : 'Agent Run'
            return (
              <button key={trace.id} type="button" onClick={() => onSelectAgent(trace)} className="grid w-full gap-2 px-3 py-2 text-left transition-colors hover:bg-control/35 sm:grid-cols-[24px_minmax(0,1fr)_100px_72px] sm:items-center">
                <div className="flex h-6 w-6 items-center justify-center rounded-control border border-border bg-control text-primary-light">{index === 0 ? <Route className="h-3 w-3" /> : <Bot className="h-3 w-3" />}</div>
                <div className="min-w-0"><p className="truncate font-mono text-[8px] font-medium text-slate-100">{agentName}</p><p className="font-mono text-[7px] text-muted-foreground">{index === 0 ? 'Entry Agent' : 'Delegated Agent'} · {trace.provider || 'provider unknown'}/{trace.model || 'model unknown'}</p></div>
                <RunStatusBadge status={normalizedStatus(trace.status)} />
                <p className="font-mono text-[8px] text-muted-foreground sm:text-right">{formatLatency(trace.total_latency_ms)}</p>
              </button>
            )
          })}
        </div>
      </InspectorSection>

      <InspectorSection title="Network waterfall" description="Relative windows reveal parallelism and the likely critical path." tone="focus">
        <div className="space-y-1.5">
          {sorted.map((trace, index) => {
            const start = timestamp(traceStartedAt(trace)) || min
            const end = timestamp(traceEndedAt(trace)) || start + (trace.total_latency_ms ?? 0)
            const left = ((start - min) / range) * 100
            const width = Math.max(2, ((Math.max(end, start) - start) / range) * 100)
            const agentName = trace.agent_id ? agentNames.get(trace.agent_id) ?? `Agent ${compactId(trace.agent_id)}` : `Agent Run ${index + 1}`
            return <div key={trace.id} className="grid gap-2 md:grid-cols-[130px_minmax(0,1fr)_62px] md:items-center"><p className="truncate font-mono text-[8px] text-slate-300">{agentName}</p><div className="relative h-4 overflow-hidden border border-border/60 bg-control/40"><div className={cn('absolute top-1/2 h-2 -translate-y-1/2 rounded-technical', normalizedStatus(trace.status) === 'failed' ? 'bg-red-400/80' : 'bg-violet-400/80')} style={{ left: `${left}%`, width: `${Math.min(100 - left, width)}%` }} /></div><p className="text-right font-mono text-[8px] text-muted-foreground">{formatLatency(trace.total_latency_ms)}</p></div>
          })}
        </div>
      </InspectorSection>

      {group.inputPreview ? <InspectorSection title="Request"><p className="whitespace-pre-wrap font-sans text-[10px] leading-5 text-slate-200">{group.inputPreview}</p></InspectorSection> : null}

      <InspectorSection title="Run evidence" description="Identifiers and child Trace references for audit." tone="muted">
        <div className="space-y-2">
          <div className="grid border border-border/60 bg-background/15 sm:grid-cols-2">
            <div className="px-3 py-2 sm:border-r sm:border-border/60"><p className="font-mono text-[7px] uppercase tracking-wide text-muted-foreground">Network Run ID</p><code className="mt-1 block truncate font-mono text-[8px] text-slate-300">{group.id}</code></div>
            <div className="px-3 py-2"><p className="font-mono text-[7px] uppercase tracking-wide text-muted-foreground">Network ID</p><code className="mt-1 block truncate font-mono text-[8px] text-slate-300">{group.networkId ?? '—'}</code></div>
          </div>
          <details className="border border-border/60 bg-background/15 px-3 py-2"><summary className="cursor-pointer font-mono text-[8px] font-medium text-slate-300">Child Trace references · {sorted.length}</summary><div className="mt-2 divide-y divide-border/50 border border-border/50">{sorted.map((trace, index) => <button key={trace.id} type="button" onClick={() => onSelectAgent(trace)} className="flex w-full items-center justify-between gap-3 px-3 py-2 text-left hover:bg-control/25"><span className="font-mono text-[7px] text-muted-foreground">Agent Run {index + 1}</span><code className="truncate font-mono text-[8px] text-slate-300">{trace.id}</code></button>)}</div></details>
        </div>
      </InspectorSection>
    </div>
  )
}

export default function TracesPage() {
  const { projectId } = useParams<{ projectId: string }>()
  const networksQuery = useNetworks(projectId)
  const agentsQuery = useAgents(projectId)
  const [runType, setRunType] = useState<RunTypeFilter>('all')
  const [statusFilter, setStatusFilter] = useState<StatusFilter>('all')
  const [networkFilter, setNetworkFilter] = useState('all')
  const [query, setQuery] = useState('')
  const [selectedKey, setSelectedKey] = useState<string | null>(null)
  const [expandedNetworkIds, setExpandedNetworkIds] = useState<Set<string>>(new Set())
  const {
    data: ledger,
    isLoading,
    isError,
    error,
    refetch,
  } = useProjectRuns(
    projectId,
    networkFilter === 'all' ? undefined : networkFilter,
  )

  const networkNames = useMemo(
    () => new Map((networksQuery.data ?? []).map((network) => [network.id, network.name])),
    [networksQuery.data],
  )
  const agentNames = useMemo(
    () => new Map((agentsQuery.data ?? []).map((agent) => [agent.id, agent.name])),
    [agentsQuery.data],
  )

  const directAgentRuns = useMemo(
    () => (ledger?.direct_agent_runs ?? []).map((run) => agentRunToTrace(run)),
    [ledger?.direct_agent_runs],
  )

  const networkGroups = useMemo(
    () => (ledger?.network_runs ?? []).map((run) => {
      const traces = run.agent_runs.map((agentRun) => agentRunToTrace(agentRun, run))
      return {
        id: run.id,
        networkId: run.network_id,
        networkName: run.network_name,
        traces,
        status: normalizedStatus(run.status),
        startedAt: run.started_at ?? run.created_at,
        endedAt: run.completed_at,
        durationMs: run.duration_ms,
        costUsd: knownCostSum(traces),
        environment: run.environment,
        versionLabel: run.network_version
          ? `Network ${run.network_version}`
          : run.draft_revision == null
            ? null
            : `Draft r${run.draft_revision}`,
        inputPreview: run.input_message,
      } satisfies NetworkRunGroup
    }),
    [ledger?.network_runs],
  )

  const items = useMemo(
    () => [
      ...directAgentRuns,
      ...networkGroups.flatMap((group) => group.traces),
    ],
    [directAgentRuns, networkGroups],
  )
  const networkGroupsById = useMemo(
    () => new Map(networkGroups.map((group) => [group.id, group])),
    [networkGroups],
  )
  const tracesById = useMemo(
    () => new Map(items.map((trace) => [trace.id, trace])),
    [items],
  )

  const baseEntries = useMemo<RunEntry[]>(() => {
    const networkEntries = networkGroups.map((group) => ({
      key: `network:${group.id}`,
      kind: 'network' as const,
      group,
      sortAt: timestamp(group.startedAt),
    }))
    const agentSource = runType === 'agent' ? items : directAgentRuns
    const agentEntries = agentSource.map((trace) => ({
      key: `agent:${trace.id}`,
      kind: 'agent' as const,
      trace,
      sortAt: timestamp(traceStartedAt(trace)),
    }))
    if (runType === 'network') {
      return networkEntries.sort((left, right) => right.sortAt - left.sortAt)
    }
    if (runType === 'agent') {
      return agentEntries.sort((left, right) => right.sortAt - left.sortAt)
    }
    return [...networkEntries, ...agentEntries].sort(
      (left, right) => right.sortAt - left.sortAt,
    )
  }, [directAgentRuns, items, networkGroups, runType])

  const normalizedQuery = query.trim().toLowerCase()
  const visibleEntries = useMemo(() => baseEntries.filter((entry) => {
    const status = entry.kind === 'network'
      ? entry.group.status
      : normalizedStatus(entry.trace.status)
    if (!statusMatches(status, statusFilter)) return false
    if (!normalizedQuery) return true
    if (entry.kind === 'network') {
      return [
        entry.group.id,
        entry.group.networkName,
        entry.group.environment,
        entry.group.versionLabel,
        entry.group.inputPreview,
      ]
        .filter(Boolean)
        .join(' ')
        .toLowerCase()
        .includes(normalizedQuery)
        || entry.group.traces.some((trace) => traceSearchText(
          trace,
          trace.agent_id ? agentNames.get(trace.agent_id) : null,
          entry.group.networkName,
        ).includes(normalizedQuery))
    }
    return traceSearchText(
      entry.trace,
      entry.trace.agent_id ? agentNames.get(entry.trace.agent_id) : null,
      entry.trace.network_id ? networkNames.get(entry.trace.network_id) : null,
    ).includes(normalizedQuery)
  }), [agentNames, baseEntries, networkNames, normalizedQuery, statusFilter])

  const statusCounts = useMemo(() => ({
    all: baseEntries.length,
    running: baseEntries.filter((entry) => statusMatches(
      entry.kind === 'network'
        ? entry.group.status
        : normalizedStatus(entry.trace.status),
      'running',
    )).length,
    completed: baseEntries.filter((entry) => statusMatches(
      entry.kind === 'network'
        ? entry.group.status
        : normalizedStatus(entry.trace.status),
      'completed',
    )).length,
    failed: baseEntries.filter((entry) => statusMatches(
      entry.kind === 'network'
        ? entry.group.status
        : normalizedStatus(entry.trace.status),
      'failed',
    )).length,
    cancelled: baseEntries.filter((entry) => statusMatches(
      entry.kind === 'network'
        ? entry.group.status
        : normalizedStatus(entry.trace.status),
      'cancelled',
    )).length,
  }), [baseEntries])

  const summary = ledger?.summary
  const activeRuns = summary?.active_top_level_runs ?? 0
  const failedRuns = summary?.failed_top_level_runs ?? 0
  const failureRate = summary?.failure_rate_percent ?? 0
  const p95Latency = summary?.p95_top_level_latency_ms ?? null
  const averageAgentRuns = summary?.avg_agent_runs_per_network_run ?? null
  const topLevelRunCount = summary?.top_level_runs
    ?? (networkGroups.length + directAgentRuns.length)

  const selectedNetworkId = selectedKey?.startsWith('network:')
    ? selectedKey.slice('network:'.length)
    : null
  const selectedAgentId = selectedKey?.startsWith('agent:')
    ? selectedKey.slice('agent:'.length)
    : null
  const selectedNetwork = selectedNetworkId
    ? networkGroupsById.get(selectedNetworkId) ?? null
    : null
  const selectedAgent = selectedAgentId
    ? tracesById.get(selectedAgentId) ?? null
    : null
  const {
    data: selectedAgentDetail,
    isLoading: detailLoading,
  } = useOptionalTraceDetail(selectedAgent?.id)
  const hasFilters = runType !== 'all'
    || statusFilter !== 'all'
    || networkFilter !== 'all'
    || query.trim().length > 0

  if (!projectId) return <ErrorState message="Project not found" />

  const toggleNetwork = (id: string) => {
    setExpandedNetworkIds((current) => {
      const next = new Set(current)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  return (
    <ResourcePage title="Runs" description="Central operational view of Agent Runs, Network Runs and their Trace evidence." className="max-w-[1600px]">
      <ResourceToolbar>
        <ResourceTabs value={runType} onChange={setRunType} label="Filter by Run type" tabs={[
          { value: 'all', label: 'All Runs', count: networkGroups.length + directAgentRuns.length },
          { value: 'network', label: 'Network Runs', count: networkGroups.length },
          { value: 'agent', label: 'Agent Runs', count: items.length },
        ]} />
        <ResourceTabs value={statusFilter} onChange={setStatusFilter} label="Filter Runs by status" tabs={[
          { value: 'all', label: 'All', count: statusCounts.all },
          { value: 'running', label: 'Running', count: statusCounts.running },
          { value: 'completed', label: 'Completed', count: statusCounts.completed },
          { value: 'failed', label: 'Failed', count: statusCounts.failed },
          { value: 'cancelled', label: 'Cancelled', count: statusCounts.cancelled },
        ]} />
        <div className="grid gap-2.5 lg:grid-cols-[180px_minmax(0,1fr)]">
          <Select value={networkFilter} onChange={(event) => setNetworkFilter(event.target.value)} aria-label="Filter Runs by Network" options={[{ value: 'all', label: 'All Networks' }, ...(networksQuery.data ?? []).map((network) => ({ value: network.id, label: network.name }))]} />
          <ResourceSearch value={query} onChange={setQuery} placeholder="Search Runs, Agents, Networks, sessions or models..." label="Search Runs" />
        </div>
      </ResourceToolbar>

      <section>
        <ResourceSectionHeader title="Run health" description="Current execution pressure and top-level reliability indicators." count={`${topLevelRuns.length} top-level Runs`} />
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-6">
          <MetricCard label="Active now" value={String(activeRuns)} detail="Queued or running" />
          <MetricCard label="Agent Runs" value={String(items.length)} detail={`${directAgentRuns.length} direct · ${items.length - directAgentRuns.length} in Networks`} />
          <MetricCard label="Network Runs" value={String(networkGroups.length)} detail="Composite executions" />
          <MetricCard label="Failure rate" value={`${failureRate.toFixed(1)}%`} detail={`${failedRuns} failed top-level Runs`} />
          <MetricCard label="P95 latency" value={p95Latency == null ? '—' : formatLatency(p95Latency)} detail="Top-level Run duration" />
          <MetricCard label="Runs / Network" value={averageAgentRuns.toFixed(1)} detail="Average Agent Runs" />
        </div>
      </section>

      <section>
        <ResourceSectionHeader title="Operational run stream" description="Select a Run to see what happened. Network Runs can be expanded into their Agent Runs." count={visibleEntries.length} />
        {isLoading ? <LoadingState message="Loading Runs" variant="panel" layout="resource-list" /> : isError ? <ErrorState error={error} onRetry={refetch} className="rounded-container border border-border bg-surface/70 py-10" /> : visibleEntries.length ? (
          <div className="grid min-h-[620px] gap-4 xl:grid-cols-[minmax(0,1.12fr)_minmax(440px,.88fr)]">
            <div className="min-w-0 overflow-hidden rounded-container border border-border bg-surface/[0.9]">
              {visibleEntries.map((entry) => entry.kind === 'network' ? <NetworkRunRow key={entry.key} group={entry.group} agentNames={agentNames} selectedKey={selectedKey} expanded={expandedNetworkIds.has(entry.group.id)} onToggle={() => toggleNetwork(entry.group.id)} onSelectNetwork={() => setSelectedKey(entry.key)} onSelectAgent={(trace) => setSelectedKey(`agent:${trace.id}`)} /> : <AgentRunRow key={entry.key} trace={entry.trace} agentName={entry.trace.agent_id ? agentNames.get(entry.trace.agent_id) ?? `Agent ${compactId(entry.trace.agent_id)}` : 'Agent Run'} networkName={entry.trace.network_id ? networkNames.get(entry.trace.network_id) : null} selected={selectedKey === entry.key} onSelect={() => setSelectedKey(entry.key)} />)}
            </div>
            <aside className={cn('min-w-0 max-h-[calc(100vh-170px)] overflow-y-auto pr-1 xl:sticky xl:top-4 xl:self-start', panelScrollClass)}>
              {selectedNetwork ? <NetworkRunInspector group={selectedNetwork} agentNames={agentNames} onSelectAgent={(trace) => setSelectedKey(`agent:${trace.id}`)} /> : selectedAgent ? (detailLoading ? <LoadingState message="Loading Agent Run" variant="panel" /> : <AgentRunInspector trace={selectedAgent} detail={selectedAgentDetail} agentName={selectedAgent.agent_id ? agentNames.get(selectedAgent.agent_id) ?? `Agent ${compactId(selectedAgent.agent_id)}` : 'Agent Run'} networkName={selectedAgent.network_id ? networkNames.get(selectedAgent.network_id) : null} />) : (
                <div className="flex min-h-[320px] items-center justify-center rounded-container border border-dashed border-border bg-surface/[0.45] p-8 text-center"><div><Activity className="mx-auto h-6 w-6 text-muted-foreground/45" /><h3 className="mt-3 font-mono text-[9px] font-bold text-slate-50">Select a Run</h3><p className="mt-2 max-w-sm font-sans text-[10px] leading-5 text-muted-foreground">Choose a Run on the left. The inspector prioritizes status, execution timeline and operations before raw evidence.</p></div></div>
              )}
            </aside>
          </div>
        ) : <ResourceEmptyState icon={<Activity className="h-4 w-4" />} title="No Runs found" description={hasFilters ? 'Adjust or clear the active filters.' : 'Agent Runs and Network Runs appear here as soon as the runtime accepts an execution.'} action={hasFilters ? <Button type="button" size="sm" variant="outline" onClick={() => { setRunType('all'); setStatusFilter('all'); setNetworkFilter('all'); setQuery('') }}>Clear filters</Button> : undefined} />}
      </section>
    </ResourcePage>
  )
}
