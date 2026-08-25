import { ensureCsrfToken, getCsrfHeaders, refreshAuthSession } from '@/lib/api/client'
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
const FINAL_PHASES = new Set(['response_generation', 'final_response_generation'])
const PROVIDER_CONTROL_TOKENS = ['<｜end▁of▁sentence｜>', '<|endoftext|>', '<|eot_id|>']

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

function stringOrNull(value: unknown): string | null {
  return typeof value === 'string' ? value : null
}

function numberOrNull(value: unknown): number | null {
  return typeof value === 'number' && Number.isFinite(value) ? value : null
}

function sanitizeAssistantContent(value: string): string {
  return PROVIDER_CONTROL_TOKENS.reduce(
    (content, token) => content.split(token).join(''),
    value,
  )
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

function streamTextOf(item: Record<string, unknown>): StreamTokenInfo {
  return {
    content: typeof item.content === 'string' ? sanitizeAssistantContent(item.content) : '',
    visibility: item.visibility === 'internal' || item.visibility === 'debug' ? item.visibility : 'assistant',
    channel: typeof item.channel === 'string' ? item.channel : 'final',
    phase: typeof item.phase === 'string' ? item.phase : null,
    provider: typeof item.provider === 'string' ? item.provider : null,
    model: typeof item.model === 'string' ? item.model : null,
    redacted: typeof item.redacted === 'boolean' ? item.redacted : null,
  }
}

function isFinalPhase(phase: string): boolean {
  return (
    FINAL_PHASES.has(phase)
    || phase === 'tool_planning'
    || phase.startsWith('tool_followup_')
  )
}

function isFinalStreamText(item: StreamTokenInfo): boolean {
  return (
    item.visibility === 'assistant' &&
    item.channel === 'final' &&
    typeof item.phase === 'string' &&
    isFinalPhase(item.phase)
  )
}

function activityMessage(status: string, toolName?: string | null): string {
  if (status === 'planning_tools') return 'Checking whether tools are needed...'
  if (status === 'calling_tool') return toolName ? `Calling tool: ${toolName}...` : 'Calling tool...'
  if (status === 'processing_tool_result') return 'Processing tool result...'
  if (status === 'generating_answer') return 'Generating response...'
  if (status === 'formatting_response') return 'Formatting structured response...'
  return 'Working...'
}

function activityOf(item: Record<string, unknown>): AgentActivityInfo {
  const status = typeof item.status === 'string' ? item.status : 'working'
  const toolName = typeof item.tool_name === 'string' ? item.tool_name : null
  return {
    status,
    phase: stringOrNull(item.phase),
    message: activityMessage(status, toolName),
    tool_name: toolName,
    provider: stringOrNull(item.provider),
    model: stringOrNull(item.model),
  }
}

function retractOf(item: Record<string, unknown>): TokenRetractInfo {
  return {
    phase: stringOrNull(item.phase),
    reason: stringOrNull(item.reason),
    content_length: numberOrNull(item.content_length) ?? 0,
    token_count: numberOrNull(item.token_count),
    provider: stringOrNull(item.provider),
    model: stringOrNull(item.model),
  }
}

function toolOf(item: Record<string, unknown>): ToolCallInfo {
  return {
    tool_call_id: stringOrNull(item.tool_call_id),
    tool_name: typeof item.tool_name === 'string' ? item.tool_name : '',
    input: item.input ?? null,
    output: item.output ?? null,
    duration_ms: numberOrNull(item.duration_ms) ?? undefined,
    success: typeof item.success === 'boolean' ? item.success : undefined,
    status: stringOrNull(item.status),
    latency_ms: numberOrNull(item.latency_ms),
    error: stringOrNull(item.error),
  }
}

function responseOf(item: Record<string, unknown>): AskResponse {
  return {
    answer: typeof item.answer === 'string' ? sanitizeAssistantContent(item.answer) : '',
    session_id: stringOrNull(item.session_id),
    message_id: stringOrNull(item.message_id),
    usage: usageOf(item.usage),
    sources: Array.isArray(item.sources) ? item.sources as SourceInfo[] : [],
    tool_calls: Array.isArray(item.tool_calls) ? item.tool_calls as ToolCallInfo[] : [],
    trace_id: stringOrNull(item.trace_id),
    model: stringOrNull(item.model),
    provider: stringOrNull(item.provider),
    provider_model_id: stringOrNull(item.provider_model_id),
    provider_credential_id: stringOrNull(item.provider_credential_id),
    fallback_provider_model_id: stringOrNull(item.fallback_provider_model_id),
    fallback_credential_id: stringOrNull(item.fallback_credential_id),
    fallback_used: item.fallback_used === true,
    fallback_info: (item.fallback_info ?? null) as AskResponse['fallback_info'],
    latency_ms: numberOrNull(item.latency_ms),
    ttft_ms: numberOrNull(item.ttft_ms),
    parsed_output: (item.parsed_output ?? null) as Record<string, unknown> | null,
    output_parse_error: stringOrNull(item.output_parse_error),
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
  if (type === 'token') {
    const text = streamTextOf(item)
    if (isFinalStreamText(text)) callbacks.onToken(text)
    else callbacks.onInternalToken?.({ ...text, visibility: 'internal', redacted: true })
  } else if (type === 'internal_token') callbacks.onInternalToken?.(streamTextOf(item))
  else if (type === 'token_retract') callbacks.onTokenRetract?.(retractOf(item))
  else if (type === 'agent_activity') callbacks.onAgentActivity?.(activityOf(item))
  else if (type === 'sources') callbacks.onSources(Array.isArray(item.sources) ? item.sources as SourceInfo[] : [])
  else if (type === 'meta') callbacks.onMeta({
    session_id: stringOrNull(item.session_id),
    trace_id: stringOrNull(item.trace_id),
    request_id: stringOrNull(item.request_id),
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

async function runStream(
  data: AskRequest,
  callbacks: StreamCallbacks,
  signal: AbortSignal | undefined,
  hasRetriedAuth: boolean,
): Promise<void> {
  await ensureCsrfToken()
  const response = await fetch(`${BASE_URL}/runtime/ask/stream`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Accept: 'text/event-stream',
      ...getCsrfHeaders('POST'),
    },
    credentials: 'include',
    body: JSON.stringify(data),
    signal,
  })

  if (response.status === 401 && !hasRetriedAuth) {
    await refreshAuthSession()
    return runStream(data, callbacks, signal, true)
  }
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

export async function askStreamV1(
  data: AskRequest,
  callbacks: StreamCallbacks,
  signal?: AbortSignal,
): Promise<void> {
  return runStream(data, callbacks, signal, false)
}
