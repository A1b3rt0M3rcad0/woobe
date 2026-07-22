import { useEffect, useMemo, useState } from 'react'
import {
  AlertTriangle,
  ChevronRight,
  GitCompareArrows,
  Loader2,
  Plus,
} from 'lucide-react'
import { toast } from 'sonner'

import { ErrorState } from '@/components/common/ErrorState'
import { LoadingState } from '@/components/common/LoadingState'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { Select } from '@/components/ui/Select'
import {
  useCreatePostHocEvaluationComparison,
  useEvaluationComparison,
  useEvaluationComparisons,
  usePreviewEvaluationComparison,
} from '@/features/evaluations/catalogHooks'
import { useEvaluationRuns } from '@/features/evaluations/hooks'
import { cn } from '@/lib/utils'
import { EvaluationComparisonView } from './EvaluationComparisonView'

interface Props {
  projectId: string
  entityId: string
  selectedComparisonId?: string | null
  onSelectComparison?: (comparisonId: string) => void
  onCreateComparison?: () => void
}

const active = new Set(['waiting', 'running'])
const terminal = new Set(['completed', 'partially_completed'])

function targetTitle(value: any, fallback: string) {
  const target = value?.target
  return target ? `${target.display_version}` : fallback
}

function runLabel(run: any) {
  const target = run.targets?.find((item: any) => item.side === 'single') || run.targets?.[0]
  return `${target?.display_version || 'Snapshot'} · ${run.repetitions} repetitions · ${run.overall_score == null ? 'No score' : `Score ${run.overall_score.toFixed(1)}`}`
}

export function EvaluationComparisonsWorkspace({
  projectId,
  entityId,
  selectedComparisonId,
  onSelectComparison,
  onCreateComparison,
}: Props) {
  const listQuery = useEvaluationComparisons(projectId, entityId)
  const runsQuery = useEvaluationRuns(projectId)
  const comparisons = listQuery.data ?? []
  const [internalId, setInternalId] = useState<string | null>(selectedComparisonId || null)
  const comparisonId = selectedComparisonId || internalId || comparisons[0]?.id || null
  const comparisonQuery = useEvaluationComparison(projectId, comparisonId)
  const preview = usePreviewEvaluationComparison(projectId)
  const create = useCreatePostHocEvaluationComparison(projectId)
  const [builderOpen, setBuilderOpen] = useState(false)
  const [candidateRunId, setCandidateRunId] = useState('')
  const [referenceRunId, setReferenceRunId] = useState('')

  const eligibleRuns = useMemo(() => (
    (runsQuery.data ?? []).filter((run) => (
      run.mode !== 'comparison'
      && terminal.has(run.status)
      && run.targets.length === 1
      && run.targets[0]?.entity_id === entityId
    ))
  ), [runsQuery.data, entityId])

  useEffect(() => {
    if (selectedComparisonId) setInternalId(selectedComparisonId)
  }, [selectedComparisonId])

  useEffect(() => {
    if (!candidateRunId || !referenceRunId || candidateRunId === referenceRunId) {
      preview.reset()
      return
    }
    const timer = window.setTimeout(() => {
      preview.mutate({
        candidate_run_id: candidateRunId,
        reference_run_id: referenceRunId,
      }, { onError: () => undefined })
    }, 300)
    return () => window.clearTimeout(timer)
  }, [candidateRunId, referenceRunId])

  const select = (id: string) => {
    setInternalId(id)
    onSelectComparison?.(id)
  }

  const createHistorical = async () => {
    if (!candidateRunId || !referenceRunId || candidateRunId === referenceRunId) return
    try {
      const comparison = await create.mutateAsync({
        candidate_run_id: candidateRunId,
        reference_run_id: referenceRunId,
        idempotency_key: crypto.randomUUID(),
      })
      select(comparison.id)
      setBuilderOpen(false)
      toast.success('Comparison created without rerunning either snapshot')
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Unable to create Comparison')
    }
  }

  if (listQuery.isLoading || runsQuery.isLoading) return <LoadingState message="Loading Comparisons" />
  if (listQuery.isError || runsQuery.isError) return <ErrorState message="Unable to load Comparisons" />

  return (
    <div className="grid min-h-[620px] gap-4 lg:grid-cols-[300px_minmax(0,1fr)]">
      <aside className="overflow-hidden rounded-2xl border border-border/80 bg-background/25">
        <div className="border-b border-border/80 p-4">
          <div className="flex items-start justify-between gap-3">
            <div>
              <h3 className="text-sm font-semibold text-white">Comparisons</h3>
              <p className="mt-1 text-[11px] leading-4 text-muted">
                Immutable comparisons between two Evaluation Runs.
              </p>
            </div>
            <Button size="sm" onClick={() => setBuilderOpen((value) => !value)}>
              <Plus className="mr-1 h-3.5 w-3.5" />New
            </Button>
          </div>
        </div>
        <div className="max-h-[690px] overflow-y-auto p-2">
          {comparisons.map((comparison) => {
            const aggregate = comparison.aggregate_result
            const candidate = targetTitle(aggregate?.candidate, 'Candidate')
            const reference = targetTitle(aggregate?.reference, 'Reference')
            const selected = comparison.id === comparisonId
            return (
              <button
                key={comparison.id}
                type="button"
                onClick={() => select(comparison.id)}
                className={cn(
                  'mb-2 w-full rounded-xl border px-3 py-3 text-left',
                  selected
                    ? 'border-primary/40 bg-primary/[0.08]'
                    : 'border-transparent hover:border-border hover:bg-surface/20',
                )}
              >
                <div className="flex items-start gap-3">
                  <span className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border border-border/80">
                    {active.has(comparison.status)
                      ? <Loader2 className="h-3.5 w-3.5 animate-spin text-primary-light" />
                      : comparison.status === 'blocked' || comparison.status === 'partial'
                        ? <AlertTriangle className="h-3.5 w-3.5 text-amber-300" />
                        : <GitCompareArrows className="h-3.5 w-3.5 text-muted" />}
                  </span>
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-xs font-semibold text-white">{candidate}</p>
                    <p className="mt-1 truncate text-[10px] text-muted">vs {reference}</p>
                    <div className="mt-2 flex items-center justify-between gap-2">
                      <Badge variant="outline">{comparison.status}</Badge>
                      <span className="text-[10px] text-muted">{comparison.comparison_mode}</span>
                    </div>
                  </div>
                  <ChevronRight className="mt-2 h-3.5 w-3.5 text-muted" />
                </div>
              </button>
            )
          })}
          {!comparisons.length ? (
            <div className="p-8 text-center text-xs leading-5 text-muted">
              No Comparison exists. Start a paired Comparison from Run or compare two compatible historical Runs.
            </div>
          ) : null}
        </div>
      </aside>

      <section className="min-w-0 rounded-2xl border border-border/80 bg-background/20 p-4">
        {builderOpen ? (
          <div className="space-y-4">
            <header>
              <Badge variant="outline">Post-hoc · no execution</Badge>
              <h3 className="mt-3 text-base font-semibold text-white">Compare existing Evaluations</h3>
              <p className="mt-1 text-xs text-muted">
                Select two compatible single-target Runs. Agent and Judge will not be executed again.
              </p>
            </header>
            <div className="grid gap-4 lg:grid-cols-2">
              <label className="space-y-2 text-xs text-muted">
                <span>Candidate Run</span>
                <Select
                  value={candidateRunId}
                  onChange={(event) => setCandidateRunId(event.target.value)}
                  options={[
                    { value: '', label: 'Select Candidate evidence' },
                    ...eligibleRuns.map((run) => ({ value: run.id, label: runLabel(run) })),
                  ]}
                />
              </label>
              <label className="space-y-2 text-xs text-muted">
                <span>Reference Run</span>
                <Select
                  value={referenceRunId}
                  onChange={(event) => setReferenceRunId(event.target.value)}
                  options={[
                    { value: '', label: 'Select Reference evidence' },
                    ...eligibleRuns.map((run) => ({ value: run.id, label: runLabel(run) })),
                  ]}
                />
              </label>
            </div>
            {preview.isError ? (
              <div className="rounded-lg border border-red-500/20 bg-red-500/[0.05] p-3 text-xs text-red-300">
                {preview.error instanceof Error ? preview.error.message : 'These Runs are not compatible.'}
              </div>
            ) : preview.data ? (
              <div className="rounded-lg border border-primary/20 bg-primary/[0.04] p-3 text-xs">
                <p className="font-medium text-white">
                  {preview.data.compatible ? 'Compatible Evaluation protocol' : 'Descriptive comparison only'}
                </p>
                <p className="mt-1 text-muted">
                  {preview.data.executes_targets ? 'Target execution required' : 'No Target or Judge execution will occur.'}
                </p>
              </div>
            ) : null}
            <div className="flex justify-end gap-2">
              {onCreateComparison ? (
                <Button variant="outline" onClick={onCreateComparison}>Run new paired Comparison</Button>
              ) : null}
              <Button
                loading={create.isPending}
                disabled={!preview.data?.compatible}
                onClick={() => void createHistorical()}
              >
                <GitCompareArrows className="mr-2 h-4 w-4" />Create Comparison
              </Button>
            </div>
          </div>
        ) : !comparisonId ? (
          <div className="flex min-h-[540px] items-center justify-center text-xs text-muted">
            Select or create a Comparison.
          </div>
        ) : comparisonQuery.isLoading ? (
          <LoadingState message="Loading Comparison evidence" />
        ) : comparisonQuery.isError || !comparisonQuery.data ? (
          <ErrorState message="Unable to load this Comparison" />
        ) : (
          <EvaluationComparisonView
            projectId={projectId}
            comparison={comparisonQuery.data}
          />
        )}
      </section>
    </div>
  )
}
