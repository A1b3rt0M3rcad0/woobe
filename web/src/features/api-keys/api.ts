import { get, post } from '@/lib/api/client'
import type { ApiKey, CreateApiKeyRequest, CreateApiKeyResponse } from './types'

export async function getApiKeys(projectId: string): Promise<ApiKey[]> {
  return get<ApiKey[]>(`/core/projects/${projectId}/api-keys`)
}

export async function createApiKey(projectId: string, data: CreateApiKeyRequest): Promise<CreateApiKeyResponse> {
  return post<CreateApiKeyResponse>(`/core/projects/${projectId}/api-keys`, data)
}
