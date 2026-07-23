import { useMemo, useState } from 'react'
import {
  Activity,
  AlertTriangle,
  BarChart3,
  CheckCircle2,
  ChevronDown,
  ExternalLink,
  FileJson,
  Gauge,
  History,
  RotateCcw,
  ShieldCheck,
  XCircle,
} from 'lucide-react'
import { useNavigate, useParams } from 'react-router-dom'
import { toast } from 'sonner'

import { ErrorState } from '@/components/common/ErrorState'
import { LoadingState } from '@/components/common/LoadingState'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { Dialog } from '@/components/ui/Dialog'
import { Input } from '@/components/ui/Input'
import { JsonCodeBlock } from '@/components/ui/JsonCodeBlock'
import { Select } from '@/components/ui/Select'
import {
  useCreateEvaluationEstimate,
  useDecideEvaluationRun,
} from '@/features/evaluations/hooks'
import type {
  EvaluationEstimate,
  EvaluationRun,
  EvaluationTarget,
  EvaluationTrial,
} from '@/features/evaluations/types'
import { useTraceDetail } from '@/features/traces/hooks'
import { cn } from '@/lib/utils'

type Tab = 'summary' | 'cases' | 'attention' | 'estimates' | 'details'
type AttentionKind = 'execution' | 'judge' | 'inconclusive' | 'criteria'

interface Props {
  run: EvaluationRun
  retrying?: boolean
  onRetryJudgments?: () => void
}

interface CaseGroup {
  key: string
  name: string
  caseType: string
  trials: EvaluationTrial[]
  passed: number
  conclusive: number
  averageScore: number | null
  stability: 'stable' | 'mixed' | 'failed' | 'inconclusive'
  attentionKinds: AttentionKind[]
}

function score(value?: number | null) {
  return value == null ? '—' : value.toFixed(1)
}

function percentage(value?: number | null) {
  return value == null ? '—' : `${value.toFixed(1)}%`
}

function money(value?: number | null) {
  if (value == null) return '—'
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: value < 0.01 ? 4 : 2,
  }).format(value)
}

function label(value?: string | null) {
  if (!value) return 'Unknown'
  return value
    .split('_')
    .map((item) => item.charAt(0).toUpperCase() + item.slice(1))
    .join(' ')
}

function trialCaseKey(trial: EvaluationTrial) {
  return trial.case?.id || trial.case?.name || trial.pair_key.split(':')[0]
}

function classifyTrial(trial: EvaluationTrial): AttentionKind | null {
  const code = String(trial.failure_code || '')
  if (trial.status === 'failed' || (code && !code.startsWith('judge_'))) {
    return 'execution'
  }
  if (code.startsWith('judge_')) return 'judge'
  if (trial.status === 'inconclusive' || trial.passed == null) return 'inconclusive'
  if (trial.status === 'completed' && trial.passed === false) return 'criteria'
  return null
}

function attentionLabel(kind: AttentionKind) {
  if (kind === 'execution') return 'Execution issue'
  if (kind === 'judge') return 'Judge issue'
  if (kind === 'inconclusive') return 'Inconclusive evidence'
  return 'Criteria not met'
}

function attentionDescription(kind: AttentionKind) {
  if (kind === 'execution') return 'Runtime, Tool or platform execution did not complete normally.'
  if (kind === 'judge') return 'Target evidence was preserved, but the Judge did not complete its assessment.'
  if (kind === 'inconclusive') return 'The available evidence did not produce a reliable outcome.'
  return 'The target responded, but the configured behavior or threshold was not satisfied.'
}

function assessmentLabel(value?: string | null) {
  if (value === 'meets_policy') return 'Meets configured policy'
  if (value === 'below_policy') return 'Below configured policy'
  if (value === 'inconclusive') return 'Inconclusive assessment'
  return 'Assessment pending'
}

function assessmentClass(value?: string | null) {
  if (value === 'meets_policy') {
    return 'border-emerald-500/30 bg-emerald-500/10 text-emerald-300'
  }
  if (value === 'below_policy') {
    return 'border-amber-500/30 bg-amber-500/10 text-amber-200'
  }
  return 'border-border bg-background/40 text-muted'
}

function statusIcon(group: CaseGroup) {
  if (group.stability === 'stable') return <CheckCircle2 className="h-4 w-4 text-emerald-300" />
  if (group.stability === 'failed') return <XCircle className="h-4 w-4 text-red-300" />
  return <AlertTriangle className="h-4 w-4 text-amber-300" />
}

function estimateRevision(item: EvaluationEstimate) {
  const value = item.assumptions?.evidence_revision
  const parsed = Number(value ?? 1)
  return Number.isFinite(parsed) && parsed > 0 ? parsed : 1
}

function estimateOrigin(item: EvaluationEstimate) {
  return item.assumptions?.origin === 'suite_default' ? 'Suite default' : 'Custom'
}

function formatDate(value?: string | null) {
  if (!value) return '—'
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? '—' : date.toLocaleString()
}

function TargetIdentityLine({ target }: { target: EvaluationTarget }) {
  const manifest = target.manifest || {}
  const model = manifest.model || {}
  const tools = Array.isArray(manifest.tools) ? manifest.tools : []
  const knowledge = manifest.knowledge || {}
  const outputContract = manifest.output_contract || {}
  const collectionIds = Array.isArray(knowledge.collection_ids)
    ? knowledge.collection_ids
    : []

  return (
    <div className="flex flex-wrap items-center gap-x-4 gap-y-2 rounded-xl border border-border/80 bg-background/30 px-4 py-3">
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-semibold text-white">
          {target.display_name} · {target.display_version}
        </p>
        <p className="mt-1 truncate text-[10px] text-muted">
          {label(target.environment)} · {String(model.model || 'Model unavailable')} · Snapshot {target.snapshot_hash.slice(0, 12)}…
        </p>
      </div>
      <div className="flex flex-wrap items-center gap-2 text-[10px] text-muted">
        <span>{tools.length} Tools</span>
        <span>·</span>
        <span>{collectionIds.length} Collections</span>
        <span>·</span>
        <span>{outputContract.has_schema ? 'Structured output' : label(String(outputContract.response_format || 'text'))}</span>
      </div>
      <Badge variant="outline">
        {target.side === 'single' ? 'Tested snapshot' : label(target.side)}
      </Badge>
    </div>
  )
}

function TraceEvidenceDialog({
  traceId,
  onClose,
}: {
  traceId: string | null
  onClose: () => void
}) {
  const navigate = useNavigate()
  const { organizationId, projectId } = useParams<{
    organizationId: string
    projectId: string
  }>()
  const query = useTraceDetail(traceId || undefined)
  const trace = query.data

  return (
    <Dialog
      open={Boolean(traceId)}
      onClose={onClose}
      title="Trace evidence"
      className="max-w-5xl"
      scrollMode="content"
    >
      {query.isLoading ? (
        <LoadingState message="Loading Trace evidence" />
      ) : query.isError || !trace ? (
        <ErrorState
          title="Unable to load Trace"
          description="The Trace may be unavailable or outside this Project."
        />
      ) : (
        <div className="space-y-4">
          <section className="rounded-xl border border-border/80 bg-background/35 p-4">
            <div className="flex flex-wrap items-start justify-between gap-4">
              <div>
                <Badge variant="outline">{label(trace.status)}</Badge>
                <p className="mt-3 font-mono text-xs text-muted">{trace.id}</p>
              </div>
              <div className="grid grid-cols-3 gap-5 text-right">
                <div><p className="text-[9px] uppercase text-muted">Latency</p><p className="mt-1 text-sm text-white">{trace.total_latency_ms == null ? '—' : `${Math.round(trace.total_latency_ms)}ms`}</p></div>
                <div><p className="text-[9px] uppercase text-muted">Cost</p><p className="mt-1 text-sm text-white">{money(trace.total_cost_usd)}</p></div>
                <div><p className="text-[9px] uppercase text-muted">Events</p><p className="mt-1 text-sm text-white">{trace.events.length}</p></div>
              </div>
            </div>
          </section>
          <section className="space-y-2">
            {trace.events.map((event) => (
              <details
                key={event.id}
                className="rounded-xl border border-border/80 bg-background/35 p-4"
              >
                <summary className="cursor-pointer text-xs font-medium text-white">
                  {label(event.event_type)}
                </summary>
                {event.payload ? (
                  <div className="mt-3">
                    <JsonCodeBlock title="Evidence" value={event.payload} maxHeight={240} />
                  </div>
                ) : null}
              </details>
            ))}
          </section>
          {organizationId && projectId ? (
            <div className="flex justify-end">
              <Button
                variant="outline"
                onClick={() => navigate(`/organizations/${organizationId}/projects/${projectId}/traces/${trace.id}`)}
              >
                <ExternalLink className="mr-2 h-4 w-4" />Open full Trace
              </Button>
            </div>
          ) : null}
        </div>
      )}
    </Dialog>
  )
}

export function EvaluationResultsView({
  run,
  retrying,
  onRetryJudgments,
}: Props) {
  const trials = run.trials || []
  const hasSessionTrials = trials.some((trial) => (
    trial.interaction_mode === 'session'
    || trial.case?.interaction_mode === 'session'
    || trial.metrics?.interaction_mode === 'session'
  ))
  const [tab, setTab] = useState<Tab>('summary')
  const [expandedCase, setExpandedCase] = useState<string | null>(null)
  const [traceId, setTraceId] = useState<string | null>(null)
  const [volume, setVolume] = useState(100000)
  const [volumeUnit, setVolumeUnit] = useState<'runs_per_month' | 'sessions_per_month'>(
    hasSessionTrials ? 'sessions_per_month' : 'runs_per_month',
  )
  const [decisionNote, setDecisionNote] = useState('')
  const decide = useDecideEvaluationRun(run.project_id, run.id)
  const estimate = useCreateEvaluationEstimate(run.project_id, run.id)
  const assessment = run.assessment_status
  const currentRevision = Number(
    run.evidence_revision
      ?? run.aggregate_result?.evidence_revision
      ?? 1,
  )
  const decisions = run.decisions || []
  const primaryTarget = run.targets.find((target) => target.side === 'single')
    || run.targets.find((target) => target.side === 'candidate')
    || run.targets[0]
  const currentDecision = decisions.find((item) => (
    item.target_id === primaryTarget?.id
    && item.evidence_revision === currentRevision
    && !item.superseded_at
  ))
  const targetSummaries = (
    run.aggregate_result?.target_summaries || []
  ) as Array<Record<string, any>>
  const primarySummary = targetSummaries.find(
    (item) => item.target_id === primaryTarget?.id,
  ) || targetSummaries[0]

  const grouped = useMemo<CaseGroup[]>(() => {
    const map = new Map<string, EvaluationTrial[]>()
    for (const trial of trials) {
      const key = trialCaseKey(trial)
      map.set(key, [...(map.get(key) || []), trial])
    }
    return [...map.entries()].map(([key, items]) => {
      const passed = items.filter((trial) => trial.passed === true).length
      const conclusive = items.filter((trial) => trial.passed != null).length
      const scores = items
        .map((item) => item.score)
        .filter((value): value is number => typeof value === 'number')
      const averageScore = scores.length
        ? scores.reduce((total, value) => total + value, 0) / scores.length
        : null
      const kinds = [...new Set(
        items.map(classifyTrial).filter((value): value is AttentionKind => value != null),
      )]
      const stability: CaseGroup['stability'] = conclusive < items.length
        ? 'inconclusive'
        : passed === items.length
          ? 'stable'
          : passed === 0
            ? 'failed'
            : 'mixed'
      return {
        key,
        name: items[0]?.case?.name || key,
        caseType: items[0]?.case?.case_type || 'success',
        trials: items,
        passed,
        conclusive,
        averageScore,
        stability,
        attentionKinds: kinds,
      }
    })
  }, [trials])

  const attentionCases = grouped.filter((item) => item.attentionKinds.length > 0)
  const trialAttention = trials.filter((item) => classifyTrial(item) != null)
  const counts = {
    criteria: trials.filter((item) => classifyTrial(item) === 'criteria').length,
    execution: trials.filter((item) => classifyTrial(item) === 'execution').length,
    judge: trials.filter((item) => classifyTrial(item) === 'judge').length,
    inconclusive: trials.filter((item) => classifyTrial(item) === 'inconclusive').length,
  }
  const retryableJudgeCount = counts.judge
  const currentEstimates = (run.estimates || []).filter((item) => (
    estimateRevision(item) === currentRevision
    && !item.assumptions?.superseded_at
  ))
  const historicalEstimates = (run.estimates || []).filter(
    (item) => !currentEstimates.includes(item),
  )

  const tabs: Array<{ value: Tab; label: string }> = [
    { value: 'summary', label: 'Overview' },
    { value: 'cases', label: `Cases (${grouped.length})` },
    { value: 'attention', label: `Attention (${attentionCases.length})` },
    { value: 'estimates', label: `Estimates (${currentEstimates.length})` },
    { value: 'details', label: 'Details' },
  ]

  const submitDecision = async (decision: 'accepted' | 'rejected') => {
    try {
      await decide.mutateAsync({
        target_id: primaryTarget?.id,
        decision,
        note: decisionNote || undefined,
      })
      toast.success(
        decision === 'accepted'
          ? `Evidence revision ${currentRevision} accepted`
          : `Evidence revision ${currentRevision} rejected`,
      )
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Unable to save decision')
    }
  }

  const createEstimate = async () => {
    try {
      await estimate.mutateAsync({ volume, volume_unit: volumeUnit })
      toast.success(`Operational Estimate created from evidence revision ${currentRevision}`)
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Unable to create Estimate')
    }
  }

  return (
    <div className="space-y-4">
      <section className="rounded-2xl border border-border/80 bg-background/35 p-4">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <Badge variant="outline" className={assessmentClass(assessment)}>
                {assessmentLabel(assessment)}
              </Badge>
              <Badge variant="outline">
                {run.mode === 'comparison' ? 'Snapshot comparison' : 'Single snapshot'}
              </Badge>
              <Badge variant="outline">Evidence revision {currentRevision}</Badge>
              <Badge variant="outline">
                {currentDecision ? `Decision: ${label(currentDecision.decision)}` : 'Decision pending'}
              </Badge>
            </div>
            <h3 className="mt-3 text-base font-semibold text-white">Evaluation evidence</h3>
            <p className="mt-1 text-xs text-muted">
              {run.repetitions} repetitions per Test Case · exact immutable snapshots
            </p>
          </div>
          <div className="grid grid-cols-3 gap-6 text-right">
            <div><p className="text-[9px] uppercase text-muted">Weighted score</p><p className="mt-1 text-lg font-semibold text-white">{score(run.overall_score)}</p></div>
            <div><p className="text-[9px] uppercase text-muted">Weighted pass</p><p className="mt-1 text-lg font-semibold text-white">{percentage(run.pass_rate)}</p></div>
            <div><p className="text-[9px] uppercase text-muted">Evaluation cost</p><p className="mt-1 text-lg font-semibold text-white">{money(run.measured_total_cost)}</p></div>
          </div>
        </div>
        <div className="mt-4 space-y-2">
          {run.targets.map((target) => <TargetIdentityLine key={target.id} target={target} />)}
        </div>
      </section>

      <div className="flex gap-1 rounded-xl border border-border bg-background/35 p-1">
        {tabs.map((item) => (
          <button
            key={item.value}
            type="button"
            onClick={() => setTab(item.value)}
            className={cn(
              'rounded-lg px-3 py-2 text-xs font-medium transition-colors',
              tab === item.value
                ? 'bg-primary/15 text-primary-light'
                : 'text-muted hover:text-white',
            )}
          >
            {item.label}
          </button>
        ))}
      </div>

      {tab === 'summary' ? (
        <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_340px]">
          <div className="space-y-4">
            <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
              <div className="rounded-xl border border-border/80 bg-background/35 p-4">
                <p className="text-[9px] uppercase text-muted">Trial outcomes passed</p>
                <p className="mt-2 text-xl font-semibold text-white">
                  {primarySummary?.trial_outcomes_passed ?? primarySummary?.raw_passed ?? 0} / {primarySummary?.trial_outcomes_total ?? primarySummary?.raw_total ?? trials.length}
                </p>
                <p className="mt-1 text-[10px] text-muted">Individual repetitions</p>
              </div>
              <div className="rounded-xl border border-border/80 bg-background/35 p-4">
                <p className="text-[9px] uppercase text-muted">Cases fully passed</p>
                <p className="mt-2 text-xl font-semibold text-white">
                  {primarySummary?.cases_fully_passed ?? grouped.filter((item) => item.stability === 'stable').length} / {primarySummary?.case_count ?? grouped.length}
                </p>
                <p className="mt-1 text-[10px] text-muted">Stable across all repetitions</p>
              </div>
              <div className="rounded-xl border border-border/80 bg-background/35 p-4">
                <p className="text-[9px] uppercase text-muted">Mixed cases</p>
                <p className="mt-2 text-xl font-semibold text-white">
                  {primarySummary?.cases_mixed ?? grouped.filter((item) => item.stability === 'mixed').length}
                </p>
                <p className="mt-1 text-[10px] text-muted">Results varied by repetition</p>
              </div>
              <div className="rounded-xl border border-border/80 bg-background/35 p-4">
                <p className="text-[9px] uppercase text-muted">Cases needing attention</p>
                <p className="mt-2 text-xl font-semibold text-white">{attentionCases.length}</p>
                <p className="mt-1 text-[10px] text-muted">{trialAttention.length} Trial outcomes affected</p>
              </div>
            </section>

            {retryableJudgeCount > 0 && onRetryJudgments ? (
              <section className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-amber-500/25 bg-amber-500/[0.05] p-4">
                <div>
                  <p className="text-sm font-semibold text-white">{retryableJudgeCount} Judge outcomes need attention</p>
                  <p className="mt-1 text-xs text-amber-200/80">
                    Target outputs, Tools and RAG evidence are preserved. A retry creates a new evidence revision and supersedes the current decision.
                  </p>
                </div>
                <Button variant="outline" loading={retrying} onClick={onRetryJudgments}>
                  <RotateCcw className="mr-2 h-4 w-4" />Retry judgments
                </Button>
              </section>
            ) : null}
          </div>

          <section className="rounded-xl border border-border/80 bg-background/35 p-4">
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="text-sm font-semibold text-white">Human decision</p>
                <p className="mt-1 text-[11px] leading-5 text-muted">
                  Applies only to evidence revision {currentRevision} for this exact snapshot.
                </p>
              </div>
              <Badge variant="outline">
                {currentDecision ? label(currentDecision.decision) : 'Pending'}
              </Badge>
            </div>
            <textarea
              value={decisionNote}
              onChange={(event) => setDecisionNote(event.target.value)}
              placeholder="Optional decision note"
              className="mt-4 min-h-24 w-full rounded-lg border border-border bg-background px-3 py-2 text-xs text-white outline-none focus:border-primary/40"
            />
            <div className="mt-3 grid grid-cols-2 gap-2">
              <Button
                variant="outline"
                loading={decide.isPending}
                onClick={() => void submitDecision('rejected')}
              >
                <XCircle className="mr-2 h-4 w-4" />Reject
              </Button>
              <Button
                loading={decide.isPending}
                onClick={() => void submitDecision('accepted')}
              >
                <ShieldCheck className="mr-2 h-4 w-4" />Accept
              </Button>
            </div>
          </section>
        </div>
      ) : null}

      {tab === 'cases' ? (
        <section className="overflow-hidden rounded-xl border border-border/80 bg-background/30">
          <div className="grid grid-cols-[36px_minmax(220px,1fr)_100px_90px_100px_32px] gap-3 border-b border-border px-4 py-3 text-[9px] uppercase tracking-wide text-muted">
            <span>Status</span><span>Test Case</span><span>Type</span><span>Outcomes</span><span>Avg score</span><span />
          </div>
          <div className="divide-y divide-border/70">
            {grouped.map((group) => {
              const open = expandedCase === group.key
              return (
                <article key={group.key}>
                  <button
                    type="button"
                    onClick={() => setExpandedCase(open ? null : group.key)}
                    className="grid w-full grid-cols-[36px_minmax(220px,1fr)_100px_90px_100px_32px] items-center gap-3 px-4 py-3 text-left hover:bg-surface/20"
                  >
                    <span>{statusIcon(group)}</span>
                    <span className="min-w-0">
                      <span className="block truncate text-xs font-medium text-white">{group.name}</span>
                      <span className="mt-1 block text-[10px] text-muted">{label(group.stability)}</span>
                    </span>
                    <span className="text-[10px] text-muted">{label(group.caseType)}</span>
                    <span className="text-xs text-white">{group.passed}/{group.trials.length}</span>
                    <span className="text-xs font-semibold text-white">{score(group.averageScore)}</span>
                    <ChevronDown className={cn('h-4 w-4 text-muted transition-transform', open && 'rotate-180')} />
                  </button>
                  {open ? (
                    <div className="space-y-3 border-t border-border bg-surface/10 p-4">
                      <div className="grid gap-3 lg:grid-cols-2">
                        <JsonCodeBlock
                          title="Input and expected contract"
                          value={{
                            input: group.trials[0]?.case?.input_payload,
                            initial_context: group.trials[0]?.case?.initial_context,
                            expected_contract: group.trials[0]?.case?.expected_contract,
                          }}
                          maxHeight={260}
                        />
                        <JsonCodeBlock
                          title="Latest target output"
                          value={group.trials[group.trials.length - 1]?.output}
                          maxHeight={260}
                        />
                      </div>
                      <div className="space-y-2">
                        {group.trials.map((trial) => (
                          <div
                            key={trial.id}
                            className="flex flex-wrap items-center gap-3 rounded-lg border border-border/70 bg-background/35 px-3 py-2 text-xs"
                          >
                            <Badge variant="outline">Run {trial.repetition}</Badge>
                            <span className="text-white">Score {score(trial.score)}</span>
                            <span className="flex-1 text-muted">
                              {classifyTrial(trial)
                                ? attentionLabel(classifyTrial(trial) as AttentionKind)
                                : 'Passed'}
                            </span>
                            {trial.trace_id ? (
                              <button
                                type="button"
                                onClick={() => setTraceId(trial.trace_id)}
                                className="flex items-center gap-1 text-primary-light"
                              >
                                <Activity className="h-3 w-3" />Trace
                              </button>
                            ) : null}
                          </div>
                        ))}
                      </div>
                    </div>
                  ) : null}
                </article>
              )
            })}
          </div>
        </section>
      ) : null}

      {tab === 'attention' ? (
        <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_260px]">
          <section className="overflow-hidden rounded-xl border border-border/80 bg-background/30">
            <div className="border-b border-border px-4 py-3">
              <p className="text-sm font-semibold text-white">Cases requiring attention</p>
              <p className="mt-1 text-[11px] text-muted">
                {attentionCases.length} Test Cases · {trialAttention.length} of {trials.length} Trial outcomes affected
              </p>
            </div>
            <div className="divide-y divide-border/70">
              {attentionCases.length ? attentionCases.map((group) => (
                <button
                  key={group.key}
                  type="button"
                  onClick={() => {
                    setExpandedCase(group.key)
                    setTab('cases')
                  }}
                  className="flex w-full items-center gap-4 px-4 py-3 text-left hover:bg-surface/20"
                >
                  {statusIcon(group)}
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-xs font-medium text-white">{group.name}</p>
                    <p className="mt-1 text-[10px] text-muted">
                      {group.passed}/{group.trials.length} passed · {group.attentionKinds.map(attentionLabel).join(' · ')}
                    </p>
                  </div>
                  <span className="text-xs font-semibold text-white">{score(group.averageScore)}</span>
                  <ChevronDown className="h-4 w-4 -rotate-90 text-muted" />
                </button>
              )) : (
                <div className="p-10 text-center text-xs text-muted">No Test Cases need attention.</div>
              )}
            </div>
          </section>
          <aside className="space-y-3">
            {([
              ['Criteria not met', counts.criteria, 'criteria'],
              ['Execution issues', counts.execution, 'execution'],
              ['Judge issues', counts.judge, 'judge'],
              ['Inconclusive', counts.inconclusive, 'inconclusive'],
            ] as const).map(([title, count, kind]) => (
              <div key={kind} className="rounded-xl border border-border/80 bg-background/35 p-4">
                <div className="flex items-center justify-between gap-2">
                  <p className="text-xs font-semibold text-white">{title}</p>
                  <Badge variant="outline">{count}</Badge>
                </div>
                <p className="mt-2 text-[10px] leading-4 text-muted">
                  {attentionDescription(kind)}
                </p>
              </div>
            ))}
          </aside>
        </div>
      ) : null}

      {tab === 'estimates' ? (
        <div className="space-y-4">
          <section className="rounded-xl border border-border/80 bg-background/35 p-4">
            <div className="flex flex-wrap items-end gap-3">
              <label className="min-w-60 flex-1 space-y-2 text-xs text-muted">
                <span>Operational volume</span>
                <Input
                  type="number"
                  min={1}
                  value={volume}
                  onChange={(event) => setVolume(Math.max(1, Number(event.target.value)))}
                />
              </label>
              <label className="min-w-52 space-y-2 text-xs text-muted">
                <span>Volume unit</span>
                <Select
                  value={volumeUnit}
                  onChange={(event) =>
                    setVolumeUnit(event.target.value as 'runs_per_month' | 'sessions_per_month')
                  }
                  options={[
                    { value: 'runs_per_month', label: 'Runs per month' },
                    ...(hasSessionTrials
                      ? [{ value: 'sessions_per_month', label: 'Sessions per month' }]
                      : []),
                  ]}
                />
              </label>
              <Button loading={estimate.isPending} onClick={() => void createEstimate()}>
                <BarChart3 className="mr-2 h-4 w-4" />Calculate projection
              </Button>
            </div>
            <p className="mt-3 text-[10px] text-muted">
              Projects target runtime cost and observed latency. Judge cost from the Evaluation is not included.
            </p>
          </section>

          {currentEstimates.length ? (
            <section className="overflow-hidden rounded-xl border border-border/80 bg-background/30">
              <div className="border-b border-border px-4 py-3">
                <p className="text-sm font-semibold text-white">Current evidence revision {currentRevision}</p>
                <p className="mt-1 text-[11px] text-muted">Operational projections using the current Trial evidence.</p>
              </div>
              <div className="divide-y divide-border/70">
                {currentEstimates.map((item) => (
                  <div key={item.id} className="p-4">
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div>
                        <p className="text-sm font-semibold text-white">
                          {item.volume.toLocaleString()} {label(item.volume_unit)}
                        </p>
                        <p className="mt-1 text-[10px] text-muted">
                          {estimateOrigin(item)} · Sample {String(item.observation_summary?.sample_size ?? '—')} · Created {formatDate(item.created_at)}
                        </p>
                      </div>
                      <Badge variant="outline">Confidence: {label(item.confidence)}</Badge>
                    </div>
                    <div className="mt-4 grid gap-3 sm:grid-cols-3">
                      {(['optimistic', 'expected', 'conservative'] as const).map((scenario) => (
                        <div key={scenario} className="rounded-lg border border-border/70 p-3">
                          <p className="text-[9px] uppercase text-muted">{scenario}</p>
                          <p className="mt-2 text-lg font-semibold text-white">
                            {money(item.scenarios?.[scenario]?.provider_cost_usd)}
                          </p>
                          <p className="mt-1 text-[10px] text-muted">
                            {(item.volume_unit === 'sessions_per_month'
                              ? item.scenarios?.[scenario]?.latency_ms_per_session
                              : item.scenarios?.[scenario]?.latency_ms_per_run) == null
                              ? 'Latency unavailable'
                              : `${Math.round(
                                  (item.volume_unit === 'sessions_per_month'
                                    ? item.scenarios[scenario].latency_ms_per_session
                                    : item.scenarios[scenario].latency_ms_per_run) as number,
                                )}ms / ${item.volume_unit === 'sessions_per_month' ? 'Session' : 'Run'}`}
                          </p>
                          {item.volume_unit === 'sessions_per_month' ? (
                            <p className="mt-1 text-[10px] text-muted">
                              {Number(item.scenarios?.[scenario]?.turns || 0).toLocaleString()} projected turns
                              {item.scenarios?.[scenario]?.cost_usd_per_session != null
                                ? ` · ${money(item.scenarios[scenario].cost_usd_per_session)} / Session`
                                : ''}
                            </p>
                          ) : null}
                        </div>
                      ))}
                    </div>
                    {item.volume_unit === 'sessions_per_month' ? (
                      <p className="mt-3 text-[10px] text-muted">
                        Average {Number(item.observation_summary?.turns_per_session?.mean || 0).toFixed(1)} turns / Session · {Number(item.observation_summary?.projected_turns || 0).toLocaleString()} expected turns
                      </p>
                    ) : null}
                    {item.limitations?.length ? (
                      <div className="mt-3 rounded-lg border border-amber-500/20 bg-amber-500/[0.04] p-3 text-xs text-amber-200">
                        {item.limitations.join(' ')}
                      </div>
                    ) : null}
                  </div>
                ))}
              </div>
            </section>
          ) : (
            <div className="rounded-xl border border-dashed border-border p-8 text-center text-xs text-muted">
              No projection exists for evidence revision {currentRevision}.
            </div>
          )}

          {historicalEstimates.length ? (
            <details className="rounded-xl border border-border/80 bg-background/30 p-4">
              <summary className="cursor-pointer text-sm font-semibold text-white">
                Projection history · {historicalEstimates.length}
              </summary>
              <div className="mt-3 overflow-hidden rounded-lg border border-border/70">
                {historicalEstimates.map((item) => (
                  <div key={item.id} className="grid grid-cols-[minmax(0,1fr)_90px_110px_100px] gap-3 border-b border-border/70 px-3 py-3 text-xs last:border-b-0">
                    <span className="truncate text-white">{item.volume.toLocaleString()} {label(item.volume_unit)}</span>
                    <span className="text-muted">Revision {estimateRevision(item)}</span>
                    <span className="text-muted">{estimateOrigin(item)}</span>
                    <span className="text-right text-muted">{money(item.scenarios?.expected?.provider_cost_usd)}</span>
                  </div>
                ))}
              </div>
            </details>
          ) : null}
        </div>
      ) : null}

      {tab === 'details' ? (
        <div className="space-y-4">
          <section className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <div className="rounded-xl border border-border/80 bg-background/35 p-4"><Gauge className="h-4 w-4 text-primary-light" /><p className="mt-3 text-[9px] uppercase text-muted">Execution policy</p><p className="mt-1 text-xs text-white">{run.execution_policy?.effective_parallel_pairs || 1} parallel pair(s)</p></div>
            <div className="rounded-xl border border-border/80 bg-background/35 p-4"><FileJson className="h-4 w-4 text-primary-light" /><p className="mt-3 text-[9px] uppercase text-muted">Suite version ID</p><p className="mt-1 truncate font-mono text-xs text-white">{run.suite_version_id}</p></div>
            <div className="rounded-xl border border-border/80 bg-background/35 p-4"><ShieldCheck className="h-4 w-4 text-primary-light" /><p className="mt-3 text-[9px] uppercase text-muted">Assessment</p><p className="mt-1 text-xs text-white">{assessmentLabel(assessment)}</p></div>
            <div className="rounded-xl border border-border/80 bg-background/35 p-4"><Activity className="h-4 w-4 text-primary-light" /><p className="mt-3 text-[9px] uppercase text-muted">Run ID</p><p className="mt-1 truncate font-mono text-xs text-white">{run.id}</p></div>
          </section>

          {decisions.length ? (
            <section className="rounded-xl border border-border/80 bg-background/35 p-4">
              <div className="flex items-center gap-2">
                <History className="h-4 w-4 text-primary-light" />
                <p className="text-sm font-semibold text-white">Decision history</p>
              </div>
              <div className="mt-3 space-y-2">
                {decisions.map((item) => (
                  <div key={item.id} className="flex flex-wrap items-center gap-3 rounded-lg border border-border/70 px-3 py-2 text-xs">
                    <Badge variant="outline">Revision {item.evidence_revision}</Badge>
                    <span className="text-white">{label(item.decision)}</span>
                    <span className="text-muted">{formatDate(item.decided_at)}</span>
                    <span className="flex-1 truncate text-muted">{item.note || 'No note'}</span>
                    {item.superseded_at ? <Badge variant="outline">Superseded</Badge> : <Badge variant="outline">Current</Badge>}
                  </div>
                ))}
              </div>
            </section>
          ) : null}

          <details className="rounded-xl border border-border/80 bg-background/35 p-4">
            <summary className="cursor-pointer text-sm font-semibold text-white">View raw JSON</summary>
            <div className="mt-3"><JsonCodeBlock title="Execution metadata" value={run} maxHeight={520} /></div>
          </details>
        </div>
      ) : null}

      <TraceEvidenceDialog traceId={traceId} onClose={() => setTraceId(null)} />
    </div>
  )
}
