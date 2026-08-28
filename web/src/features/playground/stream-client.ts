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
const FINAL_PHASES = new Set([
  'response_generation',
  'capability_response_generation',
  'final_response_generation',
])
const PROVIDER_CONTROL_TOKENS = ['<｜end▁of▁sentence｜>', '<|endoftext|>', '<|eot_id|>']
const TERMINAL_RUN_STATUSES = new Set(['completed', 'failed', 'cancelled', 'timed_out', 'uncertain'])
const MAX_VISUAL_FRAMES_PER_PAINT = 6
const TERMINAL_STREAM_EVENTS = new Set(['done', 'error', 'cancelled'])

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
  onMeta: (meta: { session_id?: string | null; trace_id?: string | null; request_id?: string | null; run_id?: string | null }) => void
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
  onRunState?: (state: Record<string, unknown>) => void
  onUnknownEvent?: (type: string, event: Record<string, unknown>) => void
  onProtocolError?: (message: string, frame?: SseFrame) => void
}

interface RuntimeClientState {
  runId: string | null
  output: string
  sequence: number | null
}

function stringOrNull(value: unknown): string | null {
  return typeof value === 'string' ? value : null
}

function numberOrNull(value: unknown): number | null {
  return typeof value === 'number' && Number.isFinite(value) ? value : null
}

function logicalSequence(frame: SseFrame, item: Record<string, unknown>): number | null {
  const payloadSequence = numberOrNull(item.sequence)
  if (payloadSequence !== null && Number.isInteger(payloadSequence) && payloadSequence >= 0) {
    return payloadSequence
  }
  if (frame.id && /^\d+$/.test(frame.id)) return Number(frame.id)
  return null
}

function acceptSequence(
  frame: SseFrame,
  item: Record<string, unknown>,
  type: string,
  callbacks: StreamCallbacks,
  state: RuntimeClientState,
): boolean {
  const sequence = logicalSequence(frame, item)
  if (sequence === null) return true

  if (type === 'run.state') {
    if (state.sequence !== null && sequence < state.sequence) return false
    state.sequence = sequence
    return true
  }

  if (state.sequence !== null) {
    if (sequence <= state.sequence) return false
    const expected = state.sequence + 1
    if (sequence !== expected) {
      const message = `Runtime stream sequence gap: expected ${expected}, received ${sequence}`
      callbacks.onProtocolError?.(message, frame)
      throw new Error(message)
    }
  }
  state.sequence = sequence
  return true
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
  return FINAL_PHASES.has(phase) || phase.startsWith('tool_followup_')
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

function frameType(frame: SseFrame): string {
  const item = parseSseJson(frame)
  return typeof item?.type === 'string' ? item.type : frame.event || 'unknown'
}

function isVisualStreamFrame(frame: SseFrame): boolean {
  const type = frameType(frame)
  return type === 'token' || type === 'token_retract' || type === 'run.state'
}

function waitForBrowserPaint(): Promise<void> {
  if (typeof requestAnimationFrame === 'function') {
    return new Promise((resolve) => requestAnimationFrame(() => resolve()))
  }
  return new Promise((resolve) => setTimeout(resolve, 0))
}

function reconcileRunState(
  item: Record<string, unknown>,
  callbacks: StreamCallbacks,
  state: RuntimeClientState,
): boolean {
  const runId = stringOrNull(item.run_id)
  if (runId) state.runId = runId
  callbacks.onMeta({
    run_id: runId,
    session_id: stringOrNull(item.session_id),
    trace_id: stringOrNull(item.trace_id),
  })
  callbacks.onRunState?.(item)

  const output = typeof item.output === 'string' ? sanitizeAssistantContent(item.output) : ''
  if (output !== state.output) {
    if (output.startsWith(state.output)) {
      const suffix = output.slice(state.output.length)
      if (suffix) callbacks.onToken({
        content: suffix,
        visibility: 'assistant',
        channel: 'final',
        phase: 'final_response_generation',
        provider: null,
        model: null,
        redacted: null,
      })
    } else {
      if (state.output.length) callbacks.onTokenRetract?.({
        content_length: state.output.length,
        reason: 'reattach_state_replace',
      })
      if (output) callbacks.onToken({
        content: output,
        visibility: 'assistant',
        channel: 'final',
        phase: 'final_response_generation',
        provider: null,
        model: null,
        redacted: null,
      })
    }
    state.output = output
  }

  const status = stringOrNull(item.status) ?? ''
  if (!TERMINAL_RUN_STATUSES.has(status)) return false
  if (status === 'completed') {
    const result = item.result && typeof item.result === 'object' && !Array.isArray(item.result)
      ? item.result as Record<string, unknown>
      : {}
    callbacks.onDone(responseOf({
      ...result,
      answer: typeof result.answer === 'string' ? result.answer : output,
      session_id: result.session_id ?? item.session_id,
      trace_id: result.trace_id ?? item.trace_id,
      usage: result.usage ?? item.usage,
      parsed_output: result.parsed_output ?? item.parsed_output,
      output_parse_error: result.output_parse_error ?? item.output_parse_error,
    }))
  } else if (status === 'cancelled') callbacks.onCancelled?.(item)
  else callbacks.onError(new Error(
    typeof item.message === 'string'
      ? item.message
      : typeof item.failure_detail === 'string'
        ? item.failure_detail
        : 'Run failed',
  ))
  return true
}

function dispatch(frame: SseFrame, callbacks: StreamCallbacks, state: RuntimeClientState): boolean {
  const item = parseSseJson(frame)
  if (!item) {
    callbacks.onProtocolError?.('Invalid JSON in SSE data field', frame)
    return false
  }
  if (item.protocol_version != null && item.protocol_version !== PROTOCOL_VERSION) {
    callbacks.onProtocolError?.(`Unsupported SSE protocol version: ${String(item.protocol_version)}`, frame)
  }

  const type = typeof item.type === 'string' ? item.type : frame.event || 'unknown'
  if (!acceptSequence(frame, item, type, callbacks, state)) return false
  if (type === 'run.state') return reconcileRunState(item, callbacks, state)
  if (type === 'run.progress') return false
  if (type === 'run.realtime_unavailable') {
    callbacks.onUnknownEvent?.(type, item)
    return false
  }
  if (type === 'token') {
    const text = streamTextOf(item)
    if (isFinalStreamText(text)) {
      state.output += text.content
      callbacks.onToken(text)
    } else callbacks.onInternalToken?.({ ...text, visibility: 'internal', redacted: true })
  } else if (type === 'internal_token') callbacks.onInternalToken?.(streamTextOf(item))
  else if (type === 'token_retract') {
    const retract = retractOf(item)
    if (retract.content_length > 0) state.output = state.output.slice(0, Math.max(0, state.output.length - retract.content_length))
    callbacks.onTokenRetract?.(retract)
  }
  else if (type === 'agent_activity') callbacks.onAgentActivity?.(activityOf(item))
  else if (type === 'sources') callbacks.onSources(Array.isArray(item.sources) ? item.sources as SourceInfo[] : [])
  else if (type === 'meta') {
    const runId = stringOrNull(item.run_id)
    if (runId) state.runId = runId
    callbacks.onMeta({
      run_id: runId,
      session_id: stringOrNull(item.session_id),
      trace_id: stringOrNull(item.trace_id),
      request_id: stringOrNull(item.request_id),
    })
  }
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
    const response = responseOf(item)
    if (response.answer) state.output = response.answer
    callbacks.onDone(response)
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

async function consumeResponse(
  response: Response,
  callbacks: StreamCallbacks,
  state: RuntimeClientState,
  signal: AbortSignal | undefined,
): Promise<boolean> {
  if (!response.body) throw new Error('Streaming response body is unavailable')
  const headerRunId = response.headers.get('X-Woobe-Run-ID')
  if (headerRunId) state.runId = headerRunId

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  const parser = new SseFrameParser()
  let terminal = false
  let visualFramesSincePaint = 0

  const consume = async (frames: SseFrame[]) => {
    for (const frame of frames) {
      const type = frameType(frame)
      if (TERMINAL_STREAM_EVENTS.has(type) && visualFramesSincePaint > 0) {
        visualFramesSincePaint = 0
        await waitForBrowserPaint()
      }

      if (dispatch(frame, callbacks, state)) {
        terminal = true
        return
      }
      if (!isVisualStreamFrame(frame)) continue

      visualFramesSincePaint += 1
      if (type === 'run.state' || visualFramesSincePaint >= MAX_VISUAL_FRAMES_PER_PAINT) {
        visualFramesSincePaint = 0
        await waitForBrowserPaint()
      }
    }
  }

  try {
    while (!terminal) {
      const { done, value } = await reader.read()
      if (done) break
      await consume(parser.push(decoder.decode(value, { stream: true })))
    }
    await consume(parser.finish(decoder.decode()))
    return terminal
  } finally {
    if (terminal || signal?.aborted) await reader.cancel().catch(() => undefined)
  }
}

async function requestNewRun(
  data: AskRequest,
  callbacks: StreamCallbacks,
  state: RuntimeClientState,
  signal: AbortSignal | undefined,
  hasRetriedAuth: boolean,
): Promise<boolean> {
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
    return requestNewRun(data, callbacks, state, signal, true)
  }
  if (!response.ok) throw new Error(`Stream request failed (${response.status})`)
  return consumeResponse(response, callbacks, state, signal)
}

async function requestReattach(
  runId: string,
  callbacks: StreamCallbacks,
  state: RuntimeClientState,
  signal: AbortSignal | undefined,
  hasRetriedAuth: boolean,
): Promise<boolean> {
  const response = await fetch(`${BASE_URL}/runtime/runs/${runId}/stream`, {
    method: 'GET',
    headers: { Accept: 'text/event-stream' },
    credentials: 'include',
    signal,
  })
  if (response.status === 401 && !hasRetriedAuth) {
    await refreshAuthSession()
    return requestReattach(runId, callbacks, state, signal, true)
  }
  if (!response.ok) throw new Error(`Run reattach failed (${response.status})`)
  return consumeResponse(response, callbacks, state, signal)
}

export async function reattachAgentRunV1(
  runId: string,
  callbacks: StreamCallbacks,
  signal?: AbortSignal,
): Promise<void> {
  const state: RuntimeClientState = { runId, output: '', sequence: null }
  for (let attempt = 0; attempt < 4; attempt += 1) {
    if (signal?.aborted) throw new DOMException('Agent stream aborted', 'AbortError')
    try {
      const terminal = await requestReattach(runId, callbacks, state, signal, false)
      if (terminal) return
    } catch (error) {
      if (signal?.aborted || attempt === 3) throw error
    }
    if (attempt < 3) await new Promise((resolve) => setTimeout(resolve, 250 * (attempt + 1)))
  }
  throw new Error('Run reattach ended without a terminal event')
}

export async function askStreamV1(
  data: AskRequest,
  callbacks: StreamCallbacks,
  signal?: AbortSignal,
): Promise<void> {
  const state: RuntimeClientState = { runId: null, output: '', sequence: null }
  for (let attempt = 0; attempt < 4; attempt += 1) {
    if (signal?.aborted) throw new DOMException('Agent stream aborted', 'AbortError')
    try {
      const terminal = state.runId
        ? await requestReattach(state.runId, callbacks, state, signal, false)
        : await requestNewRun(data, callbacks, state, signal, false)
      if (terminal) return
      if (!state.runId) throw new Error('Stream ended before the canonical Run id was observed')
    } catch (error) {
      if (signal?.aborted || attempt === 3) throw error
      // Once a Run id exists, all retries are GET observers. Never POST another
      // logical execution to recover a transport failure.
      if (!state.runId) throw error
    }
    await new Promise((resolve) => setTimeout(resolve, 250 * (attempt + 1)))
  }
  throw new Error('Stream ended without a terminal event')
}
