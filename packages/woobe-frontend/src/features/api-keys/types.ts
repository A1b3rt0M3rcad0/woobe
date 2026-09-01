export type ApiKeyScope = 'runtime:execute' | 'traces:read' | 'usage:read'
export type ApiKeyKind = 'project' | 'runtime'
export type RuntimeEnvironment = 'staging' | 'production'
export type RuntimeInterface = 'http' | 'stream' | 'jobs'
export type RuntimeTargetType = 'agent' | 'network'

export interface ApiKey {
  id: string
  credential_id: string
  project_id: string
  name: string
  description?: string | null
  key_prefix: string
  scopes: ApiKeyScope[]
  kind: ApiKeyKind
  agent_id?: string | null
  target_type?: RuntimeTargetType | null
  target_id?: string | null
  environment?: RuntimeEnvironment | null
  interfaces: RuntimeInterface[]
  status: 'active' | 'revoked' | 'expired'
  last_used_at?: string | null
  expires_at?: string | null
  revoked_at?: string | null
  rotated_from_id?: string | null
  created_at?: string | null
}

export interface CreateApiKeyRequest {
  name: string
  description?: string | null
  scopes: ApiKeyScope[]
  expires_at?: string | null
}

export interface CreateRuntimeApiKeyRequest {
  name: string
  description?: string | null
  target_type?: RuntimeTargetType
  target_id?: string
  agent_id?: string
  environment: RuntimeEnvironment
  interfaces: RuntimeInterface[]
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

export interface UpdateApiKeyCredentialRequest {
  name: string
  description?: string | null
}

export interface ApiKeyCredentialResponse {
  id: string
  credential_id: string
  project_id: string
  name: string
  description?: string | null
  kind: ApiKeyKind
  agent_id?: string | null
  target_type?: RuntimeTargetType | null
  target_id?: string | null
  environment?: RuntimeEnvironment | null
  updated_at?: string | null
}
