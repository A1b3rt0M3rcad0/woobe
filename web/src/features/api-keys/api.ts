import { get, post } from '@/lib/api/client'
import type {
  ApiKey,
  CreateApiKeyRequest,
  CreateApiKeyResponse,
  RotateApiKeyRequest,
} from './types'

export async function getApiKeys(projectId: string): Promise<ApiKey[]> {
  return get<ApiKey[]>(`/core/projects/${projectId}/api-keys`)
}

export async function createApiKey(
  projectId: string,
  data: CreateApiKeyRequest,
): Promise<CreateApiKeyResponse> {
  return post<CreateApiKeyResponse>(`/core/projects/${projectId}/api-keys`, data)
}

export async function revokeApiKey(projectId: string, apiKeyId: string): Promise<ApiKey> {
  return post<ApiKey>(`/core/projects/${projectId}/api-keys/${apiKeyId}/revoke`, {})
}

export async function rotateApiKey(
  projectId: string,
  apiKeyId: string,
  data: RotateApiKeyRequest = {},
): Promise<CreateApiKeyResponse> {
  return post<CreateApiKeyResponse>(
    `/core/projects/${projectId}/api-keys/${apiKeyId}/rotate`,
    data,
  )
}
