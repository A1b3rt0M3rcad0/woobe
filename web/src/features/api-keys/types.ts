export type ApiKeyScope = 'runtime:execute' | 'traces:read' | 'usage:read'

export interface ApiKey {
  id: string
  project_id: string
  name: string
  key_prefix: string
  scopes: ApiKeyScope[]
  status: 'active' | 'revoked' | 'expired'
  last_used_at?: string | null
  expires_at?: string | null
  revoked_at?: string | null
  created_at?: string | null
}

export interface CreateApiKeyRequest {
  name: string
  scopes?: ApiKeyScope[]
  expires_at?: string | null
}

export interface CreateApiKeyResponse extends ApiKey {
  key: string
}

export interface RotateApiKeyRequest {
  name?: string
  scopes?: ApiKeyScope[]
  expires_at?: string | null
}
