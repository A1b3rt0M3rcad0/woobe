import { getToken } from '@/lib/auth/token'
import { SseFrameParser, parseSseJson, type SseFrame } from './sse'
import type {
  AgentActivityInfo,
  AskRequest,
  AskResponse,
  ExecutionDiagnostics,
  ExecutionEvent,
  FallbackEventInfo,
  SourceInfo,
  StreamTokenInfo,
  ToolCallInfo,
  UsageInfo,
} from './types'

const BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'
const PROTOCOL_VERSION = 1

export interface TokenRetractInfo {
  phase?: string | null
  reason?: string | null
  content_length: number
  token_count?: number | null
  provider?: string | null
  model?: string | null
}

export interface StreamCallbacks {
  onToken: (token: StreamTokenInfo) => void
  onSources: (sources: SourceInfo[]) => void
  onMeta: (meta: { session_id?: string | null; trace_id?: string | null; request_id?: string | null }) => void
  onDone: (response: Partial<AskResponse>) => void
  onError: (error: Error) => void
  onFallback?: (info: FallbackEventInfo) => void
  onToolCall?: (info: ToolCallInfo) => void
  onToolCallStarted?: (info: ToolCallInfo) => void
  onToolCallCompleted?: (info: ToolCallInfo) => void
  onAgentActivity?: (info: AgentActivityInfo) => void
  onInternalToken?: (token: StreamTokenInfo) => void
  onTokenRetract?: (info: TokenRetractInfo) => void
  onUsage?: (usage: UsageInfo) => void
  onHeartbeat?: (event: Record<string, unknown>) => void
  onCancelled?: (event: Record<string, unknown>) => void
  onUnknownEvent?: (type: string, event: Record<string, unknown>) => void
  onProtocolError?: (message: string, frame?: SseFrame) => void
}

function numberOrNull(value: unknown): number | null {
  return typeof value === 'number' && Number.isFinite(value) ? value : null
}

function usageOf(value: unknown): UsageInfo | null {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return null
  const item = value as Record<string, unknown>
  return {
    input_tokens: numberOrNull(item.input_tokens),
    output_tokens: numberOrNull(item.output_tokens),
    total_tokens: numberOrNull(item.total_tokens),
    cost_usd: numberOrNull(item.cost_usd),
  }
}

function tokenOf(item: Record<string, unknown>): StreamTokenInfo {
  return {
    content: typeof item.content === 'string' ? item.content : '',
    visibility: item.visibility === 'internal' || item.visibility === 'debug' ? item.visibility : 'assistant',
    channel: typeof item.channel === 'string' ? item.channel : 'final',
    phase: typeof item.phase === 'string' ? item.phase : null,
    provider: typeof item.provider === 'string' ? item.provider : null,
    model: typeof item.model === 'string' ? item.model : null,
    redacted: typeof item.redacted === 'boolean' ? item.redacted : null,
  }
}

function activityOf(item: Record<string, unknown>): AgentActivityInfo {
  return {
    status: typeof item.status === 'string' ? item.status : 'thinking',
    phase: typeof item.phase === 'string' ? item.phase : null,
    message: typeof item.message === 'string' ? item.message : null,
    tool_name: typeof item.tool_name === 'string' ? item.tool_name : null,
    provider: typeof item.provider === 'string' ? item.provider : null,
    model: typeof item.model === 'string' ? item.model : null,
  }
}

function tokenRetractOf(item: Record<string, unknown>): TokenRetractInfo {
  return {
    phase: typeof item.phase === 'string' ? item.phase : null,
    reason: typeof item.reason === 'string' ? item.reason : null,
    content_length: numberOrNull(item.content_length) ?? 0,
    token_count: numberOrNull(item.token_count),
    provider: typeof item.provider === 'string' ? item.provider : null,
    model: typeof item.model === 'string' ? item.model : null,
  }
}

function toolOf(item: Record<string, unknown>): ToolCallInfo {
  return {
    tool_call_id: typeof item.tool_call_id === 'string' ? item.tool_call_id : null,
    tool_name: typeof item.tool_name === 'string' ? item.tool_name : '',
    input: item.input ?? null,
    output: item.output ?? null,
    duration_ms: numberOrNull(item.duration_ms) ?? undefined,
    success: typeof item.success === 'boolean' ? item.success : undefined,
    status: typeof item.status === 'string' ? item.status : null,
    latency_ms: numberOrNull(item.latency_ms),
    error: typeof item.error === 'string' ? item.error : null,
  }
}

function responseOf(item: Record<string, unknown>): AskResponse {
  return {
    answer: typeof item.answer === 'string' ? item.answer : '',
    session_id: typeof item.session_id === 'string' ? item.session_id : null,
    message_id: typeof item.message_id === 'string' ? item.message_id : null,
    usage: usageOf(item.usage),
    sources: Array.isArray(item.sources) ? item.sources as SourceInfo[] : [],
    tool_calls: Array.isArray(item.tool_calls) ? item.tool_calls as ToolCallInfo[] : [],
    trace_id: typeof item.trace_id === 'string' ? item.trace_id : null,
    model: typeof item.model === 'string' ? item.model : null,
    provider: typeof item.provider === 'string' ? item.provider : null,
    fallback_used: item.fallback_used === true,
    fallback_info: (item.fallback_info ?? null) as AskResponse['fallback_info'],
    latency_ms: numberOrNull(item.latency_ms),
    ttft_ms: numberOrNull(item.ttft_ms),
    parsed_output: (item.parsed_output ?? null) as Record<string, unknown> | null,
    output_parse_error: typeof item.output_parse_error === 'string' ? item.output_parse_error : null,
    execution_events: Array.isArray(item.execution_events) ? item.execution_events as ExecutionEvent[] : [],
    diagnostics: (item.diagnostics ?? null) as ExecutionDiagnostics | null,
  }
}

function dispatch(frame: SseFrame, callbacks: StreamCallbacks): boolean {
  const item = parseSseJson(frame)
  if (!item) {
    callbacks.onProtocolError?.('Invalid JSON in SSE data field', frame)
    return false
  }
  if (item.protocol_version != null && item.protocol_version !== PROTOCOL_VERSION) {
    callbacks.onProtocolError?.(`Unsupported SSE protocol version: ${String(item.protocol_version)}`, frame)
  }
  const type = typeof item.type === 'string' ? item.type : frame.event || 'unknown'
  if (type === 'token') callbacks.onToken(tokenOf(item))
  else if (type === 'token_retract') callbacks.onTokenRetract?.(tokenRetractOf(item))
  else if (type === 'internal_token') callbacks.onInternalToken?.(tokenOf(item))
  else if (type === 'agent_activity') callbacks.onAgentActivity?.(activityOf(item))
  else if (type === 'sources') callbacks.onSources(Array.isArray(item.sources) ? item.sources as SourceInfo[] : [])
  else if (type === 'meta') callbacks.onMeta({
    session_id: typeof item.session_id === 'string' ? item.session_id : null,
    trace_id: typeof item.trace_id === 'string' ? item.trace_id : null,
    request_id: typeof item.request_id === 'string' ? item.request_id : null,
  })
  else if (type === 'usage') {
    const usage = usageOf(item.usage)
    if (usage) callbacks.onUsage?.(usage)
  } else if (type === 'fallback') callbacks.onFallback?.({
    primary_provider: typeof item.primary_provider === 'string' ? item.primary_provider : '',
    primary_model: typeof item.primary_model === 'string' ? item.primary_model : '',
    fallback_provider: typeof item.fallback_provider === 'string' ? item.fallback_provider : '',
    fallback_model: typeof item.fallback_model === 'string' ? item.fallback_model : '',
    error: typeof item.error === 'string' ? item.error : 'Unknown error',
  })
  else if (type === 'tool_call_started') callbacks.onToolCallStarted?.(toolOf(item))
  else if (type === 'tool_call_completed') {
    const tool = toolOf(item)
    callbacks.onToolCallCompleted?.(tool)
    callbacks.onToolCall?.(tool)
  } else if (type === 'heartbeat') callbacks.onHeartbeat?.(item)
  else if (type === 'done') {
    callbacks.onDone(responseOf(item))
    return true
  } else if (type === 'error') {
    callbacks.onError(new Error(typeof item.message === 'string' ? item.message : 'Stream error'))
    return true
  } else if (type === 'cancelled') {
    callbacks.onCancelled?.(item)
    return true
  } else callbacks.onUnknownEvent?.(type, item)
  return false
}

export async function askStreamV1(
  data: AskRequest,
  callbacks: StreamCallbacks,
  signal?: AbortSignal,
): Promise<void> {
  const token = getToken()
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    Accept: 'text/event-stream',
  }
  if (token) headers.Authorization = `Bearer ${token}`

  const response = await fetch(`${BASE_URL}/runtime/ask/stream`, {
    method: 'POST', headers, body: JSON.stringify(data), signal,
  })
  if (!response.ok) throw new Error(`Stream request failed (${response.status})`)
  if (!response.body) throw new Error('Streaming response body is unavailable')

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  const parser = new SseFrameParser()
  let terminal = false
  const consume = (frames: SseFrame[]) => {
    for (const frame of frames) if (dispatch(frame, callbacks)) terminal = true
  }

  while (!terminal) {
    const { done, value } = await reader.read()
    if (done) break
    consume(parser.push(decoder.decode(value, { stream: true })))
  }
  consume(parser.finish(decoder.decode()))
  if (!terminal && !signal?.aborted) throw new Error('Stream ended without a terminal event')
}
