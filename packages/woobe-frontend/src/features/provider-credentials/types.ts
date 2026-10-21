export type ProviderRemoteAuthentication = { type: 'api_key'; fields: { api_key: { source: 'project_environment'; key: string } } }
export interface ProviderCredential {
  authentication?: { type: 'api_key'; fields: { api_key: { source: 'project_environment' | 'legacy_configuration'; key: string; alias_id?: string } } } | null
  binding_revision?: number
  supports_embedding?: boolean | null
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
  authentication?: ProviderRemoteAuthentication
  metadata?: Record<string, string>
}

export interface UpdateProviderCredentialRequest {
  authentication?: ProviderRemoteAuthentication
  name?: string
  provider?: string
  secret?: string
  metadata?: Record<string, string>
  status?: string
}

export interface RotateProviderCredentialRequest {
  secret: string
}
