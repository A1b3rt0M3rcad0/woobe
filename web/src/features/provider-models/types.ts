export interface ProviderModel {
  id: string
  project_id: string
  provider_credential_id: string
  provider?: string | null
  name: string
  model: string
  status: 'active' | 'inactive' | 'archived' | string
  metadata?: Record<string, any>
  created_at?: string
  updated_at?: string
}

export interface CreateProviderModelRequest {
  project_id: string
  provider_credential_id: string
  name: string
  model: string
  metadata?: Record<string, any>
}

export interface UpdateProviderModelRequest {
  provider_credential_id?: string
  name?: string
  model?: string
  metadata?: Record<string, any>
  status?: 'active' | 'inactive' | 'archived' | string
}
