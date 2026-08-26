import {
  API_BASE_URL,
  ensureCsrfToken,
  getCsrfHeaders,
  refreshAuthSession,
} from '@/lib/api/client'
import { createUuid } from '@/lib/uuid'

import type { NetworkRuntimeEvent } from './types'

export interface NetworkStreamInput {
  networkId: string
  projectId: string
  networkSessionId: string
  message: string
  idempotencyKey?: string
  executionId?: string
  lastEventId?: number
  expectedDraftRevision?: number
}

type PreparedNetworkStreamInput = Omit<NetworkStreamInput, 'idempotencyKey'> & {
  idempotencyKey: string
}

export interface NetworkStreamCallbacks {
  onEvent: (eventType: string, event: NetworkRuntimeEvent) => void
  onHeartbeat?: (event: NetworkRuntimeEvent) => void
  onExecutionId?: (executionId: string) => void
}

interface ParsedSseEvent {
  event: string
  id?: string
  data: string
}

interface NetworkStreamState {
  output: string
  sequence: number | null
}

const TERMINAL_NETWORK_EVENTS = new Set([
  'execution_completed',
  'execution_failed',
  'execution_cancelled',
])
const TERMINAL_RUN_STATUSES = new Set(['completed', 'failed', 'cancelled', 'timed_out', 'uncertain'])

export function isTerminalNetworkEvent(eventType: string) {
  return TERMINAL_NETWORK_EVENTS.has(eventType)
}

export function parseSseBlock(block: string): ParsedSseEvent | null {
  let event = 'message'
  let id: string | undefined
  const data: string[] = []
  for (const rawLine of block.split(/\r?\n/)) {
    const line = rawLine.trimEnd()
    if (!line || line.startsWith(':')) continue
    const separator = line.indexOf(':')
    const field = separator === -1 ? line : line.slice(0, separator)
    const value = separator === -1 ? '' : line.slice(separator + 1).replace(/^ /, '')
    if (field === 'event') event = value
    else if (field === 'id') id = value
    else if (field === 'data') data.push(value)
  }
  if (!data.length) return null
  return { event, id, data: data.join('\n') }
}

function eventData(event: NetworkRuntimeEvent): Record<string, unknown> {
  return event.data && typeof event.data === 'object' ? event.data : {}
}

function syntheticEvent(
  source: NetworkRuntimeEvent,
  data: Record<string, unknown>,
): NetworkRuntimeEvent {
  return { ...source, data }
}

function eventSequence(parsed: ParsedSseEvent, event: NetworkRuntimeEvent): number | null {
  if (typeof event.sequence === 'number' && Number.isInteger(event.sequence) && event.sequence >= 0) {
    return event.sequence
  }
  if (parsed.id && /^\d+$/.test(parsed.id)) return Number(parsed.id)
  return null
}

function acceptSequence(
  parsed: ParsedSseEvent,
  event: NetworkRuntimeEvent,
  streamState: NetworkStreamState,
): boolean {
  const sequence = eventSequence(parsed, event)
  if (sequence === null) return true
  event.sequence = sequence

  if (parsed.event === 'run.state') {
    if (streamState.sequence !== null && sequence < streamState.sequence) return false
    streamState.sequence = sequence
    return true
  }

  if (streamState.sequence !== null) {
    if (sequence <= streamState.sequence) return false
    const expected = streamState.sequence + 1
    if (sequence !== expected) {
      throw new Error(`Network stream sequence gap: expected ${expected}, received ${sequence}`)
    }
  }
  streamState.sequence = sequence
  return true
}

function applyRunState(
  event: NetworkRuntimeEvent,
  callbacks: NetworkStreamCallbacks,
  streamState: NetworkStreamState,
): boolean {
  const data = eventData(event)
  const output = typeof data.output === 'string' ? data.output : ''
  if (output !== streamState.output) {
    if (output.startsWith(streamState.output)) {
      const suffix = output.slice(streamState.output.length)
      if (suffix) {
        callbacks.onEvent('token', syntheticEvent(event, {
          content: suffix,
          visibility: 'assistant',
          channel: 'final',
          phase: 'final_response_generation',
        }))
      }
    } else {
      if (streamState.output.length) {
        callbacks.onEvent('token_retract', syntheticEvent(event, {
          content_length: streamState.output.length,
          reason: 'reattach_state_replace',
        }))
      }
      if (output) {
        callbacks.onEvent('token', syntheticEvent(event, {
          content: output,
          visibility: 'assistant',
          channel: 'final',
          phase: 'final_response_generation',
        }))
      }
    }
    streamState.output = output
  }

  callbacks.onEvent('run.state', event)
  const status = typeof data.status === 'string' ? data.status : ''
  if (!TERMINAL_RUN_STATUSES.has(status)) return false

  if (status === 'completed') {
    callbacks.onEvent('execution_completed', syntheticEvent(event, {
      trace_id: data.trace_id ?? null,
      output,
      parsed_output: data.parsed_output ?? null,
      output_parse_error: data.output_parse_error ?? null,
    }))
  } else if (status === 'cancelled') {
    callbacks.onEvent('execution_cancelled', syntheticEvent(event, {}))
  } else {
    callbacks.onEvent('execution_failed', syntheticEvent(event, {
      code: data.failure_code ?? 'runtime_error',
      message: data.failure_detail ?? 'Network execution failed',
      uncertain: status === 'uncertain',
      trace_id: data.trace_id ?? null,
    }))
  }
  return true
}

async function consumeResponse(
  response: Response,
  input: PreparedNetworkStreamInput,
  callbacks: NetworkStreamCallbacks,
  streamState: NetworkStreamState,
): Promise<boolean> {
  const executionId = response.headers.get('X-Network-Execution-ID')
  if (executionId) {
    input.executionId = executionId
    callbacks.onExecutionId?.(executionId)
  }
  if (!response.body) throw new Error('Network streaming response is unavailable')

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  const dispatchBlock = (block: string): boolean => {
    const parsed = parseSseBlock(block)
    if (!parsed) return false
    const event = JSON.parse(parsed.data) as NetworkRuntimeEvent
    const sequence = eventSequence(parsed, event)
    if (sequence !== null) input.lastEventId = sequence
    if (parsed.event === 'heartbeat') {
      callbacks.onHeartbeat?.(event)
      return false
    }
    if (!acceptSequence(parsed, event, streamState)) return false
    if (parsed.event === 'run.state') return applyRunState(event, callbacks, streamState)

    if (parsed.event === 'token') {
      const content = eventData(event).content
      if (typeof content === 'string') streamState.output += content
    } else if (parsed.event === 'token_retract') {
      const length = eventData(event).content_length
      if (typeof length === 'number' && length > 0) {
        streamState.output = streamState.output.slice(0, Math.max(0, streamState.output.length - length))
      }
    }

    callbacks.onEvent(parsed.event, event)
    return isTerminalNetworkEvent(parsed.event)
  }

  try {
    while (true) {
      const { value, done } = await reader.read()
      buffer += decoder.decode(value, { stream: !done })
      const blocks = buffer.split(/\r?\n\r?\n/)
      buffer = blocks.pop() ?? ''

      for (const block of blocks) {
        if (!dispatchBlock(block)) continue
        await reader.cancel().catch(() => undefined)
        return true
      }

      if (done && buffer.trim() && dispatchBlock(buffer)) return true
      if (done) break
    }

    return false
  } catch (error) {
    await reader.cancel().catch(() => undefined)
    throw error
  }
}

async function requestInitialStream(
  input: PreparedNetworkStreamInput,
  callbacks: NetworkStreamCallbacks,
  streamState: NetworkStreamState,
  signal: AbortSignal | undefined,
  retriedAuth: boolean,
): Promise<boolean> {
  await ensureCsrfToken()
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...getCsrfHeaders('POST'),
  }
  const response = await fetch(`${API_BASE_URL}/network/${input.networkId}/executions/stream`, {
    method: 'POST',
    credentials: 'include',
    headers,
    signal,
    body: JSON.stringify({
      project_id: input.projectId,
      network_session_id: input.networkSessionId,
      message: input.message,
      idempotency_key: input.idempotencyKey,
      expected_draft_revision: input.expectedDraftRevision,
    }),
  })
  if (response.status === 401 && !retriedAuth) {
    await refreshAuthSession()
    return requestInitialStream(input, callbacks, streamState, signal, true)
  }
  if (!response.ok) {
    const error = await response.json().catch(() => null)
    throw new Error(error?.message ?? `Network stream failed (${response.status})`)
  }
  return consumeResponse(response, input, callbacks, streamState)
}

async function requestReattach(
  input: PreparedNetworkStreamInput,
  callbacks: NetworkStreamCallbacks,
  streamState: NetworkStreamState,
  signal: AbortSignal | undefined,
  retriedAuth: boolean,
): Promise<boolean> {
  if (!input.executionId) throw new Error('Network Run identity is unavailable for reattach')
  const response = await fetch(`${API_BASE_URL}/network/executions/${input.executionId}/stream`, {
    method: 'GET',
    credentials: 'include',
    headers: { Accept: 'text/event-stream' },
    signal,
  })
  if (response.status === 401 && !retriedAuth) {
    await refreshAuthSession()
    return requestReattach(input, callbacks, streamState, signal, true)
  }
  if (!response.ok) throw new Error(`Network reattach failed (${response.status})`)
  return consumeResponse(response, input, callbacks, streamState)
}

export async function streamNetworkExecution(
  input: NetworkStreamInput,
  callbacks: NetworkStreamCallbacks,
  signal?: AbortSignal,
): Promise<void> {
  const stableInput: PreparedNetworkStreamInput = {
    ...input,
    idempotencyKey: input.idempotencyKey ?? createUuid(),
  }
  const streamState: NetworkStreamState = { output: '', sequence: null }

  for (let attempt = 0; attempt < 4; attempt += 1) {
    if (signal?.aborted) throw new DOMException('Network stream aborted', 'AbortError')
    try {
      const completed = stableInput.executionId
        ? await requestReattach(stableInput, callbacks, streamState, signal, false)
        : await requestInitialStream(stableInput, callbacks, streamState, signal, false)
      if (completed) return
    } catch (error) {
      if (signal?.aborted || attempt === 3) throw error
      // Never create a second execution after the canonical execution id is known.
      // All retries become observer reattach operations.
      if (!stableInput.executionId && attempt > 0) throw error
    }
    await new Promise((resolve) => setTimeout(resolve, 250 * (attempt + 1)))
  }
  throw new Error('Network stream ended before a terminal event')
}