export interface ApiKey {
  id: string
  name: string
  key_prefix: string
  status?: string
  created_at?: string
}

export interface CreateApiKeyRequest {
  name: string
  scopes?: string[]
}

export interface CreateApiKeyResponse {
  id: string
  name: string
  key: string
  key_prefix: string
  status: string
}
