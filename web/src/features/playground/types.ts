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
  session_id: string
  content: string
  data?: Record<string, unknown>
}

export interface SourceInfo {
  document_title?: string
  document_id?: string
  page_number?: number
  chunk_preview?: string
  score?: number | null
}

export interface ToolCallInfo {
  tool_name: string
  input?: unknown
  output?: unknown
  duration_ms?: number
}

export interface AskResponse {
  answer: string
  session_id: string
  message_id: string
  usage?: {
    input_tokens: number | null
    output_tokens: number | null
    cost_usd: number | null
  } | null
  sources?: SourceInfo[] | null
  tool_calls?: ToolCallInfo[] | null
  latency_ms?: number | null
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
