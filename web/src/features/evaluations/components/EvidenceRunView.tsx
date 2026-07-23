import { useMemo, useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import {
  AlertTriangle,
  CheckCircle2,
  Database,
  ShieldAlert,
  XCircle,
} from 'lucide-react'
import { toast } from 'sonner'

import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { JsonCodeBlock } from '@/components/ui/JsonCodeBlock'
import type { EvidenceRichRun } from '@/features/evaluations/catalogTypes'
import { post } from '@/lib/api/client'
import { EvaluationResultsView } from './EvaluationResultsView'

function money(value?: number | null) {
  return value == null ? '—' : `$${value.toFixed(value < 0.01 ? 4 : 2)}`
}

function groupedCases(run: EvidenceRichRun) {
  const map = new Map<string, NonNullable<EvidenceRichRun['trials']>>()
  for (const trial of run.trials || []) {
    const key = trial.case?.id || trial.pair_key
    map.set(key, [...(map.get(key) || []), trial])
  }
  return [...map.values()]
}

export function EvidenceRunView({
  projectId,
  run,
}: {
  projectId: string
  run: EvidenceRichRun
}) {
  const client = useQueryClient()
  const [note, setNote] = useState('')
  const [expandedCase, setExpandedCase] = useState<string | null>(null)
  const unavailable = run.evidence_status === 'unavailable'
  const groups = useMemo(() => groupedCases(run), [run])
  const decide = useMutation({
    mutationFn: (decision: 'accepted' | 'rejected') => post(
      `/evaluation/projects/${projectId}/runs/${run.id}/decision`,
      {
        target_id: run.targets[0]?.id,
        decision,
        decision_basis: 'manual_override',
        note: note.trim(),
      },
    ),
    onSuccess: () => {
      client.invalidateQueries({ queryKey: ['evaluation-evidence-run', projectId, run.id] })
      client.invalidateQueries({ queryKey: ['catalog-evaluation', projectId] })
    },
  })

  if (!unavailable) {
    return (
      <div className="space-y-4">
        {run.provenance_warnings?.length ? (
          <section className="space-y-2 rounded-xl border border-amber-500/25 bg-amber-500/[0.04] p-4">
            {run.provenance_warnings.map((warning) => (
              <div key={warning.code} className="flex items-start gap-2 text-xs">
                <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-amber-300" />
                <div><p className="font-medium text-white">{warning.code}</p><p className="mt-1 text-muted">{warning.message}</p></div>
              </div>
            ))}
          </section>
        ) : null}
        <EvaluationResultsView run={run} />
      </div>
    )
  }

  const completeness = run.evidence_completeness
  const primary = run.failure_summary?.primary
  return (
    <div className="space-y-4">
      <section className="rounded-2xl border border-amber-500/25 bg-amber-500/[0.04] p-5">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <Badge variant="outline">Evidence unavailable</Badge>
              <Badge variant="outline">Assessment inconclusive</Badge>
              <Badge variant="outline">Revision {(run as any).evidence_revision || 1}</Badge>
            </div>
            <h3 className="mt-3 flex items-center gap-2 text-base font-semibold text-white">
              <ShieldAlert className="h-4 w-4 text-amber-300" />The snapshot executed, but the Judge did not produce scored evidence
            </h3>
            <p className="mt-2 max-w-3xl text-xs leading-5 text-muted">
              Target outputs, Tool calls, RAG sources and Traces remain preserved. A retry should rerun only the affected Judgments.
            </p>
          </div>
          <div className="grid grid-cols-2 gap-5 text-right text-xs sm:grid-cols-4">
            <div><p className="text-[9px] uppercase text-muted">Runtime</p><p className="mt-1 text-lg font-semibold text-white">{completeness?.runtime_completed || 0}/{completeness?.total_trials || 0}</p></div>
            <div><p className="text-[9px] uppercase text-muted">Judge</p><p className="mt-1 text-lg font-semibold text-amber-300">{completeness?.judge_completed || 0}/{completeness?.total_trials || 0}</p></div>
            <div><p className="text-[9px] uppercase text-muted">Score</p><p className="mt-1 text-lg font-semibold text-white">—</p></div>
            <div><p className="text-[9px] uppercase text-muted">Pass rate</p><p className="mt-1 text-lg font-semibold text-white">—</p></div>
          </div>
        </div>
      </section>

      <section className="grid gap-3 sm:grid-cols-3">
        <div className="rounded-xl border border-border/80 bg-background/35 p-4"><p className="text-[9px] uppercase text-muted">Target runtime cost</p><p className="mt-2 text-lg font-semibold text-white">{money(run.cost_breakdown?.target_runtime_cost_usd)}</p></div>
        <div className="rounded-xl border border-border/80 bg-background/35 p-4"><p className="text-[9px] uppercase text-muted">Judge cost</p><p className="mt-2 text-lg font-semibold text-white">{money(run.cost_breakdown?.judge_cost_usd)}</p></div>
        <div className="rounded-xl border border-border/80 bg-background/35 p-4"><p className="text-[9px] uppercase text-muted">Total Evaluation cost</p><p className="mt-2 text-lg font-semibold text-white">{money(run.cost_breakdown?.total_evaluation_cost_usd)}</p></div>
      </section>

      <section className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_320px]">
        <div className="overflow-hidden rounded-xl border border-border/80 bg-background/30">
          <div className="border-b border-border/80 px-4 py-3">
            <p className="text-sm font-semibold text-white">Preserved Test Case evidence</p>
            <p className="mt-1 text-[10px] text-muted">Open a Case to inspect expected behavior and the exact target output.</p>
          </div>
          {groups.map((trials) => {
            const trial = trials[trials.length - 1]
            const caseId = trial.case?.id || trial.pair_key
            const open = expandedCase === caseId
            return (
              <article key={caseId} className="border-b border-border/70 last:border-b-0">
                <button
                  type="button"
                  onClick={() => setExpandedCase(open ? null : caseId)}
                  className="flex w-full items-center gap-3 px-4 py-3 text-left hover:bg-surface/20"
                >
                  {trial.output ? <CheckCircle2 className="h-4 w-4 text-emerald-300" /> : <XCircle className="h-4 w-4 text-red-300" />}
                  <div className="min-w-0 flex-1"><p className="truncate text-xs font-medium text-white">{trial.case?.name || caseId}</p><p className="mt-1 text-[10px] text-muted">{trial.output ? 'Target output preserved' : 'Target execution unavailable'} · {trial.failure_code || primary?.code || 'Judge unavailable'}</p></div>
                  <Badge variant="outline">{trials.length} outcome{trials.length === 1 ? '' : 's'}</Badge>
                </button>
                {open ? (
                  <div className="grid gap-3 border-t border-border/70 bg-surface/10 p-4 xl:grid-cols-2">
                    <JsonCodeBlock title="Expected Run Contract" value={{ input: trial.case?.input_payload, initial_context: trial.case?.initial_context, expected_contract: trial.case?.expected_contract }} maxHeight={300} />
                    <JsonCodeBlock title="Preserved target output" value={trial.output} maxHeight={300} />
                    <JsonCodeBlock title="Checks" value={trial.checks || []} maxHeight={240} />
                    <JsonCodeBlock title="Judge and execution failure" value={{ failure_classification: (trial as any).failure_classification, failure_code: trial.failure_code, failure_detail: trial.failure_detail, trace_id: trial.trace_id, metrics: trial.metrics }} maxHeight={240} />
                  </div>
                ) : null}
              </article>
            )
          })}
        </div>

        <aside className="space-y-4">
          <section className="rounded-xl border border-amber-500/25 bg-amber-500/[0.04] p-4">
            <p className="text-sm font-semibold text-white">Primary failure</p>
            <p className="mt-2 font-mono text-xs text-amber-200">{primary?.code || 'judge_evidence_unavailable'}</p>
            <p className="mt-2 text-[11px] leading-5 text-muted">{primary?.summary || 'No Trial produced a conclusive Judge score.'}</p>
            <p className="mt-3 text-[11px] text-primary-light">{primary?.recommended_action || 'Retry only affected Judgments.'}</p>
          </section>

          {run.provenance_warnings?.map((warning) => (
            <section key={warning.code} className="rounded-xl border border-border/80 bg-background/35 p-4">
              <div className="flex items-center gap-2"><Database className="h-4 w-4 text-primary-light" /><p className="text-xs font-semibold text-white">{warning.code}</p></div>
              <p className="mt-2 text-[10px] leading-4 text-muted">{warning.message}</p>
            </section>
          ))}

          <section className="rounded-xl border border-border/80 bg-background/35 p-4">
            <p className="text-sm font-semibold text-white">Manual override</p>
            <p className="mt-1 text-[10px] leading-4 text-muted">A normal decision is blocked because evidence is inconclusive. Override requires a justification and is audited separately.</p>
            <textarea value={note} onChange={(event) => setNote(event.target.value)} placeholder="Required override justification" className="mt-3 min-h-24 w-full rounded-lg border border-border bg-background px-3 py-2 text-xs text-white outline-none" />
            <div className="mt-3 grid grid-cols-2 gap-2">
              <Button variant="outline" disabled={!note.trim()} loading={decide.isPending} onClick={async () => { try { await decide.mutateAsync('rejected'); toast.success('Manual rejection recorded') } catch (error) { toast.error(error instanceof Error ? error.message : 'Unable to save decision') } }}>Override reject</Button>
              <Button disabled={!note.trim()} loading={decide.isPending} onClick={async () => { try { await decide.mutateAsync('accepted'); toast.success('Manual acceptance recorded') } catch (error) { toast.error(error instanceof Error ? error.message : 'Unable to save decision') } }}>Override accept</Button>
            </div>
          </section>
        </aside>
      </section>
    </div>
  )
}