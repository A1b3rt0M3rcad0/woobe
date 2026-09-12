export type AgentSessionEnvironment = 'draft' | 'staging' | 'production'

export interface SessionListItem {
  id: string
  project_id: string
  agent_id: string
  runtime_environment: AgentSessionEnvironment
  opened_release_id?: string | null
  opened_release_version?: string | null
  status: string
  mode: string
  data?: Record<string, unknown> | null
  last_message_at: string | null
  created_at: string | null
  message_count: number
}

export interface SessionListPage {
  items: SessionListItem[]
  next_cursor: string | null
  has_next: boolean
}

export interface Session {
  id: string
  project_id: string
  agent_id: string
  runtime_environment: AgentSessionEnvironment
  opened_release_id?: string | null
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
  runtime_environment?: AgentSessionEnvironment
  external_session_id?: string
  tenant_id?: string
  user_id?: string
  mode?: string
  data?: Record<string, unknown>
}

export type AgentExecutionContext = 'playground' | 'staging' | 'production'

export interface AskRequest {
  project_id: string
  agent_id: string
  message: string
  session_id?: string | null
  tenant_id?: string
  user_id?: string
  metadata?: Record<string, unknown>
  execution_context?: AgentExecutionContext
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
  tool_call_id?: string | null
  tool_name: string
  input?: unknown
  output?: unknown
  duration_ms?: number | null
  success?: boolean | null
  status?: string | null
  latency_ms?: number | null
  error?: string | null
  error_code?: string | null
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
  primary_provider_model_id?: string | null
  primary_credential_id?: string | null
  primary_error: string
  fallback_model: string | null
  fallback_provider: string | null
  fallback_provider_model_id?: string | null
  fallback_credential_id: string | null
}

export interface FallbackEventInfo {
  primary_provider: string
  primary_model: string
  fallback_provider: string
  fallback_model: string
  error: string
  primary_provider_model_id?: string | null
  fallback_provider_model_id?: string | null
}

export type StreamTokenVisibility = 'assistant' | 'internal' | 'debug'
export type StreamTokenChannel = 'final' | 'reasoning' | 'tool_planning' | 'system' | string

export interface StreamTokenInfo {
  content: string
  visibility: StreamTokenVisibility
  channel: StreamTokenChannel
  phase?: string | null
  provider?: string | null
  model?: string | null
  redacted?: boolean | null
}

export type AgentActivityStatus =
  | 'thinking'
  | 'working'
  | 'planning_tools'
  | 'calling_tool'
  | 'processing_tool_result'
  | 'generating_answer'
  | 'formatting_response'

export interface AgentActivityInfo {
  status: AgentActivityStatus | string
  phase?: string | null
  message?: string | null
  tool_name?: string | null
  provider?: string | null
  model?: string | null
}

export interface ExecutionEvent {
  schema_version: number
  event_id: string
  trace_id: string
  root_span_id: string
  span_id: string
  parent_span_id: string | null
  sequence: number
  event_type: string
  phase?: string | null
  status?: string | null
  occurred_at: string
  started_at?: string | null
  ended_at?: string | null
  duration_ms?: number | null
  attributes: Record<string, unknown>
}

export interface ExecutionDiagnostics {
  schema_version: number
  total_latency_ms: number
  prepare_latency_ms: number
  llm_runtime_latency_ms: number
  tool_wall_latency_ms: number
  tool_call_duration_sum_ms: number
  tool_http_latency_ms: number
  persistence_latency_ms: number
  orchestration_latency_ms: number
  llm_call_count: number
  tool_call_count: number
  usage_complete: boolean
  cost_status: 'known' | 'unknown'
  provider_model_id?: string | null
  provider_credential_id?: string | null
  fallback_provider_model_id?: string | null
  fallback_credential_id?: string | null
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
  provider_model_id?: string | null
  provider_credential_id?: string | null
  fallback_provider_model_id?: string | null
  fallback_credential_id?: string | null
  fallback_used: boolean
  fallback_info?: FallbackInfo | null
  latency_ms: number | null
  ttft_ms?: number | null
  parsed_output?: Record<string, unknown> | null
  output_parse_error?: string | null
  execution_events?: ExecutionEvent[]
  diagnostics?: ExecutionDiagnostics | null
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
  activity?: AgentActivityInfo | null
  model?: string | null
  provider?: string | null
  latency_ms?: number | null
  trace_id?: string | null
  parsed_output?: Record<string, unknown> | null
  output_parse_error?: string | null
  created_at?: string | null
}

export interface RawStreamEvent {
  type: string
  timestamp: string
  payload: unknown
}

export interface TraceItem {
  id: string
  run_id?: string | null
  title: string
  timestamp: string
  status: 'success' | 'error' | 'warning' | 'running' | 'pending' | 'cancelled'
  latency_ms: number | null
  model: string | null
  provider: string | null
  provider_model_id?: string | null
  provider_credential_id?: string | null
  fallback_provider_model_id?: string | null
  fallback_credential_id?: string | null
  input_tokens: number | null
  output_tokens: number | null
  total_tokens: number | null
  cost_usd: number | null
  trace_id: string | null
  response: AskResponse | null
  fallback_used?: boolean
  fallback_info?: FallbackInfo | null
  project_id?: string
  agent_id?: string
}
