import { useEffect, useMemo, useState } from 'react'
import {
  AlertTriangle,
  Beaker,
  CheckCircle2,
  Clock3,
  Loader2,
  TerminalSquare,
} from 'lucide-react'
import { toast } from 'sonner'

import { Button } from '@/components/ui/Button'
import {
  useEvaluationRunProgress,
  useRetryEvaluationJudgments,
} from '@/features/evaluations/experienceHooks'
import { useEvaluationRun } from '@/features/evaluations/hooks'
import type { EvaluationRun } from '@/features/evaluations/types'
import { cn } from '@/lib/utils'
import { EvaluationDiagnosticsDialog } from './EvaluationDiagnosticsDialog'
import { EvaluationResultsView } from './EvaluationResultsView'
import { EvaluationRunProgressView } from './EvaluationRunProgressView'

interface Props {
  projectId: string
  runs: EvaluationRun[]
  selectedRunId: string | null
  onSelectRun: (runId: string) => void
  onRunAnother: () => void
}

const activeStatuses = new Set([
  'queued',
  'snapshotting',
  'executing',
  'judging',
  'aggregating',
  'cancel_requested',
])

function label(value?: string | null) {
  if (!value) return 'Unknown'
  return value
    .split('_')
    .map((item) => item.charAt(0).toUpperCase() + item.slice(1))
    .join(' ')
}

function targetLabel(run: EvaluationRun) {
  const target = run.targets.find((item) => item.side === 'single')
    || run.targets.find((item) => item.side === 'candidate')
    || run.targets[0]
  return {
    title: target ? `${target.display_name} · ${target.display_version}` : 'Unknown snapshot',
    subtitle: target
      ? `${label(target.environment)} · ${run.repetitions} runs/case`
      : `${run.repetitions} runs/case`,
  }
}

function statusTone(run: EvaluationRun) {
  if (activeStatuses.has(run.status)) return 'text-primary-light'
  if (run.status === 'failed' || run.assessment_status === 'inconclusive') {
    return 'text-amber-300'
  }
  if (run.assessment_status === 'meets_policy') return 'text-emerald-300'
  if (run.assessment_status === 'below_policy') return 'text-amber-200'
  return 'text-muted'
}

export function EvaluationResultsWorkspace({
  projectId,
  runs,
  selectedRunId,
  onSelectRun,
  onRunAnother,
}: Props) {
  const [logsOpen, setLogsOpen] = useState(false)
  const ordered = useMemo(
    () => [...runs].sort((a, b) => {
      const activeDelta = Number(activeStatuses.has(b.status)) - Number(activeStatuses.has(a.status))
      if (activeDelta) return activeDelta
      return new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
    }),
    [runs],
  )
  const selectedSummary = ordered.find((item) => item.id === selectedRunId) || ordered[0] || null
  const selectedId = selectedSummary?.id || null
  const progress = useEvaluationRunProgress(projectId, selectedId)
  const run = useEvaluationRun(projectId, selectedId)
  const retry = useRetryEvaluationJudgments(projectId, selectedId)
  const active = Boolean(selectedSummary && activeStatuses.has(selectedSummary.status))

  useEffect(() => {
    if (selectedId && selectedId !== selectedRunId) onSelectRun(selectedId)
  }, [selectedId, selectedRunId, onSelectRun])

  useEffect(() => {
    setLogsOpen(false)
  }, [selectedId])

  const retryJudgments = async () => {
    try {
      await retry.mutateAsync({
        failure_codes: [
          'judge_failed',
          'judge_output_length_limit',
          'judge_invalid_json',
        ],
      })
      toast.success(
        'Judgments queued. Previous decision and Estimates were preserved as historical evidence.',
      )
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Unable to retry judgments')
    }
  }

  const running = ordered.filter((item) => activeStatuses.has(item.status))
  const needsAttention = ordered.filter((item) => (
    !activeStatuses.has(item.status)
    && (
      item.status === 'failed'
      || item.status === 'partially_completed'
      || item.assessment_status === 'inconclusive'
    )
  ))
  const completed = ordered.filter((item) => (
    !activeStatuses.has(item.status) && !needsAttention.includes(item)
  ))

  const renderGroup = (title: string, values: EvaluationRun[]) => {
    if (!values.length) return null
    return (
      <section>
        <p className="px-2 pb-2 pt-3 text-[9px] font-medium uppercase tracking-[0.16em] text-muted">
          {title} · {values.length}
        </p>
        <div className="space-y-1">
          {values.map((item) => {
            const target = targetLabel(item)
            const isActive = activeStatuses.has(item.status)
            const selected = item.id === selectedId
            return (
              <button
                key={item.id}
                type="button"
                onClick={() => onSelectRun(item.id)}
                className={cn(
                  'w-full rounded-xl border px-3 py-3 text-left transition-colors',
                  selected
                    ? 'border-primary/30 bg-primary/[0.07]'
                    : 'border-transparent hover:border-border hover:bg-surface/20',
                )}
              >
                <div className="flex items-start gap-3">
                  <div className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border border-border bg-surface/30">
                    {isActive ? (
                      <Loader2 className="h-3.5 w-3.5 animate-spin text-primary-light" />
                    ) : item.status === 'failed' || item.assessment_status === 'inconclusive' ? (
                      <AlertTriangle className="h-3.5 w-3.5 text-amber-300" />
                    ) : (
                      <CheckCircle2 className="h-3.5 w-3.5 text-emerald-300" />
                    )}
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-xs font-semibold text-white">{target.title}</p>
                    <p className="mt-1 truncate text-[10px] text-muted">{target.subtitle}</p>
                    <div className="mt-2 flex items-center justify-between gap-2">
                      <span className={cn('text-[10px] font-medium', statusTone(item))}>
                        {isActive
                          ? label(item.status)
                          : label(item.assessment_status || item.status)}
                      </span>
                      <span className="text-[10px] text-muted">
                        {item.overall_score == null ? '—' : item.overall_score.toFixed(1)}
                      </span>
                    </div>
                  </div>
                </div>
              </button>
            )
          })}
        </div>
      </section>
    )
  }

  return (
    <div className="grid min-h-[600px] gap-4 lg:grid-cols-[300px_minmax(0,1fr)]">
      <aside className="overflow-hidden rounded-2xl border border-border/80 bg-background/30">
        <div className="flex items-center justify-between gap-3 border-b border-border/80 p-4">
          <div>
            <h3 className="text-sm font-semibold text-white">Evaluation Results</h3>
            <p className="mt-1 text-[11px] text-muted">Running, attention and completed Runs.</p>
          </div>
          <button
            type="button"
            onClick={onRunAnother}
            className="rounded-lg border border-border px-3 py-2 text-[11px] font-medium text-white hover:border-primary/30"
          >
            Run another
          </button>
        </div>
        <div className="scrollbar-thin max-h-[540px] overflow-y-auto p-2">
          {ordered.length ? (
            <>
              {renderGroup('Running', running)}
              {renderGroup('Needs attention', needsAttention)}
              {renderGroup('Completed', completed)}
            </>
          ) : (
            <div className="p-10 text-center">
              <Beaker className="mx-auto h-6 w-6 text-muted" />
              <p className="mt-3 text-xs text-muted">No Evaluation Runs yet.</p>
            </div>
          )}
        </div>
      </aside>

      <main className="min-w-0 rounded-2xl border border-border/80 bg-background/20 p-4">
        {selectedSummary ? (
          <div className="mb-3 flex justify-end">
            <Button variant="outline" onClick={() => setLogsOpen(true)}>
              <TerminalSquare className="mr-2 h-4 w-4" />View execution logs
            </Button>
          </div>
        ) : null}

        {!selectedSummary ? (
          <div className="flex min-h-[520px] items-center justify-center text-sm text-muted">
            Select an Evaluation Run.
          </div>
        ) : active && progress.data ? (
          <EvaluationRunProgressView progress={progress.data} />
        ) : run.isLoading ? (
          <div className="flex min-h-[520px] items-center justify-center gap-2 text-sm text-muted">
            <Clock3 className="h-4 w-4" />Loading Evaluation evidence…
          </div>
        ) : run.data ? (
          <EvaluationResultsView
            run={run.data}
            retrying={retry.isPending}
            onRetryJudgments={() => void retryJudgments()}
          />
        ) : (
          <div className="flex min-h-[520px] items-center justify-center text-sm text-red-300">
            Unable to load this Evaluation Run.
          </div>
        )}

        {selectedId ? (
          <EvaluationDiagnosticsDialog
            open={logsOpen}
            projectId={projectId}
            runId={selectedId}
            onClose={() => setLogsOpen(false)}
          />
        ) : null}
      </main>
    </div>
  )
}
