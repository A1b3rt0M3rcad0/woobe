export interface SessionListItem {
  id: string
  project_id: string
  agent_id: string
  status: string
  mode: string
  last_message_at: string | null
  created_at: string | null
  message_count: number
}

export interface Session {
  id: string
  project_id: string
  agent_id: string
  external_session_id?: string
  tenant_id?: string
  user_id?: string
  status: string
  mode?: string
  data?: Record<string, unknown>
  last_message_at?: string
  created_at?: string
  updated_at?: string
}

export interface CreateSessionRequest {
  project_id: string
  agent_id: string
  external_session_id?: string
  tenant_id?: string
  user_id?: string
  mode?: string
  data?: Record<string, unknown>
}

export interface AskRequest {
  project_id: string
  agent_id: string
  message: string
  session_id?: string | null
  tenant_id?: string
  user_id?: string
  metadata?: Record<string, unknown>
  execution_context?: 'playground' | 'production'
  loaded_release_id?: string | null
  snapshot_override?: Record<string, unknown> | null
}

export interface SourceInfo {
  document_title?: string
  document_id?: string
  chunk_id?: string
  page_number?: number
  score?: number | null
  content_preview?: string
}

export interface ToolCallInfo {
  tool_name: string
  input?: unknown
  output?: unknown
  duration_ms?: number
  success?: boolean | null
  status?: string | null
  latency_ms?: number | null
  error?: string | null
}

export interface UsageInfo {
  input_tokens: number | null
  output_tokens: number | null
  total_tokens?: number | null
  cost_usd: number | null
}

export interface FallbackInfo {
  primary_model: string | null
  primary_provider: string | null
  primary_error: string
  fallback_model: string | null
  fallback_provider: string | null
  fallback_credential_id: string | null
}

export interface FallbackEventInfo {
  primary_provider: string
  primary_model: string
  fallback_provider: string
  fallback_model: string
  error: string
}

export interface AskResponse {
  answer: string
  session_id: string | null
  message_id: string | null
  usage: UsageInfo | null
  sources: SourceInfo[]
  tool_calls: ToolCallInfo[]
  trace_id: string | null
  model: string | null
  provider: string | null
  fallback_used: boolean
  fallback_info?: FallbackInfo | null
  latency_ms: number | null
  parsed_output?: Record<string, unknown> | null
  output_parse_error?: string | null
}

export interface Message {
  id: string
  session_id: string
  role: string
  content: string
  input_tokens?: number | null
  output_tokens?: number | null
  cost_usd?: number | null
  data?: Record<string, unknown>
  created_at: string
  updated_at?: string
}

export interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
  usage?: UsageInfo | null
  sources?: SourceInfo[] | null
  tool_calls?: ToolCallInfo[] | null
  model?: string | null
  provider?: string | null
  latency_ms?: number | null
  trace_id?: string | null
  parsed_output?: Record<string, unknown> | null
  created_at?: string | null
}

export interface TraceItem {
  id: string
  title: string
  timestamp: string
  status: 'success' | 'error' | 'warning'
  latency_ms: number | null
  model: string | null
  provider: string | null
  input_tokens: number | null
  output_tokens: number | null
  total_tokens: number | null
  cost_usd: number | null
  trace_id: string | null
  response: AskResponse | null
  fallback_used?: boolean
  fallback_info?: FallbackInfo | null
}
