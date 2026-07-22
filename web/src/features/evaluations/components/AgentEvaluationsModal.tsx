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
  useEvaluationCatalog,
  useEvaluationComparisons,
} from '@/features/evaluations/catalogHooks'
import {
  useEvaluationRuns,
  useEvaluationSuites,
} from '@/features/evaluations/hooks'
import { useProviderModels } from '@/features/provider-models/hooks'
import { cn } from '@/lib/utils'
import { AgentEvaluationExperience } from './AgentEvaluationExperience'
import { EvaluationCatalogWorkspace } from './EvaluationCatalogWorkspace'
import { EvaluationComparisonsWorkspace } from './EvaluationComparisonsWorkspace'
import { EvaluatorSuitesWorkspace } from './EvaluatorSuitesWorkspace'
import { SuiteAuthoringWizard } from './SuiteAuthoringWizard'

type Screen = 'run' | 'evaluations' | 'comparisons' | 'suites' | 'create-suite'

interface AgentEvaluationsModalProps {
  open: boolean
  onClose: () => void
  projectId: string
  agentId: string
  agentName: string
}

interface PersistedWorkspace {
  screen?: Screen
  selectedEvaluationId?: string | null
  selectedComparisonId?: string | null
  selectedSuiteVersionId?: string | null
}

function workspaceKey(projectId: string, agentId: string) {
  return `evaluation-workspace:v2:${projectId}:${agentId}`
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
  const evaluationsQuery = useEvaluationCatalog(projectId, agentId)
  const comparisonsQuery = useEvaluationComparisons(projectId, agentId)
  const releasesQuery = useReleases(agentId)
  const modelsQuery = useProviderModels(projectId)
  const [screen, setScreen] = useState<Screen>(restored.screen || 'run')
  const [selectedEvaluationId, setSelectedEvaluationId] = useState<string | null>(
    restored.selectedEvaluationId || null,
  )
  const [selectedComparisonId, setSelectedComparisonId] = useState<string | null>(
    restored.selectedComparisonId || null,
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
    nextEvaluationId = selectedEvaluationId,
    nextComparisonId = selectedComparisonId,
    nextSuiteVersionId = selectedSuiteVersionId,
  ) => {
    setScreen(nextScreen)
    setSelectedEvaluationId(nextEvaluationId)
    setSelectedComparisonId(nextComparisonId)
    setSelectedSuiteVersionId(nextSuiteVersionId)
    try {
      sessionStorage.setItem(workspaceKey(projectId, agentId), JSON.stringify({
        screen: nextScreen,
        selectedEvaluationId: nextEvaluationId,
        selectedComparisonId: nextComparisonId,
        selectedSuiteVersionId: nextSuiteVersionId,
      }))
    } catch {
      // Persistence is progressive enhancement only.
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
      className="max-w-[1360px] overflow-hidden bg-surface/95"
    >
      <div className="-m-6 flex max-h-[90vh] min-h-[740px] flex-col overflow-hidden">
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
                Run exact snapshot Evaluations, compare reusable evidence and manage immutable Suites.
              </p>
            </div>
          </div>
          {screen !== 'create-suite' ? (
            <div className="flex rounded-lg border border-border bg-background/45 p-1">
              {([
                ['run', 'Run'],
                ['evaluations', 'Evaluations'],
                ['comparisons', 'Comparisons'],
                ['suites', 'Suites'],
              ] as const).map(([value, text]) => (
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
                  {value === 'evaluations' && evaluationsQuery.data?.length ? (
                    <span className="ml-1.5 opacity-70">{evaluationsQuery.data.length}</span>
                  ) : null}
                  {value === 'comparisons' && comparisonsQuery.data?.length ? (
                    <span className="ml-1.5 opacity-70">{comparisonsQuery.data.length}</span>
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
                persist('run', selectedEvaluationId, selectedComparisonId, suite.current_version_id || null)
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
              onRunCreated={() => persist('run')}
              onComparisonCreated={(comparisonId) => {
                persist('comparisons', selectedEvaluationId, comparisonId)
              }}
              onOpenResult={() => persist('evaluations')}
              onCreateSuite={() => persist('create-suite')}
            />
          ) : screen === 'evaluations' ? (
            <EvaluationCatalogWorkspace
              projectId={projectId}
              entityId={agentId}
              selectedEvaluationId={selectedEvaluationId}
              onSelectEvaluation={(evaluationId) => {
                persist('evaluations', evaluationId)
              }}
              onRunAgain={(evaluation) => {
                persist('run', evaluation.id, selectedComparisonId, evaluation.suite_version_id)
              }}
              onCompareRun={() => persist('comparisons')}
            />
          ) : screen === 'comparisons' ? (
            <EvaluationComparisonsWorkspace
              projectId={projectId}
              entityId={agentId}
              selectedComparisonId={selectedComparisonId}
              onSelectComparison={(comparisonId) => {
                persist('comparisons', selectedEvaluationId, comparisonId)
              }}
              onCreateComparison={() => persist('run')}
            />
          ) : (
            <EvaluatorSuitesWorkspace
              projectId={projectId}
              targetType="agent"
              onCreateSuite={() => persist('create-suite')}
              onUseSuite={(suite) => {
                persist('run', selectedEvaluationId, selectedComparisonId, suite.current_version_id || null)
              }}
            />
          )}
        </main>
      </div>
    </Dialog>
  )
}
