import type { AgentRelease } from '@/features/agents/types'
import type { EvaluationSuite } from '@/features/evaluations/types'
import type { ProviderModel } from '@/features/provider-models/types'
import { EvaluatorSuiteAuthoringWizard } from './EvaluatorSuiteAuthoringWizard'

interface SuiteAuthoringWizardProps {
  projectId: string
  agentId: string
  releases: AgentRelease[]
  providerModels: ProviderModel[]
  onCancel: () => void
  onCreated: (suite: EvaluationSuite) => void
}

/**
 * Compatibility adapter for the Agent Playground.
 * The actual authoring experience is shared with Networks and the global workspace.
 */
export function SuiteAuthoringWizard({
  projectId,
  agentId,
  releases,
  providerModels,
  onCancel,
  onCreated,
}: SuiteAuthoringWizardProps) {
  return (
    <EvaluatorSuiteAuthoringWizard
      projectId={projectId}
      targetType="agent"
      entityId={agentId}
      targetName="Agent"
      versions={releases.map((release) => ({
        id: release.id,
        version: release.version,
        status: release.status,
        snapshot_kind: release.snapshot_kind,
      }))}
      providerModels={providerModels}
      onCancel={onCancel}
      onCreated={onCreated}
    />
  )
}
