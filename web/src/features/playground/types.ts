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
}

export interface UsageInfo {
  input_tokens: number | null
  output_tokens: number | null
  total_tokens?: number | null
  cost_usd: number | null
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
