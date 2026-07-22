import {
  AlertTriangle,
  CheckCircle2,
  Clock3,
  Loader2,
  RotateCcw,
} from 'lucide-react'

import { LoadingState } from '@/components/common/LoadingState'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { useEvaluationRunProgress } from '@/features/evaluations/experienceHooks'
import type { EvaluationRunProgress } from '@/features/evaluations/experienceTypes'

interface Props {
  progress?: EvaluationRunProgress
  projectId?: string
  runId?: string
  retrying?: boolean
  onRetryJudgments?: () => void
  onOpenDetails?: () => void
}

const terminal = new Set(['completed', 'partially_completed', 'failed', 'cancelled'])

function money(value?: number | null) {
  if (value == null) return 'Calculating…'
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: value < 0.01 ? 4 : 2,
  }).format(value)
}

function duration(seconds?: number | null) {
  if (seconds == null) return '—'
  const safe = Math.max(0, Math.round(seconds))
  const hours = Math.floor(safe / 3600)
  const minutes = Math.floor((safe % 3600) / 60)
  const rest = safe % 60
  if (hours > 0) return `${hours}h ${String(minutes).padStart(2, '0')}m`
  if (minutes > 0) return `${minutes}m ${String(rest).padStart(2, '0')}s`
  return `${rest}s`
}

function phaseLabel(value: string) {
  return value
    .split('_')
    .map((item) => item.charAt(0).toUpperCase() + item.slice(1))
    .join(' ')
}

function roleLabel(side: string) {
  if (side === 'single') return 'Tested snapshot'
  if (side === 'candidate') return 'Candidate snapshot'
  if (side === 'baseline') return 'Baseline snapshot'
  return phaseLabel(side)
}

export function EvaluationRunProgressView({
  progress,
  projectId,
  runId,
  retrying,
  onRetryJudgments,
  onOpenDetails,
}: Props) {
  const progressQuery = useEvaluationRunProgress(
    progress ? undefined : projectId,
    progress ? null : runId,
  )
  const resolved = progress ?? progressQuery.data
  if (!resolved) {
    return <LoadingState message="Loading Evaluation progress" />
  }

  const total = Math.max(resolved.total_trials, 1)
  const completedPercent = Math.min(
    100,
    Math.round(resolved.completed_trials / total * 100),
  )
  const runtimePercent = Math.min(
    100,
    Math.round(resolved.runtime_completed / total * 100),
  )
  const judgePercent = Math.min(
    100,
    Math.round(resolved.judge_completed / total * 100),
  )
  const active = !terminal.has(resolved.status)
  const attention = resolved.inconclusive_trials + resolved.failed_trials
  const retryActive = active && (resolved.retry_attempt || 0) > 0

  return (
    <div className="space-y-4">
      <section className="rounded-2xl border border-border/80 bg-background/40 p-5">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <div className="flex items-center gap-2">
              {active ? (
                <Loader2 className="h-4 w-4 animate-spin text-primary-light" />
              ) : resolved.status === 'completed' ? (
                <CheckCircle2 className="h-4 w-4 text-emerald-300" />
              ) : (
                <AlertTriangle className="h-4 w-4 text-amber-300" />
              )}
              <h3 className="text-base font-semibold text-white">
                {retryActive
                  ? `Retrying ${resolved.retry_trial_count || 0} judgments`
                  : active
                    ? 'Running Evaluation'
                    : 'Evaluation processing finished'}
              </h3>
            </div>
            <p className="mt-2 text-xs text-muted">
              {phaseLabel(resolved.phase)}
              {resolved.evidence_revision && resolved.evidence_revision > 1
                ? ` · Evidence revision ${resolved.evidence_revision}`
                : ''}
            </p>
          </div>
          <Badge variant="outline">
            {resolved.mode === 'comparison' ? 'Legacy Comparison Run' : 'Single snapshot'}
          </Badge>
        </div>

        <div className="mt-5 h-2 overflow-hidden rounded-full bg-surface">
          <div
            className="h-full rounded-full bg-primary transition-all duration-500"
            style={{ width: `${completedPercent}%` }}
          />
        </div>
        <div className="mt-2 flex justify-between text-[10px] text-muted">
          <span>{resolved.completed_trials} / {resolved.total_trials} Trial outcomes processed</span>
          <span>{completedPercent}%</span>
        </div>

        <div className="mt-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <div className="rounded-xl border border-border/70 bg-surface/25 p-4">
            <p className="text-[10px] uppercase tracking-wide text-muted">Target execution</p>
            <p className="mt-2 text-lg font-semibold text-white">{resolved.runtime_completed} / {resolved.total_trials}</p>
            <p className="mt-1 text-[10px] text-muted">{runtimePercent}% complete</p>
          </div>
          <div className="rounded-xl border border-border/70 bg-surface/25 p-4">
            <p className="text-[10px] uppercase tracking-wide text-muted">Judgments</p>
            <p className="mt-2 text-lg font-semibold text-white">{resolved.judge_completed} / {resolved.total_trials}</p>
            <p className="mt-1 text-[10px] text-muted">{judgePercent}% complete</p>
          </div>
          <div className="rounded-xl border border-border/70 bg-surface/25 p-4">
            <p className="text-[10px] uppercase tracking-wide text-muted">
              {retryActive ? 'Current retry' : 'Current processing'}
            </p>
            <p className="mt-2 flex items-center gap-2 text-lg font-semibold text-white">
              <Clock3 className="h-4 w-4 text-muted" />
              {duration(resolved.phase_elapsed_seconds ?? resolved.elapsed_seconds)}
            </p>
            {retryActive && resolved.processing_elapsed_seconds != null ? (
              <p className="mt-1 text-[10px] text-muted">
                Run age {duration(resolved.processing_elapsed_seconds)}
              </p>
            ) : null}
          </div>
          <div className="rounded-xl border border-border/70 bg-surface/25 p-4">
            <p className="text-[10px] uppercase tracking-wide text-muted">Measured cost</p>
            <p className="mt-2 text-lg font-semibold text-white">{money(resolved.measured_cost_usd)}</p>
            <p className="mt-1 text-[10px] text-muted">Target + Judge calls so far</p>
          </div>
        </div>

        <div className="mt-5 space-y-2">
          {resolved.targets.map((target) => (
            <div
              key={target.id}
              className="flex items-center justify-between rounded-lg border border-border/70 bg-background/30 px-3 py-2"
            >
              <div className="min-w-0">
                <p className="truncate text-xs font-medium text-white">
                  {target.display_name} · {target.display_version}
                </p>
                <p className="mt-1 text-[10px] text-muted">
                  {roleLabel(target.side)} · {phaseLabel(target.environment)} · {target.snapshot_hash.slice(0, 12)}…
                </p>
              </div>
              <Badge variant="outline">{roleLabel(target.side)}</Badge>
            </div>
          ))}
        </div>
      </section>

      {attention > 0 ? (
        <section className="rounded-xl border border-amber-500/25 bg-amber-500/[0.05] p-4">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <p className="text-sm font-semibold text-white">
                {attention} Trial{attention === 1 ? '' : 's'} need attention
              </p>
              <p className="mt-1 text-xs text-amber-200/80">
                {resolved.inconclusive_trials} inconclusive · {resolved.failed_trials} execution failures. Target evidence is preserved when only the Judge failed.
              </p>
            </div>
            <div className="flex gap-2">
              {onRetryJudgments ? (
                <Button size="sm" variant="outline" loading={retrying} onClick={onRetryJudgments}>
                  <RotateCcw className="mr-2 h-3.5 w-3.5" />Retry judgments
                </Button>
              ) : null}
              {onOpenDetails ? <Button size="sm" variant="ghost" onClick={onOpenDetails}>Details</Button> : null}
            </div>
          </div>
        </section>
      ) : onOpenDetails ? (
        <div className="flex justify-end">
          <Button variant="outline" onClick={onOpenDetails}>Open results</Button>
        </div>
      ) : null}
    </div>
  )
}
