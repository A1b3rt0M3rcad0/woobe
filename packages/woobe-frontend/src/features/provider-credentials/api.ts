import { get, post, patch } from '@/lib/api/client'
import type {
  ProviderCredential,
  CreateProviderCredentialRequest,
  RotateProviderCredentialRequest,
  UpdateProviderCredentialRequest,
} from './types'

export async function getCredentials(projectId?: string): Promise<ProviderCredential[]> {
  return get<ProviderCredential[]>('/ai/credentials', { params: { project_id: projectId } })
}

export async function createCredential(data: CreateProviderCredentialRequest): Promise<ProviderCredential> {
  return post<ProviderCredential>('/ai/credentials', data)
}

export async function updateCredential(id: string, data: UpdateProviderCredentialRequest): Promise<ProviderCredential> {
  return patch<ProviderCredential>(`/ai/credentials/${id}`, data)
}

export async function rotateCredential(
  id: string,
  data: RotateProviderCredentialRequest,
): Promise<ProviderCredential> {
  return post<ProviderCredential>(`/ai/credentials/${id}/rotate`, data)
}
