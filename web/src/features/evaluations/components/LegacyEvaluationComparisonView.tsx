import { useMemo, useState } from 'react'
import { AlertTriangle, ChevronDown, GitCompareArrows } from 'lucide-react'

import { Badge } from '@/components/ui/Badge'
import { JsonCodeBlock } from '@/components/ui/JsonCodeBlock'
import type { EvidenceRichRun } from '@/features/evaluations/catalogTypes'
import type { EvaluationTarget, EvaluationTrial } from '@/features/evaluations/types'
import { cn } from '@/lib/utils'

function score(value?: number | null) {
  return value == null ? '—' : value.toFixed(1)
}

function targetFor(run: EvidenceRichRun, side: 'candidate' | 'baseline') {
  return run.targets.find((target) => target.side === side) || null
}

function summaryFor(run: EvidenceRichRun, target: EvaluationTarget | null) {
  const summaries = run.aggregate_result?.target_summaries
  return Array.isArray(summaries)
    ? summaries.find((item: any) => String(item?.target_id) === target?.id) || null
    : null
}

function latestTrial(
  values: EvaluationTrial[],
  targetId: string | undefined,
  caseId: string,
) {
  const matches = values.filter(
    (trial) => trial.target_id === targetId && trial.case?.id === caseId,
  )
  return matches.length ? matches[matches.length - 1] : null
}

export function LegacyEvaluationComparisonView({ run }: { run: EvidenceRichRun }) {
  const [expandedCase, setExpandedCase] = useState<string | null>(null)
  const candidate = targetFor(run, 'candidate')
  const reference = targetFor(run, 'baseline')
  const candidateSummary = summaryFor(run, candidate)
  const referenceSummary = summaryFor(run, reference)
  const trials = run.trials || []
  const cases = useMemo(() => {
    const map = new Map<string, { id: string; name: string; type?: string }>()
    for (const trial of trials) {
      if (!trial.case) continue
      map.set(trial.case.id, {
        id: trial.case.id,
        name: trial.case.name,
        type: trial.case.case_type,
      })
    }
    return [...map.values()]
  }, [trials])

  return (
    <div className="space-y-4">
      <section className="rounded-2xl border border-amber-500/25 bg-amber-500/[0.035] p-4">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <Badge variant="outline">Legacy paired comparison</Badge>
              <Badge variant="outline">Read only</Badge>
              <Badge variant="outline">Single historical Run</Badge>
            </div>
            <h3 className="mt-3 flex items-center gap-2 text-base font-semibold text-white">
              <GitCompareArrows className="h-4 w-4 text-amber-300" />Historical Comparison evidence
            </h3>
            <p className="mt-1 max-w-3xl text-xs leading-5 text-muted">
              This record predates independent Evaluation Runs. Candidate and Baseline evidence is displayed separately, but new retries or decisions should use the Evaluation catalog.
            </p>
          </div>
          {run.failure_summary?.primary ? (
            <div className="max-w-sm rounded-lg border border-amber-500/20 bg-background/30 p-3">
              <p className="text-xs font-medium text-amber-200">{run.failure_summary.primary.count} × {run.failure_summary.primary.code}</p>
              <p className="mt-1 text-[10px] text-muted">{run.failure_summary.primary.recommended_action}</p>
            </div>
          ) : null}
        </div>
      </section>

      <div className="grid gap-4 xl:grid-cols-2">
        {[
          ['Candidate', candidate, candidateSummary],
          ['Reference', reference, referenceSummary],
        ].map(([title, target, summary]) => (
          <section key={String(title)} className="rounded-xl border border-border/80 bg-background/35 p-4">
            <p className="text-[9px] uppercase text-muted">{String(title)}</p>
            <h4 className="mt-2 text-sm font-semibold text-white">
              {(target as EvaluationTarget | null)?.display_name} · {(target as EvaluationTarget | null)?.display_version}
            </h4>
            <p className="mt-1 text-[10px] text-muted">
              {(target as EvaluationTarget | null)?.environment} · Snapshot {(target as EvaluationTarget | null)?.snapshot_hash.slice(0, 12)}…
            </p>
            <div className="mt-4 grid grid-cols-2 gap-3 text-xs">
              <div><p className="text-[9px] uppercase text-muted">Weighted score</p><p className="mt-1 font-semibold text-white">{score((summary as any)?.weighted_score)}</p></div>
              <div><p className="text-[9px] uppercase text-muted">Weighted pass</p><p className="mt-1 font-semibold text-white">{(summary as any)?.weighted_pass_rate == null ? '—' : `${Number((summary as any).weighted_pass_rate).toFixed(1)}%`}</p></div>
            </div>
          </section>
        ))}
      </div>

      {run.evidence_status === 'unavailable' ? (
        <section className="flex items-start gap-3 rounded-xl border border-amber-500/25 bg-amber-500/[0.04] p-4">
          <AlertTriangle className="mt-0.5 h-4 w-4 text-amber-300" />
          <div><p className="text-sm font-semibold text-white">No semantic winner can be calculated</p><p className="mt-1 text-xs text-muted">Target outputs may be preserved, but Judge evidence is unavailable. Candidate and Reference remain individually inspectable below.</p></div>
        </section>
      ) : null}

      <section className="overflow-hidden rounded-xl border border-border/80 bg-background/30">
        <div className="grid grid-cols-[minmax(220px,1fr)_120px_120px_32px] border-b border-border px-4 py-3 text-[9px] uppercase text-muted">
          <span>Test Case</span><span>Candidate</span><span>Reference</span><span />
        </div>
        {cases.map((item) => {
          const candidateTrial = latestTrial(trials, candidate?.id, item.id)
          const referenceTrial = latestTrial(trials, reference?.id, item.id)
          const open = expandedCase === item.id
          return (
            <article key={item.id} className="border-b border-border/70 last:border-b-0">
              <button
                type="button"
                onClick={() => setExpandedCase(open ? null : item.id)}
                className="grid w-full grid-cols-[minmax(220px,1fr)_120px_120px_32px] items-center px-4 py-3 text-left text-xs hover:bg-surface/20"
              >
                <div><p className="font-medium text-white">{item.name}</p><p className="mt-1 text-[10px] text-muted">{item.type}</p></div>
                <span className="text-white">{score(candidateTrial?.score)}</span>
                <span className="text-white">{score(referenceTrial?.score)}</span>
                <ChevronDown className={cn('h-4 w-4 text-muted transition-transform', open && 'rotate-180')} />
              </button>
              {open ? (
                <div className="space-y-3 border-t border-border/70 bg-surface/10 p-4">
                  <JsonCodeBlock title="Expected Run Contract" value={candidateTrial?.case?.expected_contract || referenceTrial?.case?.expected_contract} maxHeight={220} />
                  <div className="grid gap-4 xl:grid-cols-2">
                    <div className="space-y-3"><JsonCodeBlock title="Candidate output" value={candidateTrial?.output} maxHeight={280} /><JsonCodeBlock title="Candidate Judge and Trace" value={{ checks: candidateTrial?.checks, failure_code: candidateTrial?.failure_code, failure_detail: candidateTrial?.failure_detail, trace_id: candidateTrial?.trace_id }} maxHeight={220} /></div>
                    <div className="space-y-3"><JsonCodeBlock title="Reference output" value={referenceTrial?.output} maxHeight={280} /><JsonCodeBlock title="Reference Judge and Trace" value={{ checks: referenceTrial?.checks, failure_code: referenceTrial?.failure_code, failure_detail: referenceTrial?.failure_detail, trace_id: referenceTrial?.trace_id }} maxHeight={220} /></div>
                  </div>
                </div>
              ) : null}
            </article>
          )
        })}
      </section>
    </div>
  )
}
