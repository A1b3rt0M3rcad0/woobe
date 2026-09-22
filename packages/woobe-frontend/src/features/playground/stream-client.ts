import { skillActivityLabel } from '@/features/skills/operations'
import { ensureCsrfToken, getCsrfHeaders, refreshAuthSession } from '@/lib/api/client'
import {
  RUNTIME_STREAM_MAX_ATTEMPTS,
  RuntimeStreamGapError,
  RuntimeStreamProtocolError,
  acceptRuntimeFrameSequence,
  parseRuntimeFrame,
  reconcileRuntimeOutput,
  runtimeTerminalStatus,
  waitForRuntimeRetry,
  type ParsedRuntimeFrame,
  type RuntimeSequenceState,
} from '@/lib/runtime-stream'
import { SseFrameParser, parseSseJson, type SseFrame } from './sse'
import type {
  AgentActivityInfo,
  AssistantMessageInfo,
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
const PROVIDER_CONTROL_TOKENS = ['<｜end▁of▁sentence｜>', '<|endoftext|>', '<|eot_id|>']
const TERMINAL_STREAM_EVENTS = new Set(['done', 'error', 'cancelled'])
const MAX_VISUAL_FRAMES_PER_PAINT = 6

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
  onAssistantMessageDelta?: (info: AssistantMessageInfo) => void
  onAssistantMessageCompleted?: (info: AssistantMessageInfo) => void
  onInternalToken?: (token: StreamTokenInfo) => void
  onTokenRetract?: (info: TokenRetractInfo) => void
  onUsage?: (usage: UsageInfo) => void
  onHeartbeat?: (event: Record<string, unknown>) => void
  onCancelled?: (event: Record<string, unknown>) => void
  onRunState?: (state: Record<string, unknown>) => void
  onUnknownEvent?: (type: string, event: Record<string, unknown>) => void
  onProtocolError?: (message: string, frame?: SseFrame) => void
}

interface RuntimeClientState extends RuntimeSequenceState {
  runId: string | null
  output: string
}

function stringOrNull(value: unknown): string | null {
  return typeof value === 'string' ? value : null
}

function numberOrNull(value: unknown): number | null {
  return typeof value === 'number' && Number.isFinite(value) ? value : null
}

function canonicalRuntimeFrame(frame: SseFrame): ParsedRuntimeFrame | null {
  const lines: string[] = []
  if (frame.id) lines.push(`id: ${frame.id}`)
  if (frame.event) lines.push(`event: ${frame.event}`)
  for (const line of frame.data.split('\n')) lines.push(`data: ${line}`)
  return parseRuntimeFrame(lines.join('\n'))
}

function acceptSequence(
  runtime: ParsedRuntimeFrame,
  frame: SseFrame,
  callbacks: StreamCallbacks,
  state: RuntimeClientState,
): boolean {
  try {
    return acceptRuntimeFrameSequence(runtime, state)
  } catch (error) {
    if (error instanceof RuntimeStreamGapError) {
      callbacks.onProtocolError?.(error.message, frame)
    }
    throw error
  }
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
    message_id: stringOrNull(item.message_id),
    output_mode: stringOrNull(item.output_mode),
    visibility: item.visibility === 'internal' || item.visibility === 'debug' ? item.visibility : 'assistant',
    channel: typeof item.channel === 'string' ? item.channel : 'final',
    phase: typeof item.phase === 'string' ? item.phase : null,
    provider: typeof item.provider === 'string' ? item.provider : null,
    model: typeof item.model === 'string' ? item.model : null,
    redacted: typeof item.redacted === 'boolean' ? item.redacted : null,
  }
}

function assistantMessageOf(item: Record<string, unknown>): AssistantMessageInfo | null {
  const messageId = stringOrNull(item.message_id)
  if (!messageId) return null
  return {
    message_id: messageId,
    content: typeof item.content === 'string' ? sanitizeAssistantContent(item.content) : '',
    phase: stringOrNull(item.phase),
    output_mode: 'intermediate',
    provider: stringOrNull(item.provider),
    model: stringOrNull(item.model),
    partial: typeof item.partial === 'boolean' ? item.partial : null,
    status: stringOrNull(item.status),
  }
}

function isFinalStreamText(item: StreamTokenInfo): boolean {
  // Output visibility is a runtime contract. Presentation must not duplicate
  // Strategy-specific phase knowledge.
  return (
    item.visibility === 'assistant' &&
    item.channel === 'final' &&
    typeof item.phase === 'string' &&
    item.phase.length > 0
  )
}

function activityMessage(status: string, toolName?: string | null): string {
  const skillLabel = skillActivityLabel({ tool_name: toolName, status })
  if (skillLabel) return skillLabel
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
    message: stringOrNull(item.message) ?? activityMessage(status, toolName),
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

function responseOf(item: Record<string, unknown>, sessionId: string | null): AskResponse {
  return {
    answer: typeof item.answer === 'string' ? sanitizeAssistantContent(item.answer) : '',
    session_id: sessionId,
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

function frameType(frame: SseFrame): string {
  const item = parseSseJson(frame)
  return typeof item?.type === 'string' ? item.type : frame.event || 'unknown'
}

function isVisualStreamFrame(frame: SseFrame): boolean {
  const type = frameType(frame)
  return (
    type === 'token'
    || type === 'token_retract'
    || type === 'assistant_message_delta'
    || type === 'assistant_message_completed'
    || type === 'run.state'
  )
}

function streamAbortError(): DOMException {
  return new DOMException('Agent stream aborted', 'AbortError')
}

function waitForBrowserPaint(signal: AbortSignal | undefined): Promise<void> {
  if (signal?.aborted) return Promise.reject(streamAbortError())

  const documentRef = typeof document === 'undefined' ? null : document
  if (documentRef?.visibilityState === 'hidden') return Promise.resolve()

  return new Promise((resolve, reject) => {
    let settled = false
    let frameId: number | null = null
    let timerId: ReturnType<typeof setTimeout> | null = null

    const cleanup = () => {
      signal?.removeEventListener('abort', onAbort)
      documentRef?.removeEventListener('visibilitychange', onVisibilityChange)
      if (frameId !== null && typeof cancelAnimationFrame === 'function') {
        cancelAnimationFrame(frameId)
      }
      if (timerId !== null) clearTimeout(timerId)
    }

    const finish = () => {
      if (settled) return
      settled = true
      cleanup()
      resolve()
    }

    const onAbort = () => {
      if (settled) return
      settled = true
      cleanup()
      reject(streamAbortError())
    }

    const onVisibilityChange = () => {
      if (documentRef?.visibilityState === 'hidden') finish()
    }

    signal?.addEventListener('abort', onAbort, { once: true })
    documentRef?.addEventListener('visibilitychange', onVisibilityChange)

    if (signal?.aborted) {
      onAbort()
      return
    }
    if (documentRef?.visibilityState === 'hidden') {
      finish()
      return
    }
    if (typeof requestAnimationFrame === 'function') {
      frameId = requestAnimationFrame(() => finish())
      return
    }
    timerId = setTimeout(() => finish(), 0)
  })
}

function reconcileRunState(
  runtime: ParsedRuntimeFrame,
  item: Record<string, unknown>,
  callbacks: StreamCallbacks,
  state: RuntimeClientState,
): boolean {
  const runId = runtime.kind === 'semantic' ? runtime.runId : null
  if (runId) state.runId = runId
  callbacks.onMeta({
    run_id: runId,
    session_id: runtime.kind === 'semantic' ? runtime.sessionId : null,
    trace_id: stringOrNull(item.trace_id),
  })
  callbacks.onRunState?.(item)
  if (Array.isArray(item.messages)) {
    for (const raw of item.messages) {
      if (!raw || typeof raw !== 'object' || Array.isArray(raw)) continue
      const message = assistantMessageOf(raw as Record<string, unknown>)
      if (message) callbacks.onAssistantMessageCompleted?.(message)
    }
  }

  const output = typeof item.output === 'string' ? sanitizeAssistantContent(item.output) : ''
  const reconciliation = reconcileRuntimeOutput(state.output, output)
  if (reconciliation.changed) {
    if (reconciliation.retract > 0) {
      callbacks.onTokenRetract?.({
        content_length: reconciliation.retract,
        reason: 'reattach_state_replace',
      })
    }
    if (reconciliation.append) {
      callbacks.onToken({
        content: reconciliation.append,
        visibility: 'assistant',
        channel: 'final',
        phase: 'final_response_generation',
        provider: null,
        model: null,
        redacted: null,
      })
    }
    state.output = reconciliation.output
  }

  const status = runtimeTerminalStatus(runtime)
  if (status === null) return false
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
    }, runtime.kind === 'semantic' ? runtime.sessionId : null))
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
  let runtime: ParsedRuntimeFrame | null
  try {
    runtime = canonicalRuntimeFrame(frame)
  } catch (error) {
    if (error instanceof RuntimeStreamProtocolError) {
      callbacks.onProtocolError?.(error.message, frame)
    }
    throw error
  }
  if (!runtime) {
    callbacks.onProtocolError?.('Invalid JSON in SSE data field', frame)
    return false
  }

  const item = runtime.payload
  const type = runtime.eventType
  if (runtime.kind === 'semantic') {
    state.runId = runtime.runId
    callbacks.onMeta({ run_id: runtime.runId, session_id: runtime.sessionId })
  } else if (type !== 'error') {
    if (type === 'run.realtime_unavailable') callbacks.onUnknownEvent?.(type, item)
    return false
  }
  if (!acceptSequence(runtime, frame, callbacks, state)) return false
  if (type === 'run.state') return reconcileRunState(runtime, item, callbacks, state)
  if (type === 'run.progress') return false
  if (type === 'run.realtime_unavailable') {
    callbacks.onUnknownEvent?.(type, item)
    return false
  }
  if (type === 'assistant_message_delta') {
    const message = assistantMessageOf(item)
    if (message) callbacks.onAssistantMessageDelta?.(message)
  } else if (type === 'assistant_message_completed') {
    const message = assistantMessageOf(item)
    if (message) callbacks.onAssistantMessageCompleted?.(message)
  } else if (type === 'token') {
    const text = streamTextOf(item)
    if (isFinalStreamText(text)) {
      state.output += text.content
      callbacks.onToken(text)
    } else callbacks.onInternalToken?.({ ...text, visibility: 'internal', redacted: true })
  } else if (type === 'internal_token') callbacks.onInternalToken?.(streamTextOf(item))
  else if (type === 'token_retract') {
    const retract = retractOf(item)
    if (retract.content_length > 0) {
      state.output = state.output.slice(0, Math.max(0, state.output.length - retract.content_length))
    }
    callbacks.onTokenRetract?.(retract)
  }
  else if (type === 'agent_activity') callbacks.onAgentActivity?.(activityOf(item))
  else if (type === 'sources') callbacks.onSources(Array.isArray(item.sources) ? item.sources as SourceInfo[] : [])
  else if (type === 'meta') {
    const runId = runtime.kind === 'semantic' ? runtime.runId : null
    if (runId) state.runId = runId
    callbacks.onMeta({
      run_id: runId,
      session_id: runtime.kind === 'semantic' ? runtime.sessionId : null,
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
    const response = responseOf(item, runtime.kind === 'semantic' ? runtime.sessionId : null)
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
        await waitForBrowserPaint(signal)
      }

      if (dispatch(frame, callbacks, state)) {
        terminal = true
        return
      }
      if (!isVisualStreamFrame(frame)) continue

      visualFramesSincePaint += 1
      if (type === 'run.state' || visualFramesSincePaint >= MAX_VISUAL_FRAMES_PER_PAINT) {
        visualFramesSincePaint = 0
        await waitForBrowserPaint(signal)
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
  for (let attempt = 0; attempt < RUNTIME_STREAM_MAX_ATTEMPTS; attempt += 1) {
    if (signal?.aborted) throw new DOMException('Agent stream aborted', 'AbortError')
    try {
      const terminal = await requestReattach(runId, callbacks, state, signal, false)
      if (terminal) return
    } catch (error) {
      if (signal?.aborted || attempt === RUNTIME_STREAM_MAX_ATTEMPTS - 1) throw error
    }
    if (attempt < RUNTIME_STREAM_MAX_ATTEMPTS - 1) {
      await waitForRuntimeRetry(attempt, signal)
    }
  }
  throw new Error('Run reattach ended without a terminal event')
}

export async function askStreamV1(
  data: AskRequest,
  callbacks: StreamCallbacks,
  signal?: AbortSignal,
): Promise<void> {
  const state: RuntimeClientState = { runId: null, output: '', sequence: null }
  for (let attempt = 0; attempt < RUNTIME_STREAM_MAX_ATTEMPTS; attempt += 1) {
    if (signal?.aborted) throw new DOMException('Agent stream aborted', 'AbortError')
    try {
      const terminal = state.runId
        ? await requestReattach(state.runId, callbacks, state, signal, false)
        : await requestNewRun(data, callbacks, state, signal, false)
      if (terminal) return
      if (!state.runId) throw new Error('Stream ended before the canonical Run id was observed')
    } catch (error) {
      if (signal?.aborted || attempt === RUNTIME_STREAM_MAX_ATTEMPTS - 1) throw error
      // Once a Run id exists, all retries are GET observers. Never POST another
      // logical execution to recover a transport failure.
      if (!state.runId) throw error
    }
    await waitForRuntimeRetry(attempt, signal)
  }
  throw new Error('Stream ended without a terminal event')
}
