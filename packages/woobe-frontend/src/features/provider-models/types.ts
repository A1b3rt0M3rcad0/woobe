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

export interface AvailableProviderModel {
  id: string
  label: string
  provider: string
  source: string
  owned_by?: string | null
  context_window?: number | null
  max_output_tokens?: number | null
  input_cost_per_1m_tokens?: number | null
  output_cost_per_1m_tokens?: number | null
  supports_tools?: boolean | null
  supports_json?: boolean | null
  supports_streaming?: boolean | null
  raw?: Record<string, any>
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
