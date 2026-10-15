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

export async function getAvailableProviderModels(projectId?: string, credentialId?: string, capability?: string, environment = 'draft'): Promise<AvailableProviderModel[]> {
  if (!credentialId) return []
  return get<AvailableProviderModel[]>('/ai/provider-models', {
    params: {
      project_id: projectId,
      available_for_credential_id: credentialId,
      environment,
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

export interface ReconciliationScope {
  project_id: string
  provider_credential_id: string
  environment: string
  capability: 'generation' | 'embedding'
}

export interface ReconciliationItem {
  model_id: string
  label: string
  installed_model_id: string | null
  expected_model_revision?: string | null
  candidate_digest?: string
  state: string
  change_kind: string
  installed_spec?: Record<string, any> | null
  proposed_spec?: Record<string, any> | null
}

export interface ReconciliationPreview {
  expected_credential_revision: number
  expected_configuration_revision: string | null
  items: ReconciliationItem[]
}

export function previewProviderModels(scope: ReconciliationScope) {
  return get<ReconciliationPreview>('/ai/provider-models/sync-preview', { params: { ...scope } })
}

export function applyProviderModels(scope: ReconciliationScope, preview: ReconciliationPreview, items: ReconciliationItem[]) {
  return post<{ items: { model_id: string; result: string; provider_model_id: string; evidence_updated?: boolean }[]; adoption: string }>('/ai/provider-models/sync-apply', {
    ...scope, expected_credential_revision: preview.expected_credential_revision,
    expected_configuration_revision: preview.expected_configuration_revision,
    selections: items.map(({ model_id, installed_model_id, expected_model_revision, candidate_digest }) => ({
      model_id, installed_model_id, expected_model_revision, candidate_digest,
    })),
  })
}
