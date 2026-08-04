export type ChatSurfaceTargetType = 'agent' | 'network'
export type ChatSurfaceStatus = 'draft' | 'active' | 'disabled' | 'archived'
export type ChatSurfaceTheme = 'light' | 'dark' | 'system'

export interface ChatSurfaceAppearance {
  theme: ChatSurfaceTheme
  primary_color: string
  title: string
  placeholder: string
  welcome_message?: string | null
}

export interface ChatSurface {
  id: string
  public_id: string
  project_id: string
  name: string
  description?: string | null
  target_type: ChatSurfaceTargetType
  target_id: string
  target_release_id: string
  environment: 'production'
  status: ChatSurfaceStatus
  access_mode: 'backend_managed'
  allowed_origins: string[]
  appearance_config: ChatSurfaceAppearance
  requests_per_minute: number
  max_concurrent_runs: number
  session_token_ttl_seconds: number
  token_epoch: number
  activated_at?: string | null
  archived_at?: string | null
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
  appearance_config?: ChatSurfaceAppearance
  requests_per_minute?: number
  max_concurrent_runs?: number
  session_token_ttl_seconds?: number
}

export interface UpdateChatSurfaceInput {
  name?: string
  description?: string | null
  allowed_origins?: string[]
  appearance_config?: ChatSurfaceAppearance
  requests_per_minute?: number
  max_concurrent_runs?: number
  session_token_ttl_seconds?: number
}
