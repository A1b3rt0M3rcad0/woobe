import { useMemo, useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import {
  AlertTriangle,
  CheckCircle2,
  ChevronRight,
  Database,
  RotateCcw,
  ShieldAlert,
  XCircle,
} from 'lucide-react'
import { toast } from 'sonner'

import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { JsonCodeBlock } from '@/components/ui/JsonCodeBlock'
import type { EvidenceRichRun } from '@/features/evaluations/catalogTypes'
import { post } from '@/lib/api/client'
import { cn } from '@/lib/utils'
import { EvaluationResultsView } from './EvaluationResultsView'

function money(value?: number | null) {
  return value == null ? '—' : `$${value.toFixed(value < 0.01 ? 4 : 2)}`
}

type TrialList = NonNullable<EvidenceRichRun['trials']>

interface EvidenceCaseGroup {
  key: string
  name: string
  trials: TrialList
}

function groupedCases(run: EvidenceRichRun): EvidenceCaseGroup[] {
  const map = new Map<string, TrialList>()
  for (const trial of run.trials || []) {
    const key = trial.case?.id || trial.pair_key
    map.set(key, [...(map.get(key) || []), trial])
  }
  return [...map.entries()].map(([key, trials]) => ({
    key,
    name: trials[trials.length - 1]?.case?.name || key,
    trials,
  }))
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
  const [selectedCaseId, setSelectedCaseId] = useState<string | null>(null)
  const unavailable = run.evidence_status === 'unavailable'
  const groups = useMemo(() => groupedCases(run), [run])
  const selectedGroup = useMemo(
    () => groups.find((group) => group.key === selectedCaseId) || groups[0] || null,
    [groups, selectedCaseId],
  )
  const selectedTrial = selectedGroup?.trials[selectedGroup.trials.length - 1]
  const selectedJudgeCall = useMemo(
    () => (run.judge_calls || []).find((call) => call.trial_id === selectedTrial?.id) || null,
    [run.judge_calls, selectedTrial?.id],
  )
  const completeness = run.evidence_completeness
  const primary = run.failure_summary?.primary

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

  const retryJudgments = useMutation({
    mutationFn: () => post(
      `/evaluation/projects/${projectId}/runs/${run.id}/retry-judgments`,
      {
        trial_ids: primary?.trial_ids || [],
      },
    ),
    onSuccess: () => {
      client.invalidateQueries({ queryKey: ['evaluation-evidence-run', projectId, run.id] })
      client.invalidateQueries({ queryKey: ['catalog-evaluation', projectId] })
      client.invalidateQueries({ queryKey: ['evaluation-run-progress', projectId, run.id] })
      toast.success('Judgments queued with controlled reasoning')
    },
    onError: (error) => {
      toast.error(error instanceof Error ? error.message : 'Unable to retry Judgments')
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
                <div>
                  <p className="font-medium text-white">{warning.code}</p>
                  <p className="mt-1 text-muted">{warning.message}</p>
                  {warning.recommended_action ? (
                    <p className="mt-1 text-primary-light">{warning.recommended_action}</p>
                  ) : null}
                </div>
              </div>
            ))}
          </section>
        ) : null}
        <EvaluationResultsView run={run} />
      </div>
    )
  }

  return (
    <div className="space-y-4">
      <section className="rounded-2xl border border-amber-500/25 bg-amber-500/[0.04] p-5">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <Badge variant="outline">Evidence unavailable</Badge>
              <Badge variant="outline">Assessment inconclusive</Badge>
              <Badge variant="outline">Revision {run.evidence_revision || 1}</Badge>
            </div>
            <h3 className="mt-3 flex items-center gap-2 text-base font-semibold text-white">
              <ShieldAlert className="h-4 w-4 text-amber-300" />
              The snapshot executed, but the Judge did not produce scored evidence
            </h3>
            <p className="mt-2 max-w-3xl text-xs leading-5 text-muted">
              Target outputs, Tool calls, RAG sources and Traces remain preserved. Retry processes only the affected Judgments.
            </p>
          </div>
          <div className="flex flex-wrap gap-5 text-right text-xs">
            <div><p className="text-[9px] uppercase text-muted">Runtime</p><p className="mt-1 text-lg font-semibold text-white">{completeness?.runtime_completed || 0}/{completeness?.total_trials || 0}</p></div>
            <div><p className="text-[9px] uppercase text-muted">Judge</p><p className="mt-1 text-lg font-semibold text-amber-300">{completeness?.judge_completed || 0}/{completeness?.total_trials || 0}</p></div>
            <div><p className="text-[9px] uppercase text-muted">Score</p><p className="mt-1 text-lg font-semibold text-white">—</p></div>
            <div><p className="text-[9px] uppercase text-muted">Pass rate</p><p className="mt-1 text-lg font-semibold text-white">—</p></div>
          </div>
        </div>
      </section>

      <section className="flex flex-wrap gap-3">
        <div className="min-w-48 flex-1 rounded-xl border border-border/80 bg-background/35 p-4"><p className="text-[9px] uppercase text-muted">Target runtime cost</p><p className="mt-2 text-lg font-semibold text-white">{money(run.cost_breakdown?.target_runtime_cost_usd)}</p></div>
        <div className="min-w-48 flex-1 rounded-xl border border-border/80 bg-background/35 p-4"><p className="text-[9px] uppercase text-muted">Judge cost</p><p className="mt-2 text-lg font-semibold text-white">{money(run.cost_breakdown?.judge_cost_usd)}</p></div>
        <div className="min-w-48 flex-1 rounded-xl border border-border/80 bg-background/35 p-4"><p className="text-[9px] uppercase text-muted">Total Evaluation cost</p><p className="mt-2 text-lg font-semibold text-white">{money(run.cost_breakdown?.total_evaluation_cost_usd)}</p></div>
      </section>

      <section className="flex flex-wrap items-stretch gap-4">
        <div className="min-w-[300px] flex-1 rounded-xl border border-amber-500/25 bg-amber-500/[0.04] p-4">
          <p className="text-sm font-semibold text-white">Primary failure</p>
          <div className="mt-2 flex flex-wrap items-center gap-2">
            <p className="font-mono text-xs text-amber-200">{primary?.code || 'judge_evidence_unavailable'}</p>
            {primary?.count ? <Badge variant="outline">{primary.count} Trials</Badge> : null}
          </div>
          <p className="mt-2 text-[11px] leading-5 text-muted">{primary?.summary || 'No Trial produced a conclusive Judge score.'}</p>
          <p className="mt-3 text-[11px] text-primary-light">{primary?.recommended_action || 'Retry only affected Judgments.'}</p>
          {primary?.stage === 'judge' ? (
            <Button
              className="mt-4"
              variant="outline"
              loading={retryJudgments.isPending}
              onClick={() => retryJudgments.mutate()}
            >
              <RotateCcw className="mr-2 h-3.5 w-3.5" />
              Retry Judgments
            </Button>
          ) : null}
        </div>

        {run.provenance_warnings?.map((warning) => (
          <div key={warning.code} className="min-w-[280px] flex-1 rounded-xl border border-border/80 bg-background/35 p-4">
            <div className="flex items-center gap-2"><Database className="h-4 w-4 text-primary-light" /><p className="text-xs font-semibold text-white">{warning.code}</p></div>
            <p className="mt-2 text-[10px] leading-4 text-muted">{warning.message}</p>
            {warning.recommended_action ? (
              <p className="mt-2 text-[10px] leading-4 text-primary-light">{warning.recommended_action}</p>
            ) : null}
          </div>
        ))}

        <div className="min-w-[320px] flex-1 rounded-xl border border-border/80 bg-background/35 p-4">
          <p className="text-sm font-semibold text-white">Manual override</p>
          <p className="mt-1 text-[10px] leading-4 text-muted">A normal decision is blocked because evidence is inconclusive. Override requires a justification and is audited separately.</p>
          <textarea value={note} onChange={(event) => setNote(event.target.value)} placeholder="Required override justification" className="mt-3 min-h-24 w-full rounded-lg border border-border bg-background px-3 py-2 text-xs text-white outline-none" />
          <div className="mt-3 flex flex-wrap gap-2">
            <Button className="flex-1" variant="outline" disabled={!note.trim()} loading={decide.isPending} onClick={async () => { try { await decide.mutateAsync('rejected'); toast.success('Manual rejection recorded') } catch (error) { toast.error(error instanceof Error ? error.message : 'Unable to save decision') } }}>Override reject</Button>
            <Button className="flex-1" disabled={!note.trim()} loading={decide.isPending} onClick={async () => { try { await decide.mutateAsync('accepted'); toast.success('Manual acceptance recorded') } catch (error) { toast.error(error instanceof Error ? error.message : 'Unable to save decision') } }}>Override accept</Button>
          </div>
        </div>
      </section>

      <section className="flex h-[640px] min-h-0 flex-col overflow-hidden rounded-xl border border-border/80 bg-background/30">
        <div className="shrink-0 border-b border-border/80 px-4 py-3">
          <div className="flex items-center justify-between gap-3">
            <div>
              <p className="text-sm font-semibold text-white">Preserved Test Case evidence</p>
              <p className="mt-1 text-[10px] text-muted">Select a Case. JSON blocks scroll locally and can be expanded to the full-screen inspector.</p>
            </div>
            <Badge variant="outline">{groups.length} Cases</Badge>
          </div>
        </div>

        {selectedGroup && selectedTrial ? (
          <div className="flex min-h-0 flex-1 overflow-hidden">
            <div className="w-60 shrink-0 overflow-y-auto border-r border-border/70 scrollbar-thin">
              {groups.map((group) => {
                const trial = group.trials[group.trials.length - 1]
                const selected = group.key === selectedGroup.key
                return (
                  <button
                    key={group.key}
                    type="button"
                    onClick={() => setSelectedCaseId(group.key)}
                    className={cn(
                      'flex w-full items-center gap-3 border-b border-border/60 px-4 py-3 text-left transition-colors last:border-b-0',
                      selected ? 'bg-primary/10' : 'hover:bg-surface/20',
                    )}
                  >
                    {trial.output ? <CheckCircle2 className="h-4 w-4 shrink-0 text-emerald-300" /> : <XCircle className="h-4 w-4 shrink-0 text-red-300" />}
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-xs font-medium text-white">{group.name}</p>
                      <p className="mt-1 truncate text-[10px] text-muted">
                        {trial.output ? 'Output preserved' : 'Runtime unavailable'} · {trial.failure_classification?.code || trial.failure_code || primary?.code || 'Judge unavailable'}
                      </p>
                    </div>
                    <div className="flex shrink-0 items-center gap-2">
                      <Badge variant="outline">{group.trials.length}</Badge>
                      <ChevronRight className={cn('h-3.5 w-3.5 text-muted', selected && 'text-primary-light')} />
                    </div>
                  </button>
                )
              })}
            </div>

            <div className="min-w-0 flex-1 overflow-y-auto p-4 scrollbar-thin">
              <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
                <div>
                  <p className="text-sm font-semibold text-white">{selectedGroup.name}</p>
                  <p className="mt-1 text-[10px] text-muted">Exact evidence from the selected snapshot and Evidence Revision.</p>
                </div>
                <Badge variant="outline">{selectedGroup.trials.length} outcome{selectedGroup.trials.length === 1 ? '' : 's'}</Badge>
              </div>

              <div className="min-w-0 space-y-4">
                <section className="min-w-0 rounded-xl border border-border/70 bg-surface/10 p-3">
                  <JsonCodeBlock
                    title="Expected Run Contract"
                    value={{
                      input: selectedTrial.case?.input_payload,
                      initial_context: selectedTrial.case?.initial_context,
                      expected_contract: selectedTrial.case?.expected_contract,
                    }}
                    maxHeight={300}
                    actions={['copy', 'expand']}
                  />
                </section>
                <section className="min-w-0 rounded-xl border border-border/70 bg-surface/10 p-3">
                  <JsonCodeBlock
                    title="Preserved target output"
                    value={selectedTrial.output}
                    maxHeight={320}
                    actions={['copy', 'expand']}
                  />
                </section>
                <section className="min-w-0 rounded-xl border border-border/70 bg-surface/10 p-3">
                  <JsonCodeBlock
                    title="Deterministic checks"
                    value={selectedTrial.checks || []}
                    maxHeight={280}
                    actions={['copy', 'expand']}
                  />
                </section>
                <section className="min-w-0 rounded-xl border border-border/70 bg-surface/10 p-3">
                  <JsonCodeBlock
                    title="Judge call and failure diagnostics"
                    value={{
                      failure_classification: selectedTrial.failure_classification,
                      failure_code: selectedTrial.failure_code,
                      failure_detail: selectedTrial.failure_detail,
                      trace_id: selectedTrial.trace_id,
                      judge_call: selectedJudgeCall,
                      judge_diagnostics:
                        selectedTrial.metrics?.judge_diagnostics
                        || selectedJudgeCall?.pricing_snapshot?._evaluation_judge
                        || null,
                      metrics: selectedTrial.metrics,
                    }}
                    maxHeight={360}
                    actions={['copy', 'expand']}
                  />
                </section>
              </div>
            </div>
          </div>
        ) : (
          <div className="flex flex-1 items-center justify-center px-6 text-center text-xs text-muted">
            No preserved Test Case evidence is available.
          </div>
        )}
      </section>
    </div>
  )
}
