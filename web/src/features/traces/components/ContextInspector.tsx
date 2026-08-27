import { AlertTriangle, Brain, ChevronRight, RefreshCw } from 'lucide-react'
import { JsonCodeBlock } from '@/components/ui/JsonCodeBlock'
import { formatTokens } from '@/lib/formatters/number'
import { cn } from '@/lib/utils'
import { useTraceModelInvocations } from '../hooks'
import type { ContextModelInvocation, ContextSnapshotEvidence } from '../types'

function pressureClass(status: string | undefined): string {
  switch ((status ?? '').toUpperCase()) {
    case 'CRITICAL':
      return 'border-red-500/25 bg-red-500/10 text-red-300'
    case 'HIGH':
      return 'border-orange-500/25 bg-orange-500/10 text-orange-300'
    case 'MODERATE':
      return 'border-yellow-500/25 bg-yellow-500/10 text-yellow-300'
    case 'LOW':
      return 'border-emerald-500/25 bg-emerald-500/10 text-emerald-300'
    default:
      return 'border-border bg-background text-muted'
  }
}

function formatPercent(value: number | null | undefined): string {
  if (value == null || !Number.isFinite(value)) return '—'
  return `${(value * 100).toFixed(value >= 0.1 ? 1 : 2)}%`
}

function formatUnits(value: number | null | undefined): string {
  return value == null ? '—' : formatTokens(value)
}

function asRecord(value: unknown): Record<string, unknown> | null {
  return value && typeof value === 'object' && !Array.isArray(value)
    ? value as Record<string, unknown>
    : null
}

function metric(snapshot: ContextSnapshotEvidence, key: string): number | null {
  const metrics = asRecord(snapshot.manifest?.metrics)
  const value = metrics?.[key]
  return typeof value === 'number' && Number.isFinite(value) ? value : null
}

function warnings(snapshot: ContextSnapshotEvidence): string[] {
  const value = asRecord(snapshot.manifest?.health)
  const raw = value?.warnings
  return Array.isArray(raw)
    ? raw.filter((item): item is string => typeof item === 'string')
    : []
}

function warningLabel(value: string): string {
  switch (value) {
    case 'usable_input_budget_unknown':
      return 'Model context capacity unavailable'
    case 'context_truncation_applied':
      return 'Context was truncated before this invocation'
    case 'multimodal_units_not_fully_comparable':
      return 'Multimodal units are only partially comparable'
    default:
      return value.replaceAll('_', ' ')
  }
}

function median(values: number[]): number | null {
  if (!values.length) return null
  const sorted = [...values].sort((a, b) => a - b)
  const middle = Math.floor(sorted.length / 2)
  return sorted.length % 2 === 0
    ? (sorted[middle - 1] + sorted[middle]) / 2
    : sorted[middle]
}

function RunContextSummary({ invocations }: { invocations: ContextModelInvocation[] }) {
  const snapshots = invocations
    .map((invocation) => invocation.context_snapshot)
    .filter((snapshot): snapshot is ContextSnapshotEvidence => Boolean(snapshot))
  const totalInput = snapshots.reduce(
    (total, snapshot) => total + (snapshot.reported_input_units ?? snapshot.estimated_input_units ?? 0),
    0,
  )
  const utilizations = snapshots
    .map((snapshot) => snapshot.utilization)
    .filter((value): value is number => typeof value === 'number' && Number.isFinite(value))
  const budgetUnknown = snapshots.filter((snapshot) => snapshot.usable_input_budget == null).length
  const compactionSaving = snapshots.reduce(
    (total, snapshot) => total + (metric(snapshot, 'compaction_saving_units') ?? 0),
    0,
  )
  const truncationCount = snapshots.reduce(
    (total, snapshot) => total + (metric(snapshot, 'truncation_count') ?? 0),
    0,
  )

  return (
    <div className="rounded-lg border border-border bg-background px-2.5 py-2">
      <div className="flex items-end justify-between gap-3">
        <div>
          <p className="text-[9px] uppercase tracking-wider text-muted">Run model input</p>
          <p className="mt-0.5 text-sm font-mono text-white">{formatUnits(totalInput)}</p>
        </div>
        <span className="text-[9px] text-muted">{snapshots.length} invocation{snapshots.length === 1 ? '' : 's'}</span>
      </div>
      <div className="mt-2 flex flex-wrap gap-x-3 gap-y-1 text-[9px] text-muted">
        {utilizations.length ? <span>Median utilization {formatPercent(median(utilizations))}</span> : null}
        {budgetUnknown ? <span className="text-amber-300">Budget unavailable for {budgetUnknown}</span> : null}
        {compactionSaving > 0 ? <span>Compaction saved {formatUnits(compactionSaving)}</span> : null}
        {truncationCount > 0 ? <span className="text-amber-300">{truncationCount} truncated</span> : null}
      </div>
    </div>
  )
}

type CompositionRow = {
  key: string
  label: string
  units: number
  count: number
}

function compositionLabel(sourceType: string, sourceRef?: string | null): { key: string; label: string } {
  if (sourceType === 'SYSTEM' && sourceRef === 'runtime_tool_definitions') {
    return { key: 'tool_definitions', label: 'Tool definitions' }
  }
  switch (sourceType) {
    case 'SYSTEM':
      return { key: 'system', label: 'System instructions' }
    case 'SESSION':
      return { key: 'session', label: 'Conversation' }
    case 'USER_INPUT':
      return { key: 'user_input', label: 'Current input' }
    case 'KNOWLEDGE':
      return { key: 'knowledge', label: 'Knowledge' }
    case 'TOOL':
      return { key: 'tool', label: 'Tool results' }
    case 'DELEGATION':
      return { key: 'delegation', label: 'Delegation' }
    case 'RUNTIME':
      return { key: 'runtime', label: 'Runtime instructions' }
    case 'CHECKPOINT':
      return { key: 'checkpoint', label: 'Checkpoint' }
    case 'MEMORY':
      return { key: 'memory', label: 'Memory' }
    case 'ARTIFACT':
      return { key: 'artifact', label: 'Artifacts' }
    default:
      return { key: sourceType.toLowerCase(), label: sourceType }
  }
}

function Composition({ snapshot }: { snapshot: ContextSnapshotEvidence }) {
  const groups = new Map<string, CompositionRow>()
  for (const contribution of snapshot.contributions) {
    const { key, label } = compositionLabel(contribution.source_type, contribution.source_ref)
    const existing = groups.get(key)
    const units = contribution.materialized_units ?? 0
    if (existing) {
      existing.units += units
      existing.count += 1
    } else {
      groups.set(key, { key, label, units, count: 1 })
    }
  }
  const rows = [...groups.values()].sort((a, b) => b.units - a.units)
  const total = rows.reduce((sum, row) => sum + row.units, 0)
  if (!rows.length) return null

  return (
    <div className="space-y-1">
      {rows.map((row) => (
        <div key={row.key} className="grid grid-cols-[minmax(0,1fr)_auto_auto] items-center gap-2 text-[10px]">
          <span className="truncate text-slate-300">{row.label}{row.count > 1 ? ` · ${row.count}` : ''}</span>
          <span className="font-mono text-slate-200">{formatUnits(row.units)}</span>
          <span className="w-11 text-right text-muted">{formatPercent(total > 0 ? row.units / total : null)}</span>
        </div>
      ))}
    </div>
  )
}

function InvocationCard({ invocation }: { invocation: ContextModelInvocation }) {
  const snapshot = invocation.context_snapshot
  if (!snapshot) return null

  const providerReported = snapshot.reported_input_units
  const input = providerReported ?? snapshot.estimated_input_units
  const snapshotWarnings = warnings(snapshot)
  const selected = metric(snapshot, 'selected_count')
  const candidates = metric(snapshot, 'raw_candidate_count')
  const compactionSaving = metric(snapshot, 'compaction_saving_units') ?? 0
  const truncationCount = metric(snapshot, 'truncation_count') ?? 0
  const modalities = asRecord(snapshot.manifest?.modalities)
  const aggregateComparable = modalities?.aggregate_comparable !== false
  const budgetKnown = snapshot.usable_input_budget != null
  const pressureKnown = budgetKnown && snapshot.utilization != null

  return (
    <div className="rounded-lg border border-border bg-background p-2.5 space-y-2.5">
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="truncate text-[11px] font-medium text-white">
            Invocation #{invocation.call_index ?? '—'} · {invocation.phase || 'model_invocation'}
          </p>
          <p className="truncate font-mono text-[10px] text-muted">
            {invocation.provider || '—'}/{invocation.model || '—'}
          </p>
        </div>
        {pressureKnown ? (
          <span className={cn(
            'shrink-0 rounded-full border px-1.5 py-0.5 text-[9px] font-medium',
            pressureClass(snapshot.pressure_status),
          )}>
            {snapshot.pressure_status} pressure
          </span>
        ) : (
          <span className="shrink-0 rounded-full border border-amber-500/25 bg-amber-500/10 px-1.5 py-0.5 text-[9px] font-medium text-amber-300">
            Budget unavailable
          </span>
        )}
      </div>

      <div className="grid grid-cols-2 gap-1.5">
        <div className="rounded border border-border px-2 py-1.5">
          <p className="text-[9px] uppercase tracking-wider text-muted">Input</p>
          <p className="text-[12px] font-mono text-white">{formatUnits(input)}</p>
          <p className="text-[9px] text-muted">{providerReported != null ? 'Provider reported' : 'Woobe estimate'}</p>
        </div>
        <div className="rounded border border-border px-2 py-1.5">
          <p className="text-[9px] uppercase tracking-wider text-muted">Context budget</p>
          <p className="text-[12px] font-mono text-white">{budgetKnown ? formatUnits(snapshot.usable_input_budget) : 'Unavailable'}</p>
          <p className="text-[9px] text-muted">
            {budgetKnown ? `${formatPercent(snapshot.utilization)} used` : 'Model capacity was not resolved'}
          </p>
        </div>
      </div>

      <div>
        <div className="mb-1.5 flex items-center justify-between gap-2">
          <p className="text-[9px] uppercase tracking-wider text-muted">Composition</p>
          <span className="text-[9px] text-muted">estimated shares</span>
        </div>
        <Composition snapshot={snapshot} />
      </div>

      <div className="flex flex-wrap gap-x-3 gap-y-1 text-[9px] text-muted">
        {selected != null && candidates != null ? <span>{selected}/{candidates} selected</span> : null}
        {compactionSaving > 0 ? <span>Saved {formatUnits(compactionSaving)} by compaction</span> : null}
        {truncationCount > 0 ? <span className="text-amber-300">{truncationCount} truncated</span> : null}
        {providerReported != null ? <span>Pre-call estimate {formatUnits(snapshot.estimated_input_units)}</span> : null}
        {snapshot.model_capacity_units != null ? <span>Capacity {formatUnits(snapshot.model_capacity_units)}</span> : null}
        {snapshot.reserved_output_units != null ? <span>Output reserve {formatUnits(snapshot.reserved_output_units)}</span> : null}
      </div>

      {!aggregateComparable ? (
        <div className="flex items-start gap-1.5 rounded border border-amber-500/20 bg-amber-500/5 px-2 py-1.5 text-[9px] text-amber-200">
          <AlertTriangle className="mt-0.5 h-3 w-3 shrink-0" />
          Multimodal Context uses partial source-level accounting; values are not treated as exact text-token equivalents.
        </div>
      ) : null}

      {snapshotWarnings.length > 0 ? (
        <div className="space-y-1">
          {snapshotWarnings.map((warning) => (
            <p key={warning} className="flex items-center gap-1.5 text-[9px] text-amber-300">
              <AlertTriangle className="h-3 w-3 shrink-0" />
              {warningLabel(warning)}
            </p>
          ))}
        </div>
      ) : null}

      <details className="group border-t border-border/70 pt-2">
        <summary className="flex cursor-pointer list-none items-center gap-1 text-[9px] text-muted hover:text-white">
          <ChevronRight className="h-3 w-3 transition-transform group-open:rotate-90" />
          Technical context evidence
        </summary>
        <div className="mt-2 space-y-1.5">
          <div className="flex flex-wrap gap-x-3 gap-y-1 text-[9px] text-muted">
            <span>measurement {snapshot.measurement_status}</span>
            <span>retention {snapshot.retention_mode}</span>
            <span>reproduction {snapshot.reproduction_level}</span>
          </div>
          <JsonCodeBlock value={snapshot.manifest} maxHeight={180} />
          <JsonCodeBlock value={snapshot.contributions} maxHeight={180} />
          <p className="break-all text-[9px] text-muted">
            policy {snapshot.policy_hash} · materialized {snapshot.materialized_hash}
          </p>
        </div>
      </details>
    </div>
  )
}

export function ContextInspector({ traceId }: { traceId: string }) {
  const { data, isLoading, isError, error, refetch } = useTraceModelInvocations(traceId)

  if (isLoading) {
    return (
      <div className="px-4 pb-4">
        <div className="flex items-center gap-2 rounded-lg border border-border bg-surface/30 p-3 text-xs text-muted">
          <RefreshCw className="h-3.5 w-3.5 animate-spin" />
          Loading Context evidence...
        </div>
      </div>
    )
  }

  if (isError) {
    return (
      <div className="px-4 pb-4">
        <div className="space-y-1.5 rounded-lg border border-border bg-surface/30 p-3">
          <div className="flex items-center gap-2 text-xs text-muted">
            <Brain className="h-3.5 w-3.5" />
            Context evidence unavailable
          </div>
          {error instanceof Error ? <p className="text-[10px] text-muted">{error.message}</p> : null}
          <button onClick={() => refetch()} className="text-[10px] text-primary hover:underline">
            Retry
          </button>
        </div>
      </div>
    )
  }

  if (!data?.length) return null

  return (
    <div className="space-y-2 px-4 pb-4">
      <div className="flex items-center gap-2 border-t border-border pt-3">
        <Brain className="h-3.5 w-3.5 text-muted" />
        <span className="text-xs font-medium text-white">Context</span>
        <span className="ml-auto text-[10px] text-muted">{data.length} model invocation{data.length === 1 ? '' : 's'}</span>
      </div>
      <RunContextSummary invocations={data} />
      {data.map((invocation, index) => (
        <InvocationCard key={invocation.id ?? `${invocation.call_index ?? index}-${index}`} invocation={invocation} />
      ))}
    </div>
  )
}
