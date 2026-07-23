import { useMemo, useState } from 'react'
import {
  AlertTriangle,
  CheckCircle2,
  ChevronDown,
  GitCompareArrows,
  Minus,
  ShieldCheck,
  Trophy,
} from 'lucide-react'
import { toast } from 'sonner'

import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { JsonCodeBlock } from '@/components/ui/JsonCodeBlock'
import { useDecideEvaluationComparison } from '@/features/evaluations/catalogHooks'
import type {
  ComparisonSideSummary,
  ComparisonWinnerKpi,
  EvaluationComparison,
  EvaluationComparisonCase,
} from '@/features/evaluations/catalogTypes'
import type { EvaluationTrial } from '@/features/evaluations/types'
import { cn } from '@/lib/utils'

type Tab = 'overview' | 'cases' | 'attention' | 'decision' | 'technical'

function score(value?: number | null) {
  return value == null ? '—' : value.toFixed(1)
}

function percentage(value?: number | null) {
  return value == null ? '—' : `${value.toFixed(1)}%`
}

function money(value?: number | null) {
  return value == null ? '—' : `$${value.toFixed(value < 0.01 ? 4 : 2)}`
}

function delta(value?: number | null, suffix = '') {
  if (value == null) return '—'
  return `${value > 0 ? '+' : ''}${value.toFixed(1)}${suffix}`
}

function label(value: string) {
  return value
    .replaceAll('_', ' ')
    .replace(/\b\w/g, (char) => char.toUpperCase())
}

function Winner({ value }: { value: EvaluationComparisonCase['winner'] }) {
  if (value === 'candidate') return <span className="text-emerald-300">Candidate</span>
  if (value === 'reference') return <span className="text-amber-300">Reference</span>
  if (value === 'tie') return <span className="text-muted">Tie</span>
  return <span className="text-muted">Unavailable</span>
}

function KpiWinner({ value }: { value: ComparisonWinnerKpi['winner'] }) {
  if (value === 'candidate') return <Badge variant="outline" className="border-emerald-500/30 text-emerald-300">Candidate</Badge>
  if (value === 'reference') return <Badge variant="outline" className="border-amber-500/30 text-amber-300">Reference</Badge>
  if (value === 'tie') return <Badge variant="outline">Tie</Badge>
  return <Badge variant="outline">Unavailable</Badge>
}

function kpiValue(item: ComparisonWinnerKpi, side: 'candidate' | 'reference') {
  const value = item[side]
  if (value == null) return '—'
  if (item.key.includes('cost')) return money(value)
  if (item.key.includes('latency')) return `${Math.round(value)}ms`
  if (item.key.includes('rate')) return percentage(value)
  return value.toFixed(1)
}

function SideCard({ title, side }: { title: string; side: ComparisonSideSummary }) {
  return (
    <section className="rounded-xl border border-border/80 bg-background/35 p-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-[9px] uppercase tracking-wide text-muted">{title}</p>
          <h4 className="mt-2 text-sm font-semibold text-white">
            {side.target?.display_name} · {side.target?.display_version}
          </h4>
          <p className="mt-1 text-[10px] text-muted">
            {side.target?.environment} · Snapshot {side.target?.snapshot_hash.slice(0, 12)}…
          </p>
        </div>
        <Badge variant="outline">Revision {side.run.evidence_revision}</Badge>
      </div>
      <div className="mt-4 grid grid-cols-2 gap-3 text-xs sm:grid-cols-4">
        <div><p className="text-[9px] uppercase text-muted">Score</p><p className="mt-1 font-semibold text-white">{score(side.kpis?.quality_score ?? side.summary?.weighted_score)}</p></div>
        <div><p className="text-[9px] uppercase text-muted">Pass</p><p className="mt-1 font-semibold text-white">{percentage(side.kpis?.pass_rate ?? side.summary?.weighted_pass_rate)}</p></div>
        <div><p className="text-[9px] uppercase text-muted">Runtime cost</p><p className="mt-1 font-semibold text-white">{money(side.kpis?.runtime_cost_usd_total ?? side.runtime.runtime_cost_usd)}</p></div>
        <div><p className="text-[9px] uppercase text-muted">Median latency</p><p className="mt-1 font-semibold text-white">{(side.kpis?.latency_median_ms ?? side.runtime.latency_median_ms) == null ? '—' : `${Math.round(Number(side.kpis?.latency_median_ms ?? side.runtime.latency_median_ms))}ms`}</p></div>
      </div>
      {side.failures.primary ? (
        <div className="mt-4 rounded-lg border border-amber-500/20 bg-amber-500/[0.04] p-3">
          <p className="text-xs font-medium text-amber-200">
            {side.failures.primary.count} × {side.failures.primary.code}
          </p>
          <p className="mt-1 text-[10px] leading-4 text-muted">
            {side.failures.primary.recommended_action}
          </p>
        </div>
      ) : null}
    </section>
  )
}

function latestTrial(trials: EvaluationTrial[], caseId: string) {
  const values = trials.filter((trial) => trial.case?.id === caseId)
  return values.length ? values[values.length - 1] : null
}

function TrialEvidence({ title, trial }: { title: string; trial: EvaluationTrial | null }) {
  if (!trial) {
    return (
      <section className="rounded-xl border border-dashed border-border p-4 text-xs text-muted">
        {title} evidence is unavailable for this Test Case.
      </section>
    )
  }
  return (
    <section className="space-y-3 rounded-xl border border-border/80 bg-background/30 p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <p className="text-[9px] uppercase tracking-wide text-muted">{title}</p>
          <p className="mt-1 text-xs font-semibold text-white">
            {trial.passed == null ? 'Inconclusive' : trial.passed ? 'Passed' : 'Criteria not met'}
          </p>
        </div>
        <div className="flex items-center gap-2">
          {trial.interaction_mode === 'session' ? <Badge variant="outline">Session · {trial.turns?.length || 0} turns</Badge> : null}
          <Badge variant="outline">Score {score(trial.score)}</Badge>
          <Badge variant="outline">Repetition {trial.repetition}</Badge>
        </div>
      </div>
      {trial.interaction_mode === 'session' ? (
        <JsonCodeBlock title={`${title} session transcript`} value={trial.turns || trial.output?.transcript || []} maxHeight={300} />
      ) : (
        <JsonCodeBlock title={`${title} output`} value={trial.output} maxHeight={240} />
      )}
      <div className="grid gap-3 sm:grid-cols-2">
        <JsonCodeBlock title="Deterministic and Judge checks" value={trial.checks || []} maxHeight={220} />
        <JsonCodeBlock
          title="Failure and execution references"
          value={{
            status: trial.status,
            failure_code: trial.failure_code,
            failure_detail: trial.failure_detail,
            metrics: trial.metrics,
            trace_id: trial.trace_id,
            agent_run_id: trial.agent_run_id,
            network_execution_id: trial.network_execution_id,
          }}
          maxHeight={220}
        />
      </div>
    </section>
  )
}

export function EvaluationComparisonView({
  projectId,
  comparison,
}: {
  projectId: string
  comparison: EvaluationComparison
}) {
  const [tab, setTab] = useState<Tab>('overview')
  const [note, setNote] = useState('')
  const [expandedCaseId, setExpandedCaseId] = useState<string | null>(null)
  const decide = useDecideEvaluationComparison(projectId, comparison.id)
  const aggregate = comparison.aggregate_result
  const candidate = aggregate?.candidate
  const reference = aggregate?.reference
  const cases = aggregate?.cases || []
  const candidateTrials = comparison.candidate_run?.trials || []
  const referenceTrials = comparison.reference_run?.trials || []
  const unavailableCases = useMemo(
    () => cases.filter((item) => item.winner == null),
    [cases],
  )
  const ready = comparison.status === 'ready' && Boolean(aggregate?.comparison_available)
  const calculatedWinner = aggregate?.winner

  const submit = async (
    decision: 'select_candidate' | 'keep_reference' | 'no_preference',
    override = false,
  ) => {
    if (override && !note.trim()) {
      toast.error('Manual override requires a decision note')
      return
    }
    try {
      await decide.mutateAsync({
        decision,
        decision_basis: override ? 'manual_override' : 'evidence',
        note: note.trim() || undefined,
      })
      toast.success('Operational decision saved for these exact evidence revisions')
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Unable to save decision')
    }
  }

  const tabs: Array<{ value: Tab; label: string }> = [
    { value: 'overview', label: 'Overview' },
    { value: 'cases', label: `Cases (${cases.length})` },
    { value: 'attention', label: `Attention (${unavailableCases.length})` },
    { value: 'decision', label: 'Operational decision' },
    { value: 'technical', label: 'Technical' },
  ]

  const failureSides: Array<{ title: string; side?: ComparisonSideSummary }> = [
    { title: 'Candidate', side: candidate },
    { title: 'Reference', side: reference },
  ]

  return (
    <div className="space-y-4">
      <section className="rounded-2xl border border-border/80 bg-background/30 p-4">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <Badge variant="outline">{comparison.comparison_mode === 'paired' ? 'Paired Comparison' : 'Post-hoc Comparison'}</Badge>
              <Badge variant="outline">{comparison.status}</Badge>
              <Badge variant="outline">Immutable evidence pair</Badge>
              {calculatedWinner ? <Badge variant="outline">Winner: {calculatedWinner.side ? label(calculatedWinner.side) : 'Unavailable'}</Badge> : null}
            </div>
            <h3 className="mt-3 flex items-center gap-2 text-base font-semibold text-white">
              <GitCompareArrows className="h-4 w-4 text-primary-light" />Evaluation Comparison
            </h3>
            <p className="mt-1 text-[11px] text-muted">
              Candidate revision {comparison.candidate_evidence_revision} versus Reference revision {comparison.reference_evidence_revision}.
            </p>
          </div>
          {aggregate?.case_outcomes ? (
            <div className="grid grid-cols-3 gap-5 text-right text-xs">
              <div><p className="text-[9px] uppercase text-muted">Candidate wins</p><p className="mt-1 text-lg font-semibold text-emerald-300">{aggregate.case_outcomes.candidate_wins}</p></div>
              <div><p className="text-[9px] uppercase text-muted">Reference wins</p><p className="mt-1 text-lg font-semibold text-amber-300">{aggregate.case_outcomes.reference_wins}</p></div>
              <div><p className="text-[9px] uppercase text-muted">Ties</p><p className="mt-1 text-lg font-semibold text-white">{aggregate.case_outcomes.ties}</p></div>
            </div>
          ) : null}
        </div>
      </section>

      {!ready ? (
        <section className="flex items-start gap-3 rounded-xl border border-amber-500/25 bg-amber-500/[0.05] p-4">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-amber-300" />
          <div>
            <p className="text-sm font-semibold text-white">Comparison result unavailable</p>
            <p className="mt-1 text-xs leading-5 text-amber-100/75">
              {comparison.failure_detail || 'The independent Evaluation Runs are still processing or lack conclusive Judge evidence.'}
            </p>
            <p className="mt-2 text-[10px] text-muted">
              Candidate and Reference outputs remain independent and can be retried without rerunning the other side.
            </p>
          </div>
        </section>
      ) : null}

      <div className="flex gap-1 rounded-xl border border-border bg-background/35 p-1">
        {tabs.map((item) => (
          <button
            key={item.value}
            type="button"
            onClick={() => setTab(item.value)}
            className={cn(
              'rounded-lg px-3 py-2 text-xs font-medium',
              tab === item.value ? 'bg-primary/15 text-primary-light' : 'text-muted hover:text-white',
            )}
          >
            {item.label}
          </button>
        ))}
      </div>

      {tab === 'overview' ? (
        <div className="space-y-4">
          {calculatedWinner ? (
            <section className="rounded-xl border border-primary/25 bg-primary/[0.035] p-4">
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div>
                  <p className="flex items-center gap-2 text-[9px] uppercase tracking-wide text-muted"><Trophy className="h-3.5 w-3.5 text-primary-light" />Calculated KPI winner</p>
                  <p className="mt-2 text-xl font-semibold text-white">
                    {calculatedWinner.side ? label(calculatedWinner.side) : 'Unavailable'}
                  </p>
                  <p className="mt-1 text-[11px] text-muted">
                    {calculatedWinner.authoritative ? 'Authoritative · same protocol and repetition count' : 'Indicative · evidence is comparable but not fully symmetric'}
                  </p>
                </div>
                <div className="grid grid-cols-2 gap-5 text-right text-xs">
                  <div><p className="text-[9px] uppercase text-muted">Candidate KPI score</p><p className="mt-1 text-lg font-semibold text-emerald-300">{calculatedWinner.candidate_score == null ? '—' : percentage(calculatedWinner.candidate_score * 100)}</p></div>
                  <div><p className="text-[9px] uppercase text-muted">Reference KPI score</p><p className="mt-1 text-lg font-semibold text-amber-300">{calculatedWinner.reference_score == null ? '—' : percentage(calculatedWinner.reference_score * 100)}</p></div>
                </div>
              </div>
            </section>
          ) : null}

          {candidate && reference ? (
            <div className="grid gap-4 xl:grid-cols-2">
              <SideCard title="Candidate Evaluation" side={candidate} />
              <SideCard title="Reference Evaluation" side={reference} />
            </div>
          ) : null}

          {calculatedWinner?.kpis?.length ? (
            <section className="overflow-hidden rounded-xl border border-border/80 bg-background/30">
              <div className="grid grid-cols-[minmax(180px,1fr)_110px_120px_120px_100px] border-b border-border px-4 py-3 text-[9px] uppercase text-muted">
                <span>KPI</span><span>Direction</span><span>Candidate</span><span>Reference</span><span>Winner</span>
              </div>
              {calculatedWinner.kpis.map((item) => (
                <div key={item.key} className="grid grid-cols-[minmax(180px,1fr)_110px_120px_120px_100px] items-center border-b border-border/70 px-4 py-3 text-xs last:border-b-0">
                  <span className="text-white">{label(item.key)} <span className="ml-1 text-[9px] text-muted">{Math.round(item.weight * 100)}%</span></span>
                  <span className="text-muted">{item.direction === 'maximize' ? 'Higher wins' : 'Lower wins'}</span>
                  <span className={item.winner === 'candidate' ? 'font-medium text-emerald-300' : 'text-slate-200'}>{kpiValue(item, 'candidate')}</span>
                  <span className={item.winner === 'reference' ? 'font-medium text-amber-300' : 'text-slate-200'}>{kpiValue(item, 'reference')}</span>
                  <KpiWinner value={item.winner} />
                </div>
              ))}
            </section>
          ) : (
            <section className="overflow-hidden rounded-xl border border-border/80 bg-background/30">
              <div className="grid grid-cols-[minmax(180px,1fr)_120px_120px_120px] border-b border-border px-4 py-3 text-[9px] uppercase text-muted">
                <span>Metric</span><span>Candidate</span><span>Reference</span><span>Delta</span>
              </div>
              {[
                ['Weighted score', candidate?.summary?.weighted_score, reference?.summary?.weighted_score, aggregate?.delta?.score, ''],
                ['Weighted pass', candidate?.summary?.weighted_pass_rate, reference?.summary?.weighted_pass_rate, aggregate?.delta?.pass_rate_percentage_points, ' pp'],
                ['Runtime cost', candidate?.runtime.runtime_cost_usd, reference?.runtime.runtime_cost_usd, aggregate?.delta?.runtime_cost_usd, '$'],
                ['Median latency', candidate?.runtime.latency_median_ms, reference?.runtime.latency_median_ms, aggregate?.delta?.latency_median_ms, 'ms'],
              ].map(([name, candidateValue, referenceValue, deltaValue, suffix]) => (
                <div key={String(name)} className="grid grid-cols-[minmax(180px,1fr)_120px_120px_120px] border-b border-border/70 px-4 py-3 text-xs last:border-b-0">
                  <span className="text-white">{name}</span>
                  <span className="text-slate-200">{candidateValue == null ? '—' : Number(candidateValue).toFixed(name === 'Runtime cost' ? 4 : 1)}</span>
                  <span className="text-slate-200">{referenceValue == null ? '—' : Number(referenceValue).toFixed(name === 'Runtime cost' ? 4 : 1)}</span>
                  <span className="flex items-center gap-1 text-slate-200"><Minus className="h-3 w-3 text-muted" />{deltaValue == null ? '—' : `${name === 'Runtime cost' ? '$' : ''}${delta(Number(deltaValue), suffix === '$' ? '' : String(suffix))}`}</span>
                </div>
              ))}
            </section>
          )}
        </div>
      ) : null}

      {tab === 'cases' ? (
        <section className="overflow-hidden rounded-xl border border-border/80 bg-background/30">
          <div className="grid grid-cols-[minmax(220px,1fr)_120px_120px_100px_100px_32px] border-b border-border px-4 py-3 text-[9px] uppercase tracking-wide text-muted">
            <span>Test Case</span><span>Candidate</span><span>Reference</span><span>Delta</span><span>Result</span><span />
          </div>
          {cases.map((item) => {
            const expanded = expandedCaseId === item.test_case_id
            const candidateTrial = latestTrial(candidateTrials, item.test_case_id)
            const referenceTrial = latestTrial(referenceTrials, item.test_case_id)
            return (
              <article key={item.test_case_id} className="border-b border-border/70 last:border-b-0">
                <button
                  type="button"
                  onClick={() => setExpandedCaseId(expanded ? null : item.test_case_id)}
                  className="grid w-full grid-cols-[minmax(220px,1fr)_120px_120px_100px_100px_32px] items-center px-4 py-3 text-left text-xs hover:bg-surface/20"
                >
                  <div><p className="font-medium text-white">{item.name}</p><p className="mt-1 text-[10px] text-muted">{item.case_type}</p></div>
                  <div><p className="text-white">{score(item.candidate.score)}</p><p className="mt-1 text-[10px] text-muted">{item.candidate.passed}/{item.candidate.total} passed</p></div>
                  <div><p className="text-white">{score(item.reference.score)}</p><p className="mt-1 text-[10px] text-muted">{item.reference.passed}/{item.reference.total} passed</p></div>
                  <span className="text-white">{delta(item.score_delta)}</span>
                  <Winner value={item.winner} />
                  <ChevronDown className={cn('h-4 w-4 text-muted transition-transform', expanded && 'rotate-180')} />
                </button>
                {expanded ? (
                  <div className="space-y-4 border-t border-border/70 bg-surface/10 p-4">
                    <JsonCodeBlock
                      title="Expected Run Contract"
                      value={candidateTrial?.case?.expected_contract || referenceTrial?.case?.expected_contract}
                      maxHeight={240}
                    />
                    <div className="grid gap-4 xl:grid-cols-2">
                      <TrialEvidence title="Candidate" trial={candidateTrial} />
                      <TrialEvidence title="Reference" trial={referenceTrial} />
                    </div>
                  </div>
                ) : null}
              </article>
            )
          })}
        </section>
      ) : null}

      {tab === 'attention' ? (
        <div className="grid gap-4 xl:grid-cols-2">
          {failureSides.map(({ title, side }) => (
            <section key={title} className="rounded-xl border border-border/80 bg-background/30 p-4">
              <h4 className="text-sm font-semibold text-white">{title} failures</h4>
              <div className="mt-3 space-y-2">
                {side?.failures.groups.length
                  ? side.failures.groups.map((group) => (
                    <div key={group.code} className="rounded-lg border border-border/70 p-3">
                      <div className="flex items-center justify-between gap-2">
                        <p className="text-xs font-medium text-white">{group.code}</p>
                        <Badge variant="outline">{group.count}</Badge>
                      </div>
                      <p className="mt-2 text-[10px] leading-4 text-muted">{group.summary}</p>
                      <p className="mt-2 text-[10px] text-primary-light">{group.recommended_action}</p>
                    </div>
                  ))
                  : <p className="text-xs text-muted">No operational failures.</p>}
              </div>
            </section>
          ))}
        </div>
      ) : null}

      {tab === 'decision' ? (
        <section className="rounded-xl border border-border/80 bg-background/30 p-4">
          <div className="flex items-start justify-between gap-3">
            <div>
              <h4 className="flex items-center gap-2 text-sm font-semibold text-white"><ShieldCheck className="h-4 w-4 text-primary-light" />Operational decision</h4>
              <p className="mt-1 text-[11px] text-muted">
                The calculated Winner above is evidence. This optional decision records what the operator chose to do and may explicitly override that Winner without rewriting either Evaluation.
              </p>
            </div>
            <Badge variant="outline">{comparison.decision?.decision || 'Pending'}</Badge>
          </div>
          <textarea
            value={note}
            onChange={(event) => setNote(event.target.value)}
            placeholder={ready ? 'Optional decision note' : 'Required justification for manual override'}
            className="mt-4 min-h-24 w-full rounded-lg border border-border bg-background px-3 py-2 text-xs text-white outline-none"
          />
          <div className="mt-3 flex flex-wrap justify-end gap-2">
            <Button variant="outline" loading={decide.isPending} onClick={() => void submit('no_preference', !ready)}>No preference</Button>
            <Button variant="outline" loading={decide.isPending} onClick={() => void submit('keep_reference', !ready)}>Keep Reference</Button>
            <Button loading={decide.isPending} onClick={() => void submit('select_candidate', !ready)}><CheckCircle2 className="mr-2 h-4 w-4" />Select Candidate</Button>
          </div>
        </section>
      ) : null}

      {tab === 'technical' ? (
        <JsonCodeBlock title="Comparison evidence contract" value={comparison} maxHeight={520} />
      ) : null}
    </div>
  )
}
