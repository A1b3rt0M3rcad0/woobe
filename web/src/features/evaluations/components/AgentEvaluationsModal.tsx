import { useMemo, useState } from 'react'
import {
  ArrowLeft,
  Bot,
} from 'lucide-react'

import { ErrorState } from '@/components/common/ErrorState'
import { LoadingState } from '@/components/common/LoadingState'
import { Dialog } from '@/components/ui/Dialog'
import { useReleases } from '@/features/agents/hooks'
import {
  useEvaluationRuns,
  useEvaluationSuites,
} from '@/features/evaluations/hooks'
import { useProviderModels } from '@/features/provider-models/hooks'
import { cn } from '@/lib/utils'
import { AgentEvaluationExperience } from './AgentEvaluationExperience'
import { EvaluationResultsWorkspace } from './EvaluationResultsWorkspace'
import { EvaluatorSuitesWorkspace } from './EvaluatorSuitesWorkspace'
import { SuiteAuthoringWizard } from './SuiteAuthoringWizard'

type Screen = 'run' | 'suites' | 'results' | 'create-suite'

interface AgentEvaluationsModalProps {
  open: boolean
  onClose: () => void
  projectId: string
  agentId: string
  agentName: string
}

interface PersistedWorkspace {
  screen?: Screen
  selectedResultRunId?: string | null
  selectedSuiteVersionId?: string | null
}

function workspaceKey(projectId: string, agentId: string) {
  return `evaluation-workspace:${projectId}:${agentId}`
}

function loadWorkspace(projectId: string, agentId: string): PersistedWorkspace {
  try {
    const value = sessionStorage.getItem(workspaceKey(projectId, agentId))
    return value ? JSON.parse(value) as PersistedWorkspace : {}
  } catch {
    return {}
  }
}

export function AgentEvaluationsModal({
  open,
  onClose,
  projectId,
  agentId,
  agentName,
}: AgentEvaluationsModalProps) {
  const restored = loadWorkspace(projectId, agentId)
  const suitesQuery = useEvaluationSuites(projectId)
  const runsQuery = useEvaluationRuns(projectId)
  const releasesQuery = useReleases(agentId)
  const modelsQuery = useProviderModels(projectId)
  const [screen, setScreen] = useState<Screen>(restored.screen || 'run')
  const [selectedResultRunId, setSelectedResultRunId] = useState<string | null>(
    restored.selectedResultRunId || null,
  )
  const [selectedSuiteVersionId, setSelectedSuiteVersionId] = useState<string | null>(
    restored.selectedSuiteVersionId || null,
  )

  const suites = useMemo(
    () => (suitesQuery.data ?? []).filter(
      (suite) => suite.target_type === 'agent'
        && suite.status !== 'archived'
        && suite.current_version_id,
    ),
    [suitesQuery.data],
  )
  const runs = useMemo(
    () => (runsQuery.data ?? []).filter((run) => run.targets.some(
      (target) => target.target_type === 'agent' && target.entity_id === agentId,
    )),
    [runsQuery.data, agentId],
  )

  const persist = (
    nextScreen: Screen,
    nextResultRunId = selectedResultRunId,
    nextSuiteVersionId = selectedSuiteVersionId,
  ) => {
    setScreen(nextScreen)
    setSelectedResultRunId(nextResultRunId)
    setSelectedSuiteVersionId(nextSuiteVersionId)
    try {
      sessionStorage.setItem(workspaceKey(projectId, agentId), JSON.stringify({
        screen: nextScreen,
        selectedResultRunId: nextResultRunId,
        selectedSuiteVersionId: nextSuiteVersionId,
      }))
    } catch {
      // Storage is an enhancement; the workspace remains functional without it.
    }
  }

  const loading = (
    suitesQuery.isLoading
    || runsQuery.isLoading
    || releasesQuery.isLoading
    || modelsQuery.isLoading
  )
  const failed = (
    suitesQuery.isError
    || runsQuery.isError
    || releasesQuery.isError
    || modelsQuery.isError
  )

  return (
    <Dialog
      open={open}
      onClose={onClose}
      title="Evaluate Agent"
      className="max-w-[1280px] overflow-hidden bg-surface/95"
    >
      <div className="-m-6 flex max-h-[88vh] min-h-[720px] flex-col overflow-hidden">
        <header className="flex shrink-0 items-center justify-between gap-4 border-b border-border/80 px-5 py-4">
          <div className="flex min-w-0 items-center gap-3">
            {screen === 'create-suite' ? (
              <button
                type="button"
                onClick={() => persist('suites')}
                className="flex h-8 w-8 items-center justify-center rounded-lg border border-border text-muted hover:text-white"
              >
                <ArrowLeft className="h-4 w-4" />
              </button>
            ) : null}
            <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl border border-primary/20 bg-primary/10 text-primary-light">
              <Bot className="h-4 w-4" />
            </div>
            <div className="min-w-0">
              <p className="truncate text-sm font-semibold text-white">{agentName}</p>
              <p className="text-[11px] text-muted">
                Run Evaluations, manage immutable Suites and inspect evidence.
              </p>
            </div>
          </div>
          {screen !== 'create-suite' ? (
            <div className="flex rounded-lg border border-border bg-background/45 p-1">
              {([['run', 'Run'], ['suites', 'Suites'], ['results', 'Results']] as const).map(([value, text]) => (
                <button
                  key={value}
                  type="button"
                  onClick={() => persist(value)}
                  className={cn(
                    'rounded-md px-4 py-2 text-xs font-medium transition-colors',
                    screen === value
                      ? 'bg-primary/15 text-primary-light'
                      : 'text-muted hover:text-white',
                  )}
                >
                  {text}
                  {value === 'results' && runs.length ? (
                    <span className="ml-1.5 opacity-70">{runs.length}</span>
                  ) : null}
                </button>
              ))}
            </div>
          ) : null}
        </header>

        <main className="scrollbar-thin min-h-0 flex-1 overflow-y-auto p-5">
          {loading ? (
            <LoadingState message="Loading Evaluations" />
          ) : failed ? (
            <ErrorState message="Unable to load Agent Evaluations" />
          ) : screen === 'create-suite' ? (
            <SuiteAuthoringWizard
              projectId={projectId}
              agentId={agentId}
              releases={releasesQuery.data ?? []}
              providerModels={modelsQuery.data ?? []}
              onCancel={() => persist('suites')}
              onCreated={(suite) => {
                persist('run', selectedResultRunId, suite.current_version_id || null)
              }}
            />
          ) : screen === 'run' ? (
            <AgentEvaluationExperience
              projectId={projectId}
              agentId={agentId}
              suites={suites}
              releases={releasesQuery.data ?? []}
              runs={runs}
              initialSuiteVersionId={selectedSuiteVersionId}
              onRunCreated={(runId) => {
                persist('run', runId, selectedSuiteVersionId)
              }}
              onOpenResult={(runId) => persist('results', runId)}
              onCreateSuite={() => persist('create-suite')}
            />
          ) : screen === 'suites' ? (
            <EvaluatorSuitesWorkspace
              projectId={projectId}
              targetType="agent"
              onCreateSuite={() => persist('create-suite')}
              onUseSuite={(suite) => {
                persist('run', selectedResultRunId, suite.current_version_id || null)
              }}
            />
          ) : (
            <EvaluationResultsWorkspace
              projectId={projectId}
              runs={runs}
              selectedRunId={selectedResultRunId}
              onSelectRun={(runId) => persist('results', runId)}
              onRunAnother={() => persist('run')}
            />
          )}
        </main>
      </div>
    </Dialog>
  )
}
