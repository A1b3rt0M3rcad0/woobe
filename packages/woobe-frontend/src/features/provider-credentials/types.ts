export interface ProviderCredential {
  authentication?: { type: 'api_key'; fields: { api_key: { source: 'project_environment'; key: string } } } | null
  binding_revision?: number
  id: string
  project_id: string
  provider: string
  name: string
  status?: string
  last_validated_at?: string
  created_at?: string
  updated_at?: string
  metadata?: Record<string, string>
}

export interface CreateProviderCredentialRequest {
  project_id: string
  provider: string
  name: string
  secret?: string
  authentication?: ProviderCredential['authentication']
  metadata?: Record<string, string>
}

export interface UpdateProviderCredentialRequest {
  authentication?: ProviderCredential['authentication']
  name?: string
  provider?: string
  secret?: string
  metadata?: Record<string, string>
  status?: string
}

export interface RotateProviderCredentialRequest {
  secret: string
}
