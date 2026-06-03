import { get, post } from '@/lib/api/client'
import type { ProviderCredential, CreateProviderCredentialRequest } from './types'

export async function getCredentials(projectId?: string): Promise<ProviderCredential[]> {
  return get<ProviderCredential[]>('/ai/credentials', { params: { project_id: projectId } })
}

export async function createCredential(data: CreateProviderCredentialRequest): Promise<ProviderCredential> {
  return post<ProviderCredential>('/ai/credentials', data)
}
