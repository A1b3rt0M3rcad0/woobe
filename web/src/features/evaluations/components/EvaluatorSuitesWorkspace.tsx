import { useEffect, useMemo, useState } from 'react'
import {
  AlertTriangle,
  Archive,
  Beaker,
  CheckCircle2,
  History,
  Play,
  Plus,
  RotateCcw,
} from 'lucide-react'
import { toast } from 'sonner'

import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { useEvaluationJudgeModels } from '@/features/evaluations/experienceHooks'
import {
  useArchiveEvaluationSuite,
  useEvaluationSuites,
  useRestoreEvaluationSuite,
} from '@/features/evaluations/hooks'
import type { EvaluationSuite, EvaluationTargetType } from '@/features/evaluations/types'
import { cn } from '@/lib/utils'

interface Props {
  projectId: string
  targetType: EvaluationTargetType
  onUseSuite: (suite: EvaluationSuite) => void
  onCreateSuite: () => void
}

type Filter = 'active' | 'archived'

function policyScore(suite: EvaluationSuite) {
  return Number(suite.acceptance_policy?.minimum_score ?? 70)
}

function repetitions(suite: EvaluationSuite) {
  return Number(suite.repetition_policy?.default_repetitions ?? 3)
}

function stalenessLabel(suite: EvaluationSuite) {
  const status = suite.staleness?.status
  if (status === 'current') return 'Current target'
  if (status === 'stale') return 'Target changed'
  if (status === 'target_unavailable') return 'Target unavailable'
  if (status === 'generic') return 'Generic Suite'
  return 'Target status unknown'
}

function stalenessClass(suite: EvaluationSuite) {
  if (suite.staleness?.status === 'current') {
    return 'border-emerald-500/25 bg-emerald-500/[0.06] text-emerald-300'
  }
  if (suite.staleness?.status === 'stale') {
    return 'border-amber-500/25 bg-amber-500/[0.06] text-amber-200'
  }
  return 'border-border bg-background/40 text-muted'
}

function money(value?: number | null) {
  if (value == null) return 'Unknown'
  return `$${value.toFixed(value < 1 ? 4 : 2)}/1M`
}

export function EvaluatorSuitesWorkspace({
  projectId,
  targetType,
  onUseSuite,
  onCreateSuite,
}: Props) {
  const query = useEvaluationSuites(projectId, true)
  const judgeModelsQuery = useEvaluationJudgeModels(projectId)
  const archive = useArchiveEvaluationSuite(projectId)
  const restore = useRestoreEvaluationSuite(projectId)
  const [filter, setFilter] = useState<Filter>('active')
  const [selectedId, setSelectedId] = useState<string | null>(null)

  const suites = useMemo(
    () => (query.data ?? []).filter((item) => item.target_type === targetType),
    [query.data, targetType],
  )
  const judgeModels = useMemo(
    () => new Map(
      (judgeModelsQuery.data ?? []).map((item) => [item.provider_model_id, item]),
    ),
    [judgeModelsQuery.data],
  )
  const visible = suites.filter((item) => (
    filter === 'archived' ? item.status === 'archived' : item.status !== 'archived'
  ))
  const selected = visible.find((item) => item.id === selectedId) || visible[0] || null
  const selectedJudge = selected?.judge_provider_model_id
    ? judgeModels.get(selected.judge_provider_model_id)
    : null

  useEffect(() => {
    if (selected && selected.id !== selectedId) setSelectedId(selected.id)
    if (!selected) setSelectedId(null)
  }, [filter, selected?.id])

  const archiveSuite = async (suite: EvaluationSuite) => {
    const confirmed = window.confirm(
      `Archive “${suite.name}”?\n\nIt will stop appearing in new Runs. Existing Results and version history remain available.`,
    )
    if (!confirmed) return
    try {
      await archive.mutateAsync(suite.id)
      toast.success('Evaluator Suite archived')
      setFilter('active')
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Unable to archive Suite')
    }
  }

  const restoreSuite = async (suite: EvaluationSuite) => {
    try {
      await restore.mutateAsync(suite.id)
      toast.success('Evaluator Suite restored')
      setFilter('active')
      setSelectedId(suite.id)
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Unable to restore Suite')
    }
  }

  return (
    <div className="grid min-h-[560px] gap-4 lg:grid-cols-[300px_minmax(0,1fr)]">
      <aside className="overflow-hidden rounded-2xl border border-border/80 bg-background/30">
        <div className="border-b border-border/80 p-4">
          <div className="flex items-center justify-between gap-3">
            <div>
              <h3 className="text-sm font-semibold text-white">Evaluator Suites</h3>
              <p className="mt-1 text-[11px] text-muted">Reusable immutable test contracts.</p>
            </div>
            <Button size="sm" onClick={onCreateSuite}>
              <Plus className="mr-1.5 h-3.5 w-3.5" />New
            </Button>
          </div>
          <div className="mt-4 flex rounded-lg border border-border bg-surface/30 p-1">
            {(['active', 'archived'] as const).map((value) => (
              <button
                key={value}
                type="button"
                onClick={() => setFilter(value)}
                className={cn(
                  'flex-1 rounded-md px-3 py-1.5 text-[11px] font-medium',
                  filter === value ? 'bg-primary/15 text-primary-light' : 'text-muted',
                )}
              >
                {value === 'active' ? 'Active' : 'Archived'}
                <span className="ml-1 opacity-70">
                  {suites.filter((item) => (
                    value === 'archived' ? item.status === 'archived' : item.status !== 'archived'
                  )).length}
                </span>
              </button>
            ))}
          </div>
        </div>

        <div className="scrollbar-thin max-h-[500px] overflow-y-auto p-2">
          {visible.length ? visible.map((suite) => {
            const judge = suite.judge_provider_model_id
              ? judgeModels.get(suite.judge_provider_model_id)
              : null
            return (
              <button
                key={suite.id}
                type="button"
                onClick={() => setSelectedId(suite.id)}
                className={cn(
                  'mb-1 w-full rounded-xl border px-3 py-3 text-left transition-colors',
                  selected?.id === suite.id
                    ? 'border-primary/30 bg-primary/[0.07]'
                    : 'border-transparent hover:border-border hover:bg-surface/25',
                )}
              >
                <div className="flex items-start gap-3">
                  <div className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border border-border bg-surface/40">
                    <Beaker className="h-3.5 w-3.5 text-primary-light" />
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-xs font-semibold text-white">{suite.name}</p>
                    <p className="mt-1 text-[10px] font-medium text-primary-light">
                      {suite.status === 'archived' ? 'Archived' : 'Current'} · {suite.current_version || 'No version'}
                    </p>
                    <p className="mt-1 truncate text-[10px] text-muted">
                      Judge: {judge?.display_name || 'Unavailable model'}
                    </p>
                    <p className="mt-1 text-[10px] text-muted">
                      {suite.case_count ?? 0} cases · Score ≥ {policyScore(suite)} · {repetitions(suite)} runs
                    </p>
                  </div>
                </div>
              </button>
            )
          }) : (
            <div className="p-8 text-center text-xs text-muted">
              {filter === 'archived' ? 'No archived Suites.' : 'No active Suites.'}
            </div>
          )}
        </div>
      </aside>

      <section className="rounded-2xl border border-border/80 bg-background/30 p-5">
        {selected ? (
          <div className="space-y-5">
            <div className="flex flex-wrap items-start justify-between gap-4 border-b border-border pb-5">
              <div>
                <div className="flex flex-wrap items-center gap-2">
                  <h3 className="text-base font-semibold text-white">{selected.name}</h3>
                  <Badge variant="outline">
                    {selected.status === 'archived' ? 'Archived' : 'Current'} · {selected.current_version}
                  </Badge>
                  <Badge variant="outline" className={stalenessClass(selected)}>
                    {stalenessLabel(selected)}
                  </Badge>
                  {selectedJudge ? (
                    <Badge
                      variant="outline"
                      className={selectedJudge.eligible
                        ? 'border-emerald-500/25 text-emerald-300'
                        : 'border-red-500/25 text-red-300'}
                    >
                      {selectedJudge.eligible ? 'Judge ready' : 'Judge blocked'}
                    </Badge>
                  ) : null}
                </div>
                <p className="mt-2 max-w-2xl text-xs leading-5 text-muted">
                  {selected.description || 'Versioned Test Cases, Judge configuration and acceptance policy.'}
                </p>
              </div>
              <div className="flex gap-2">
                {selected.status === 'archived' ? (
                  <Button
                    size="sm"
                    variant="outline"
                    loading={restore.isPending}
                    onClick={() => void restoreSuite(selected)}
                  >
                    <RotateCcw className="mr-2 h-3.5 w-3.5" />Restore
                  </Button>
                ) : (
                  <>
                    <Button
                      size="sm"
                      disabled={selectedJudge ? !selectedJudge.eligible : false}
                      onClick={() => onUseSuite(selected)}
                    >
                      <Play className="mr-2 h-3.5 w-3.5" />Use Suite
                    </Button>
                    <Button
                      size="sm"
                      variant="outline"
                      loading={archive.isPending}
                      onClick={() => void archiveSuite(selected)}
                    >
                      <Archive className="mr-2 h-3.5 w-3.5" />Archive
                    </Button>
                  </>
                )}
              </div>
            </div>

            <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
              <div className="rounded-xl border border-border/70 bg-surface/20 p-4">
                <p className="text-[9px] uppercase tracking-wide text-muted">Test Cases</p>
                <p className="mt-2 text-xl font-semibold text-white">{selected.case_count ?? 0}</p>
              </div>
              <div className="rounded-xl border border-border/70 bg-surface/20 p-4">
                <p className="text-[9px] uppercase tracking-wide text-muted">Policy score</p>
                <p className="mt-2 text-xl font-semibold text-white">≥ {policyScore(selected)}</p>
              </div>
              <div className="rounded-xl border border-border/70 bg-surface/20 p-4">
                <p className="text-[9px] uppercase tracking-wide text-muted">Default repetitions</p>
                <p className="mt-2 text-xl font-semibold text-white">{repetitions(selected)}</p>
              </div>
              <div className="rounded-xl border border-border/70 bg-surface/20 p-4">
                <p className="text-[9px] uppercase tracking-wide text-muted">Target</p>
                <p className="mt-2 text-sm font-semibold text-white">{selected.target_type === 'agent' ? 'Agent' : 'Network'}</p>
              </div>
            </div>

            {selectedJudge ? (
              <section className={cn(
                'rounded-xl border p-4',
                selectedJudge.eligible
                  ? 'border-emerald-500/20 bg-emerald-500/[0.035]'
                  : 'border-red-500/25 bg-red-500/[0.04]',
              )}>
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <div className="flex items-center gap-2">
                      {selectedJudge.eligible
                        ? <CheckCircle2 className="h-4 w-4 text-emerald-300" />
                        : <AlertTriangle className="h-4 w-4 text-red-300" />}
                      <h4 className="text-sm font-semibold text-white">Judge Model</h4>
                    </div>
                    <p className="mt-2 text-sm font-medium text-white">{selectedJudge.display_name}</p>
                    <p className="mt-1 font-mono text-[10px] text-muted">
                      {selectedJudge.provider} · {selectedJudge.model}
                    </p>
                    <p className="mt-1 text-[10px] text-muted">
                      Credential: {selectedJudge.credential_name}
                    </p>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <Badge variant="outline">{selectedJudge.capabilities.response_strategy}</Badge>
                    <Badge variant="outline">
                      {selectedJudge.budget.effective_initial_tokens.toLocaleString()} → {selectedJudge.budget.effective_retry_tokens.toLocaleString()} tokens
                    </Badge>
                  </div>
                </div>
                <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                  <div><p className="text-[9px] uppercase text-muted">Context</p><p className="mt-1 text-xs text-white">{selectedJudge.budget.context_window.toLocaleString()} tokens</p></div>
                  <div><p className="text-[9px] uppercase text-muted">Model output limit</p><p className="mt-1 text-xs text-white">{selectedJudge.budget.model_output_limit.toLocaleString()}</p></div>
                  <div><p className="text-[9px] uppercase text-muted">Input price</p><p className="mt-1 text-xs text-white">{money(selectedJudge.pricing.input_cost_per_1m_tokens)}</p></div>
                  <div><p className="text-[9px] uppercase text-muted">Output price</p><p className="mt-1 text-xs text-white">{money(selectedJudge.pricing.output_cost_per_1m_tokens)}</p></div>
                </div>
                {selectedJudge.blockers.length ? (
                  <div className="mt-4 space-y-2">
                    {selectedJudge.blockers.map((blocker) => (
                      <div key={blocker.code} className="rounded-lg border border-red-500/20 bg-red-500/[0.05] p-3 text-xs text-red-200">
                        <span className="font-mono text-[10px]">{blocker.code}</span>
                        <p className="mt-1">{blocker.message}</p>
                      </div>
                    ))}
                  </div>
                ) : null}
              </section>
            ) : (
              <section className="rounded-xl border border-red-500/25 bg-red-500/[0.04] p-4">
                <div className="flex items-start gap-2">
                  <AlertTriangle className="mt-0.5 h-4 w-4 text-red-300" />
                  <div>
                    <p className="text-sm font-semibold text-white">Judge Model unavailable</p>
                    <p className="mt-1 text-xs text-muted">
                      This Suite Version references a model that is not available in the current Project catalog. Create a new Suite Version with an active Judge Model.
                    </p>
                  </div>
                </div>
              </section>
            )}

            <div className="grid gap-4 lg:grid-cols-2">
              <section className="rounded-xl border border-border/70 bg-surface/20 p-4">
                <div className="flex items-center gap-2">
                  <History className="h-4 w-4 text-primary-light" />
                  <h4 className="text-sm font-semibold text-white">Current version</h4>
                </div>
                <dl className="mt-4 grid grid-cols-[140px_minmax(0,1fr)] gap-y-3 text-xs">
                  <dt className="text-muted">Version</dt><dd className="text-white">{selected.current_version}</dd>
                  <dt className="text-muted">Change</dt><dd className="text-white">{selected.change_description || 'Initial immutable version'}</dd>
                  <dt className="text-muted">Suite hash</dt><dd className="truncate font-mono text-[10px] text-white">{selected.suite_hash || '—'}</dd>
                  <dt className="text-muted">Authoring</dt><dd className="text-white">{selected.authoring_source || 'manual'}</dd>
                </dl>
              </section>
              <section className="rounded-xl border border-border/70 bg-surface/20 p-4">
                <h4 className="text-sm font-semibold text-white">Operational policy</h4>
                <dl className="mt-4 grid grid-cols-[160px_minmax(0,1fr)] gap-y-3 text-xs">
                  <dt className="text-muted">Minimum score</dt><dd className="text-white">{policyScore(selected)}</dd>
                  <dt className="text-muted">Minimum pass rate</dt><dd className="text-white">{String(selected.acceptance_policy?.minimum_pass_rate ?? 80)}%</dd>
                  <dt className="text-muted">Default volume</dt><dd className="text-white">{Number(selected.estimate_defaults?.volume ?? 10000).toLocaleString()} runs/month</dd>
                  <dt className="text-muted">Judge Model</dt><dd className="truncate text-xs text-white">{selectedJudge?.display_name || 'Unavailable'}</dd>
                </dl>
              </section>
            </div>
          </div>
        ) : (
          <div className="flex min-h-[420px] items-center justify-center text-sm text-muted">
            Select an Evaluator Suite.
          </div>
        )}
      </section>
    </div>
  )
}
