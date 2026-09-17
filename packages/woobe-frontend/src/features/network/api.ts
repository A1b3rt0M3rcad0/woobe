import { get, patch, post } from '@/lib/api/client'

import type { RuntimeEnvironment, RuntimeEnvironmentState, RuntimeEnvironmentStates } from '@/features/agents/types'
import type { NetworkRunDiagnostics } from './components/networkRunDiagnosticsTypes'
import type {
  ActivateNetworkProductionInput,
  ActivateNetworkProductionResult,
  NetworkDefinition,
  NetworkEnvironment,
  NetworkExecutionSnapshot,
  NetworkMessageResource,
  NetworkProductionActivation,
  NetworkPromotionEnvironment,
  NetworkResource,
  NetworkSessionResource,
  NetworkVersion,
  PromoteNetworkInput,
  PromotionPreview,
} from './types'

const activeNetworkCancellationRequests = new Map<string, Promise<{ execution_id: string }>>()

export function listNetworks(projectId: string): Promise<NetworkResource[]> {
  return get<NetworkResource[]>(`/network/projects/${projectId}/networks`)
}

export function createNetwork(
  projectId: string,
  input: { name: string; description?: string },
): Promise<NetworkResource> {
  return post<NetworkResource>(`/network/projects/${projectId}/networks`, input)
}

export function getNetwork(projectId: string, networkId: string): Promise<NetworkResource> {
  return get<NetworkResource>(`/network/projects/${projectId}/networks/${networkId}`)
}

export function getNetworkRuntimeEnvironments(networkId: string, projectId: string): Promise<RuntimeEnvironmentStates> {
  return get<RuntimeEnvironmentStates>(`/network/${networkId}/runtime-environments`, {
    params: { project_id: projectId },
  })
}

export function updateNetworkRuntimeEnvironment(
  networkId: string,
  projectId: string,
  environment: RuntimeEnvironment,
  enabled: boolean,
): Promise<RuntimeEnvironmentState & { environment: RuntimeEnvironment }> {
  return patch<RuntimeEnvironmentState & { environment: RuntimeEnvironment }>(
    `/network/${networkId}/runtime-environments/${environment}`,
    { project_id: projectId, enabled },
  )
}

export function updateNetworkRuntimeEnvironmentContext(
  networkId: string,
  projectId: string,
  environment: RuntimeEnvironment,
  externalContextValues: Record<string, unknown>,
): Promise<RuntimeEnvironmentState & { environment: RuntimeEnvironment }> {
  return patch<RuntimeEnvironmentState & { environment: RuntimeEnvironment }>(
    `/network/${networkId}/runtime-environments/${environment}`,
    { project_id: projectId, external_context_values: externalContextValues },
  )
}

export function updateNetworkMetadata(
  projectId: string,
  networkId: string,
  input: { name?: string; description?: string },
): Promise<NetworkResource> {
  return patch<NetworkResource>(`/network/projects/${projectId}/networks/${networkId}`, input)
}

export function saveNetworkDraft(
  networkId: string,
  input: {
    project_id: string
    expected_revision: number
    name: string
    description: string
    definition: NetworkDefinition
  },
): Promise<NetworkResource> {
  return patch<NetworkResource>(`/network/${networkId}/draft`, input)
}

export function previewNetworkPromotion(
  networkId: string,
  projectId: string,
  environment: NetworkPromotionEnvironment,
): Promise<PromotionPreview> {
  return post<PromotionPreview>(`/network/${networkId}/promotions/preview`, {
    project_id: projectId,
    environment,
  })
}

export function promoteNetwork(
  networkId: string,
  projectId: string,
  input: PromoteNetworkInput,
): Promise<NetworkVersion> {
  return post<NetworkVersion>(`/network/${networkId}/promotions`, {
    project_id: projectId,
    environment: input.environment,
    expected_revision: input.expected_revision ?? undefined,
    expected_network_version_id: input.expected_network_version_id ?? undefined,
    approved_action_ids: input.approved_action_ids ?? [],
  })
}

export function getNetworkVersions(
  networkId: string,
  projectId: string,
): Promise<NetworkVersion[]> {
  return get<NetworkVersion[]>(`/network/${networkId}/management/versions`, {
    params: { project_id: projectId },
  })
}

export function getNetworkProductionActivations(
  networkId: string,
  projectId: string,
): Promise<NetworkProductionActivation[]> {
  return get<NetworkProductionActivation[]>(`/network/${networkId}/management/activations`, {
    params: { project_id: projectId },
  })
}

export function rollbackNetworkProduction(
  networkId: string,
  projectId: string,
  targetVersionId: string,
): Promise<NetworkVersion> {
  return post<NetworkVersion>(`/network/${networkId}/rollback`, {
    project_id: projectId,
    target_version_id: targetVersionId,
  })
}

export function activateNetworkProduction(
  networkId: string,
  projectId: string,
  input: ActivateNetworkProductionInput,
): Promise<ActivateNetworkProductionResult> {
  return post<ActivateNetworkProductionResult>(`/network/${networkId}/production/activations`, {
    project_id: projectId,
    source_version_id: input.source_version_id,
    expected_current_production_version_id: input.expected_current_production_version_id,
    change_description: input.change_description,
  })
}

export function getNetworkExecutionSnapshot(
  executionId: string,
  projectId: string,
): Promise<NetworkExecutionSnapshot> {
  return get<NetworkExecutionSnapshot>(`/network/executions/${executionId}/snapshot`, {
    params: { project_id: projectId },
  })
}

export function getNetworkRunDiagnostics(
  executionId: string,
  projectId: string,
): Promise<NetworkRunDiagnostics> {
  return get<NetworkRunDiagnostics>(`/network/executions/${executionId}/diagnostics`, {
    params: { project_id: projectId },
  })
}

export function createNetworkSession(
  networkId: string,
  input: {
    project_id: string
    environment: NetworkEnvironment
    title?: string
    external_session_id?: string
  },
): Promise<NetworkSessionResource> {
  return post<NetworkSessionResource>(`/network/${networkId}/sessions`, input)
}

export function getNetworkSessions(
  networkId: string,
  projectId: string,
): Promise<NetworkSessionResource[]> {
  return get<NetworkSessionResource[]>(`/network/${networkId}/sessions`, {
    params: { project_id: projectId },
  })
}

export function getNetworkSessionMessages(
  networkId: string,
  sessionId: string,
  projectId: string,
): Promise<NetworkMessageResource[]> {
  return get<NetworkMessageResource[]>(`/network/${networkId}/sessions/${sessionId}/messages`, {
    params: { project_id: projectId },
  })
}

export function resetNetworkSessionContext(
  networkId: string,
  sessionId: string,
  projectId: string,
): Promise<{ network_session_id: string }> {
  return post<{ network_session_id: string }>(
    `/network/${networkId}/sessions/${sessionId}/reset-context?project_id=${encodeURIComponent(projectId)}`,
  )
}

export function cancelNetworkExecution(
  executionId: string,
  projectId: string,
): Promise<{ execution_id: string }> {
  const requestKey = `${projectId}:${executionId}`
  const existing = activeNetworkCancellationRequests.get(requestKey)
  if (existing) return existing

  const request = post<{ execution_id: string }>(
    `/network/executions/${executionId}/cancel?project_id=${encodeURIComponent(projectId)}`,
  ).finally(() => {
    if (activeNetworkCancellationRequests.get(requestKey) === request) {
      activeNetworkCancellationRequests.delete(requestKey)
    }
  })

  activeNetworkCancellationRequests.set(requestKey, request)
  return request
}
