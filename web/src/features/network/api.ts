import { get, patch, post, put } from '@/lib/api/client'

import type {
  NetworkDefinition,
  NetworkEnvironment,
  NetworkMessageResource,
  NetworkPromotionEnvironment,
  NetworkResource,
  NetworkSessionResource,
  NetworkVersion,
  PromotionPreview,
} from './types'

export function ensureNetwork(projectId: string, name: string): Promise<NetworkResource> {
  return put<NetworkResource>(`/network/projects/${projectId}`, { name })
}

export function getNetwork(projectId: string): Promise<NetworkResource> {
  return get<NetworkResource>(`/network/projects/${projectId}`)
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
  environment: NetworkPromotionEnvironment,
): Promise<NetworkVersion> {
  return post<NetworkVersion>(`/network/${networkId}/promotions`, {
    project_id: projectId,
    environment,
  })
}

export function getNetworkVersions(
  networkId: string,
  projectId: string,
): Promise<NetworkVersion[]> {
  return get<NetworkVersion[]>(`/network/${networkId}/versions`, {
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
  return post<{ execution_id: string }>(
    `/network/executions/${executionId}/cancel?project_id=${encodeURIComponent(projectId)}`,
  )
}
