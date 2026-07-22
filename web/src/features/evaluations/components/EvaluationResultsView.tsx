import { useMemo, useState } from 'react'
import {
  AlertTriangle,
  CheckCircle2,
  ChevronDown,
  ExternalLink,
  RotateCcw,
  XCircle,
} from 'lucide-react'

import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import type { EvaluationRun, EvaluationTrial } from '@/features/evaluations/types'
import { cn } from '@/lib/utils'

type Tab = 'overview' | 'cases' | 'failures' | 'technical'

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
  return value.split('_').map((item) => item.charAt(0).toUpperCase() + item.slice(1)).join(' ')
}

function average(values: Array<number | null | undefined>) {
  const usable = values.filter((value): value is number => typeof value === 'number')
  if (!usable.length) return null
  return usable.reduce((total, value) => total + value, 0) / usable.length
}

function trialCaseKey(trial: EvaluationTrial) {
  return trial.case?.id || trial.case?.name || trial.pair_key.split(':')[0]
}

function userFailureMessage(trial: EvaluationTrial) {
  if (trial.failure_code === 'judge_failed' || trial.failure_detail?.includes('judge_output_length_limit')) {
    return 'Judge could not complete the structured score. The Agent response is preserved.'
  }
  if (trial.failure_code === 'judge_output_length_limit') {
    return 'Judge exhausted its output budget. The Agent response is preserved.'
  }
  if (trial.failure_code) return label(trial.failure_code)
  return label(trial.status)
}

export function EvaluationResultsView({ run, retrying, onRetryJudgments }: Props) {
  const [tab, setTab] = useState<Tab>('overview')
  const [expandedCase, setExpandedCase] = useState<string | null>(null)
  const trials = run.trials || []
  const grouped = useMemo(() => {
    const map = new Map<string, EvaluationTrial[]>()
    for (const trial of trials) {
      const key = trialCaseKey(trial)
      map.set(key, [...(map.get(key) || []), trial])
    }
    return [...map.entries()].map(([key, items]) => ({ key, items }))
  }, [trials])
  const failureGroups = useMemo(() => {
    const map = new Map<string, EvaluationTrial[]>()
    for (const trial of trials) {
      if (!trial.failure_code && trial.status !== 'failed' && trial.status !== 'inconclusive') continue
      const key = trial.failure_code || trial.status
      map.set(key, [...(map.get(key) || []), trial])
    }
    return [...map.entries()].sort((a, b) => b[1].length - a[1].length)
  }, [trials])
  const sideStats = useMemo(() => run.targets.map((target) => {
    const values = trials.filter((trial) => trial.target_id === target.id)
    const passed = values.filter((trial) => trial.passed === true).length
    return {
      target,
      score: average(values.map((trial) => trial.score)),
      passRate: values.length ? passed / values.length * 100 : null,
      latency: average(values.map((trial) => Number(trial.metrics?.latency_ms ?? NaN)).filter(Number.isFinite)),
      cost: values.reduce((total, trial) => total + Number(trial.metrics?.cost_usd || 0), 0),
    }
  }), [run.targets, trials])
  const judgeFailures = trials.filter((trial) => (
    trial.failure_code === 'judge_failed'
    || trial.failure_code === 'judge_output_length_limit'
    || trial.failure_detail?.includes('judge_output_length_limit')
  )).length

  const tabs: Array<{ value: Tab; label: string }> = [
    { value: 'overview', label: 'Overview' },
    { value: 'cases', label: `Cases (${grouped.length})` },
    { value: 'failures', label: `Failures (${failureGroups.reduce((total, item) => total + item[1].length, 0)})` },
    { value: 'technical', label: 'Technical' },
  ]

  return (
    <div className="mx-auto max-w-5xl space-y-5">
      <section className="rounded-2xl border border-border/80 bg-background/40 p-5">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <Badge variant="outline">{label(run.qualification_status || run.status)}</Badge>
              <Badge variant="outline">{run.mode === 'comparison' ? 'Comparison' : 'Single target'}</Badge>
            </div>
            <h3 className="mt-3 text-base font-semibold text-white">Evaluation results</h3>
            <p className="mt-1 text-xs text-muted">{run.repetitions} Runs per Test Case · immutable target snapshots</p>
          </div>
          <div className="grid grid-cols-3 gap-5 text-right">
            <div><p className="text-[9px] uppercase text-muted">Score</p><p className="mt-1 text-lg font-semibold text-white">{score(run.overall_score)}</p></div>
            <div><p className="text-[9px] uppercase text-muted">Pass rate</p><p className="mt-1 text-lg font-semibold text-white">{run.pass_rate == null ? '—' : `${run.pass_rate.toFixed(1)}%`}</p></div>
            <div><p className="text-[9px] uppercase text-muted">Cost</p><p className="mt-1 text-lg font-semibold text-white">{money(run.measured_total_cost)}</p></div>
          </div>
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
              tab === item.value ? 'bg-primary/15 text-primary-light' : 'text-muted hover:text-white',
            )}
          >
            {item.label}
          </button>
        ))}
      </div>

      {tab === 'overview' ? (
        <div className="space-y-4">
          <section className="grid gap-3 md:grid-cols-2">
            {sideStats.map(({ target, score: targetScore, passRate, latency, cost }) => (
              <article key={target.id} className="rounded-xl border border-border/80 bg-background/35 p-5">
                <div className="flex items-start justify-between gap-3">
                  <div><p className="text-sm font-semibold text-white">{target.display_version}</p><p className="mt-1 text-[10px] text-muted">{target.side} · {target.environment}</p></div>
                  <Badge variant="outline">{target.side}</Badge>
                </div>
                <div className="mt-5 grid grid-cols-4 gap-3 border-t border-border pt-4">
                  <div><p className="text-[9px] uppercase text-muted">Score</p><p className="mt-1 text-sm text-white">{score(targetScore)}</p></div>
                  <div><p className="text-[9px] uppercase text-muted">Pass</p><p className="mt-1 text-sm text-white">{passRate == null ? '—' : `${passRate.toFixed(0)}%`}</p></div>
                  <div><p className="text-[9px] uppercase text-muted">Latency</p><p className="mt-1 text-sm text-white">{latency == null ? '—' : `${Math.round(latency)}ms`}</p></div>
                  <div><p className="text-[9px] uppercase text-muted">Cost</p><p className="mt-1 text-sm text-white">{money(cost)}</p></div>
                </div>
              </article>
            ))}
          </section>
          <section className="grid gap-3 sm:grid-cols-3">
            <div className="rounded-xl border border-border/80 bg-background/35 p-4"><p className="text-[10px] uppercase text-muted">Passed Trials</p><p className="mt-2 text-xl font-semibold text-white">{trials.filter((trial) => trial.passed === true).length}</p></div>
            <div className="rounded-xl border border-border/80 bg-background/35 p-4"><p className="text-[10px] uppercase text-muted">Inconclusive</p><p className="mt-2 text-xl font-semibold text-white">{trials.filter((trial) => trial.status === 'inconclusive').length}</p></div>
            <div className="rounded-xl border border-border/80 bg-background/35 p-4"><p className="text-[10px] uppercase text-muted">Judge attention</p><p className="mt-2 text-xl font-semibold text-white">{judgeFailures}</p></div>
          </section>
          {judgeFailures > 0 && onRetryJudgments ? (
            <section className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-amber-500/25 bg-amber-500/[0.05] p-4">
              <div><p className="text-sm font-semibold text-white">{judgeFailures} judgments can be retried</p><p className="mt-1 text-xs text-amber-200/80">Agent Runs, Tools and RAG evidence will not be executed again.</p></div>
              <Button variant="outline" loading={retrying} onClick={onRetryJudgments}><RotateCcw className="mr-2 h-4 w-4" />Retry judgments</Button>
            </section>
          ) : null}
        </div>
      ) : null}

      {tab === 'cases' ? (
        <div className="space-y-2">
          {grouped.map(({ key, items }) => {
            const passed = items.filter((trial) => trial.passed === true).length
            const caseScore = average(items.map((trial) => trial.score))
            const open = expandedCase === key
            return (
              <article key={key} className="overflow-hidden rounded-xl border border-border/80 bg-background/35">
                <button type="button" onClick={() => setExpandedCase(open ? null : key)} className="flex w-full items-center gap-4 p-4 text-left">
                  {passed === items.length ? <CheckCircle2 className="h-4 w-4 text-emerald-300" /> : passed === 0 ? <XCircle className="h-4 w-4 text-red-300" /> : <AlertTriangle className="h-4 w-4 text-amber-300" />}
                  <div className="min-w-0 flex-1"><p className="truncate text-sm font-medium text-white">{items[0]?.case?.name || key}</p><p className="mt-1 text-[10px] text-muted">{passed}/{items.length} passed · {label(items[0]?.case?.case_type || 'success')}</p></div>
                  <p className="text-sm font-semibold text-white">{score(caseScore)}</p>
                  <ChevronDown className={cn('h-4 w-4 text-muted transition-transform', open && 'rotate-180')} />
                </button>
                {open ? (
                  <div className="space-y-2 border-t border-border p-3">
                    {items.map((trial) => (
                      <div key={trial.id} className="flex flex-wrap items-center gap-3 rounded-lg border border-border/70 bg-surface/20 px-3 py-2 text-xs">
                        <Badge variant="outline">{trial.side}</Badge>
                        <span className="text-muted">Run {trial.repetition}</span>
                        <span className="text-white">Score {score(trial.score)}</span>
                        <span className="flex-1 text-muted">{trial.failure_code ? userFailureMessage(trial) : label(trial.status)}</span>
                        {trial.execution_reference?.kind === 'agent_trace' ? (
                          <a href={`/traces/${trial.execution_reference.trace_id}`} className="flex items-center gap-1 text-primary-light"><ExternalLink className="h-3 w-3" />Trace</a>
                        ) : trial.execution_reference?.kind === 'network_execution' && trial.execution_reference.trace_id ? (
                          <a href={`/traces/${trial.execution_reference.trace_id}`} className="flex items-center gap-1 text-primary-light"><ExternalLink className="h-3 w-3" />Trace</a>
                        ) : null}
                      </div>
                    ))}
                  </div>
                ) : null}
              </article>
            )
          })}
        </div>
      ) : null}

      {tab === 'failures' ? (
        <div className="space-y-3">
          {failureGroups.length ? failureGroups.map(([key, items]) => (
            <section key={key} className="rounded-xl border border-border/80 bg-background/35 p-4">
              <div className="flex items-center justify-between gap-3"><div><p className="text-sm font-semibold text-white">{label(key)}</p><p className="mt-1 text-xs text-muted">{userFailureMessage(items[0])}</p></div><Badge variant="outline">{items.length}</Badge></div>
            </section>
          )) : <div className="rounded-xl border border-dashed border-border p-10 text-center text-sm text-muted">No failed or inconclusive Trials.</div>}
        </div>
      ) : null}

      {tab === 'technical' ? (
        <div className="space-y-3">
          <section className="rounded-xl border border-border/80 bg-background/35 p-4">
            <h4 className="text-sm font-semibold text-white">Execution metadata</h4>
            <pre className="mt-3 max-h-64 overflow-auto whitespace-pre-wrap break-all rounded-lg bg-background p-3 text-[10px] leading-4 text-muted">{JSON.stringify({ id: run.id, execution_policy: run.execution_policy, targets: run.targets, aggregate_result: run.aggregate_result }, null, 2)}</pre>
          </section>
          {trials.filter((trial) => trial.failure_detail).map((trial) => (
            <details key={trial.id} className="rounded-xl border border-border/80 bg-background/35 p-4">
              <summary className="cursor-pointer text-xs font-medium text-white">{trial.case?.name || trial.id} · {trial.failure_code || trial.status}</summary>
              <pre className="mt-3 whitespace-pre-wrap break-all text-[10px] leading-4 text-muted">{trial.failure_detail}</pre>
            </details>
          ))}
        </div>
      ) : null}
    </div>
  )
}
