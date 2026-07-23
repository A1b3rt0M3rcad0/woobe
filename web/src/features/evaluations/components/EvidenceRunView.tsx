import { useMemo, useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import {
  AlertTriangle,
  Bot,
  Database,
  Eye,
  RotateCcw,
  ShieldAlert,
  TerminalSquare,
} from 'lucide-react'
import { toast } from 'sonner'

import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import type { EvidenceRichRun } from '@/features/evaluations/catalogTypes'
import type { EvaluationKpis } from '@/features/evaluations/types'
import { post } from '@/lib/api/client'
import { EvaluationDiagnosticsDialog } from './EvaluationDiagnosticsDialog'
import { EvaluationResultsView } from './EvaluationResultsView'
import { PreservedEvidenceDialog } from './PreservedEvidenceDialog'

function money(value?: number | null) {
  return value == null ? '—' : `$${value.toFixed(value < 0.01 ? 4 : 2)}`
}

function percentage(value?: number | null) {
  return value == null ? '—' : `${value.toFixed(1)}%`
}

function score(value?: number | null) {
  return value == null ? '—' : value.toFixed(1)
}

function latency(value?: number | null) {
  return value == null ? '—' : `${Math.round(value)}ms`
}

interface RunJudgeSummary {
  displayName: string
  provider: string | null
  model: string | null
  credentialName: string | null
  responseStrategy: string | null
  source: string
}

function judgeSummary(run: EvidenceRichRun): RunJudgeSummary {
  const aggregate = run.aggregate_result && typeof run.aggregate_result === 'object'
    ? run.aggregate_result
    : {}
  const preflight = aggregate.judge_preflight && typeof aggregate.judge_preflight === 'object'
    ? aggregate.judge_preflight as Record<string, any>
    : {}
  const frozenModel = preflight.judge_model && typeof preflight.judge_model === 'object'
    ? preflight.judge_model as Record<string, any>
    : {}
  const protocol = run.execution_policy?.judge_protocol && typeof run.execution_policy.judge_protocol === 'object'
    ? run.execution_policy.judge_protocol as Record<string, any>
    : {}
  const protocolModel = protocol.judge_model_snapshot && typeof protocol.judge_model_snapshot === 'object'
    ? protocol.judge_model_snapshot as Record<string, any>
    : {}
  const call = (run.judge_calls || [])[0] as Record<string, any> | undefined
  const source = protocol.source === 'run_override' ? 'Run override' : 'Suite default'
  const selected = Object.keys(protocolModel).length ? protocolModel : frozenModel

  return {
    displayName: String(selected.display_name || selected.model || call?.model || 'Judge Model'),
    provider: selected.provider || call?.provider || null,
    model: selected.model || call?.model || null,
    credentialName: selected.credential_name || null,
    responseStrategy: selected.capabilities?.response_strategy || null,
    source,
  }
}

function JudgeUsedCard({ run }: { run: EvidenceRichRun }) {
  const judge = useMemo(() => judgeSummary(run), [run])
  return (
    <section className="rounded-xl border border-primary/20 bg-primary/[0.025] p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex min-w-0 items-start gap-3">
          <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-primary/20 bg-primary/10">
            <Bot className="h-4 w-4 text-primary-light" />
          </div>
          <div className="min-w-0">
            <p className="text-[9px] uppercase tracking-wide text-muted">Judge used by this Run</p>
            <p className="mt-1 truncate text-sm font-semibold text-white">{judge.displayName}</p>
            <p className="mt-1 truncate font-mono text-[10px] text-muted">
              {[judge.provider, judge.model].filter(Boolean).join(' · ') || 'Historical Judge metadata unavailable'}
            </p>
          </div>
        </div>
        <div className="flex flex-wrap gap-2">
          <Badge variant="outline">{judge.source}</Badge>
          {judge.responseStrategy ? <Badge variant="outline">{judge.responseStrategy}</Badge> : null}
          {judge.credentialName ? <Badge variant="outline">Credential: {judge.credentialName}</Badge> : null}
        </div>
      </div>
      <p className="mt-3 text-[10px] leading-4 text-muted">
        This Judge identity is historical evidence for the Run. Retrying Judgments keeps the same frozen Judge protocol.
      </p>
    </section>
  )
}

function CanonicalKpis({ run }: { run: EvidenceRichRun }) {
  const kpis = (run.kpis || run.aggregate_result?.kpis) as EvaluationKpis | null | undefined
  if (!kpis) return null
  const session = kpis.session
  return (
    <section className="rounded-xl border border-border/80 bg-background/35 p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-sm font-semibold text-white">Evaluation KPIs</p>
          <p className="mt-1 text-[10px] text-muted">
            Canonical metrics frozen with this Evidence Revision and consumed directly by Comparisons.
          </p>
        </div>
        <Badge variant="outline">{kpis.schema_version}</Badge>
      </div>
      <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-6">
        <div><p className="text-[9px] uppercase text-muted">Quality</p><p className="mt-1 text-lg font-semibold text-white">{score(kpis.quality_score)}</p></div>
        <div><p className="text-[9px] uppercase text-muted">Pass rate</p><p className="mt-1 text-lg font-semibold text-white">{percentage(kpis.pass_rate)}</p></div>
        <div><p className="text-[9px] uppercase text-muted">Runtime / Trial</p><p className="mt-1 text-lg font-semibold text-white">{money(kpis.runtime_cost_usd_per_trial)}</p></div>
        <div><p className="text-[9px] uppercase text-muted">Median latency</p><p className="mt-1 text-lg font-semibold text-white">{latency(kpis.latency_median_ms)}</p></div>
        <div><p className="text-[9px] uppercase text-muted">P90 latency</p><p className="mt-1 text-lg font-semibold text-white">{latency(kpis.latency_p90_ms)}</p></div>
        <div><p className="text-[9px] uppercase text-muted">Stable cases</p><p className="mt-1 text-lg font-semibold text-white">{percentage(kpis.stable_case_rate)}</p></div>
      </div>
      {session?.session_count ? (
        <div className="mt-4 border-t border-border/70 pt-4">
          <div className="flex flex-wrap items-center gap-2">
            <Badge variant="outline">Session Evaluation</Badge>
            <span className="text-[10px] text-muted">{session.session_count} Session Trials · {session.turn_count} turns</span>
          </div>
          <div className="mt-3 grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
            <div><p className="text-[9px] uppercase text-muted">Session completion</p><p className="mt-1 text-sm font-semibold text-white">{percentage(session.session_completion_rate)}</p></div>
            <div><p className="text-[9px] uppercase text-muted">Turn completion</p><p className="mt-1 text-sm font-semibold text-white">{percentage(session.turn_completion_rate)}</p></div>
            <div><p className="text-[9px] uppercase text-muted">Avg turns / Session</p><p className="mt-1 text-sm font-semibold text-white">{score(session.average_turns_per_session)}</p></div>
            <div><p className="text-[9px] uppercase text-muted">Cost / Session</p><p className="mt-1 text-sm font-semibold text-white">{money(session.cost_usd_per_session)}</p></div>
            <div><p className="text-[9px] uppercase text-muted">Latency / Session</p><p className="mt-1 text-sm font-semibold text-white">{latency(session.latency_ms_per_session)}</p></div>
          </div>
        </div>
      ) : null}
    </section>
  )
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
  const [logsOpen, setLogsOpen] = useState(false)
  const [evidenceOpen, setEvidenceOpen] = useState(false)
  const unavailable = run.evidence_status === 'unavailable'
  const completeness = run.evidence_completeness
  const primary = run.failure_summary?.primary
  const judgeRetryAllowed = primary?.stage === 'judge'
    && primary?.recoverability === 'retryable'
  const preservedCaseCount = useMemo(() => new Set(
    (run.trials || []).map((trial) => trial.case?.id || trial.pair_key),
  ).size, [run.trials])

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
      client.invalidateQueries({ queryKey: ['evaluation-run-diagnostics', projectId, run.id] })
      toast.success('Judgments queued with the same immutable Judge protocol')
    },
    onError: (error) => {
      toast.error(error instanceof Error ? error.message : 'Unable to retry Judgments')
    },
  })

  if (!unavailable) {
    return (
      <div className="space-y-4">
        <CanonicalKpis run={run} />
        <JudgeUsedCard run={run} />
        <div className="flex justify-end">
          <Button variant="outline" onClick={() => setLogsOpen(true)}>
            <TerminalSquare className="mr-2 h-4 w-4" />View execution logs
          </Button>
        </div>
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
        <EvaluationDiagnosticsDialog
          open={logsOpen}
          projectId={projectId}
          runId={run.id}
          onClose={() => setLogsOpen(false)}
        />
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
              {primary?.recoverability === 'user_action_required' ? (
                <Badge variant="outline" className="border-red-500/25 text-red-300">
                  Configuration required
                </Badge>
              ) : null}
            </div>
            <h3 className="mt-3 flex items-center gap-2 text-base font-semibold text-white">
              <ShieldAlert className="h-4 w-4 text-amber-300" />
              The snapshot executed, but the Judge did not produce scored evidence
            </h3>
            <p className="mt-2 max-w-3xl text-xs leading-5 text-muted">
              Target outputs, Tool calls, RAG sources and Traces remain preserved. Automatic retry is offered only for transient or repairable Judge failures.
            </p>
            <Button className="mt-4" variant="outline" onClick={() => setLogsOpen(true)}>
              <TerminalSquare className="mr-2 h-4 w-4" />View all execution logs
            </Button>
          </div>
          <div className="flex flex-wrap gap-5 text-right text-xs">
            <div><p className="text-[9px] uppercase text-muted">Runtime</p><p className="mt-1 text-lg font-semibold text-white">{completeness?.runtime_completed || 0}/{completeness?.total_trials || 0}</p></div>
            <div><p className="text-[9px] uppercase text-muted">Judge</p><p className="mt-1 text-lg font-semibold text-amber-300">{completeness?.judge_completed || 0}/{completeness?.total_trials || 0}</p></div>
            <div><p className="text-[9px] uppercase text-muted">Score</p><p className="mt-1 text-lg font-semibold text-white">—</p></div>
            <div><p className="text-[9px] uppercase text-muted">Pass rate</p><p className="mt-1 text-lg font-semibold text-white">—</p></div>
          </div>
        </div>
      </section>

      <CanonicalKpis run={run} />
      <JudgeUsedCard run={run} />

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
          <p className="mt-3 text-[11px] text-primary-light">{primary?.recommended_action || 'Review the persisted Judge diagnostics.'}</p>
          <div className="mt-4 flex flex-wrap gap-2">
            <Button variant="outline" onClick={() => setLogsOpen(true)}>
              <TerminalSquare className="mr-2 h-3.5 w-3.5" />Execution logs
            </Button>
            {judgeRetryAllowed ? (
              <Button
                variant="outline"
                loading={retryJudgments.isPending}
                onClick={() => retryJudgments.mutate()}
              >
                <RotateCcw className="mr-2 h-3.5 w-3.5" />
                Retry Judgments
              </Button>
            ) : null}
          </div>
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

      <section className="flex flex-wrap items-center justify-between gap-4 rounded-xl border border-border/80 bg-background/30 p-4">
        <div>
          <p className="text-sm font-semibold text-white">Preserved Test Case evidence</p>
          <p className="mt-1 text-[10px] leading-4 text-muted">
            {preservedCaseCount} Cases preserve target outputs, Session turns, expected contracts, deterministic checks and Judge diagnostics. Open them only when detailed evidence is needed.
          </p>
        </div>
        <Button variant="outline" disabled={!preservedCaseCount} onClick={() => setEvidenceOpen(true)}>
          <Eye className="mr-2 h-4 w-4" />View preserved evidence
        </Button>
      </section>

      <PreservedEvidenceDialog
        open={evidenceOpen}
        onClose={() => setEvidenceOpen(false)}
        run={run}
      />
      <EvaluationDiagnosticsDialog
        open={logsOpen}
        projectId={projectId}
        runId={run.id}
        onClose={() => setLogsOpen(false)}
      />
    </div>
  )
}
