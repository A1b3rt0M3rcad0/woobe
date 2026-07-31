export type ChatSurfaceTargetType = 'agent' | 'network'
export type ChatSurfaceStatus = 'draft' | 'active' | 'disabled' | 'archived'

export interface ChatSurface {
  id: string
  public_id: string
  project_id: string
  name: string
  description?: string | null
  target_type: ChatSurfaceTargetType
  target_id: string
  environment: 'production'
  status: ChatSurfaceStatus
  allowed_origins: string[]
  appearance_config: Record<string, unknown>
  requests_per_minute: number
  max_concurrent_runs: number
  session_token_ttl_seconds: number
  token_epoch: number
  activated_at?: string | null
  created_at: string
  updated_at: string
}

export interface ChatSurfaceAccessKey {
  id: string
  credential_id: string
  chat_surface_id: string
  name: string
  description?: string | null
  prefix: string
  access_key?: string
  scopes: string[]
  status: string
  created_at: string
}

export interface CreateChatSurfaceInput {
  name: string
  description?: string
  target_type: ChatSurfaceTargetType
  target_id: string
  allowed_origins: string[]
  appearance_config?: Record<string, unknown>
  requests_per_minute?: number
  max_concurrent_runs?: number
  session_token_ttl_seconds?: number
}
