import { operationCountsLabel, operationEventLabel } from '@/features/skills/operations'
import { ToolCallsCollapsible } from '@/features/playground/components/ToolCallsCollapsible'
import { useMemo, useState } from 'react'
import { useParams } from 'react-router-dom'
import {
  Activity,
  Bot,
  ChevronDown,
  ChevronRight,
  CircleDot,
  Clock3,
  Cpu,
  Database,
  Network,
  Route,
  TriangleAlert,
  Wrench,
} from 'lucide-react'

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
import { Button } from '@/components/ui/Button'
import { JsonCodeBlock } from '@/components/ui/JsonCodeBlock'
import { useAgents } from '@/features/agents/hooks'
import { useNetworks } from '@/features/network/hooks'
import { useTraceDetail, useTraces } from '@/features/traces/hooks'
import type { Trace, TraceDetail, TraceEvent } from '@/features/traces/types'
import { formatDateTime } from '@/lib/formatters/date'
import { formatMoney } from '@/lib/formatters/money'
import { formatLatency, formatTokens } from '@/lib/formatters/number'
import { cn } from '@/lib/utils'

type RunTypeFilter = 'all' | 'network' | 'agent'
type StatusFilter = 'all' | 'running' | 'completed' | 'failed' | 'cancelled'
type RunStatus = 'pending' | 'running' | 'completed' | 'completed_with_issues' | 'failed' | 'cancelled'

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
  rootTrace: Trace
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

const panelScrollClass = 'scrollbar-thin scrollbar-track-transparent scrollbar-thumb-border hover:scrollbar-thumb-muted [scrollbar-color:rgb(51_65_85)_transparent] [scrollbar-width:thin] [&::-webkit-scrollbar]:w-2 [&::-webkit-scrollbar-track]:bg-transparent [&::-webkit-scrollbar-thumb]:rounded-full [&::-webkit-scrollbar-thumb]:border-2 [&::-webkit-scrollbar-thumb]:border-transparent [&::-webkit-scrollbar-thumb]:bg-border/70 [&::-webkit-scrollbar-thumb]:bg-clip-padding hover:[&::-webkit-scrollbar-thumb]:bg-muted'
const runRowGridClass = 'xl:grid-cols-[32px_minmax(0,1.45fr)_minmax(0,.9fr)_140px_145px_20px]'

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' && !Array.isArray(value)
    ? value as Record<string, unknown>
    : {}
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
  if (value === 'failed' || value === 'error') return 'failed'
  if (value === 'cancelled' || value === 'canceled') return 'cancelled'
  return 'completed'
}

function statusMatches(status: RunStatus, filter: StatusFilter) {
  if (filter === 'all') return true
  if (filter === 'running') return status === 'running' || status === 'pending'
  if (filter === 'completed') return status === 'completed' || status === 'completed_with_issues'
  return status === filter
}

function aggregateNetworkStatus(traces: Trace[]): RunStatus {
  const statuses = traces.map((trace) => normalizedStatus(trace.status))
  if (statuses.some((status) => status === 'running' || status === 'pending')) return 'running'
  if (statuses.every((status) => status === 'cancelled')) return 'cancelled'
  const failures = statuses.filter((status) => status === 'failed').length
  const completed = statuses.filter((status) => status === 'completed').length
  if (failures > 0 && completed > 0) return 'completed_with_issues'
  if (failures > 0) return 'failed'
  return 'completed'
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

function networkDuration(traces: Trace[]): { startedAt: string | null; endedAt: string | null; durationMs: number | null } {
  const starts = traces.map(traceStartedAt).filter((value): value is string => Boolean(value))
  const ends = traces.map(traceEndedAt).filter((value): value is string => Boolean(value))
  const startedAt = starts.sort((left, right) => timestamp(left) - timestamp(right))[0] ?? null
  const endedAt = ends.sort((left, right) => timestamp(right) - timestamp(left))[0] ?? null
  if (startedAt && endedAt) {
    const durationMs = timestamp(endedAt) - timestamp(startedAt)
    if (durationMs >= 0) return { startedAt, endedAt, durationMs }
  }
  const recorded = traces.map((trace) => trace.total_latency_ms).filter((value): value is number => typeof value === 'number')
  return { startedAt, endedAt, durationMs: recorded.length ? Math.max(...recorded) : null }
}

function percentile(values: number[], percentileValue: number): number | null {
  if (!values.length) return null
  const sorted = [...values].sort((left, right) => left - right)
  const index = Math.min(sorted.length - 1, Math.max(0, Math.ceil(percentileValue * sorted.length) - 1))
  return sorted[index]
}

function statusMeta(status: RunStatus) {
  if (status === 'running' || status === 'pending') return { label: status === 'pending' ? 'Queued' : 'Running', className: 'border-blue-500/30 bg-blue-500/10 text-blue-300', dot: 'bg-blue-400 animate-pulse' }
  if (status === 'failed') return { label: 'Failed', className: 'border-red-500/30 bg-red-500/10 text-red-300', dot: 'bg-red-400' }
  if (status === 'completed_with_issues') return { label: 'Completed with issues', className: 'border-amber-500/30 bg-amber-500/10 text-amber-200', dot: 'bg-amber-400' }
  if (status === 'cancelled') return { label: 'Cancelled', className: 'border-border bg-background text-muted', dot: 'bg-slate-400' }
  return { label: 'Completed', className: 'border-emerald-500/30 bg-emerald-500/10 text-emerald-300', dot: 'bg-emerald-400' }
}

function RunStatusBadge({ status }: { status: RunStatus }) {
  const meta = statusMeta(status)
  return (
    <span className={cn('inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5 text-[10px] font-medium', meta.className)}>
      <span className={cn('h-1.5 w-1.5 rounded-full', meta.dot)} />
      {meta.label}
    </span>
  )
}

function MetricCard({ label, value, detail }: { label: string; value: string; detail: string }) {
  return (
    <div className="rounded-xl border border-border/80 bg-surface/55 px-4 py-3">
      <p className="text-[10px] font-medium uppercase tracking-[0.12em] text-muted">{label}</p>
      <p className="mt-2 text-xl font-semibold tracking-tight text-white">{value}</p>
      <p className="mt-1 text-[11px] text-muted">{detail}</p>
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
        'group grid w-full gap-3 border-b border-border/70 px-4 py-3 text-left transition-colors last:border-b-0 hover:bg-background/50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/30 xl:items-center',
        runRowGridClass,
        nested && 'bg-background/20',
        selected && 'bg-primary/10 hover:bg-primary/10',
      )}
    >
      <RunTreeSlot nested={nested} isLastNested={isLastNested} />

      <div className="min-w-0">
        <div className="flex flex-wrap items-center gap-2">
          <Bot className="h-3.5 w-3.5 text-primary-light" />
          <span className="truncate text-sm font-medium text-white">{agentName}</span>
          <ResourcePill>Agent Run</ResourcePill>
          {!nested && networkName ? <ResourcePill tone="primary">{networkName}</ResourcePill> : null}
          {trace.fallback_used ? <ResourcePill tone="primary">Fallback</ResourcePill> : null}
        </div>
        <p className="mt-1 truncate text-xs text-muted">{preview ?? `Run ${compactId(trace.id)}`}</p>
      </div>

      <div className="min-w-0 text-xs text-muted">
        <p className="truncate text-slate-300">{environment ?? 'Environment not recorded'}{version ? ` · ${version}` : ''}</p>
        <p className="mt-1 truncate">{trace.provider || 'Provider unknown'} / {trace.model || 'Model unknown'}</p>
        {(llmCalls != null || toolCalls != null) && <p className="mt-1">{llmCalls ?? 0} LLM · {toolCalls ?? 0} Tool/Skill operations</p>}
      </div>

      <RunStatusBadge status={status} />

      <div className="xl:text-right">
        <p className="text-sm font-medium text-white">{formatLatency(trace.total_latency_ms)}</p>
        <p className="mt-1 text-xs text-muted">{trace.total_cost_usd == null ? 'Cost unknown' : formatMoney(trace.total_cost_usd)}</p>
        <p className="mt-1 text-[11px] text-muted">{traceStartedAt(trace) ? formatDateTime(traceStartedAt(trace)!) : '—'}</p>
      </div>

      <ChevronRight className={cn('hidden h-4 w-4 text-muted transition-transform group-hover:translate-x-0.5 group-hover:text-primary-light xl:block', selected && 'text-primary-light')} />
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
      <div className={cn('grid gap-3 px-4 py-3 transition-colors hover:bg-background/50 xl:items-center', runRowGridClass, selectedKey === `network:${group.id}` && 'bg-primary/10 hover:bg-primary/10')}>
        <button
          type="button"
          onClick={onToggle}
          className="flex h-8 w-8 items-center justify-center rounded-lg border border-border/80 bg-background/50 text-muted hover:border-primary/30 hover:text-white"
          aria-label={expanded ? 'Collapse Network Run' : 'Expand Network Run'}
          aria-expanded={expanded}
        >
          {expanded ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
        </button>

        <button type="button" onClick={onSelectNetwork} className="min-w-0 text-left focus-visible:outline-none">
          <div className="flex flex-wrap items-center gap-2">
            <Network className="h-3.5 w-3.5 text-violet-300" />
            <span className="truncate text-sm font-medium text-white">{group.networkName}</span>
            <ResourcePill tone="primary">Network Run</ResourcePill>
          </div>
          <p className="mt-1 truncate text-xs text-muted">{group.inputPreview ?? `Execution ${compactId(group.id)}`}</p>
        </button>

        <button type="button" onClick={onSelectNetwork} className="min-w-0 text-left text-xs text-muted focus-visible:outline-none">
          <p className="truncate text-slate-300">{group.environment ?? 'Environment not recorded'}{group.versionLabel ? ` · ${group.versionLabel}` : ''}</p>
          <p className="mt-1">{group.traces.length} Agent Run{group.traces.length === 1 ? '' : 's'} · {toolCalls} Tool/Skill operations</p>
          {failedChildren > 0 && <p className="mt-1 text-amber-300">{failedChildren} child failure{failedChildren === 1 ? '' : 's'}</p>}
        </button>

        <button type="button" onClick={onSelectNetwork} className="text-left focus-visible:outline-none"><RunStatusBadge status={group.status} /></button>

        <button type="button" onClick={onSelectNetwork} className="text-left focus-visible:outline-none xl:text-right">
          <p className="text-sm font-medium text-white">{formatLatency(group.durationMs)}</p>
          <p className="mt-1 text-xs text-muted">{group.costUsd == null ? 'Cost partial/unknown' : formatMoney(group.costUsd)}</p>
          <p className="mt-1 text-[11px] text-muted">{group.startedAt ? formatDateTime(group.startedAt) : '—'}</p>
        </button>

        <button type="button" onClick={onSelectNetwork} className="hidden text-muted hover:text-primary-light xl:block" aria-label="Inspect Network Run"><ChevronRight className="h-4 w-4" /></button>
      </div>

      {expanded ? (
        <div className="border-t border-border/60 bg-background/15">
          {sortedTraces.map((trace, index) => (
            <AgentRunRow
              key={trace.id}
              trace={trace}
              agentName={trace.agent_id ? agentNames.get(trace.agent_id) ?? `Agent ${compactId(trace.agent_id)}` : 'Agent Run'}
              nested
              isLastNested={index === sortedTraces.length - 1}
              selected={selectedKey === `agent:${trace.id}`}
              onSelect={() => onSelectAgent(trace)}
            />
          ))}
        </div>
      ) : null}
    </div>
  )
}

function parseTimeline(detail: TraceDetail): TimelineItem[] {
  const data = traceData(detail)
  const rawItems = Array.isArray(data.execution_events) ? data.execution_events : []
  return rawItems.flatMap((raw, index) => {
    const event = asRecord(raw)
    const attributes = asRecord(event.attributes)
    const started = timestamp(asString(event.started_at) ?? asString(event.occurred_at))
    const ended = timestamp(asString(event.ended_at) ?? asString(event.occurred_at))
    const duration = asNumber(event.duration_ms) ?? Math.max(0, ended - started)
    if (!started) return []
    return [{
      id: asString(event.event_id) ?? `${index}`,
      label: (asString(event.event_type) ?? 'runtime.event').replaceAll('.', ' '),
      phase: asString(event.phase) ?? 'runtime',
      status: asString(event.status) ?? 'unknown',
      startedAt: started,
      endedAt: ended || started + duration,
      durationMs: duration,
      payload: attributes,
    }]
  })
}

function Timeline({ items }: { items: TimelineItem[] }) {
  if (!items.length) return <p className="rounded-xl border border-dashed border-border/80 px-4 py-6 text-center text-xs text-muted">Detailed execution timeline was not recorded for this Run.</p>
  const min = Math.min(...items.map((item) => item.startedAt))
  const max = Math.max(...items.map((item) => Math.max(item.endedAt, item.startedAt + item.durationMs)))
  const range = Math.max(1, max - min)
  return (
    <div className="space-y-2">
      {items.map((item) => {
        const left = ((item.startedAt - min) / range) * 100
        const width = Math.max(2, (Math.max(item.durationMs, item.endedAt - item.startedAt) / range) * 100)
        const failed = item.status === 'error' || item.status === 'failed'
        return (
          <div key={item.id} className="grid gap-2 rounded-lg border border-border/70 bg-background/35 px-3 py-2 md:grid-cols-[170px_minmax(0,1fr)_74px] md:items-center">
            <div className="min-w-0">
              <p className="truncate text-[11px] font-medium capitalize text-slate-200">{item.label}</p>
              <p className="mt-0.5 text-[9px] uppercase tracking-wide text-muted">{item.phase}</p>
            </div>
            <div className="relative h-5 overflow-hidden rounded-md border border-border/60 bg-background/70">
              <div
                className={cn('absolute top-1/2 h-2.5 -translate-y-1/2 rounded-full', failed ? 'bg-red-400/75' : item.status === 'running' ? 'bg-blue-400/75' : 'bg-primary/70')}
                style={{ left: `${left}%`, width: `${Math.min(100 - left, width)}%` }}
              />
            </div>
            <p className="text-right font-mono text-[10px] text-muted">{formatLatency(item.durationMs)}</p>
          </div>
        )
      })}
    </div>
  )
}

function DetailSection({ title, description, children }: { title: string; description?: string; children: React.ReactNode }) {
  return (
    <section className="rounded-xl border border-border/80 bg-surface/55 p-4">
      <div className="mb-4">
        <h3 className="text-sm font-semibold text-white">{title}</h3>
        {description ? <p className="mt-1 text-xs text-muted">{description}</p> : null}
      </div>
      {children}
    </section>
  )
}

function AgentRunInspector({ trace, detail, agentName, networkName }: {
  trace: Trace
  detail?: TraceDetail
  agentName: string
  networkName?: string | null
}) {
  const source = detail ?? trace
  const data = traceData(source)
  const diagnostics = asRecord(data.diagnostics)
  const timeline = detail ? parseTimeline(detail) : []
  const llmCalls = Array.isArray(data.llm_calls) ? data.llm_calls.map(asRecord) : []
  const toolCalls = Array.isArray(data.tool_calls) ? data.tool_calls.map(asRecord) : []
  const sources = Array.isArray(data.sources) ? data.sources.map(asRecord) : []
  const totalTokens = asNumber(data.total_tokens)
  const status = normalizedStatus(source.status)
  const preview = inputPreview(source)
  const output = asString(data.answer) ?? asString(data.output_preview)

  return (
    <div className="space-y-4">
      <section className="rounded-xl border border-border/90 bg-surface/70 p-4">
        <div className="flex items-start gap-3">
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-primary/25 bg-primary/10 text-primary-light"><Bot className="h-5 w-5" /></div>
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-2">
              <h2 className="truncate text-base font-semibold text-white">{agentName}</h2>
              <RunStatusBadge status={status} />
            </div>
            <p className="mt-1 text-xs text-muted">Agent Run{networkName ? ` in ${networkName}` : ' · direct execution'}</p>
          </div>
        </div>
        <div className="mt-4 grid gap-3 border-t border-border/70 pt-4 sm:grid-cols-2 xl:grid-cols-4">
          <div><p className="text-[10px] uppercase tracking-wide text-muted">Duration</p><p className="mt-1 text-sm font-medium text-white">{formatLatency(source.total_latency_ms)}</p></div>
          <div><p className="text-[10px] uppercase tracking-wide text-muted">Tokens</p><p className="mt-1 text-sm font-medium text-white">{totalTokens == null ? 'Unknown' : formatTokens(totalTokens)}</p></div>
          <div><p className="text-[10px] uppercase tracking-wide text-muted">Cost</p><p className="mt-1 text-sm font-medium text-white">{source.total_cost_usd == null ? 'Unknown' : formatMoney(source.total_cost_usd)}</p></div>
          <div><p className="text-[10px] uppercase tracking-wide text-muted">Operations</p><p className="mt-1 text-sm font-medium text-white">{llmCalls.length || asNumber(diagnostics.llm_call_count) || 0} LLM · {toolCalls.length ? operationCountsLabel(toolCalls) : `${asNumber(diagnostics.tool_call_count) || 0} Tool/Skill operations`}</p></div>
        </div>
      </section>

      {source.error ? <section className="rounded-xl border border-red-500/30 bg-red-500/10 p-4"><div className="flex items-center gap-2 text-red-200"><TriangleAlert className="h-4 w-4" /><h3 className="text-sm font-semibold">Run failure</h3></div><p className="mt-2 text-sm leading-6 text-red-100/90">{source.error}</p></section> : null}

      {(preview || output) ? (
        <DetailSection title="Request and result" description="Business input and observable output for this Agent Run.">
          <div className="grid gap-3">
            {preview ? <div className="rounded-lg border border-border/70 bg-background/40 p-3"><p className="text-[10px] uppercase tracking-wide text-muted">Request</p><p className="mt-2 whitespace-pre-wrap text-xs leading-5 text-slate-200">{preview}</p></div> : null}
            {output ? <div className="rounded-lg border border-border/70 bg-background/40 p-3"><p className="text-[10px] uppercase tracking-wide text-muted">Result</p><p className="mt-2 whitespace-pre-wrap text-xs leading-5 text-slate-200">{output}</p></div> : null}
          </div>
        </DetailSection>
      ) : null}

      <DetailSection title="Execution timeline" description="Measured phases and operations across the Run lifecycle."><Timeline items={timeline} /></DetailSection>

      {(llmCalls.length || toolCalls.length || sources.length) ? (
        <DetailSection title="Operations" description="Model calls, Skills, Tools and Knowledge used inside this Agent Run.">
          <div className="space-y-4">
            {llmCalls.length ? <div><div className="mb-2 flex items-center gap-2 text-xs font-medium text-slate-200"><Cpu className="h-3.5 w-3.5 text-primary-light" />LLM Calls <span className="text-muted">{llmCalls.length}</span></div><div className="space-y-2">{llmCalls.map((call, index) => <div key={asString(call.call_id) ?? `${index}`} className="grid gap-2 rounded-lg border border-border/70 bg-background/40 p-3 sm:grid-cols-[minmax(0,1fr)_90px_90px]"><div className="min-w-0"><p className="truncate text-xs font-medium text-white">{asString(call.provider) ?? 'Provider unknown'} / {asString(call.model) ?? 'Model unknown'}</p><p className="mt-1 text-[10px] text-muted">{asString(call.phase) ?? 'inference'} · {asString(call.status) ?? 'unknown'}</p></div><p className="text-xs text-muted sm:text-right">{formatLatency(asNumber(call.latency_ms))}</p><p className="text-xs text-muted sm:text-right">{asNumber(call.cost_usd) == null ? 'Cost unknown' : formatMoney(asNumber(call.cost_usd)!)}</p></div>)}</div></div> : null}
            {toolCalls.length ? <ToolCallsCollapsible toolCalls={toolCalls.map(call => ({ ...call, tool_name: asString(call.tool_name) ?? 'Unknown Tool', duration_ms: asNumber(call.duration_ms) ?? undefined, status: asString(call.status), success: typeof call.success === 'boolean' ? call.success : null }))} /> : null}
            {sources.length ? <div><div className="mb-2 flex items-center gap-2 text-xs font-medium text-slate-200"><Database className="h-3.5 w-3.5 text-violet-300" />Knowledge sources <span className="text-muted">{sources.length}</span></div><div className="space-y-2">{sources.map((item, index) => <div key={asString(item.chunk_id) ?? asString(item.document_id) ?? `${index}`} className="rounded-lg border border-border/70 bg-background/40 p-3"><p className="truncate text-xs font-medium text-white">{asString(item.document_title) ?? 'Knowledge source'}</p><p className="mt-1 line-clamp-2 text-[10px] leading-4 text-muted">{asString(item.content_preview) ?? 'No content preview recorded.'}</p></div>)}</div></div> : null}
          </div>
        </DetailSection>
      ) : null}

      <DetailSection title="Trace evidence" description="Raw evidence remains available for incident analysis and audit.">
        <div className="space-y-3">
          <div className="grid gap-2 sm:grid-cols-2">
            <div className="rounded-lg border border-border/70 bg-background/40 p-3"><p className="text-[10px] uppercase tracking-wide text-muted">Trace ID</p><code className="mt-2 block truncate text-xs text-white">{source.id}</code></div>
            <div className="rounded-lg border border-border/70 bg-background/40 p-3"><p className="text-[10px] uppercase tracking-wide text-muted">Agent ID</p><code className="mt-2 block truncate text-xs text-white">{source.agent_id ?? '—'}</code></div>
          </div>
          {detail?.events?.length ? <details className="rounded-lg border border-border/70 bg-background/40 p-3"><summary className="cursor-pointer text-xs font-medium text-slate-200">Recorded events · {detail.events.length}</summary><div className="mt-3 space-y-2">{detail.events.map((event: TraceEvent) => <div key={event.id} className="rounded-lg border border-border/60 bg-background/60 p-3"><div className="flex items-center justify-between gap-3"><code className="truncate text-[10px] text-white">{operationEventLabel(event.event_type, event.payload)}</code><span className="text-[9px] text-muted">{event.created_at ? formatDateTime(event.created_at) : '—'}</span></div>{event.payload ? <JsonCodeBlock value={event.payload} maxHeight={150} className="mt-2" /> : null}</div>)}</div></details> : null}
          <details className="rounded-lg border border-border/70 bg-background/40 p-3"><summary className="cursor-pointer text-xs font-medium text-slate-200">Raw Trace</summary><JsonCodeBlock value={detail ?? trace} maxHeight={320} className="mt-3" /></details>
        </div>
      </DetailSection>
    </div>
  )
}

function NetworkRunInspector({ group, agentNames, onSelectAgent }: { group: NetworkRunGroup; agentNames: Map<string, string>; onSelectAgent: (trace: Trace) => void }) {
  const failed = group.traces.filter((trace) => normalizedStatus(trace.status) === 'failed')
  const totalTools = group.traces.reduce((total, trace) => total + (asNumber(traceData(trace).tool_call_count ?? asRecord(traceData(trace).diagnostics).tool_call_count) ?? 0), 0)
  const totalTokens = group.traces.reduce((total, trace) => total + (asNumber(traceData(trace).total_tokens) ?? 0), 0)
  const sorted = group.traces.slice().sort((left, right) => timestamp(traceStartedAt(left)) - timestamp(traceStartedAt(right)))
  const min = Math.min(...sorted.map((trace) => timestamp(traceStartedAt(trace))).filter(Boolean))
  const max = Math.max(...sorted.map((trace) => timestamp(traceEndedAt(trace)) || timestamp(traceStartedAt(trace)) + (trace.total_latency_ms ?? 0)))
  const range = Math.max(1, max - min)

  return (
    <div className="space-y-4">
      <section className="rounded-xl border border-border/90 bg-surface/70 p-4">
        <div className="flex items-start gap-3">
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-violet-500/25 bg-violet-500/10 text-violet-300"><Network className="h-5 w-5" /></div>
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-2"><h2 className="truncate text-base font-semibold text-white">{group.networkName}</h2><RunStatusBadge status={group.status} /></div>
            <p className="mt-1 text-xs text-muted">Network Run · {group.environment ?? 'environment unknown'}{group.versionLabel ? ` · ${group.versionLabel}` : ''}</p>
          </div>
        </div>
        <div className="mt-4 grid gap-3 border-t border-border/70 pt-4 sm:grid-cols-2 xl:grid-cols-5">
          <div><p className="text-[10px] uppercase tracking-wide text-muted">Duration</p><p className="mt-1 text-sm font-medium text-white">{formatLatency(group.durationMs)}</p></div>
          <div><p className="text-[10px] uppercase tracking-wide text-muted">Agent Runs</p><p className="mt-1 text-sm font-medium text-white">{group.traces.length}</p></div>
          <div><p className="text-[10px] uppercase tracking-wide text-muted">Tool/Skill operations</p><p className="mt-1 text-sm font-medium text-white">{totalTools}</p></div>
          <div><p className="text-[10px] uppercase tracking-wide text-muted">Tokens</p><p className="mt-1 text-sm font-medium text-white">{totalTokens ? formatTokens(totalTokens) : 'Unknown'}</p></div>
          <div><p className="text-[10px] uppercase tracking-wide text-muted">Cost</p><p className="mt-1 text-sm font-medium text-white">{group.costUsd == null ? 'Partial/unknown' : formatMoney(group.costUsd)}</p></div>
        </div>
      </section>

      {failed.length ? <section className="rounded-xl border border-amber-500/30 bg-amber-500/10 p-4"><div className="flex items-center gap-2 text-amber-100"><TriangleAlert className="h-4 w-4" /><h3 className="text-sm font-semibold">{failed.length} Agent Run failure{failed.length === 1 ? '' : 's'} inside this Network Run</h3></div><p className="mt-2 text-xs leading-5 text-amber-100/80">Inspect the execution path to distinguish a handled child failure from the root cause of a failed Network Run.</p></section> : null}

      {group.inputPreview ? <DetailSection title="Request"><p className="whitespace-pre-wrap text-xs leading-5 text-slate-200">{group.inputPreview}</p></DetailSection> : null}

      <DetailSection title="Execution path" description="Agent Runs correlated to the same Network Run, ordered by execution start.">
        <div className="space-y-2">
          {sorted.map((trace, index) => {
            const agentName = trace.agent_id ? agentNames.get(trace.agent_id) ?? `Agent ${compactId(trace.agent_id)}` : 'Agent Run'
            const childStatus = normalizedStatus(trace.status)
            return (
              <button key={trace.id} type="button" onClick={() => onSelectAgent(trace)} className="group grid w-full gap-2 rounded-lg border border-border/70 bg-background/35 p-3 text-left transition-colors hover:border-primary/30 hover:bg-background/55 sm:grid-cols-[32px_minmax(0,1fr)_100px_90px] sm:items-center">
                <div className="flex h-8 w-8 items-center justify-center rounded-lg border border-border bg-surface text-primary-light">{index === 0 ? <Route className="h-4 w-4" /> : <Bot className="h-4 w-4" />}</div>
                <div className="min-w-0"><p className="truncate text-xs font-medium text-white">{agentName}</p><p className="mt-1 text-[10px] text-muted">{index === 0 ? 'Entry Agent' : 'Delegated Agent'} · {trace.provider || 'provider unknown'}/{trace.model || 'model unknown'}</p></div>
                <RunStatusBadge status={childStatus} />
                <p className="text-xs text-muted sm:text-right">{formatLatency(trace.total_latency_ms)}</p>
              </button>
            )
          })}
        </div>
      </DetailSection>

      <DetailSection title="Network waterfall" description="Relative execution windows expose parallelism and the likely critical path.">
        <div className="space-y-2">
          {sorted.map((trace, index) => {
            const start = timestamp(traceStartedAt(trace)) || min
            const end = timestamp(traceEndedAt(trace)) || start + (trace.total_latency_ms ?? 0)
            const left = ((start - min) / range) * 100
            const width = Math.max(2, ((Math.max(end, start) - start) / range) * 100)
            const agentName = trace.agent_id ? agentNames.get(trace.agent_id) ?? `Agent ${compactId(trace.agent_id)}` : `Agent Run ${index + 1}`
            return <div key={trace.id} className="grid gap-2 md:grid-cols-[160px_minmax(0,1fr)_70px] md:items-center"><p className="truncate text-[11px] text-slate-200">{agentName}</p><div className="relative h-5 overflow-hidden rounded-md border border-border/60 bg-background/70"><div className={cn('absolute top-1/2 h-2.5 -translate-y-1/2 rounded-full', normalizedStatus(trace.status) === 'failed' ? 'bg-red-400/75' : 'bg-violet-400/70')} style={{ left: `${left}%`, width: `${Math.min(100 - left, width)}%` }} /></div><p className="text-right font-mono text-[10px] text-muted">{formatLatency(trace.total_latency_ms)}</p></div>
          })}
        </div>
      </DetailSection>

      <DetailSection title="Run evidence" description="Identifiers and child Trace references for audit and incident correlation.">
        <div className="grid gap-2 sm:grid-cols-2">
          <div className="rounded-lg border border-border/70 bg-background/40 p-3"><p className="text-[10px] uppercase tracking-wide text-muted">Network Run ID</p><code className="mt-2 block truncate text-xs text-white">{group.id}</code></div>
          <div className="rounded-lg border border-border/70 bg-background/40 p-3"><p className="text-[10px] uppercase tracking-wide text-muted">Network ID</p><code className="mt-2 block truncate text-xs text-white">{group.networkId ?? '—'}</code></div>
          {sorted.map((trace, index) => <button key={trace.id} type="button" onClick={() => onSelectAgent(trace)} className="rounded-lg border border-border/70 bg-background/40 p-3 text-left hover:border-primary/30"><p className="text-[10px] uppercase tracking-wide text-muted">Agent Run {index + 1} Trace</p><code className="mt-2 block truncate text-xs text-white">{trace.id}</code></button>)}
        </div>
      </DetailSection>
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
  const { data: traces, isLoading, isError, error, refetch } = useTraces(projectId, networkFilter === 'all' ? undefined : networkFilter)

  const networkNames = useMemo(() => new Map((networksQuery.data ?? []).map((network) => [network.id, network.name])), [networksQuery.data])
  const agentNames = useMemo(() => new Map((agentsQuery.data ?? []).map((agent) => [agent.id, agent.name])), [agentsQuery.data])
  const items = traces ?? []

  const networkGroups = useMemo(() => {
    const grouped = new Map<string, Trace[]>()
    items.forEach((trace) => {
      if (!trace.network_execution_id) return
      const current = grouped.get(trace.network_execution_id) ?? []
      current.push(trace)
      grouped.set(trace.network_execution_id, current)
    })
    return [...grouped.entries()].map(([id, correlated]) => {
      const sorted = correlated.slice().sort((left, right) => timestamp(traceStartedAt(left)) - timestamp(traceStartedAt(right)))
      const rootTrace = sorted[0]
      const duration = networkDuration(sorted)
      const networkId = rootTrace.network_id ?? null
      return {
        id,
        networkId,
        networkName: networkId ? networkNames.get(networkId) ?? `Network ${compactId(networkId)}` : 'Network Run',
        traces: sorted,
        rootTrace,
        status: aggregateNetworkStatus(sorted),
        ...duration,
        costUsd: knownCostSum(sorted),
        environment: environmentLabel(rootTrace),
        versionLabel: versionLabel(rootTrace),
        inputPreview: inputPreview(rootTrace),
      } satisfies NetworkRunGroup
    })
  }, [items, networkNames])

  const networkGroupsById = useMemo(() => new Map(networkGroups.map((group) => [group.id, group])), [networkGroups])
  const tracesById = useMemo(() => new Map(items.map((trace) => [trace.id, trace])), [items])
  const directAgentRuns = useMemo(() => items.filter((trace) => !trace.network_execution_id), [items])

  const baseEntries = useMemo<RunEntry[]>(() => {
    const networkEntries = networkGroups.map((group) => ({ key: `network:${group.id}`, kind: 'network' as const, group, sortAt: timestamp(group.startedAt) }))
    const agentSource = runType === 'agent' ? items : directAgentRuns
    const agentEntries = agentSource.map((trace) => ({ key: `agent:${trace.id}`, kind: 'agent' as const, trace, sortAt: timestamp(traceStartedAt(trace)) }))
    if (runType === 'network') return networkEntries.sort((left, right) => right.sortAt - left.sortAt)
    if (runType === 'agent') return agentEntries.sort((left, right) => right.sortAt - left.sortAt)
    return [...networkEntries, ...agentEntries].sort((left, right) => right.sortAt - left.sortAt)
  }, [directAgentRuns, items, networkGroups, runType])

  const normalizedQuery = query.trim().toLowerCase()
  const visibleEntries = useMemo(() => baseEntries.filter((entry) => {
    const status = entry.kind === 'network' ? entry.group.status : normalizedStatus(entry.trace.status)
    if (!statusMatches(status, statusFilter)) return false
    if (!normalizedQuery) return true
    if (entry.kind === 'network') {
      return [entry.group.id, entry.group.networkName, entry.group.environment, entry.group.versionLabel, entry.group.inputPreview]
        .filter(Boolean).join(' ').toLowerCase().includes(normalizedQuery)
        || entry.group.traces.some((trace) => traceSearchText(trace, trace.agent_id ? agentNames.get(trace.agent_id) : null, entry.group.networkName).includes(normalizedQuery))
    }
    return traceSearchText(entry.trace, entry.trace.agent_id ? agentNames.get(entry.trace.agent_id) : null, entry.trace.network_id ? networkNames.get(entry.trace.network_id) : null).includes(normalizedQuery)
  }), [agentNames, baseEntries, networkNames, normalizedQuery, statusFilter])

  const statusCounts = useMemo(() => ({
    all: baseEntries.length,
    running: baseEntries.filter((entry) => statusMatches(entry.kind === 'network' ? entry.group.status : normalizedStatus(entry.trace.status), 'running')).length,
    completed: baseEntries.filter((entry) => statusMatches(entry.kind === 'network' ? entry.group.status : normalizedStatus(entry.trace.status), 'completed')).length,
    failed: baseEntries.filter((entry) => statusMatches(entry.kind === 'network' ? entry.group.status : normalizedStatus(entry.trace.status), 'failed')).length,
    cancelled: baseEntries.filter((entry) => statusMatches(entry.kind === 'network' ? entry.group.status : normalizedStatus(entry.trace.status), 'cancelled')).length,
  }), [baseEntries])

  const topLevelRuns = useMemo(() => [
    ...networkGroups.map((group) => ({ status: group.status, duration: group.durationMs })),
    ...directAgentRuns.map((trace) => ({ status: normalizedStatus(trace.status), duration: trace.total_latency_ms ?? null })),
  ], [directAgentRuns, networkGroups])
  const activeRuns = topLevelRuns.filter((run) => run.status === 'running' || run.status === 'pending').length
  const failedRuns = topLevelRuns.filter((run) => run.status === 'failed').length
  const failureRate = topLevelRuns.length ? (failedRuns / topLevelRuns.length) * 100 : 0
  const p95Latency = percentile(topLevelRuns.map((run) => run.duration).filter((value): value is number => typeof value === 'number'), 0.95)
  const averageAgentRuns = networkGroups.length ? networkGroups.reduce((total, group) => total + group.traces.length, 0) / networkGroups.length : 0

  const selectedNetworkId = selectedKey?.startsWith('network:') ? selectedKey.slice('network:'.length) : null
  const selectedAgentId = selectedKey?.startsWith('agent:') ? selectedKey.slice('agent:'.length) : null
  const selectedNetwork = selectedNetworkId ? networkGroupsById.get(selectedNetworkId) ?? null : null
  const selectedAgent = selectedAgentId ? tracesById.get(selectedAgentId) ?? null : null
  const { data: selectedAgentDetail, isLoading: detailLoading } = useTraceDetail(selectedAgent?.id)
  const hasFilters = runType !== 'all' || statusFilter !== 'all' || networkFilter !== 'all' || query.trim().length > 0

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
    <ResourcePage title="Runs" description="Central operational view of Agent Runs, Network Runs and their Trace evidence.">
      <ResourceToolbar>
        <ResourceTabs
          value={runType}
          onChange={setRunType}
          label="Filter by Run type"
          tabs={[
            { value: 'all', label: 'All Runs', count: networkGroups.length + directAgentRuns.length },
            { value: 'network', label: 'Network Runs', count: networkGroups.length },
            { value: 'agent', label: 'Agent Runs', count: items.length },
          ]}
        />
        <ResourceTabs
          value={statusFilter}
          onChange={setStatusFilter}
          label="Filter Runs by status"
          tabs={[
            { value: 'all', label: 'All', count: statusCounts.all },
            { value: 'running', label: 'Running', count: statusCounts.running },
            { value: 'completed', label: 'Completed', count: statusCounts.completed },
            { value: 'failed', label: 'Failed', count: statusCounts.failed },
            { value: 'cancelled', label: 'Cancelled', count: statusCounts.cancelled },
          ]}
        />
        <label className="flex items-center gap-2 rounded-xl border border-border bg-background/55 px-3 py-2 text-xs text-muted">
          <span className="shrink-0">Network</span>
          <select value={networkFilter} onChange={(event) => setNetworkFilter(event.target.value)} className="min-w-36 bg-transparent text-xs text-white outline-none">
            <option value="all">All Networks</option>
            {(networksQuery.data ?? []).map((network) => <option key={network.id} value={network.id}>{network.name}</option>)}
          </select>
        </label>
        <ResourceSearch value={query} onChange={setQuery} placeholder="Search Runs, Agents, Networks, sessions or models..." label="Search Runs" />
      </ResourceToolbar>

      <section className="grid gap-3 md:grid-cols-2 xl:grid-cols-6">
        <MetricCard label="Active now" value={String(activeRuns)} detail="Queued or running" />
        <MetricCard label="Agent Runs" value={String(items.length)} detail={`${directAgentRuns.length} direct · ${items.length - directAgentRuns.length} in Networks`} />
        <MetricCard label="Network Runs" value={String(networkGroups.length)} detail="Composite executions" />
        <MetricCard label="Failure rate" value={`${failureRate.toFixed(1)}%`} detail={`${failedRuns} failed top-level Runs`} />
        <MetricCard label="P95 latency" value={p95Latency == null ? '—' : formatLatency(p95Latency)} detail="Top-level Run duration" />
        <MetricCard label="Runs / Network" value={averageAgentRuns.toFixed(1)} detail="Average Agent Runs" />
      </section>

      <section>
        <ResourceSectionHeader title="Operational run stream" description="Network Runs contain their correlated Agent Runs. Select a Run to inspect behavior, latency and evidence." count={visibleEntries.length} />

        {isLoading ? (
          <LoadingState message="Loading Runs" variant="panel" layout="resource-list" />
        ) : isError ? (
          <ErrorState error={error} onRetry={refetch} className="rounded-xl border border-border/80 bg-surface/40 py-10" />
        ) : visibleEntries.length ? (
          <div className="grid min-h-[620px] gap-4 xl:grid-cols-[minmax(0,1.18fr)_minmax(420px,.82fr)]">
            <div className="min-w-0 overflow-hidden rounded-xl border border-border/90 bg-surface/70">
              {visibleEntries.map((entry) => entry.kind === 'network' ? (
                <NetworkRunRow
                  key={entry.key}
                  group={entry.group}
                  agentNames={agentNames}
                  selectedKey={selectedKey}
                  expanded={expandedNetworkIds.has(entry.group.id)}
                  onToggle={() => toggleNetwork(entry.group.id)}
                  onSelectNetwork={() => setSelectedKey(entry.key)}
                  onSelectAgent={(trace) => setSelectedKey(`agent:${trace.id}`)}
                />
              ) : (
                <AgentRunRow
                  key={entry.key}
                  trace={entry.trace}
                  agentName={entry.trace.agent_id ? agentNames.get(entry.trace.agent_id) ?? `Agent ${compactId(entry.trace.agent_id)}` : 'Agent Run'}
                  networkName={entry.trace.network_id ? networkNames.get(entry.trace.network_id) : null}
                  selected={selectedKey === entry.key}
                  onSelect={() => setSelectedKey(entry.key)}
                />
              ))}
            </div>

            <aside className={cn('min-w-0 max-h-[calc(100vh-170px)] overflow-y-auto pr-1 xl:sticky xl:top-4 xl:self-start', panelScrollClass)}>
              {selectedNetwork ? (
                <NetworkRunInspector group={selectedNetwork} agentNames={agentNames} onSelectAgent={(trace) => setSelectedKey(`agent:${trace.id}`)} />
              ) : selectedAgent ? (
                detailLoading ? <LoadingState message="Loading Agent Run" variant="panel" /> : <AgentRunInspector trace={selectedAgent} detail={selectedAgentDetail} agentName={selectedAgent.agent_id ? agentNames.get(selectedAgent.agent_id) ?? `Agent ${compactId(selectedAgent.agent_id)}` : 'Agent Run'} networkName={selectedAgent.network_id ? networkNames.get(selectedAgent.network_id) : null} />
              ) : (
                <div className="flex min-h-[420px] items-center justify-center rounded-xl border border-dashed border-border/80 bg-surface/35 p-8 text-center">
                  <div><Activity className="mx-auto h-8 w-8 text-muted/40" /><h3 className="mt-3 text-sm font-semibold text-white">Select a Run</h3><p className="mt-2 max-w-sm text-xs leading-5 text-muted">Inspect the execution path of a Network Run or open an Agent Run to review its timeline, model calls, Skills, Tools, Knowledge and Trace evidence.</p></div>
                </div>
              )}
            </aside>
          </div>
        ) : (
          <ResourceEmptyState
            icon={<Activity className="h-4 w-4" />}
            title="No Runs found"
            description={hasFilters ? 'Adjust or clear the active filters.' : 'Agent Runs and Network Runs appear here as soon as the runtime accepts an execution.'}
            action={hasFilters ? <Button type="button" size="sm" variant="outline" onClick={() => { setRunType('all'); setStatusFilter('all'); setNetworkFilter('all'); setQuery('') }}>Clear filters</Button> : undefined}
          />
        )}
      </section>
    </ResourcePage>
  )
}
