import { RunMetrics } from '@/features/traces/components/RunMetrics'
import {
  AlertTriangle,
  ChevronRight,
  RefreshCw,
} from 'lucide-react'
import { ContributionBars, SectionBlock } from '@woobe/ui'

import { JsonCodeBlock } from '@/components/ui/JsonCodeBlock'
import { useAgentRunDetail, useContextModelInvocations } from '@/features/traces/hooks'
import type { ContextModelInvocation, ContextSnapshotEvidence } from '@/features/traces/types'
import { formatCurrency, formatLatency, formatTokens } from '@/lib/formatters/number'
import { cn } from '@/lib/utils'

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : {}
}

function numberOrNull(value: unknown): number | null {
  if (typeof value === 'number' && Number.isFinite(value)) return value
  if (typeof value === 'string' && value.trim()) {
    const parsed = Number(value)
    return Number.isFinite(parsed) ? parsed : null
  }
  return null
}

function formatPercent(value: number | null | undefined): string {
  if (value == null || !Number.isFinite(value)) return '—'
  return `${(value * 100).toFixed(value >= 0.1 ? 1 : 2)}%`
}

function metricText(snapshot: ContextSnapshotEvidence, key: string): string | null {
  const metrics = asRecord(asRecord(snapshot.manifest).metrics)
  const value = metrics[key]
  return typeof value === 'string' && value.trim() ? value : null
}

type CompositionRow = {
  key: string
  label: string
  units: number | null
  contributions: number
}

function compositionLabel(sourceType: string, sourceRef?: string | null): { key: string; label: string } {
  if (sourceType === 'SYSTEM' && sourceRef === 'runtime_tool_definitions') return { key: 'tool_definitions', label: 'Tool / Skill definitions' }
  switch (sourceType) {
    case 'SYSTEM': return { key: 'system', label: 'System instructions' }
    case 'SKILL': return { key: 'skill', label: 'Skills' }
    case 'SESSION': return { key: 'session', label: 'Conversation' }
    case 'USER_INPUT': return { key: 'user_input', label: 'Current input' }
    case 'KNOWLEDGE': return { key: 'knowledge', label: 'Knowledge' }
    case 'TOOL': return { key: 'tool', label: 'Tool / Skill results' }
    case 'DELEGATION': return { key: 'delegation', label: 'Delegation' }
    case 'RUNTIME': return { key: 'runtime', label: 'Runtime instructions' }
    case 'CHECKPOINT': return { key: 'checkpoint', label: 'Checkpoint' }
    case 'MEMORY': return { key: 'memory', label: 'Memory' }
    case 'ARTIFACT': return { key: 'artifact', label: 'Artifacts' }
    default: return { key: sourceType.toLowerCase(), label: sourceType }
  }
}

function aggregateComposition(invocations: ContextModelInvocation[]): CompositionRow[] {
  const groups = new Map<string, CompositionRow>()
  for (const invocation of invocations) {
    for (const contribution of invocation.context_snapshot?.contributions ?? []) {
      const { key, label } = compositionLabel(contribution.source_type, contribution.source_ref)
      const units = contribution.materialized_units ?? null
      const current = groups.get(key)
      if (current) {
        current.units = current.units == null || units == null ? null : current.units + units
        current.contributions += 1
      } else {
        groups.set(key, { key, label, units, contributions: 1 })
      }
    }
  }
  return [...groups.values()].sort((left, right) => (right.units ?? -1) - (left.units ?? -1))
}

function invocationComposition(invocation: ContextModelInvocation): CompositionRow[] {
  const snapshot = invocation.context_snapshot
  if (!snapshot) return []
  return aggregateComposition([{ ...invocation, context_snapshot: snapshot }])
}

function CompositionRows({ rows }: { rows: CompositionRow[] }) {
  const total = rows.reduce((sum, row) => sum + (row.units ?? 0), 0)
  if (!rows.length) return <p className="font-sans text-system-meta leading-4 text-muted-foreground">No source-level Context composition was persisted for this Run.</p>

  return <ContributionBars unit="Persisted contribution units" rows={rows.map(row => ({ id: row.key, label: row.label, value: row.units, share: total > 0 && rows.every(item => item.units != null) && row.units != null ? row.units / total : null }))} />
}

function InvocationDetails({ invocation, index }: { invocation: ContextModelInvocation; index: number }) {
  const snapshot = invocation.context_snapshot
  const rows = invocationComposition(invocation)
  const input = invocation.input_units ?? snapshot?.reported_input_units ?? snapshot?.estimated_input_units ?? null
  const output = invocation.output_units ?? null
  const total = invocation.total_units ?? (input != null && output != null ? input + output : null)
  const fitStatus = snapshot ? metricText(snapshot, 'context_fit_status') : null
  const blocked = asRecord(invocation.data).code === 'CONTEXT_BUDGET_EXCEEDED'
  const callIndex = invocation.call_index ?? index + 1

  return (
    <details className="group border-t border-border/60 first:border-t-0">
      <summary className="flex cursor-pointer list-none items-center gap-2 px-2 py-2.5 text-left">
        <ChevronRight className="h-3 w-3 shrink-0 text-muted-foreground transition-transform group-open:rotate-90" />
        <div className="min-w-0 flex-1">
          <p className="break-words font-mono text-system-meta font-medium text-slate-200">Invocation #{callIndex} · {invocation.phase || 'model_invocation'}</p>
          <p className="break-all font-mono text-system-meta text-muted-foreground">{invocation.provider || '—'}/{invocation.model || '—'}</p>
        </div>
        <div className="shrink-0 text-right">
          <p className="font-mono text-system-meta text-slate-300">{total == null ? '—' : formatTokens(total)}</p>
          <p className="font-mono text-system-meta text-muted-foreground">{invocation.latency_ms == null ? '—' : formatLatency(invocation.latency_ms)} · {formatCurrency(invocation.cost_usd ?? null)}</p>
        </div>
      </summary>

      <div className="space-y-3 px-2 pb-3 pl-7">
        {blocked ? <div className="flex items-start gap-1.5 rounded-container border border-red-500/20 bg-background/25 px-2.5 py-2 font-sans text-system-meta leading-4 text-error"><AlertTriangle className="mt-0.5 h-3 w-3 shrink-0" />Provider call was blocked because mandatory Context exceeded the invocation budget.</div> : null}

        <div className="grid grid-cols-2 gap-px overflow-hidden rounded-container border border-border/70 bg-border/70">
          {[
            ['Input', input == null ? '—' : formatTokens(input)],
            ['Output', output == null ? '—' : formatTokens(output)],
            ['Effective budget', snapshot?.usable_input_budget == null ? 'Unavailable' : formatTokens(snapshot.usable_input_budget)],
            ['Context utilization', formatPercent(snapshot?.utilization)],
            ['Measurement', snapshot?.measurement_status || 'Unavailable'],
            ['Context fit', blocked ? 'UNFIT' : fitStatus || '—'],
          ].map(([label, value]) => <div key={label} className="bg-background/35 px-2.5 py-2"><span className="font-mono text-system-meta uppercase tracking-[0.08em] text-muted-foreground">{label}</span><p className={cn('mt-0.5 font-mono text-system-meta', label === 'Context fit' && blocked ? 'text-error' : label === 'Context fit' && fitStatus === 'DEGRADED' ? 'text-warning' : 'text-slate-200')}>{value}</p></div>)}
        </div>

        <div>
          <div className="mb-1.5 flex items-center justify-between gap-2"><p className="font-mono text-system-meta font-medium uppercase tracking-[0.08em] text-muted-foreground">Context composition</p><span className="font-mono text-system-meta text-muted-foreground">estimated source units</span></div>
          <CompositionRows rows={rows} />
        </div>

        {snapshot ? <details className="group/raw border-t border-border/60 pt-2"><summary className="flex cursor-pointer list-none items-center gap-1 font-mono text-system-meta text-muted-foreground hover:text-slate-50"><ChevronRight className="h-3 w-3 transition-transform group-open/raw:rotate-90" />Technical Context evidence</summary><div className="mt-2 space-y-1.5"><JsonCodeBlock value={snapshot.manifest} maxHeight={180} /><JsonCodeBlock value={snapshot.contributions} maxHeight={180} /></div></details> : invocation.data ? <JsonCodeBlock value={invocation.data} maxHeight={180} /> : null}
      </div>
    </details>
  )
}

export function AgentRunAnalyticsPanel({ traceId, runId, finalizing = false }: { traceId?: string | null; runId?: string | null; finalizing?: boolean }) {
  const identity = { runId: runId ?? undefined, traceId: runId ? undefined : traceId ?? undefined }
  const { data: run, isLoading: runLoading } = useAgentRunDetail(identity)
  const context = useContextModelInvocations(identity)

  if (!runId && !traceId) {
    return <div className="border-b border-border p-3"><SectionBlock density="compact" eyebrow="Run" title="Analytics unavailable" description="Analytics require a durable Agent Run identity." className="bg-background/20" /></div>
  }

  const diagnostics = asRecord(run?.diagnostics)
  const usage = asRecord(run?.usage)
  const invocations = context.data ?? []
  const runtime = numberOrNull(diagnostics.agent_runtime_latency_ms ?? diagnostics.total_latency_ms)
  const inputTokens = numberOrNull(diagnostics.input_tokens) ?? numberOrNull(usage.input_tokens)
  const outputTokens = numberOrNull(diagnostics.output_tokens) ?? numberOrNull(usage.output_tokens)
  const totalTokens = numberOrNull(diagnostics.total_tokens) ?? numberOrNull(usage.total_tokens) ?? (inputTokens != null && outputTokens != null ? inputTokens + outputTokens : null)
  const costUsd = numberOrNull(diagnostics.cost_usd) ?? numberOrNull(usage.cost_usd)
  const costStatus = typeof diagnostics.cost_status === 'string' ? diagnostics.cost_status : costUsd != null ? 'known' : 'unknown'
  const usageComplete = diagnostics.usage_complete === true
  const llmCount = numberOrNull(diagnostics.llm_call_count) ?? (invocations.length || run?.llm_calls.length || 0)
  const toolCount = numberOrNull(diagnostics.tool_call_count) ?? run?.tool_calls.length ?? 0
  const sourceCount = numberOrNull(diagnostics.source_count) ?? run?.sources.length ?? 0
  const successfulOperations = numberOrNull(diagnostics.successful_tool_calls)
  const failedOperations = numberOrNull(diagnostics.failed_tool_calls)
  const fallbackUsed = diagnostics.fallback_used === true

  const rows = aggregateComposition(invocations)
  const trackedContextUnits = rows.reduce((sum, row) => sum + (row.units ?? 0), 0)
  const snapshotCount = invocations.filter((invocation) => Boolean(invocation.context_snapshot)).length
  const reportedSnapshotCount = invocations.filter((invocation) => invocation.context_snapshot?.reported_input_units != null).length
  const contextMeasurement = snapshotCount === 0 ? 'unavailable' : reportedSnapshotCount === snapshotCount ? 'reported' : reportedSnapshotCount === 0 ? 'estimated' : 'mixed'

  return (
    <div className="space-y-3 border-b border-border p-3">
      <div className="flex items-start justify-between gap-3">
        <div><p className="font-sans text-product-body font-medium text-slate-50">Run Analytics</p><p className="mt-0.5 font-sans text-system-meta leading-4 text-muted-foreground">Run totals first; invocation detail remains available on demand.</p></div>
        {fallbackUsed ? <span className="rounded-technical border border-amber-500/25 bg-amber-500/[0.07] px-1.5 py-0.5 font-mono text-system-meta text-warning">Fallback used</span> : null}
      </div>

      <RunMetrics cost={costUsd} costStatus={costStatus} tokens={totalTokens} runtime={runtime} loading={runLoading} counts={[
        { label: 'Model invocations', value: run ? llmCount : null },
        { label: 'Tool / Skill operations', value: run ? toolCount : null },
        { label: 'Sources', value: run ? sourceCount : null },
      ]} />

      <div className="flex flex-wrap gap-x-3 gap-y-1 font-mono text-system-meta text-muted-foreground">
        {inputTokens != null || outputTokens != null ? <span>Tokens {inputTokens == null ? '—' : formatTokens(inputTokens)} in → {outputTokens == null ? '—' : formatTokens(outputTokens)} out{usageComplete ? '' : ' · partial'}</span> : <span>Token usage unavailable</span>}
        {successfulOperations != null ? <span>{successfulOperations} successful operations</span> : null}
        {failedOperations != null && failedOperations > 0 ? <span className="text-error">{failedOperations} failed operations</span> : null}

      </div>

      <SectionBlock variant="product" density="compact" eyebrow="Context" title="Input composition" description={`Cumulative across ${invocations.length} Model Invocation${invocations.length === 1 ? '' : 's'}`} actions={<div className="text-right"><p className="font-mono text-system-meta text-slate-50">{rows.some(row => row.units != null) ? `${formatTokens(trackedContextUnits)}${rows.some(row => row.units == null) ? ' known' : ''}` : '—'}</p><p className="font-mono text-system-meta text-muted-foreground">{contextMeasurement}</p></div>} className="bg-background/20">
        {context.isLoading ? <div className="flex items-center gap-2 font-sans text-system-meta text-muted-foreground"><RefreshCw className="h-3 w-3 animate-spin" />Loading Context composition…</div> : context.isError ? <div className="flex items-start gap-1.5 font-sans text-system-meta text-warning"><AlertTriangle className="mt-0.5 h-3 w-3 shrink-0" />Context composition is unavailable for this Run.</div> : !invocations.length && finalizing ? <div className="flex items-center gap-2 font-sans text-system-meta text-muted-foreground"><RefreshCw className="h-3 w-3 animate-spin" />Finalizing Context evidence…</div> : <CompositionRows rows={rows} />}
        <p className="mt-2 font-sans text-system-meta leading-3.5 text-muted-foreground">Source shares use persisted Context contribution units. They are not a proportional allocation of USD cost.</p>
      </SectionBlock>

      {invocations.length ? <details className="group overflow-hidden rounded-container border border-border/80 bg-background/20"><summary className="flex cursor-pointer list-none items-center gap-2 px-2.5 py-2.5 font-mono text-system-meta text-muted-foreground hover:text-slate-50"><ChevronRight className="h-3 w-3 transition-transform group-open:rotate-90" />Invocation details<span className="ml-auto">{invocations.length} call{invocations.length === 1 ? '' : 's'}</span></summary><div className="border-t border-border/60">{invocations.map((invocation, index) => <InvocationDetails key={invocation.id ?? `${invocation.call_index ?? index}-${index}`} invocation={invocation} index={index} />)}</div></details> : null}
    </div>
  )
}
