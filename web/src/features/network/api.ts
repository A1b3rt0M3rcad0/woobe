import { get, patch, post, put } from '@/lib/api/client'

import type {
  NetworkDefinition,
  NetworkEnvironment,
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
  environment: NetworkEnvironment,
): Promise<PromotionPreview> {
  return post<PromotionPreview>(`/network/${networkId}/promotions/preview`, {
    project_id: projectId,
    environment,
  })
}

export function promoteNetwork(
  networkId: string,
  projectId: string,
  environment: NetworkEnvironment,
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

export function cancelNetworkExecution(
  executionId: string,
  projectId: string,
): Promise<{ execution_id: string }> {
  return post<{ execution_id: string }>(
    `/network/executions/${executionId}/cancel?project_id=${encodeURIComponent(projectId)}`,
  )
}
