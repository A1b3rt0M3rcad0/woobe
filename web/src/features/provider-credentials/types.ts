export interface ProviderCredential {
  id: string
  project_id: string
  provider: string
  name: string
  status?: string
  last_validated_at?: string
  created_at?: string
}

export interface CreateProviderCredentialRequest {
  project_id: string
  provider: string
  name: string
  secret: string
}
