import { get, post, patch } from '@/lib/api/client'
import type { AvailableProviderModel, CreateProviderModelRequest, ProviderModel, UpdateProviderModelRequest } from './types'

export async function getProviderModels(projectId?: string, credentialId?: string): Promise<ProviderModel[]> {
  return get<ProviderModel[]>('/ai/provider-models', {
    params: {
      project_id: projectId,
      provider_credential_id: credentialId,
    },
  })
}

export async function getAvailableProviderModels(projectId?: string, credentialId?: string, capability?: string): Promise<AvailableProviderModel[]> {
  if (!credentialId) return []
  return get<AvailableProviderModel[]>('/ai/provider-models', {
    params: {
      project_id: projectId,
      available_for_credential_id: credentialId,
      capability,
    },
  })
}

export async function getProviderModel(id: string): Promise<ProviderModel> {
  return get<ProviderModel>(`/ai/provider-models/${id}`)
}

export async function createProviderModel(data: CreateProviderModelRequest): Promise<ProviderModel> {
  return post<ProviderModel>('/ai/provider-models', data)
}

export async function updateProviderModel(id: string, data: UpdateProviderModelRequest): Promise<ProviderModel> {
  return patch<ProviderModel>(`/ai/provider-models/${id}`, data)
}
