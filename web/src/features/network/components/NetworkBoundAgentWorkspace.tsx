import type { Agent, AgentRelease } from '@/features/agents/types'
import { useReleases } from '@/features/agents/hooks'

import { NetworkAgentWorkspace } from './NetworkAgentWorkspace'
import type { NetworkBinding } from './networkWorkspaceTypes'

interface NetworkBoundAgentWorkspaceProps {
  agent: Agent
  projectId: string
  binding: NetworkBinding
  readOnly: boolean
  requireExecutionSnapshot?: boolean
  onOpenComposition: () => void
  onDirtyChange?: (dirty: boolean) => void
  onRegisterSaveAction?: (action: (() => Promise<boolean>) | null) => void
}

function agentFromRelease(agent: Agent, release: AgentRelease): Agent {
  return {
    ...agent,
    name: release.name ?? agent.name,
    description: release.description ?? agent.description,
    system_prompt: release.system_prompt ?? agent.system_prompt,
    provider: release.provider ?? agent.provider,
    model: release.model ?? agent.model,
    provider_model_id: release.provider_model_id ?? agent.provider_model_id,
    fallback_provider_model_id: release.fallback_provider_model_id ?? agent.fallback_provider_model_id,
    provider_credential_id: release.provider_credential_id ?? agent.provider_credential_id,
    fallback_provider: release.fallback_provider ?? agent.fallback_provider,
    fallback_model: release.fallback_model ?? agent.fallback_model,
    fallback_credential_id: release.fallback_credential_id ?? agent.fallback_credential_id,
    temperature: release.temperature ?? agent.temperature,
    max_output_tokens: release.max_output_tokens ?? agent.max_output_tokens,
    settings: release.runtime_config ?? agent.settings,
  }
}

function SnapshotUnavailable({ message }: { message: string }) {
  return (
    <div className="flex h-full min-h-0 items-center justify-center p-6 text-center">
      <div className="max-w-sm rounded-2xl border border-amber-500/25 bg-amber-500/5 p-5">
        <p className="text-[11px] font-medium text-white">Exact Agent snapshot unavailable</p>
        <p className="mt-2 text-[9px] leading-5 text-muted">{message}</p>
      </div>
    </div>
  )
}

export function NetworkBoundAgentWorkspace({
  agent,
  projectId,
  binding,
  readOnly,
  requireExecutionSnapshot = false,
  onOpenComposition,
  onDirtyChange,
  onRegisterSaveAction,
}: NetworkBoundAgentWorkspaceProps) {
  const releasesQuery = useReleases(readOnly && binding.source !== 'draft' ? agent.id : undefined)

  if (readOnly && binding.source === 'draft' && requireExecutionSnapshot) {
    return <SnapshotUnavailable message="This Draft Run is immutable, but the current history contract does not yet return the captured Agent Draft payload. The current mutable Agent is intentionally not shown as if it were the executed snapshot." />
  }

  if (readOnly && binding.source !== 'draft') {
    if (releasesQuery.isLoading) {
      return <div className="flex h-full items-center justify-center text-[10px] text-muted">Loading exact Agent snapshot…</div>
    }
    const release = releasesQuery.data?.find((item) => item.id === binding.ref)
    if (!release) {
      return <SnapshotUnavailable message={`The Network binding references ${binding.ref}, but that Agent snapshot could not be loaded. The current Agent is intentionally not substituted.`} />
    }
    return (
      <NetworkAgentWorkspace
        key={`${agent.id}:${release.id}`}
        agent={agentFromRelease(agent, release)}
        projectId={projectId}
        networkBinding={{ source: binding.source, version: release.version }}
        readOnly
        onOpenComposition={onOpenComposition}
      />
    )
  }

  return (
    <NetworkAgentWorkspace
      key={agent.id}
      agent={agent}
      projectId={projectId}
      networkBinding={{ source: binding.source, version: binding.version }}
      readOnly={readOnly}
      onOpenComposition={onOpenComposition}
      onDirtyChange={onDirtyChange}
      onRegisterSaveAction={onRegisterSaveAction}
    />
  )
}
