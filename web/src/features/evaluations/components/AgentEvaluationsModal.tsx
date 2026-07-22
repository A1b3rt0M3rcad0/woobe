import { useEffect, useMemo, useState } from 'react'
import {
  ArrowLeft,
  Beaker,
  Bot,
  ChevronRight,
  Plus,
  RefreshCw,
} from 'lucide-react'

import { ErrorState } from '@/components/common/ErrorState'
import { LoadingState } from '@/components/common/LoadingState'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { Dialog } from '@/components/ui/Dialog'
import { useReleases } from '@/features/agents/hooks'
import {
  useEvaluationRuns,
  useEvaluationSuites,
} from '@/features/evaluations/hooks'
import type { EvaluationRun } from '@/features/evaluations/types'
import { useProviderModels } from '@/features/provider-models/hooks'
import { cn } from '@/lib/utils'
import { AgentEvaluationExperience } from './AgentEvaluationExperience'
import { SuiteAuthoringWizard } from './SuiteAuthoringWizard'

type Screen = 'run' | 'suites' | 'results' | 'create-suite'

interface AgentEvaluationsModalProps {
  open: boolean
  onClose: () => void
  projectId: string
  agentId: string
  agentName: string
}

const terminalStatuses = new Set(['completed', 'partially_completed', 'failed', 'cancelled'])

function label(value?: string | null) {
  if (!value) return 'Unknown'
  return value.split('_').map((item) => item.charAt(0).toUpperCase() + item.slice(1)).join(' ')
}

function statusClass(status?: string | null) {
  if (status === 'qualified' || status === 'completed') return 'border-emerald-500/30 bg-emerald-500/10 text-emerald-300'
  if (status === 'not_qualified' || status === 'failed') return 'border-red-500/30 bg-red-500/10 text-red-300'
  if (status === 'qualified_with_warnings' || status === 'partially_completed') return 'border-amber-500/30 bg-amber-500/10 text-amber-300'
  return 'border-border bg-background/50 text-muted'
}

function runBelongsToAgent(run: EvaluationRun, agentId: string) {
  return run.targets.some((target) => target.target_type === 'agent' && target.entity_id === agentId)
}

export function AgentEvaluationsModal({
  open,
  onClose,
  projectId,
  agentId,
  agentName,
}: AgentEvaluationsModalProps) {
  const suitesQuery = useEvaluationSuites(projectId)
  const runsQuery = useEvaluationRuns(projectId)
  const releasesQuery = useReleases(agentId)
  const modelsQuery = useProviderModels(projectId)
  const [screen, setScreen] = useState<Screen>('run')
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null)

  const suites = useMemo(
    () => (suitesQuery.data ?? []).filter((suite) => suite.target_type === 'agent' && suite.current_version_id),
    [suitesQuery.data],
  )
  const runs = useMemo(
    () => (runsQuery.data ?? []).filter((run) => runBelongsToAgent(run, agentId)),
    [runsQuery.data, agentId],
  )

  useEffect(() => {
    if (!open) return
    setScreen('run')
    setSelectedRunId(null)
  }, [open])

  const loading = suitesQuery.isLoading || runsQuery.isLoading || releasesQuery.isLoading || modelsQuery.isLoading
  const failed = suitesQuery.isError || runsQuery.isError || releasesQuery.isError || modelsQuery.isError

  return (
    <Dialog open={open} onClose={onClose} title="Evaluate Agent" className="max-w-6xl overflow-hidden bg-surface/95">
      <div className="-m-6 flex max-h-[84vh] min-h-[680px] flex-col overflow-hidden">
        <header className="flex shrink-0 items-center justify-between gap-4 border-b border-border/80 px-5 py-4">
          <div className="flex min-w-0 items-center gap-3">
            {screen === 'create-suite' ? (
              <button type="button" onClick={() => setScreen('suites')} className="flex h-8 w-8 items-center justify-center rounded-lg border border-border text-muted hover:text-white"><ArrowLeft className="h-4 w-4" /></button>
            ) : null}
            <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl border border-primary/20 bg-primary/10 text-primary-light"><Bot className="h-4 w-4" /></div>
            <div className="min-w-0"><p className="truncate text-sm font-semibold text-white">{agentName}</p><p className="text-[11px] text-muted">Test quickly, compare configurations or inspect advanced evidence.</p></div>
          </div>
          {screen !== 'create-suite' ? (
            <div className="flex rounded-lg border border-border bg-background/45 p-1">
              {([['run', 'Run'], ['suites', 'Suites'], ['results', 'Results']] as const).map(([value, text]) => (
                <button key={value} type="button" onClick={() => { setScreen(value); if (value !== 'run') setSelectedRunId(null) }} className={cn('rounded-md px-3 py-1.5 text-xs font-medium transition-colors', screen === value ? 'bg-primary/15 text-primary-light' : 'text-muted hover:text-white')}>{text}</button>
              ))}
            </div>
          ) : null}
        </header>

        <main className="scrollbar-thin min-h-0 flex-1 overflow-y-auto p-5">
          {loading ? <LoadingState message="Loading Evaluations" /> : failed ? <ErrorState message="Unable to load Agent Evaluations" /> : screen === 'create-suite' ? (
            <SuiteAuthoringWizard
              projectId={projectId}
              agentId={agentId}
              releases={releasesQuery.data ?? []}
              providerModels={modelsQuery.data ?? []}
              onCancel={() => setScreen('suites')}
              onCreated={() => setScreen('run')}
            />
          ) : screen === 'run' ? (
            <AgentEvaluationExperience
              projectId={projectId}
              agentId={agentId}
              suites={suites}
              releases={releasesQuery.data ?? []}
              providerModels={modelsQuery.data ?? []}
              initialRunId={selectedRunId}
              onRunCreated={setSelectedRunId}
              onCreateSuite={() => setScreen('create-suite')}
            />
          ) : screen === 'suites' ? (
            <div className="mx-auto max-w-5xl">
              <div className="mb-4 flex items-center justify-between gap-4"><div><h3 className="text-sm font-semibold text-white">Evaluator Suites</h3><p className="mt-1 text-xs text-muted">Reusable and immutable Test Case configurations.</p></div><Button onClick={() => setScreen('create-suite')}><Plus className="mr-2 h-4 w-4" />New Suite</Button></div>
              {suites.length ? <div className="grid gap-3 md:grid-cols-2">{suites.map((suite) => (
                <article key={suite.id} className="rounded-xl border border-border/80 bg-background/40 p-4">
                  <div className="flex items-start justify-between gap-4"><div><h4 className="text-sm font-semibold text-white">{suite.name}</h4><p className="mt-1 text-xs leading-5 text-muted">{suite.description || 'Versioned Test Cases and grading policy.'}</p></div><Badge variant="outline">{suite.current_version}</Badge></div>
                  <div className="mt-4 grid grid-cols-3 gap-3 border-t border-border pt-3 text-xs"><div><p className="text-[9px] uppercase text-muted">Cases</p><p className="mt-1 text-white">{suite.case_count ?? '—'}</p></div><div><p className="text-[9px] uppercase text-muted">Minimum score</p><p className="mt-1 text-white">{String(suite.acceptance_policy?.minimum_score ?? 70)}</p></div><div><p className="text-[9px] uppercase text-muted">Default Runs</p><p className="mt-1 text-white">{String(suite.repetition_policy?.default_repetitions ?? 3)}</p></div></div>
                  <div className="mt-4 flex justify-end"><Button size="sm" onClick={() => setScreen('run')}>Use Suite</Button></div>
                </article>
              ))}</div> : <div className="rounded-xl border border-dashed border-border p-10 text-center text-sm text-muted">No Evaluator Suites configured.</div>}
            </div>
          ) : (
            <div className="mx-auto max-w-5xl">
              <div className="mb-4"><h3 className="text-sm font-semibold text-white">Evaluation history</h3><p className="mt-1 text-xs text-muted">Open a Run to see compact progress, grouped cases and technical evidence.</p></div>
              {runs.length ? <div className="space-y-2">{runs.map((run) => {
                const target = run.targets.find((item) => item.side === 'candidate' || item.side === 'single') || run.targets[0]
                const active = !terminalStatuses.has(run.status)
                return (
                  <button key={run.id} type="button" onClick={() => { setSelectedRunId(run.id); setScreen('run') }} className="flex w-full items-center gap-4 rounded-xl border border-border/80 bg-background/40 p-4 text-left hover:border-primary/30">
                    <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-border bg-surface"><Beaker className="h-4 w-4 text-primary-light" /></div>
                    <div className="min-w-0 flex-1"><div className="flex flex-wrap items-center gap-2"><p className="truncate text-sm font-semibold text-white">{target?.display_version || 'Agent snapshot'}</p><Badge variant="outline" className={statusClass(run.qualification_status || run.status)}>{label(run.qualification_status || run.status)}</Badge>{active ? <RefreshCw className="h-3.5 w-3.5 animate-spin text-primary-light" /> : null}</div><p className="mt-1 text-[11px] text-muted">{run.repetitions} Runs per case · {run.mode}</p></div>
                    <div className="text-right"><p className="text-[9px] uppercase text-muted">Score</p><p className="mt-1 text-sm font-semibold text-white">{run.overall_score == null ? '—' : run.overall_score.toFixed(1)}</p></div>
                    <ChevronRight className="h-4 w-4 text-muted" />
                  </button>
                )
              })}</div> : <div className="rounded-xl border border-dashed border-border p-10 text-center text-sm text-muted">No Evaluations have been run for this Agent.</div>}
            </div>
          )}
        </main>
      </div>
    </Dialog>
  )
}
