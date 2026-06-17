export type TraceStatus = 'pending' | 'running' | 'completed' | 'failed' | 'cancelled'

export interface FallbackInfo {
  primary_model: string | null
  primary_provider: string | null
  primary_error: string
  fallback_model: string | null
  fallback_provider: string | null
  fallback_credential_id: string | null
}

export interface Trace {
  id: string
  project_id: string
  agent_id?: string
  session_id?: string
  status: string
  provider?: string
  model?: string
  fallback_used?: boolean
  total_latency_ms?: number
  total_cost_usd?: number
  error?: string
  data?: Record<string, unknown>
  created_at?: string
}

export interface TraceEvent {
  id: string
  trace_id: string
  event_type: string
  latency_ms?: number | null
  cost_usd?: number | null
  payload?: Record<string, unknown> | null
  payload_ref?: string | null
  created_at?: string | null
}

export interface TraceDetail extends Trace {
  events: TraceEvent[]
}

export interface TraceSource {
  document_id?: string | null
  document_title?: string | null
  chunk_id?: string | null
  page_number?: number | null
  score?: number | null
  content_preview?: string | null
}

export interface TraceToolCall {
  tool_name: string
  input?: unknown
  output?: unknown
  duration_ms?: number | null
  success?: boolean | null
  status?: string | null
  latency_ms?: number | null
  error?: string | null
}

export interface TraceUsage {
  inputTokens: number | null
  outputTokens: number | null
  totalTokens: number | null
  costUsd: number | null
}

export interface TraceDiagnostics {
  schemaVersion: number
  agentRuntimeLatencyMs: number | null
  toolRuntimeLatencyMs: number | null
  toolHttpLatencyMs: number | null
  toolOverheadLatencyMs: number | null
  nonToolRuntimeLatencyMs: number | null
  toolSharePercent: number | null
  toolCallCount: number
  successfulToolCalls: number
  failedToolCalls: number
  sourceCount: number
  answerLength: number | null
  fallbackUsed: boolean
  structuredOutput: boolean
  notes: string[]
}

export interface TraceSummary {
  id: string
  projectId: string
  agentId?: string | null
  sessionId?: string | null
  messageId?: string | null
  title: string
  status: TraceStatus
  model?: string | null
  provider?: string | null
  latencyMs?: number | null
  inputTokens?: number | null
  outputTokens?: number | null
  totalTokens?: number | null
  costUsd?: number | null
  createdAt?: string | null
  fallbackUsed?: boolean
  fallbackInfo?: FallbackInfo | null
}

export interface TraceDetailNormalized extends TraceSummary {
  usage: TraceUsage
  diagnostics: TraceDiagnostics | null
  parsedOutput: unknown | null
  outputParseError?: string | null
  sources: TraceSource[]
  toolCalls: TraceToolCall[]
  events: TraceEvent[]
}
