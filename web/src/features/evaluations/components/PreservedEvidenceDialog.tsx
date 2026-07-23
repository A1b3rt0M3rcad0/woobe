import { useEffect, useMemo, useState } from 'react'
import { CheckCircle2, ChevronRight, MessagesSquare, XCircle } from 'lucide-react'

import { Badge } from '@/components/ui/Badge'
import { Dialog } from '@/components/ui/Dialog'
import { JsonCodeBlock } from '@/components/ui/JsonCodeBlock'
import type { EvidenceRichRun } from '@/features/evaluations/catalogTypes'
import { cn } from '@/lib/utils'

type TrialList = NonNullable<EvidenceRichRun['trials']>

interface EvidenceCaseGroup {
  key: string
  name: string
  trials: TrialList
}

function groupedCases(run: EvidenceRichRun): EvidenceCaseGroup[] {
  const map = new Map<string, TrialList>()
  for (const trial of run.trials || []) {
    const key = trial.case?.id || trial.pair_key.split(':')[0]
    map.set(key, [...(map.get(key) || []), trial])
  }
  return [...map.entries()].map(([key, trials]) => ({
    key,
    name: trials[trials.length - 1]?.case?.name || key,
    trials,
  }))
}

export function PreservedEvidenceDialog({
  open,
  onClose,
  run,
}: {
  open: boolean
  onClose: () => void
  run: EvidenceRichRun
}) {
  const groups = useMemo(() => groupedCases(run), [run])
  const [selectedCaseId, setSelectedCaseId] = useState<string | null>(null)
  const [selectedTrialId, setSelectedTrialId] = useState<string | null>(null)
  const selectedGroup = useMemo(
    () => groups.find((group) => group.key === selectedCaseId) || groups[0] || null,
    [groups, selectedCaseId],
  )
  const selectedTrial = useMemo(() => (
    selectedGroup?.trials.find((trial) => trial.id === selectedTrialId)
    || selectedGroup?.trials[selectedGroup.trials.length - 1]
    || null
  ), [selectedGroup, selectedTrialId])
  const selectedJudgeCall = useMemo(
    () => (run.judge_calls || []).find((call) => call.trial_id === selectedTrial?.id) || null,
    [run.judge_calls, selectedTrial?.id],
  )
  const isSession = selectedTrial?.interaction_mode === 'session'
    || selectedTrial?.case?.interaction_mode === 'session'
    || selectedTrial?.metrics?.interaction_mode === 'session'
  const turns = selectedTrial?.turns || []

  useEffect(() => {
    setSelectedTrialId(null)
  }, [selectedGroup?.key])

  return (
    <Dialog
      open={open}
      onClose={onClose}
      title="Preserved Test Case evidence"
      className="w-[min(1240px,calc(100vw-2rem))] max-w-[1240px]"
      contentClassName="p-0"
      scrollMode="content"
    >
      <div className="border-b border-border/80 px-5 py-3">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <p className="text-[11px] text-muted">
            Frozen runtime evidence from this exact target snapshot and Evidence Revision.
          </p>
          <div className="flex items-center gap-2">
            {isSession ? <Badge variant="outline"><MessagesSquare className="mr-1 h-3 w-3" />Session Test</Badge> : null}
            <Badge variant="outline">{groups.length} Cases</Badge>
          </div>
        </div>
      </div>

      {selectedGroup && selectedTrial ? (
        <div className="flex h-[min(760px,calc(100svh-10rem))] min-h-[500px] overflow-hidden">
          <aside className="w-64 shrink-0 overflow-y-auto border-r border-border/70 scrollbar-thin">
            {groups.map((group) => {
              const trial = group.trials[group.trials.length - 1]
              const selected = group.key === selectedGroup.key
              const groupIsSession = trial.interaction_mode === 'session'
                || trial.case?.interaction_mode === 'session'
                || trial.metrics?.interaction_mode === 'session'
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
                  {trial.output
                    ? <CheckCircle2 className="h-4 w-4 shrink-0 text-emerald-300" />
                    : <XCircle className="h-4 w-4 shrink-0 text-red-300" />}
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-xs font-medium text-white">{group.name}</p>
                    <p className="mt-1 truncate text-[10px] text-muted">
                      {groupIsSession ? `Session · ${trial.case?.turns?.length || trial.turns?.length || 0} turns` : 'Single-turn'} · {trial.failure_classification?.code || trial.failure_code || 'No failure'}
                    </p>
                  </div>
                  <div className="flex shrink-0 items-center gap-2">
                    <Badge variant="outline">{group.trials.length}</Badge>
                    <ChevronRight className={cn('h-3.5 w-3.5 text-muted', selected && 'text-primary-light')} />
                  </div>
                </button>
              )
            })}
          </aside>

          <main className="min-w-0 flex-1 overflow-y-auto p-5 scrollbar-thin">
            <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
              <div>
                <p className="text-sm font-semibold text-white">{selectedGroup.name}</p>
                <p className="mt-1 text-[10px] text-muted">
                  {isSession
                    ? 'One Trial represents one isolated full session. Select a repetition to inspect every preserved turn.'
                    : 'Exact evidence from the selected snapshot and Evidence Revision.'}
                </p>
              </div>
              <div className="flex flex-wrap gap-2">
                {selectedGroup.trials.map((trial) => (
                  <button
                    key={trial.id}
                    type="button"
                    onClick={() => setSelectedTrialId(trial.id)}
                    className={cn(
                      'rounded-md border px-2.5 py-1 text-[10px]',
                      trial.id === selectedTrial.id
                        ? 'border-primary/40 bg-primary/10 text-primary-light'
                        : 'border-border text-muted hover:text-white',
                    )}
                  >
                    Repetition {trial.repetition}
                  </button>
                ))}
              </div>
            </div>

            <div className="min-w-0 space-y-4">
              <section className="min-w-0 rounded-xl border border-border/70 bg-surface/10 p-3">
                <JsonCodeBlock
                  title={isSession ? 'Expected Session Contract' : 'Expected Run Contract'}
                  value={{
                    interaction_mode: selectedTrial.interaction_mode || selectedTrial.case?.interaction_mode || 'single_turn',
                    input: selectedTrial.case?.input_payload,
                    defined_turns: selectedTrial.case?.turns,
                    initial_context: selectedTrial.case?.initial_context,
                    expected_contract: selectedTrial.case?.expected_contract,
                  }}
                  maxHeight={300}
                  actions={['copy', 'expand']}
                />
              </section>

              {isSession ? (
                <section className="min-w-0 rounded-xl border border-border/70 bg-surface/10 p-3">
                  <div className="mb-3 flex items-center justify-between gap-3">
                    <div>
                      <p className="text-xs font-semibold text-white">Preserved Session transcript</p>
                      <p className="mt-1 text-[10px] text-muted">
                        {turns.length} preserved turn{turns.length === 1 ? '' : 's'} · Session {selectedTrial.metrics?.session_id || 'ID unavailable'}
                      </p>
                    </div>
                    <Badge variant="outline">
                      {selectedTrial.metrics?.session_completed ? 'Completed session' : 'Incomplete session'}
                    </Badge>
                  </div>
                  <div className="space-y-3">
                    {turns.length ? turns.map((turn) => (
                      <div key={turn.id || turn.position} className="rounded-lg border border-border/70 bg-background/35 p-3">
                        <div className="flex flex-wrap items-center justify-between gap-2">
                          <p className="text-xs font-semibold text-white">Turn {turn.position}</p>
                          <div className="flex gap-2">
                            <Badge variant="outline">{turn.status}</Badge>
                            {turn.metrics?.latency_ms != null ? <Badge variant="outline">{Math.round(Number(turn.metrics.latency_ms))}ms</Badge> : null}
                            {turn.metrics?.cost_usd != null ? <Badge variant="outline">${Number(turn.metrics.cost_usd).toFixed(4)}</Badge> : null}
                          </div>
                        </div>
                        <div className="mt-3 grid gap-3 xl:grid-cols-2">
                          <JsonCodeBlock title="User input" value={turn.input_payload} maxHeight={180} actions={['copy', 'expand']} />
                          <JsonCodeBlock title="Target response" value={turn.output} maxHeight={220} actions={['copy', 'expand']} />
                        </div>
                        {(turn.failure_code || turn.failure_detail) ? (
                          <p className="mt-3 text-[10px] text-red-300">
                            {turn.failure_code || 'Turn failure'} · {turn.failure_detail || 'No detail'}
                          </p>
                        ) : null}
                        <p className="mt-3 font-mono text-[9px] text-muted">
                          Trace {turn.trace_id || '—'} · Agent session {turn.agent_session_id || '—'} · Network session {turn.network_session_id || '—'}
                        </p>
                      </div>
                    )) : (
                      <p className="rounded-lg border border-dashed border-border p-5 text-center text-xs text-muted">
                        No turn rows were preserved for this historical Trial.
                      </p>
                    )}
                  </div>
                </section>
              ) : (
                <section className="min-w-0 rounded-xl border border-border/70 bg-surface/10 p-3">
                  <JsonCodeBlock
                    title="Preserved target output"
                    value={selectedTrial.output}
                    maxHeight={320}
                    actions={['copy', 'expand']}
                  />
                </section>
              )}

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
                  title={isSession ? 'Session Judge and failure diagnostics' : 'Judge call and failure diagnostics'}
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
          </main>
        </div>
      ) : (
        <div className="flex min-h-64 items-center justify-center px-6 text-center text-xs text-muted">
          No preserved Test Case evidence is available.
        </div>
      )}
    </Dialog>
  )
}
