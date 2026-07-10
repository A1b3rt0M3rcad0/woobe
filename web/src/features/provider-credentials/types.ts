export interface ProviderCredential {
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
  secret: string
  metadata?: Record<string, string>
}

export interface UpdateProviderCredentialRequest {
  name?: string
  provider?: string
  secret?: string
  metadata?: Record<string, string>
  status?: string
}

export interface RotateProviderCredentialRequest {
  secret: string
}
