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

export interface AskResponse {
  answer: string
  session_id: string
  message_id: string
  usage?: {
    input_tokens: number
    output_tokens: number
    cost_usd: number
  }
}

export interface Message {
  id: string
  session_id: string
  role: string
  content: string
  input_tokens?: number
  output_tokens?: number
  cost_usd?: number
  data?: Record<string, unknown>
  created_at: string
  updated_at?: string
}
