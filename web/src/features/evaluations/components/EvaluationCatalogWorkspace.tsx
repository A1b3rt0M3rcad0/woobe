import { useEffect, useMemo, useState } from 'react'
import {
  Archive,
  ChevronRight,
  History,
  Loader2,
  Play,
  RotateCcw,
} from 'lucide-react'
import { toast } from 'sonner'

import { ErrorState } from '@/components/common/ErrorState'
import { LoadingState } from '@/components/common/LoadingState'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import {
  useArchiveCatalogEvaluation,
  useCatalogEvaluation,
  useEvaluationCatalog,
  useEvidenceRichEvaluationRun,
  useRestoreCatalogEvaluation,
} from '@/features/evaluations/catalogHooks'
import type { EvaluationCatalogItem } from '@/features/evaluations/catalogTypes'
import { cn } from '@/lib/utils'
import { EvidenceRunView } from './EvidenceRunView'
import { EvaluationRunProgressView } from './EvaluationRunProgressView'

interface Props {
  projectId: string
  entityId: string
  selectedEvaluationId?: string | null
  onSelectEvaluation?: (evaluationId: string) => void
  onRunAgain?: (evaluation: EvaluationCatalogItem) => void
  onCompareRun?: (runId: string) => void
}

const activeStatuses = new Set(['queued', 'snapshotting', 'executing', 'judging', 'aggregating', 'cancel_requested'])

function assessmentLabel(value?: string | null) {
  if (value === 'meets_policy') return 'Meets policy'
  if (value === 'below_policy') return 'Below policy'
  if (value === 'pending') return 'Running'
  return 'Inconclusive'
}

function date(value?: string | null) {
  if (!value) return '—'
  return new Intl.DateTimeFormat(undefined, {
    month: 'short',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  }).format(new Date(value))
}

function suiteLabel(item: EvaluationCatalogItem) {
  if (item.suite_name) {
    return `${item.suite_name}${item.suite_version ? ` · ${item.suite_version}` : ''}`
  }
  return `Suite ${item.suite_version_id.slice(0, 8)}`
}

function targetFilterKey(item: EvaluationCatalogItem) {
  return item.target_identity_hash || item.target_version_id || item.target_snapshot_hash
}

export function EvaluationCatalogWorkspace({
  projectId,
  entityId,
  selectedEvaluationId,
  onSelectEvaluation,
  onRunAgain,
  onCompareRun,
}: Props) {
  const [showArchived, setShowArchived] = useState(false)
  const [suiteFilter, setSuiteFilter] = useState('all')
  const [targetFilter, setTargetFilter] = useState('all')
  const catalogQuery = useEvaluationCatalog(projectId, entityId, showArchived)
  const evaluations = catalogQuery.data ?? []
  const [internalEvaluationId, setInternalEvaluationId] = useState<string | null>(
    selectedEvaluationId || null,
  )

  const suiteOptions = useMemo(() => {
    const values = new Map<string, string>()
    evaluations.forEach((item) => values.set(item.suite_version_id, suiteLabel(item)))
    return [...values.entries()].sort((a, b) => a[1].localeCompare(b[1]))
  }, [evaluations])

  const targetOptions = useMemo(() => {
    const values = new Map<string, string>()
    evaluations.forEach((item) => {
      values.set(
        targetFilterKey(item),
        `${item.display_version} · ${item.source_type}`,
      )
    })
    return [...values.entries()].sort((a, b) => a[1].localeCompare(b[1]))
  }, [evaluations])

  const visibleEvaluations = useMemo(() => evaluations.filter((item) => (
    (suiteFilter === 'all' || item.suite_version_id === suiteFilter)
    && (targetFilter === 'all' || targetFilterKey(item) === targetFilter)
  )), [evaluations, suiteFilter, targetFilter])

  const preferredEvaluationId = selectedEvaluationId || internalEvaluationId
  const evaluationId = (
    visibleEvaluations.some((item) => item.id === preferredEvaluationId)
      ? preferredEvaluationId
      : visibleEvaluations[0]?.id
  ) || null
  const evaluationQuery = useCatalogEvaluation(projectId, evaluationId)
  const evaluation = evaluationQuery.data
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null)
  const runId = selectedRunId || evaluation?.latest_run_id || null
  const runQuery = useEvidenceRichEvaluationRun(projectId, runId)
  const archive = useArchiveCatalogEvaluation(projectId)
  const restore = useRestoreCatalogEvaluation(projectId)

  useEffect(() => {
    if (selectedEvaluationId) setInternalEvaluationId(selectedEvaluationId)
  }, [selectedEvaluationId])

  useEffect(() => {
    if (evaluationId && evaluationId !== internalEvaluationId) {
      setInternalEvaluationId(evaluationId)
    }
  }, [evaluationId, internalEvaluationId])

  useEffect(() => {
    setSelectedRunId(null)
  }, [evaluationId])

  const selectEvaluation = (id: string) => {
    setInternalEvaluationId(id)
    onSelectEvaluation?.(id)
  }

  const grouped = useMemo(() => ({
    active: visibleEvaluations.filter((item) => item.status !== 'archived'),
    archived: visibleEvaluations.filter((item) => item.status === 'archived'),
  }), [visibleEvaluations])

  if (catalogQuery.isLoading) return <LoadingState message="Loading snapshot Evaluations" />
  if (catalogQuery.isError) return <ErrorState message="Unable to load snapshot Evaluations" />

  return (
    <div className="grid min-h-[620px] gap-4 lg:grid-cols-[320px_minmax(0,1fr)]">
      <aside className="overflow-hidden rounded-2xl border border-border/80 bg-background/25">
        <div className="border-b border-border/80 p-4">
          <div className="flex items-start justify-between gap-3">
            <div>
              <h3 className="text-sm font-semibold text-white">Snapshot Evaluations</h3>
              <p className="mt-1 text-[11px] leading-4 text-muted">
                Runs grouped by exact target snapshot and immutable Suite Version.
              </p>
            </div>
            <button
              type="button"
              onClick={() => setShowArchived((value) => !value)}
              className="text-[10px] text-primary-light"
            >
              {showArchived ? 'Active only' : 'Include archived'}
            </button>
          </div>
          <div className="mt-4 grid gap-2">
            <label className="space-y-1 text-[10px] text-muted">
              <span>Suite Version</span>
              <select
                value={suiteFilter}
                onChange={(event) => setSuiteFilter(event.target.value)}
                className="h-9 w-full rounded-lg border border-border bg-background/60 px-2 text-xs text-white"
              >
                <option value="all">All Suites</option>
                {suiteOptions.map(([value, label]) => (
                  <option key={value} value={value}>{label}</option>
                ))}
              </select>
            </label>
            <label className="space-y-1 text-[10px] text-muted">
              <span>Exact Agent Version / Snapshot</span>
              <select
                value={targetFilter}
                onChange={(event) => setTargetFilter(event.target.value)}
                className="h-9 w-full rounded-lg border border-border bg-background/60 px-2 text-xs text-white"
              >
                <option value="all">All target versions</option>
                {targetOptions.map(([value, label]) => (
                  <option key={value} value={value}>{label}</option>
                ))}
              </select>
            </label>
          </div>
        </div>
        <div className="max-h-[650px] overflow-y-auto p-2">
          {[...grouped.active, ...grouped.archived].map((item) => {
            const latest = item.latest_run
            const selected = item.id === evaluationId
            return (
              <button
                key={item.id}
                type="button"
                onClick={() => selectEvaluation(item.id)}
                className={cn(
                  'mb-2 w-full rounded-xl border px-3 py-3 text-left transition-colors',
                  selected
                    ? 'border-primary/40 bg-primary/[0.08]'
                    : 'border-transparent hover:border-border hover:bg-surface/20',
                )}
              >
                <div className="flex items-start gap-3">
                  <span className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border border-border/80">
                    {latest && activeStatuses.has(latest.status)
                      ? <Loader2 className="h-3.5 w-3.5 animate-spin text-primary-light" />
                      : <History className="h-3.5 w-3.5 text-muted" />}
                  </span>
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-xs font-semibold text-white">{item.display_version}</p>
                    <p className="mt-1 truncate text-[10px] text-primary-light">
                      {suiteLabel(item)}
                    </p>
                    <p className="mt-1 truncate text-[10px] text-muted">
                      {item.source_type} · {item.run_count ?? 0} Runs
                    </p>
                    <div className="mt-2 flex items-center justify-between gap-2">
                      <span className="text-[10px] text-muted">
                        {assessmentLabel(latest?.assessment_status)}
                      </span>
                      <span className="text-[10px] font-medium text-white">
                        {latest?.overall_score == null ? '—' : latest.overall_score.toFixed(1)}
                      </span>
                    </div>
                  </div>
                  <ChevronRight className="mt-2 h-3.5 w-3.5 text-muted" />
                </div>
              </button>
            )
          })}
          {!visibleEvaluations.length ? (
            <div className="p-8 text-center text-xs text-muted">
              {evaluations.length
                ? 'No Evaluation matches the selected Suite and target version.'
                : 'No snapshot Evaluation exists yet. Start one from Run.'}
            </div>
          ) : null}
        </div>
      </aside>

      <section className="min-w-0 rounded-2xl border border-border/80 bg-background/20 p-4">
        {!evaluationId ? (
          <div className="flex min-h-[540px] items-center justify-center text-xs text-muted">
            Select an Evaluation.
          </div>
        ) : evaluationQuery.isLoading ? (
          <LoadingState message="Loading Evaluation history" />
        ) : evaluationQuery.isError || !evaluation ? (
          <ErrorState message="Unable to load this Evaluation" />
        ) : (
          <div className="space-y-4">
            <header className="flex flex-wrap items-start justify-between gap-4 rounded-xl border border-border/80 bg-background/35 p-4">
              <div>
                <div className="flex flex-wrap items-center gap-2">
                  <Badge variant="outline">{evaluation.source_type}</Badge>
                  <Badge variant="outline">{evaluation.run_count ?? 0} Runs</Badge>
                  <Badge variant="outline">{suiteLabel(evaluation)}</Badge>
                </div>
                <h3 className="mt-3 text-base font-semibold text-white">
                  {evaluation.display_name} · {evaluation.display_version}
                </h3>
                <p className="mt-1 font-mono text-[10px] text-muted">
                  Snapshot {evaluation.target_snapshot_hash.slice(0, 16)}…
                </p>
              </div>
              <div className="flex gap-2">
                {evaluation.status === 'archived' ? (
                  <Button
                    size="sm"
                    variant="outline"
                    loading={restore.isPending}
                    onClick={async () => {
                      await restore.mutateAsync(evaluation.id)
                      toast.success('Evaluation restored')
                    }}
                  >
                    <RotateCcw className="mr-2 h-3.5 w-3.5" />Restore
                  </Button>
                ) : (
                  <Button
                    size="sm"
                    variant="outline"
                    loading={archive.isPending}
                    onClick={async () => {
                      await archive.mutateAsync(evaluation.id)
                      toast.success('Evaluation archived without deleting Runs')
                    }}
                  >
                    <Archive className="mr-2 h-3.5 w-3.5" />Archive
                  </Button>
                )}
                <Button size="sm" onClick={() => onRunAgain?.(evaluation)}>
                  <Play className="mr-2 h-3.5 w-3.5" />Run again
                </Button>
              </div>
            </header>

            <div className="grid gap-4 xl:grid-cols-[230px_minmax(0,1fr)]">
              <aside className="overflow-hidden rounded-xl border border-border/80 bg-background/25">
                <div className="border-b border-border/80 px-3 py-3">
                  <p className="text-xs font-semibold text-white">Run history</p>
                  <p className="mt-1 text-[10px] text-muted">Exact Suite and snapshot only.</p>
                </div>
                <div className="max-h-[570px] overflow-y-auto p-2">
                  {(evaluation.runs || []).map((run) => (
                    <button
                      key={run.id}
                      type="button"
                      onClick={() => setSelectedRunId(run.id)}
                      className={cn(
                        'mb-2 w-full rounded-lg border px-3 py-3 text-left',
                        run.id === runId
                          ? 'border-primary/35 bg-primary/[0.07]'
                          : 'border-transparent hover:border-border',
                      )}
                    >
                      <div className="flex items-center justify-between gap-2">
                        <span className="text-xs font-medium text-white">{date(run.created_at)}</span>
                        <span className="text-[10px] text-muted">r{run.evidence_revision}</span>
                      </div>
                      <p className="mt-1 text-[10px] text-muted">
                        {assessmentLabel(run.assessment_status)} · {run.repetitions} repetitions
                      </p>
                      <div className="mt-2 flex items-center justify-between text-[10px]">
                        <span className="text-muted">Score</span>
                        <span className="font-medium text-white">
                          {run.overall_score == null ? '—' : run.overall_score.toFixed(1)}
                        </span>
                      </div>
                      {onCompareRun && !activeStatuses.has(run.status) ? (
                        <span
                          role="button"
                          tabIndex={0}
                          onClick={(event) => {
                            event.stopPropagation()
                            onCompareRun(run.id)
                          }}
                          className="mt-2 block text-[10px] text-primary-light"
                        >
                          Compare this Run
                        </span>
                      ) : null}
                    </button>
                  ))}
                </div>
              </aside>

              <div className="min-w-0">
                {runQuery.isLoading ? (
                  <LoadingState message="Loading Run evidence" />
                ) : runQuery.isError || !runQuery.data ? (
                  <ErrorState message="Unable to load Run evidence" />
                ) : activeStatuses.has(runQuery.data.status) ? (
                  <EvaluationRunProgressView projectId={projectId} runId={runQuery.data.id} />
                ) : (
                  <EvidenceRunView projectId={projectId} run={runQuery.data} />
                )}
              </div>
            </div>
          </div>
        )}
      </section>
    </div>
  )
}
