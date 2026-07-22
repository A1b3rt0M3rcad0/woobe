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
import {
  useCreateEvaluationEstimate,
  useDecideEvaluationRun,
} from '@/features/evaluations/hooks'
import type { EvaluationRun, EvaluationTarget, EvaluationTrial } from '@/features/evaluations/types'
import { useTraceDetail } from '@/features/traces/hooks'
import { cn } from '@/lib/utils'

type Tab = 'summary' | 'cases' | 'issues' | 'estimates' | 'details'

interface Props {
  run: EvaluationRun
  retrying?: boolean
  onRetryJudgments?: () => void
}

function score(value?: number | null) {
  return value == null ? '—' : value.toFixed(1)
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

function userFailureMessage(trial: EvaluationTrial) {
  if (trial.failure_code === 'judge_output_length_limit') {
    return 'Judge exhausted its output budget. Agent evidence was preserved.'
  }
  if (trial.failure_code === 'judge_failed') {
    return 'Judge could not complete the structured assessment. Agent evidence was preserved.'
  }
  if (trial.failure_code) return label(trial.failure_code)
  if (trial.passed === false) return 'The response completed but did not meet the configured criteria.'
  return label(trial.status)
}

function assessmentLabel(value?: string | null) {
  if (value === 'meets_policy') return 'Meets configured policy'
  if (value === 'below_policy') return 'Below configured policy'
  if (value === 'inconclusive') return 'Inconclusive assessment'
  return 'Assessment pending'
}

function assessmentClass(value?: string | null) {
  if (value === 'meets_policy') return 'border-emerald-500/30 bg-emerald-500/10 text-emerald-300'
  if (value === 'below_policy') return 'border-amber-500/30 bg-amber-500/10 text-amber-200'
  return 'border-border bg-background/40 text-muted'
}

function TargetIdentity({ target }: { target: EvaluationTarget }) {
  const manifest = (target as any).manifest || {}
  const identity = manifest.identity || {}
  const model = manifest.model || {}
  const tools = Array.isArray(manifest.tools) ? manifest.tools : []
  const knowledge = manifest.knowledge || {}
  const outputContract = manifest.output_contract || {}

  return (
    <article className="rounded-xl border border-border/80 bg-background/35 p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-sm font-semibold text-white">{target.display_name}</p>
          <p className="mt-1 text-xs text-muted">
            {label(target.environment)} · {target.display_version}
          </p>
        </div>
        <Badge variant="outline">{target.side === 'single' ? 'Tested snapshot' : label(target.side)}</Badge>
      </div>
      <div className="mt-4 grid gap-3 border-t border-border pt-4 sm:grid-cols-2 lg:grid-cols-4">
        <div><p className="text-[9px] uppercase text-muted">Snapshot</p><p className="mt-1 truncate font-mono text-[10px] text-white" title={target.snapshot_hash}>{target.snapshot_hash.slice(0, 12)}…</p></div>
        <div><p className="text-[9px] uppercase text-muted">Provider</p><p className="mt-1 text-xs text-white">{model.provider || '—'}</p></div>
        <div><p className="text-[9px] uppercase text-muted">Model</p><p className="mt-1 truncate text-xs text-white" title={model.model}>{model.model || '—'}</p></div>
        <div><p className="text-[9px] uppercase text-muted">Release ID</p><p className="mt-1 truncate font-mono text-[10px] text-white" title={identity.release_id}>{identity.release_id ? `${String(identity.release_id).slice(0, 12)}…` : '—'}</p></div>
      </div>
      <div className="mt-4 grid gap-3 sm:grid-cols-3">
        <div className="rounded-lg border border-border/70 p-3"><p className="text-[9px] uppercase text-muted">Tools</p><p className="mt-1 text-xs text-white">{tools.length}</p><p className="mt-1 truncate text-[10px] text-muted">{tools.map((item: any) => item.name).join(', ') || 'No Tools'}</p></div>
        <div className="rounded-lg border border-border/70 p-3"><p className="text-[9px] uppercase text-muted">Knowledge</p><p className="mt-1 text-xs text-white">{(knowledge.collection_ids || []).length} Collections</p><p className="mt-1 truncate text-[10px] text-muted">{knowledge.vector_snapshot_id || 'No Vector Snapshot'}</p></div>
        <div className="rounded-lg border border-border/70 p-3"><p className="text-[9px] uppercase text-muted">Output contract</p><p className="mt-1 text-xs text-white">{outputContract.has_schema ? 'Structured schema' : label(outputContract.response_format || 'text')}</p><p className="mt-1 truncate font-mono text-[10px] text-muted">{outputContract.schema_hash ? `${String(outputContract.schema_hash).slice(0, 12)}…` : 'No schema hash'}</p></div>
      </div>
    </article>
  )
}

function TraceEvidenceDialog({ traceId, onClose }: { traceId: string | null; onClose: () => void }) {
  const navigate = useNavigate()
  const { organizationId, projectId } = useParams<{ organizationId: string; projectId: string }>()
  const query = useTraceDetail(traceId || undefined)
  const trace = query.data

  return (
    <Dialog open={Boolean(traceId)} onClose={onClose} title="Trace evidence" className="max-w-5xl" scrollMode="content">
      {query.isLoading ? <LoadingState message="Loading Trace evidence" /> : query.isError || !trace ? (
        <ErrorState title="Unable to load Trace" description="The Trace may be unavailable or outside this Project." />
      ) : (
        <div className="space-y-4">
          <section className="rounded-xl border border-border/80 bg-background/35 p-4">
            <div className="flex flex-wrap items-start justify-between gap-4">
              <div><Badge variant="outline">{label(trace.status)}</Badge><p className="mt-3 font-mono text-xs text-muted">{trace.id}</p></div>
              <div className="grid grid-cols-3 gap-5 text-right">
                <div><p className="text-[9px] uppercase text-muted">Latency</p><p className="mt-1 text-sm text-white">{trace.total_latency_ms == null ? '—' : `${Math.round(trace.total_latency_ms)}ms`}</p></div>
                <div><p className="text-[9px] uppercase text-muted">Cost</p><p className="mt-1 text-sm text-white">{money(trace.total_cost_usd)}</p></div>
                <div><p className="text-[9px] uppercase text-muted">Events</p><p className="mt-1 text-sm text-white">{trace.events.length}</p></div>
              </div>
            </div>
          </section>
          <section className="space-y-2">
            {trace.events.map((event) => (
              <details key={event.id} className="rounded-xl border border-border/80 bg-background/35 p-4">
                <summary className="cursor-pointer text-xs font-medium text-white">{label(event.event_type)}</summary>
                {event.payload ? <div className="mt-3"><JsonCodeBlock title="Evidence" value={event.payload} maxHeight={240} /></div> : null}
              </details>
            ))}
          </section>
          {organizationId && projectId ? (
            <div className="flex justify-end">
              <Button variant="outline" onClick={() => navigate(`/organizations/${organizationId}/projects/${projectId}/traces/${trace.id}`)}>
                <ExternalLink className="mr-2 h-4 w-4" />Open full Trace
              </Button>
            </div>
          ) : null}
        </div>
      )}
    </Dialog>
  )
}

export function EvaluationResultsView({ run, retrying, onRetryJudgments }: Props) {
  const [tab, setTab] = useState<Tab>('summary')
  const [expandedCase, setExpandedCase] = useState<string | null>(null)
  const [traceId, setTraceId] = useState<string | null>(null)
  const [volume, setVolume] = useState(100000)
  const [decisionNote, setDecisionNote] = useState('')
  const decide = useDecideEvaluationRun(run.project_id, run.id)
  const estimate = useCreateEvaluationEstimate(run.project_id, run.id)
  const trials = run.trials || []
  const assessment = (run as any).assessment_status as string | null
  const decisions = ((run as any).decisions || []) as Array<Record<string, any>>
  const primaryTarget = run.targets.find((target) => target.side === 'single')
    || run.targets.find((target) => target.side === 'candidate')
    || run.targets[0]
  const currentDecision = decisions.find((item) => item.target_id === primaryTarget?.id) || decisions[0]
  const targetSummaries = ((run.aggregate_result as any)?.target_summaries || []) as Array<Record<string, any>>

  const grouped = useMemo(() => {
    const map = new Map<string, EvaluationTrial[]>()
    for (const trial of trials) {
      const key = trialCaseKey(trial)
      map.set(key, [...(map.get(key) || []), trial])
    }
    return [...map.entries()].map(([key, items]) => ({ key, items }))
  }, [trials])

  const issues = useMemo(() => ({
    criteria: trials.filter((trial) => trial.status === 'completed' && trial.passed === false),
    execution: trials.filter((trial) => trial.status === 'failed' || (trial.failure_code && !String(trial.failure_code).startsWith('judge_'))),
    inconclusive: trials.filter((trial) => trial.status === 'inconclusive'),
    judge: trials.filter((trial) => String(trial.failure_code || '').startsWith('judge_')),
  }), [trials])

  const retryableJudgeCount = issues.judge.length
  const tabs: Array<{ value: Tab; label: string }> = [
    { value: 'summary', label: 'Summary' },
    { value: 'cases', label: `Cases (${grouped.length})` },
    { value: 'issues', label: `Issues (${issues.criteria.length + issues.execution.length + issues.inconclusive.length})` },
    { value: 'estimates', label: `Estimates (${run.estimates?.length || 0})` },
    { value: 'details', label: 'Details' },
  ]

  const submitDecision = async (decision: 'accepted' | 'rejected') => {
    try {
      await decide.mutateAsync({
        target_id: primaryTarget?.id,
        decision,
        note: decisionNote || undefined,
      })
      toast.success(decision === 'accepted' ? 'Evaluation result accepted' : 'Evaluation result rejected')
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Unable to save decision')
    }
  }

  const createEstimate = async () => {
    try {
      await estimate.mutateAsync({ volume })
      toast.success('Operational Estimate created')
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Unable to create Estimate')
    }
  }

  return (
    <div className="mx-auto max-w-6xl space-y-5">
      <section className="rounded-2xl border border-border/80 bg-background/40 p-5">
        <div className="flex flex-wrap items-start justify-between gap-5">
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <Badge variant="outline" className={assessmentClass(assessment)}>{assessmentLabel(assessment)}</Badge>
              <Badge variant="outline">{run.mode === 'comparison' ? 'Snapshot comparison' : 'Single snapshot'}</Badge>
              {currentDecision ? <Badge variant="outline">Decision: {label(currentDecision.decision)}</Badge> : <Badge variant="outline">Decision pending</Badge>}
            </div>
            <h3 className="mt-3 text-base font-semibold text-white">Evaluation result</h3>
            <p className="mt-1 text-xs text-muted">{run.repetitions} Runs per Test Case · exact immutable target snapshots</p>
          </div>
          <div className="grid grid-cols-3 gap-6 text-right">
            <div><p className="text-[9px] uppercase text-muted">Weighted score</p><p className="mt-1 text-lg font-semibold text-white">{score(run.overall_score)}</p></div>
            <div><p className="text-[9px] uppercase text-muted">Weighted pass</p><p className="mt-1 text-lg font-semibold text-white">{run.pass_rate == null ? '—' : `${run.pass_rate.toFixed(1)}%`}</p></div>
            <div><p className="text-[9px] uppercase text-muted">Measured cost</p><p className="mt-1 text-lg font-semibold text-white">{money(run.measured_total_cost)}</p></div>
          </div>
        </div>
      </section>

      <div className="flex gap-1 rounded-xl border border-border bg-background/35 p-1">
        {tabs.map((item) => (
          <button key={item.value} type="button" onClick={() => setTab(item.value)} className={cn('rounded-lg px-3 py-2 text-xs font-medium transition-colors', tab === item.value ? 'bg-primary/15 text-primary-light' : 'text-muted hover:text-white')}>{item.label}</button>
        ))}
      </div>

      {tab === 'summary' ? (
        <div className="space-y-4">
          <section className="grid gap-4 lg:grid-cols-2">
            {run.targets.map((target) => <TargetIdentity key={target.id} target={target} />)}
          </section>

          <section className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            {targetSummaries.map((item) => (
              <div key={item.target_id} className="rounded-xl border border-border/80 bg-background/35 p-4">
                <p className="text-[9px] uppercase text-muted">{label(item.side)} cases passed</p>
                <p className="mt-2 text-xl font-semibold text-white">{item.raw_passed} / {item.raw_total}</p>
                <p className="mt-1 text-[10px] text-muted">Raw {item.raw_pass_rate == null ? '—' : `${Number(item.raw_pass_rate).toFixed(1)}%`} · weighted {item.weighted_pass_rate == null ? '—' : `${Number(item.weighted_pass_rate).toFixed(1)}%`}</p>
              </div>
            ))}
            <div className="rounded-xl border border-border/80 bg-background/35 p-4"><p className="text-[9px] uppercase text-muted">Criteria not met</p><p className="mt-2 text-xl font-semibold text-white">{issues.criteria.length}</p></div>
            <div className="rounded-xl border border-border/80 bg-background/35 p-4"><p className="text-[9px] uppercase text-muted">Inconclusive</p><p className="mt-2 text-xl font-semibold text-white">{issues.inconclusive.length}</p></div>
          </section>

          <section className="rounded-xl border border-border/80 bg-background/35 p-5">
            <div className="flex flex-wrap items-start justify-between gap-4">
              <div><p className="text-sm font-semibold text-white">Human decision</p><p className="mt-1 text-xs text-muted">The system assessment is evidence. Accepting or rejecting the result is an explicit user decision for this exact snapshot.</p></div>
              {currentDecision ? <Badge variant="outline">{label(currentDecision.decision)}</Badge> : <Badge variant="outline">Pending</Badge>}
            </div>
            <textarea value={decisionNote} onChange={(event) => setDecisionNote(event.target.value)} placeholder="Optional decision note" className="mt-4 min-h-20 w-full rounded-lg border border-border bg-background px-3 py-2 text-xs text-white outline-none focus:border-primary/40" />
            <div className="mt-3 flex justify-end gap-2">
              <Button variant="outline" loading={decide.isPending} onClick={() => void submitDecision('rejected')}><XCircle className="mr-2 h-4 w-4" />Reject result</Button>
              <Button loading={decide.isPending} onClick={() => void submitDecision('accepted')}><ShieldCheck className="mr-2 h-4 w-4" />Accept result</Button>
            </div>
          </section>

          {retryableJudgeCount > 0 && onRetryJudgments ? (
            <section className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-amber-500/25 bg-amber-500/[0.05] p-4">
              <div><p className="text-sm font-semibold text-white">{retryableJudgeCount} judgments need attention</p><p className="mt-1 text-xs text-amber-200/80">Agent Runs, Tools and RAG evidence will not be executed again.</p></div>
              <Button variant="outline" loading={retrying} onClick={onRetryJudgments}><RotateCcw className="mr-2 h-4 w-4" />Retry judgments</Button>
            </section>
          ) : null}
        </div>
      ) : null}

      {tab === 'cases' ? (
        <div className="space-y-2">
          {grouped.map(({ key, items }) => {
            const passed = items.filter((trial) => trial.passed === true).length
            const caseScore = items.map((item) => item.score).filter((value): value is number => typeof value === 'number')
            const averageScore = caseScore.length ? caseScore.reduce((total, value) => total + value, 0) / caseScore.length : null
            const open = expandedCase === key
            return (
              <article key={key} className="overflow-hidden rounded-xl border border-border/80 bg-background/35">
                <button type="button" onClick={() => setExpandedCase(open ? null : key)} className="flex w-full items-center gap-4 p-4 text-left">
                  {passed === items.length ? <CheckCircle2 className="h-4 w-4 text-emerald-300" /> : passed === 0 ? <XCircle className="h-4 w-4 text-red-300" /> : <AlertTriangle className="h-4 w-4 text-amber-300" />}
                  <div className="min-w-0 flex-1"><p className="truncate text-sm font-medium text-white">{items[0]?.case?.name || key}</p><p className="mt-1 text-[10px] text-muted">{passed}/{items.length} passed · {label(items[0]?.case?.case_type || 'success')}</p></div>
                  <p className="text-sm font-semibold text-white">{score(averageScore)}</p>
                  <ChevronDown className={cn('h-4 w-4 text-muted transition-transform', open && 'rotate-180')} />
                </button>
                {open ? (
                  <div className="space-y-3 border-t border-border p-3">
                    <div className="grid gap-3 lg:grid-cols-2"><JsonCodeBlock title="Input and expected contract" value={{ input: items[0]?.case?.input_payload, initial_context: items[0]?.case?.initial_context, expected_contract: items[0]?.case?.expected_contract }} maxHeight={260} /><JsonCodeBlock title="Latest target output" value={items[items.length - 1]?.output} maxHeight={260} /></div>
                    {items.map((trial) => (
                      <div key={trial.id} className="flex flex-wrap items-center gap-3 rounded-lg border border-border/70 bg-surface/20 px-3 py-2 text-xs">
                        <Badge variant="outline">{trial.side === 'single' ? 'Tested snapshot' : label(trial.side)}</Badge><span className="text-muted">Run {trial.repetition}</span><span className="text-white">Score {score(trial.score)}</span><span className="flex-1 text-muted">{trial.passed === false ? 'Criteria not met' : userFailureMessage(trial)}</span>
                        {trial.trace_id ? <button type="button" onClick={() => setTraceId(trial.trace_id)} className="flex items-center gap-1 text-primary-light"><Activity className="h-3 w-3" />Trace</button> : null}
                      </div>
                    ))}
                  </div>
                ) : null}
              </article>
            )
          })}
        </div>
      ) : null}

      {tab === 'issues' ? (
        <div className="grid gap-4 lg:grid-cols-2">
          {([
            ['Criteria not met', issues.criteria, 'Responses completed but did not satisfy the expected behavior or thresholds.'],
            ['Execution issues', issues.execution, 'Runtime, Tool or platform failures that prevented normal evidence.'],
            ['Inconclusive', issues.inconclusive, 'Evidence could not produce a reliable score.'],
            ['Judge issues', issues.judge, 'The Judge failed after target evidence was preserved.'],
          ] as const).map(([title, values, description]) => (
            <section key={title} className="rounded-xl border border-border/80 bg-background/35 p-4">
              <div className="flex items-start justify-between gap-3"><div><p className="text-sm font-semibold text-white">{title}</p><p className="mt-1 text-xs text-muted">{description}</p></div><Badge variant="outline">{values.length}</Badge></div>
              {values.length ? <div className="mt-3 space-y-2">{values.slice(0, 8).map((trial) => <div key={trial.id} className="rounded-lg border border-border/70 p-3"><p className="text-xs text-white">{trial.case?.name || trial.id}</p><p className="mt-1 text-[10px] text-muted">{userFailureMessage(trial)}</p></div>)}</div> : <p className="mt-4 text-xs text-muted">No items.</p>}
            </section>
          ))}
        </div>
      ) : null}

      {tab === 'estimates' ? (
        <div className="space-y-4">
          <section className="rounded-xl border border-border/80 bg-background/35 p-4">
            <div className="flex flex-wrap items-end gap-3"><label className="min-w-60 flex-1 space-y-2 text-xs text-muted"><span>Operational volume</span><Input type="number" min={1} value={volume} onChange={(event) => setVolume(Math.max(1, Number(event.target.value)))} /></label><Button loading={estimate.isPending} onClick={() => void createEstimate()}><BarChart3 className="mr-2 h-4 w-4" />Create Estimate</Button></div>
          </section>
          {(run.estimates || []).length ? (run.estimates || []).map((item) => (
            <section key={item.id} className="rounded-xl border border-border/80 bg-background/35 p-5">
              <div className="flex items-start justify-between gap-3"><div><p className="text-sm font-semibold text-white">{item.volume.toLocaleString()} {label(item.volume_unit)}</p><p className="mt-1 text-xs text-muted">Sample size {String((item.observation_summary as any)?.sample_size ?? '—')}</p></div><Badge variant="outline">Confidence: {label(item.confidence)}</Badge></div>
              <div className="mt-4 grid gap-3 sm:grid-cols-3">{(['optimistic', 'expected', 'conservative'] as const).map((scenario) => <div key={scenario} className="rounded-lg border border-border/70 p-3"><p className="text-[9px] uppercase text-muted">{scenario}</p><p className="mt-2 text-lg font-semibold text-white">{money(item.scenarios?.[scenario]?.provider_cost_usd)}</p><p className="mt-1 text-[10px] text-muted">{item.scenarios?.[scenario]?.latency_ms_per_run == null ? 'Latency unavailable' : `${Math.round(item.scenarios[scenario].latency_ms_per_run as number)}ms / Run`}</p></div>)}</div>
              {item.limitations?.length ? <div className="mt-4 rounded-lg border border-amber-500/20 bg-amber-500/[0.04] p-3 text-xs text-amber-200">{item.limitations.join(' ')}</div> : null}
            </section>
          )) : <div className="rounded-xl border border-dashed border-border p-10 text-center text-sm text-muted">No operational Estimates created.</div>}
        </div>
      ) : null}

      {tab === 'details' ? (
        <div className="space-y-4">
          <section className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <div className="rounded-xl border border-border/80 bg-background/35 p-4"><Gauge className="h-4 w-4 text-primary-light" /><p className="mt-3 text-[9px] uppercase text-muted">Execution policy</p><p className="mt-1 text-xs text-white">{run.execution_policy?.effective_parallel_pairs || 1} parallel pair(s)</p></div>
            <div className="rounded-xl border border-border/80 bg-background/35 p-4"><FileJson className="h-4 w-4 text-primary-light" /><p className="mt-3 text-[9px] uppercase text-muted">Suite version</p><p className="mt-1 truncate font-mono text-xs text-white">{run.suite_version_id}</p></div>
            <div className="rounded-xl border border-border/80 bg-background/35 p-4"><ShieldCheck className="h-4 w-4 text-primary-light" /><p className="mt-3 text-[9px] uppercase text-muted">Assessment</p><p className="mt-1 text-xs text-white">{assessmentLabel(assessment)}</p></div>
            <div className="rounded-xl border border-border/80 bg-background/35 p-4"><Activity className="h-4 w-4 text-primary-light" /><p className="mt-3 text-[9px] uppercase text-muted">Run ID</p><p className="mt-1 truncate font-mono text-xs text-white">{run.id}</p></div>
          </section>
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
