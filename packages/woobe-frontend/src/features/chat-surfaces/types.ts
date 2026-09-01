export type ChatSurfaceTargetType = 'agent' | 'network'
export type ChatSurfaceStatus = 'draft' | 'active' | 'disabled' | 'archived'
export type ChatSurfaceTheme = 'light' | 'dark' | 'system'
export type ChatSurfaceResponseRenderMode = 'plain' | 'rich'
export type ChatSurfaceActivityMode = 'dots' | 'status'
export type ChatSurfaceActivityDetailLevel = 'generic' | 'named'

export interface ChatSurfaceSurfaceStyle {
  background_color: string | null
  border_color: string | null
  border_width: number
  border_radius: number
  shadow: 'none' | 'sm' | 'md' | 'lg'
}

export interface ChatSurfaceHeaderStyle {
  visible: boolean
  background_color: string | null
  text_color: string | null
  border_color: string | null
  border_width: number
  height: number
  padding: number
  alignment: 'left' | 'center' | 'right'
}

export interface ChatSurfaceConversationStyle {
  background_color: string | null
  padding: number
  message_gap: number
  max_content_width: number
}

export interface ChatSurfaceMessageStyle {
  background_color: string | null
  text_color: string | null
  border_color: string | null
  border_width: number
  border_radius: number
  padding_y: number
  padding_x: number
  max_width: number
  show_avatar: boolean
}

export interface ChatSurfaceComposerStyle {
  background_color: string | null
  border_color: string | null
  padding: number
}

export interface ChatSurfaceInputStyle {
  background_color: string | null
  text_color: string | null
  placeholder_color: string | null
  border_color: string | null
  focus_border_color: string | null
  border_radius: number
  font_size: number
  padding_y: number
  padding_x: number
}

export interface ChatSurfaceSendButtonStyle {
  variant: 'text' | 'icon' | 'icon_text'
  background_color: string | null
  text_color: string | null
  border_color: string | null
  border_width: number
  border_radius: number
  label: string
  icon: 'arrow_up' | 'arrow_right' | 'none'
}

export interface ChatSurfaceActivityLabels {
  preparing: string
  planning_tools: string
  calling_tool: string
  processing_tool_result: string
  generating_answer: string
  formatting_response: string
}

export interface ChatSurfaceActivityStyle {
  mode: ChatSurfaceActivityMode
  detail_level: ChatSurfaceActivityDetailLevel
  show_icon: boolean
  labels: ChatSurfaceActivityLabels
}

export interface ChatSurfaceAppearance {
  schema_version: 2
  theme: ChatSurfaceTheme
  primary_color: string
  title: string
  placeholder: string
  welcome_message?: string | null
  surface: ChatSurfaceSurfaceStyle
  header: ChatSurfaceHeaderStyle
  conversation: ChatSurfaceConversationStyle
  messages: {
    user: ChatSurfaceMessageStyle
    assistant: ChatSurfaceMessageStyle
    system: ChatSurfaceMessageStyle
  }
  composer: ChatSurfaceComposerStyle
  input: ChatSurfaceInputStyle
  send_button: ChatSurfaceSendButtonStyle
  activity: ChatSurfaceActivityStyle
  response: {
    render_mode: ChatSurfaceResponseRenderMode
  }
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
  last_used_at?: string | null
  expires_at?: string | null
  created_at: string
}

export interface ChatSurfaceTestSession {
  session_id: string
  target_release_id: string
  session_token: string
  expires_in: number
  source: 'control_plane_test'
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
