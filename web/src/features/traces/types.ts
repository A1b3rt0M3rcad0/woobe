export type TraceStatus = 'pending' | 'running' | 'completed' | 'failed' | 'cancelled'

export interface ModelBindingInfo {
  provider_model_id?: string | null
  provider_credential_id?: string | null
  provider?: string | null
  model?: string | null
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

export interface Trace {
  id: string
  project_id: string
  agent_id?: string
  session_id?: string
  network_id?: string | null
  network_execution_id?: string | null
  network_session_id?: string | null
  network_version_id?: string | null
  status: string
  provider?: string
  model?: string
  provider_model_id?: string | null
  provider_credential_id?: string | null
  fallback_provider_model_id?: string | null
  fallback_credential_id?: string | null
  fallback_used?: boolean
  total_latency_ms?: number
  total_cost_usd?: number | null
  error?: string
  data?: Record<string, unknown>
  started_at?: string | null
  ended_at?: string | null
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
  occurred_at?: string | null
  recorded_at?: string | null
  sequence?: number | null
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

export type TraceCostStatus = 'known' | 'partial' | 'unknown' | 'unknown_tokens' | 'unknown_pricing'

export interface TraceDiagnostics {
  schemaVersion: number
  agentRuntimeLatencyMs: number | null
  llmWorkLatencyMs: number | null
  llmRuntimeLatencyMs: number | null
  toolWallLatencyMs: number | null
  toolWorkLatencyMs: number | null
  toolCallDurationSumMs: number | null
  toolParallelismRatio: number | null
  toolProviderWorkMs: number | null
  toolRuntimeOverheadMs: number | null
  toolHttpLatencyMs: number | null
  toolOverheadLatencyMs: number | null
  prepareLatencyMs: number | null
  finalizationWorkLatencyMs: number | null
  persistenceLatencyMs: number | null
  otherLatencyMs: number | null
  orchestrationLatencyMs: number | null
  unaccountedLatencyMs: number | null
  toolSharePercent: number | null
  toolCallCount: number
  llmCallCount: number
  successfulToolCalls: number
  failedToolCalls: number
  usageComplete: boolean
  costStatus: TraceCostStatus
  costUsd: number | null
  sourceCount: number
  answerLength: number | null
  fallbackUsed: boolean
  structuredOutput: boolean
  providerModelId?: string | null
  providerCredentialId?: string | null
  fallbackProviderModelId?: string | null
  fallbackCredentialId?: string | null
  notes?: string[]
}

export interface TraceSummary {
  id: string
  projectId: string
  agentId?: string | null
  sessionId?: string | null
  networkId?: string | null
  networkExecutionId?: string | null
  networkSessionId?: string | null
  networkVersionId?: string | null
  messageId?: string | null
  title: string
  status: TraceStatus
  model?: string | null
  provider?: string | null
  providerModelId?: string | null
  providerCredentialId?: string | null
  fallbackProviderModelId?: string | null
  fallbackCredentialId?: string | null
  modelBinding?: ModelBindingInfo | null
  fallbackModelBinding?: ModelBindingInfo | null
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
  diagnostics?: TraceDiagnostics | null
  parsedOutput: unknown | null
  outputParseError?: string | null
  sources: TraceSource[]
  toolCalls: TraceToolCall[]
  events: TraceEvent[]
}
