import {
  AlertTriangle,
  CheckCircle2,
  Clock3,
  Loader2,
  RefreshCw,
  Settings2,
} from 'lucide-react'

import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import type {
  EvaluationAuthoringBatch,
  EvaluationAuthoringCall,
} from '@/features/evaluations/authoringTypes'
import { cn } from '@/lib/utils'

function phaseLabel(call: EvaluationAuthoringCall) {
  if (call.status === 'completed') return 'Evaluator Suite ready for review'
  if (call.status === 'failed') return 'Evaluator Suite generation failed'
  if (call.status === 'cancelled') return 'Evaluator Suite generation cancelled'
  if (call.status === 'cancel_requested') return 'Cancelling Evaluator Suite generation'
  if (call.status === 'partial') return 'Generating remaining Evaluator Suite batches'
  if (call.phase === 'queued') return 'Evaluator Suite generation queued'
  return 'Generating Evaluator Suite'
}

function statusClass(status: EvaluationAuthoringBatch['status']) {
  if (status === 'completed') return 'border-emerald-500/25 text-emerald-300'
  if (status === 'failed') return 'border-red-500/25 text-red-300'
  if (status === 'running') return 'border-primary/30 text-primary-light'
  if (status === 'cancelled') return 'border-amber-500/25 text-amber-300'
  return 'border-border text-muted'
}

function actionLabel(action?: string | null) {
  return {
    repair_invalid_cases: 'Repair invalid cases',
    repair_duplicate_cases: 'Repair duplicate cases',
    retry_provider_call: 'Retry provider call',
    retry_with_backoff: 'Retry after rate limit',
    retry_with_larger_output_budget: 'Retry with larger output budget',
    edit_tool_references: 'Review Tool references',
    change_model_or_credential: 'Change model or credential',
    reduce_cases_or_raise_cost_limit: 'Change generation limits',
    contact_support: 'Inspect platform error',
  }[String(action || '')] || 'Review generation failure'
}

function failureExplanation(batch: EvaluationAuthoringBatch) {
  if (batch.failure_category === 'output_length_limit') {
    return 'The model exhausted its completion budget before closing the JSON. The retry uses a larger adaptive output budget and requests a more concise response.'
  }
  if (batch.failure_category === 'cost_limit') {
    return 'The configured cost ceiling prevented or stopped this generation.'
  }
  return batch.retryable
    ? 'This failure is eligible for a targeted retry.'
    : 'Repeating the same request will not resolve this failure.'
}

function BatchCard({ batch, blocked }: { batch: EvaluationAuthoringBatch; blocked: boolean }) {
  const failure = batch.failure_category
  const returned = batch.returned_case_count ?? batch.case_count
  const valid = batch.valid_case_count ?? batch.case_count
  const invalid = batch.invalid_case_count ?? 0
  const latestAttempt = batch.attempts?.[batch.attempts.length - 1]

  return (
    <article className="rounded-xl border border-border/80 bg-background/35 p-4">
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <p className="text-xs font-semibold text-white">
              Batch {batch.batch_index} · {batch.requested_case_count} cases
            </p>
            <Badge variant="outline" className={statusClass(batch.status)}>
              {batch.status}
            </Badge>
          </div>
          <p className="mt-1 text-[10px] text-muted">
            Attempt {batch.attempt}
            {batch.status === 'pending' && blocked
              ? ' · Waiting while a previous batch requires attention'
              : ''}
          </p>
        </div>
        {batch.status === 'running' ? (
          <Loader2 className="h-4 w-4 shrink-0 animate-spin text-primary-light" />
        ) : batch.status === 'completed' ? (
          <CheckCircle2 className="h-4 w-4 shrink-0 text-emerald-300" />
        ) : batch.status === 'failed' ? (
          <AlertTriangle className="h-4 w-4 shrink-0 text-red-300" />
        ) : null}
      </div>

      {(returned > 0 || batch.status === 'failed') ? (
        <div className="mt-3 grid grid-cols-3 gap-3 rounded-lg border border-border/70 bg-surface/30 p-3">
          <div>
            <p className="text-[9px] uppercase text-muted">Returned</p>
            <p className="mt-1 text-xs font-medium text-white">{returned}</p>
          </div>
          <div>
            <p className="text-[9px] uppercase text-muted">Valid</p>
            <p className="mt-1 text-xs font-medium text-emerald-300">{valid}</p>
          </div>
          <div>
            <p className="text-[9px] uppercase text-muted">Invalid</p>
            <p className={cn('mt-1 text-xs font-medium', invalid ? 'text-red-300' : 'text-white')}>
              {invalid}
            </p>
          </div>
        </div>
      ) : null}

      {batch.status === 'failed' ? (
        <div className="mt-3 rounded-lg border border-red-500/20 bg-red-500/[0.04] p-3">
          <p className="text-xs font-medium text-red-200">
            {actionLabel(batch.recommended_action)}
          </p>
          <p className="mt-1 break-words text-[10px] leading-4 text-red-300/80">
            {batch.error || failure || 'The batch could not be validated.'}
          </p>
          <p className="mt-2 text-[10px] leading-4 text-muted">
            {failureExplanation(batch)}
          </p>
        </div>
      ) : null}

      {(batch.validation_errors?.length || batch.normalization_warnings?.length || batch.attempts?.length) ? (
        <details className="mt-3 rounded-lg border border-border/70 bg-surface/20 px-3 py-2">
          <summary className="cursor-pointer text-[10px] font-medium text-muted">
            Technical details
          </summary>
          <div className="mt-2 space-y-2 text-[10px] leading-4 text-muted">
            {batch.validation_errors?.map((issue, index) => (
              <p key={`error-${index}`} className="break-words text-red-300/85">
                {issue.path ? `${issue.path}: ` : ''}{issue.message}
              </p>
            ))}
            {batch.normalization_warnings?.map((issue, index) => (
              <p key={`warning-${index}`} className="text-amber-300/80">
                {issue.path ? `${issue.path}: ` : ''}{issue.message}
              </p>
            ))}
            {latestAttempt ? (
              <p>
                Provider latency {latestAttempt.latency_ms == null ? 'unknown' : `${(latestAttempt.latency_ms / 1000).toFixed(1)}s`}
                {' · '}{Number(latestAttempt.input_tokens || 0).toLocaleString()} input tokens
                {' · '}{Number(latestAttempt.output_tokens || 0).toLocaleString()} output tokens
                {latestAttempt.cost_usd == null ? '' : ` · $${latestAttempt.cost_usd.toFixed(6)}`}
              </p>
            ) : null}
          </div>
        </details>
      ) : null}
    </article>
  )
}

interface Props {
  call: EvaluationAuthoringCall
  cancelling: boolean
  retrying: boolean
  onCancel: () => void
  onRetry: () => void
  onChangeSettings: () => void
}

export function SuiteGenerationProgress({
  call,
  cancelling,
  retrying,
  onCancel,
  onRetry,
  onChangeSettings,
}: Props) {
  const active = ['queued', 'running', 'partial', 'cancel_requested'].includes(call.status)
  const retryableFailures = call.batches.filter(
    (batch) => batch.status === 'failed' && batch.retryable,
  )
  const nonRetryableFailures = call.batches.filter(
    (batch) => batch.status === 'failed' && !batch.retryable,
  )
  const failedBeforePending = call.batches.some((batch) => batch.status === 'failed')
  const processedPercent = call.processed_percent ?? call.progress_percent
  const primaryRetryAction = retryableFailures[0]?.recommended_action

  return (
    <div className="mx-auto max-w-4xl space-y-5">
      <div>
        <div className="flex items-center gap-2">
          {active ? (
            <Loader2 className="h-4 w-4 animate-spin text-primary-light" />
          ) : call.status === 'completed' ? (
            <CheckCircle2 className="h-4 w-4 text-emerald-300" />
          ) : (
            <AlertTriangle className="h-4 w-4 text-red-300" />
          )}
          <h3 className="text-base font-semibold text-white">{phaseLabel(call)}</h3>
        </div>
        <p className="mt-1 text-xs text-muted">
          Cases are validated before a batch is accepted. Completed batches are preserved independently.
        </p>
      </div>

      <section className="rounded-xl border border-primary/25 bg-primary/[0.04] p-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <p className="text-sm font-semibold text-white">
              {call.processed_batch_count ?? call.completed_batch_count} / {call.total_batch_count} batches processed
            </p>
            <p className="mt-1 text-[10px] text-muted">
              {call.generator.model} · {call.target?.source_type || 'snapshot'} · {call.source_snapshot_hash.slice(0, 12)}
            </p>
          </div>
          <Badge variant="outline">{String(call.phase || call.status).replaceAll('_', ' ')}</Badge>
        </div>
        <div className="mt-3 h-2 overflow-hidden rounded-full bg-background">
          <div
            className="h-full bg-primary transition-all"
            style={{ width: `${processedPercent}%` }}
          />
        </div>
        <div className="mt-4 grid gap-3 sm:grid-cols-4">
          <div>
            <p className="text-[9px] uppercase text-muted">Processed</p>
            <p className="mt-1 text-sm text-white">{processedPercent.toFixed(1)}%</p>
          </div>
          <div>
            <p className="text-[9px] uppercase text-muted">Elapsed</p>
            <p className="mt-1 flex items-center gap-1 text-sm text-white">
              <Clock3 className="h-3.5 w-3.5 text-muted" />
              {call.elapsed_seconds == null ? '—' : `${call.elapsed_seconds}s`}
            </p>
          </div>
          <div>
            <p className="text-[9px] uppercase text-muted">Tokens</p>
            <p className="mt-1 text-sm text-white">
              {Number(call.generator.input_tokens || 0).toLocaleString()} in ·{' '}
              {Number(call.generator.output_tokens || 0).toLocaleString()} out
            </p>
          </div>
          <div>
            <p className="text-[9px] uppercase text-muted">Cost</p>
            <p className="mt-1 text-sm text-white">
              {call.generator.cost_usd == null ? 'Unknown' : `$${call.generator.cost_usd.toFixed(4)}`}
            </p>
          </div>
        </div>
      </section>

      <div className="space-y-3">
        {call.batches.map((batch) => (
          <BatchCard
            key={batch.id}
            batch={batch}
            blocked={failedBeforePending && call.status === 'failed'}
          />
        ))}
      </div>

      <div className="flex flex-wrap justify-end gap-2 border-t border-border pt-4">
        {active && call.status !== 'cancel_requested' ? (
          <Button variant="outline" loading={cancelling} onClick={onCancel}>
            Cancel generation
          </Button>
        ) : null}
        {nonRetryableFailures.length ? (
          <Button variant="outline" onClick={onChangeSettings}>
            <Settings2 className="mr-2 h-4 w-4" />
            Change settings
          </Button>
        ) : null}
        {retryableFailures.length ? (
          <Button loading={retrying} onClick={onRetry}>
            <RefreshCw className="mr-2 h-4 w-4" />
            {actionLabel(primaryRetryAction)}
          </Button>
        ) : null}
      </div>
    </div>
  )
}
