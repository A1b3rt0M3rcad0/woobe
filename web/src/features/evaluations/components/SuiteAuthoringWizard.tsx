import type { AgentRelease } from '@/features/agents/types'
import type { EvaluationSuite } from '@/features/evaluations/types'
import type { ProviderModel } from '@/features/provider-models/types'
import { AgentSuiteQuickAuthoringWizard } from './AgentSuiteQuickAuthoringWizard'

interface SuiteAuthoringWizardProps {
  projectId: string
  agentId: string
  releases: AgentRelease[]
  providerModels: ProviderModel[]
  onCancel: () => void
  onCreated: (suite: EvaluationSuite) => void
}

/** Agent Playground adapter for the simplified contextual authoring flow. */
export function SuiteAuthoringWizard({
  projectId,
  agentId,
  releases,
  providerModels,
  onCancel,
  onCreated,
}: SuiteAuthoringWizardProps) {
  return (
    <AgentSuiteQuickAuthoringWizard
      projectId={projectId}
      agentId={agentId}
      releases={releases}
      providerModels={providerModels}
      onCancel={onCancel}
      onCreated={onCreated}
    />
  )
}
