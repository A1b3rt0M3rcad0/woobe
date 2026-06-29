export interface ProviderModel {
  id: string
  project_id: string
  provider_credential_id: string
  provider?: string | null
  name: string
  model: string
  status: 'active' | 'inactive' | 'archived' | string
  metadata?: Record<string, string>
  created_at?: string
  updated_at?: string
}

export interface CreateProviderModelRequest {
  project_id: string
  provider_credential_id: string
  name: string
  model: string
  metadata?: Record<string, string>
}

export interface UpdateProviderModelRequest {
  provider_credential_id?: string
  name?: string
  model?: string
  metadata?: Record<string, string>
  status?: 'active' | 'inactive' | 'archived' | string
}
