import { useMemo, useState } from 'react'
import {
  AlertTriangle,
  CheckCircle2,
  Circle,
  Clock3,
  Loader2,
  RefreshCw,
  Settings2,
  Wrench,
} from 'lucide-react'

import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { Select } from '@/components/ui/Select'
import type {
  EvaluationAuthoringCall,
  EvaluationAuthoringCaseSlot,
  ResumeAuthoringInput,
} from '@/features/evaluations/authoringTypes'
import type { ProviderModel } from '@/features/provider-models/types'
import { cn } from '@/lib/utils'

function phaseLabel(call: EvaluationAuthoringCall) {
  if (call.status === 'completed') return 'Evaluator Suite ready for review'
  if (call.status === 'paused_requires_action') return 'Generation paused'
  if (call.status === 'partially_ready') return 'Some Use Cases need attention'
  if (call.status === 'failed_internal') return 'Evaluator Suite processing failed'
  if (call.status === 'failed') return 'Evaluator Suite generation needs attention'
  if (call.status === 'cancelled') return 'Evaluator Suite generation cancelled'
  if (call.status === 'cancel_requested') return 'Cancelling Evaluator Suite generation'
  if (call.status === 'partial') return 'Generating remaining Use Cases'
  if (call.phase === 'queued') return 'Preparing Evaluator Suite generation'
  return 'Generating Evaluator Suite'
}

function coverageLabel(value: string) {
  return value
    .split('_')
    .map((item) => item.charAt(0).toUpperCase() + item.slice(1))
    .join(' ')
}

function slotLabel(slot: EvaluationAuthoringCaseSlot) {
  return slot.name || `${coverageLabel(slot.coverage_category)} Use Case`
}

function slotStatusLabel(slot: EvaluationAuthoringCaseSlot) {
  return {
    planned: 'Waiting',
    generating: 'Generating',
    validating: 'Validating',
    ready: 'Ready',
    paused: 'Paused',
    needs_attention: 'Needs attention',
    cancelled: 'Cancelled',
  }[slot.status]
}

function SlotIcon({ status }: { status: EvaluationAuthoringCaseSlot['status'] }) {
  if (status === 'ready') return <CheckCircle2 className="h-4 w-4 text-emerald-300" />
  if (status === 'generating' || status === 'validating') {
    return <Loader2 className="h-4 w-4 animate-spin text-primary-light" />
  }
  if (status === 'paused' || status === 'needs_attention') {
    return <AlertTriangle className="h-4 w-4 text-amber-300" />
  }
  return <Circle className="h-4 w-4 text-muted/60" />
}

function usageValue(
  call: EvaluationAuthoringCall,
  value: number | null,
  render: (value: number) => string,
) {
  if (value != null) {
    const suffix = call.usage_status === 'partial' ? ' so far' : ''
    return `${render(value)}${suffix}`
  }
  if (call.usage_status === 'pending' || call.usage_status === 'partial') {
    return 'Calculating…'
  }
  return 'Not reported'
}

interface Props {
  call: EvaluationAuthoringCall
  providerModels: ProviderModel[]
  cancelling: boolean
  resuming: boolean
  onCancel: () => void
  onResume: (input: ResumeAuthoringInput) => void
  onChangeSettings: () => void
}

export function SuiteGenerationProgress({
  call,
  providerModels,
  cancelling,
  resuming,
  onCancel,
  onResume,
  onChangeSettings,
}: Props) {
  const active = ['queued', 'running', 'partial', 'repairing', 'cancel_requested'].includes(call.status)
  const slots = call.case_slots || []
  const ready = call.ready_case_count ?? slots.filter((slot) => slot.status === 'ready').length
  const attention = call.attention_case_count ?? slots.filter(
    (slot) => slot.status === 'paused' || slot.status === 'needs_attention',
  ).length
  const processing = slots.filter(
    (slot) => slot.status === 'generating' || slot.status === 'validating',
  ).length
  const pending = Math.max(
    0,
    call.pending_case_count ?? slots.length - ready - attention,
  )
  const progress = call.case_progress_percent ?? call.progress_percent
  const [modelId, setModelId] = useState(call.generator.provider_model_id)
  const activeModels = providerModels.filter((model) => model.status === 'active')
  const groupedIssues = useMemo(() => {
    const grouped = new Map<string, EvaluationAuthoringCaseSlot[]>()
    slots
      .filter((slot) => slot.status === 'needs_attention' || slot.status === 'paused')
      .forEach((slot) => {
        const key = slot.failure_category || 'generation_failure'
        grouped.set(key, [...(grouped.get(key) || []), slot])
      })
    return [...grouped.entries()]
  }, [slots])
  const hasToolIssue = groupedIssues.some(([category]) => (
    category === 'tool_reference_mismatch' || category === 'unknown_tool'
  ))
  const requiresProviderAction = call.status === 'paused_requires_action'

  return (
    <div className="mx-auto max-w-4xl space-y-5">
      <div>
        <div className="flex items-center gap-2">
          {active ? (
            <Loader2 className="h-4 w-4 animate-spin text-primary-light" />
          ) : call.status === 'completed' ? (
            <CheckCircle2 className="h-4 w-4 text-emerald-300" />
          ) : (
            <AlertTriangle className="h-4 w-4 text-amber-300" />
          )}
          <h3 className="text-base font-semibold text-white">{phaseLabel(call)}</h3>
        </div>
        <p className="mt-1 text-xs text-muted">
          Every valid Use Case is preserved. Resume only processes missing or affected cases.
        </p>
      </div>

      <section className="rounded-xl border border-primary/25 bg-primary/[0.04] p-4">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="text-lg font-semibold text-white">
              {ready} / {call.requested_case_count} Use Cases ready
            </p>
            <p className="mt-1 text-[11px] text-muted">
              {processing} processing · {pending} waiting · {attention} need attention
            </p>
            <p className="mt-2 text-[10px] text-muted">
              {call.generator.model} · {call.target?.source_type || 'snapshot'} · {call.source_snapshot_hash.slice(0, 12)}
            </p>
          </div>
          <Badge variant="outline">{String(call.phase || call.status).replaceAll('_', ' ')}</Badge>
        </div>
        <div className="mt-4 h-2 overflow-hidden rounded-full bg-background">
          <div
            className="h-full bg-primary transition-all"
            style={{ width: `${Math.max(0, Math.min(100, progress))}%` }}
          />
        </div>
        <div className="mt-4 grid gap-3 sm:grid-cols-3">
          <div>
            <p className="text-[9px] uppercase text-muted">Elapsed</p>
            <p className="mt-1 flex items-center gap-1 text-sm text-white">
              <Clock3 className="h-3.5 w-3.5 text-muted" />
              {call.elapsed_seconds == null ? 'Starting…' : `${call.elapsed_seconds}s`}
            </p>
          </div>
          <div>
            <p className="text-[9px] uppercase text-muted">Tokens</p>
            <p className="mt-1 text-sm text-white">
              {usageValue(
                call,
                call.generator.input_tokens == null && call.generator.output_tokens == null
                  ? null
                  : Number(call.generator.input_tokens || 0) + Number(call.generator.output_tokens || 0),
                () => `${Number(call.generator.input_tokens || 0).toLocaleString()} in · ${Number(call.generator.output_tokens || 0).toLocaleString()} out`,
              )}
            </p>
          </div>
          <div>
            <p className="text-[9px] uppercase text-muted">Cost</p>
            <p className="mt-1 text-sm text-white">
              {usageValue(call, call.generator.cost_usd, (value) => `$${value.toFixed(4)}`)}
            </p>
          </div>
        </div>
      </section>

      {groupedIssues.length ? (
        <section className="rounded-xl border border-amber-500/20 bg-amber-500/[0.04] p-4">
          <div className="flex items-start gap-3">
            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-amber-300" />
            <div className="min-w-0 flex-1">
              <p className="text-sm font-semibold text-white">Needs attention</p>
              <div className="mt-3 space-y-3">
                {groupedIssues.map(([category, affected]) => (
                  <div key={category} className="rounded-lg border border-border/70 bg-background/35 p-3">
                    <p className="text-xs font-medium text-white">
                      {category === 'tool_reference_mismatch'
                        ? 'Invalid Tool reference'
                        : category.replaceAll('_', ' ')}
                    </p>
                    <p className="mt-1 text-[11px] leading-5 text-muted">
                      {category === 'tool_reference_mismatch'
                        ? `${affected.length} Use Case(s) reference a Tool that is not present in the selected snapshot. Conversational actions will be repaired as behavior; real unknown Tools remain blocked.`
                        : `${affected.length} Use Case(s) are affected. Ready cases will not be generated again.`}
                    </p>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </section>
      ) : null}

      <section className="rounded-xl border border-border/80 bg-background/25">
        <div className="border-b border-border/80 px-4 py-3">
          <p className="text-sm font-semibold text-white">Use Cases</p>
          <p className="mt-1 text-[10px] text-muted">
            Cases are generated in provider calls internally, then validated and persisted individually.
          </p>
        </div>
        <div className="divide-y divide-border/70">
          {slots.map((slot) => (
            <div key={slot.id} className="flex items-center gap-3 px-4 py-3">
              <SlotIcon status={slot.status} />
              <div className="min-w-0 flex-1">
                <p className="truncate text-xs font-medium text-white">
                  {slot.position}. {slotLabel(slot)}
                </p>
                <p className="mt-0.5 text-[10px] text-muted">
                  {coverageLabel(slot.coverage_category)}
                  {slot.failure_category ? ` · ${slot.failure_category.replaceAll('_', ' ')}` : ''}
                </p>
              </div>
              <span className={cn(
                'text-[10px]',
                slot.status === 'ready' && 'text-emerald-300',
                (slot.status === 'generating' || slot.status === 'validating') && 'text-primary-light',
                (slot.status === 'paused' || slot.status === 'needs_attention') && 'text-amber-300',
                (slot.status === 'planned' || slot.status === 'cancelled') && 'text-muted',
              )}>
                {slotStatusLabel(slot)}
              </span>
            </div>
          ))}
        </div>
      </section>

      {(requiresProviderAction || attention > 0) ? (
        <section className="rounded-xl border border-border/80 bg-background/35 p-4">
          <p className="text-sm font-semibold text-white">Continue generation</p>
          <p className="mt-1 text-[11px] leading-5 text-muted">
            Restore provider balance and retry, or select another active generator model. Completed Use Cases and their provenance remain unchanged.
          </p>
          <div className="mt-4 grid gap-3 sm:grid-cols-[minmax(0,1fr)_auto]">
            <Select
              value={modelId}
              onChange={(event) => setModelId(event.target.value)}
              options={activeModels.map((model) => ({
                value: model.id,
                label: `${model.name} · ${model.model}`,
              }))}
            />
            <Button
              loading={resuming}
              onClick={() => onResume({
                provider_model_id: modelId,
                strategy: modelId !== call.generator.provider_model_id
                  ? 'continue_with_new_model'
                  : hasToolIssue
                    ? 'repair_tool_references'
                    : 'retry_failed_and_missing',
              })}
            >
              <RefreshCw className="mr-2 h-4 w-4" />
              {modelId !== call.generator.provider_model_id
                ? 'Continue with this model'
                : hasToolIssue
                  ? 'Repair affected Use Cases'
                  : 'Resume from where it stopped'}
            </Button>
          </div>
        </section>
      ) : null}

      <details className="rounded-xl border border-border/70 bg-surface/20 px-4 py-3">
        <summary className="cursor-pointer text-xs font-medium text-muted">
          Technical details
        </summary>
        <div className="mt-4 space-y-4 text-[10px] leading-4 text-muted">
          <div>
            <p className="font-medium text-white">Provider attempts</p>
            <div className="mt-2 space-y-2">
              {(call.attempts || []).map((attempt, index) => (
                <div key={attempt.id || index} className="rounded-lg border border-border/70 p-3">
                  <p>{attempt.model || call.generator.model} · {attempt.status || 'unknown'}</p>
                  <p className="mt-1">
                    {attempt.latency_ms == null ? 'Latency not reported' : `${(attempt.latency_ms / 1000).toFixed(1)}s`}
                    {' · '}{attempt.input_tokens == null ? 'input pending' : `${attempt.input_tokens.toLocaleString()} input`}
                    {' · '}{attempt.output_tokens == null ? 'output pending' : `${attempt.output_tokens.toLocaleString()} output`}
                    {attempt.cost_usd == null ? '' : ` · $${attempt.cost_usd.toFixed(6)}`}
                  </p>
                  {attempt.error_detail ? <p className="mt-2 break-words text-red-300/80">{attempt.error_detail}</p> : null}
                </div>
              ))}
            </div>
          </div>
          <div>
            <p className="font-medium text-white">Internal batches</p>
            <div className="mt-2 space-y-2">
              {call.batches.map((batch) => (
                <div key={batch.id} className="rounded-lg border border-border/70 p-3">
                  Batch {batch.batch_index} · {batch.status} · attempt {batch.attempt}
                  {batch.error ? <p className="mt-1 break-words text-red-300/80">{batch.error}</p> : null}
                </div>
              ))}
            </div>
          </div>
          {call.tool_catalog ? (
            <div className="rounded-lg border border-border/70 p-3">
              <p className="flex items-center gap-2 font-medium text-white">
                <Wrench className="h-3.5 w-3.5" />Target Tool catalog
              </p>
              <p className="mt-1">
                {call.tool_catalog.status} · {call.tool_catalog.source} · {call.tool_catalog.allowed_names.length} Tool(s)
              </p>
              {call.tool_catalog.allowed_names.length ? (
                <p className="mt-1">{call.tool_catalog.allowed_names.join(', ')}</p>
              ) : null}
            </div>
          ) : null}
        </div>
      </details>

      <div className="flex flex-wrap justify-end gap-2 border-t border-border pt-4">
        {active && call.status !== 'cancel_requested' ? (
          <Button variant="outline" loading={cancelling} onClick={onCancel}>
            Cancel generation
          </Button>
        ) : null}
        {!active && call.status !== 'completed' && !requiresProviderAction && attention === 0 ? (
          <Button variant="outline" onClick={onChangeSettings}>
            <Settings2 className="mr-2 h-4 w-4" />
            Change settings
          </Button>
        ) : null}
      </div>
    </div>
  )
}
