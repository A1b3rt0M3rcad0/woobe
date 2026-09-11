import {
  API_BASE_URL,
  ensureCsrfToken,
  getCsrfHeaders,
  refreshAuthSession,
} from '@/lib/api/client'
import {
  RUNTIME_STREAM_MAX_ATTEMPTS,
  acceptRuntimeFrameSequence,
  parseRuntimeFrame,
  reconcileRuntimeOutput,
  runtimeRetryDelayMs,
  runtimeTerminalStatus,
  type ParsedRuntimeFrame,
  type RuntimeSequenceState,
} from '@/lib/runtime-stream'
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

interface NetworkStreamState extends RuntimeSequenceState {
  output: string
}

const TERMINAL_NETWORK_EVENTS = new Set([
  'execution_completed',
  'execution_failed',
  'execution_cancelled',
])

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

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' && !Array.isArray(value)
    ? value as Record<string, unknown>
    : {}
}

function asString(value: unknown): string | null {
  return typeof value === 'string' && value.length > 0 ? value : null
}

function asNumber(value: unknown): number | null {
  return typeof value === 'number' && Number.isFinite(value) ? value : null
}

function syntheticEvent(
  source: NetworkRuntimeEvent,
  data: Record<string, unknown>,
): NetworkRuntimeEvent {
  return { ...source, data }
}

function snapshotInvocationEvent(
  source: NetworkRuntimeEvent,
  rawInvocation: unknown,
  completed: boolean,
): NetworkRuntimeEvent | null {
  const invocation = asRecord(rawInvocation)
  const invocationId = asString(invocation.id)
  if (!invocationId) return null
  const data: Record<string, unknown> = {
    agent_run_id: invocation.agent_run_id ?? null,
    label: invocation.label ?? invocation.agent_id ?? 'Agent',
    provider: invocation.provider ?? null,
    model: invocation.model ?? null,
    source: invocation.source ?? null,
    version: invocation.version ?? null,
    context_state: invocation.context_state ?? null,
    previous_invocation_count: invocation.previous_invocation_count ?? 0,
    agent_session_id: invocation.agent_session_id ?? null,
  }
  if (completed) {
    data.trace_id = invocation.trace_id ?? null
    data.usage = invocation.usage ?? null
    const failure = asRecord(invocation.failure)
    Object.assign(data, failure)
  } else {
    data.started_at = invocation.started_at ?? source.created_at ?? null
  }
  return {
    ...source,
    invocation_id: invocationId,
    parent_invocation_id: asString(invocation.parent_invocation_id),
    node_id: asString(invocation.node_id),
    agent_id: asString(invocation.agent_id),
    depth: asNumber(invocation.depth) ?? 0,
    created_at: asString(completed ? invocation.completed_at : invocation.started_at) ?? source.created_at,
    data,
  }
}

function hydrateInvocationSnapshot(
  source: NetworkRuntimeEvent,
  data: Record<string, unknown>,
  callbacks: NetworkStreamCallbacks,
) {
  const rawInvocations = Array.isArray(data.invocations) ? data.invocations : []
  for (const rawInvocation of rawInvocations) {
    const invocation = asRecord(rawInvocation)
    const started = snapshotInvocationEvent(source, invocation, false)
    if (!started) continue
    callbacks.onEvent('agent_invocation_started', started)

    const status = asString(invocation.status)
    if (!status || status === 'running' || status === 'queued') continue
    const terminal = snapshotInvocationEvent(source, invocation, true)
    if (!terminal) continue
    if (status === 'completed' || status === 'success') {
      callbacks.onEvent('agent_invocation_completed', terminal)
    } else if (status === 'cancelled') {
      callbacks.onEvent('agent_invocation_cancelled', terminal)
    } else {
      callbacks.onEvent('agent_invocation_failed', terminal)
    }
  }
}

function hydrateDelegationSnapshot(
  source: NetworkRuntimeEvent,
  data: Record<string, unknown>,
  callbacks: NetworkStreamCallbacks,
) {
  const rawDelegations = Array.isArray(data.delegations) ? data.delegations : []
  for (const rawDelegation of rawDelegations) {
    const delegation = asRecord(rawDelegation)
    const target = asString(delegation.target) ?? asString(delegation.target_node_id)
    if (!target) continue
    const sharedData: Record<string, unknown> = {
      target,
      target_node_id: delegation.target_node_id ?? null,
      task_fingerprint: delegation.id ?? null,
      reason: delegation.reason ?? null,
    }
    const startedAt = asString(delegation.started_at) ?? source.created_at
    callbacks.onEvent('delegation_started', {
      ...source,
      invocation_id: asString(delegation.parent_invocation_id),
      created_at: startedAt,
      data: sharedData,
    })

    const status = asString(delegation.status)
    if (!status || status === 'running' || status === 'queued') continue
    const eventType = status === 'completed' || status === 'success'
      ? 'delegation_completed'
      : status === 'skipped'
        ? 'delegation_skipped'
        : 'delegation_failed'
    callbacks.onEvent(eventType, {
      ...source,
      invocation_id: asString(delegation.parent_invocation_id),
      created_at: asString(delegation.completed_at) ?? source.created_at,
      data: sharedData,
    })
  }
}

function hydrateToolSnapshot(
  source: NetworkRuntimeEvent,
  data: Record<string, unknown>,
  callbacks: NetworkStreamCallbacks,
) {
  const rawTools = Array.isArray(data.tools) ? data.tools : []
  for (const rawTool of rawTools) {
    const tool = asRecord(rawTool)
    const toolName = asString(tool.tool_name)
    if (!toolName || toolName.startsWith('delegate_to_')) continue
    const toolCallId = asString(tool.tool_call_id) ?? asString(tool.id)
    const invocationId = asString(tool.invocation_id)
    const sharedData: Record<string, unknown> = {
      tool_call_id: toolCallId,
      tool_name: toolName,
    }
    callbacks.onEvent('tool_call_started', {
      ...source,
      invocation_id: invocationId,
      created_at: asString(tool.started_at) ?? source.created_at,
      data: {
        ...sharedData,
        status: 'running',
        started_at: tool.started_at ?? source.created_at ?? null,
      },
    })

    const status = asString(tool.status)
    if (!status || status === 'running' || status === 'queued') continue
    callbacks.onEvent('tool_call_completed', {
      ...source,
      invocation_id: invocationId,
      created_at: asString(tool.completed_at) ?? source.created_at,
      data: {
        ...sharedData,
        duration_ms: tool.duration_ms ?? null,
        success: tool.success ?? (status === 'success' || status === 'completed'),
        status,
        error_code: tool.error_code ?? null,
        error: tool.error ?? null,
      },
    })
  }
}

function applyRunState(
  runtime: ParsedRuntimeFrame,
  event: NetworkRuntimeEvent,
  callbacks: NetworkStreamCallbacks,
  streamState: NetworkStreamState,
): boolean {
  const data = eventData(event)
  const output = typeof data.output === 'string' ? data.output : ''
  const reconciliation = reconcileRuntimeOutput(streamState.output, output)
  if (reconciliation.changed) {
    if (reconciliation.retract > 0) {
      callbacks.onEvent('token_retract', syntheticEvent(event, {
        content_length: reconciliation.retract,
        reason: 'reattach_state_replace',
      }))
    }
    if (reconciliation.append) {
      callbacks.onEvent('token', syntheticEvent(event, {
        content: reconciliation.append,
        visibility: 'assistant',
        channel: 'final',
        phase: 'capability_response_generation',
      }))
    }
    streamState.output = reconciliation.output
  }

  hydrateInvocationSnapshot(event, data, callbacks)
  hydrateDelegationSnapshot(event, data, callbacks)
  hydrateToolSnapshot(event, data, callbacks)
  callbacks.onEvent('run.state', event)
  const status = runtimeTerminalStatus(runtime)
  if (status === null) return false

  if (status === 'completed') {
    callbacks.onEvent('execution_completed', syntheticEvent(event, {
      trace_id: data.trace_id ?? null,
      output,
      parsed_output: data.parsed_output ?? null,
      output_parse_error: data.output_parse_error ?? null,
    }))
  } else if (status === 'cancelled') {
    callbacks.onEvent('execution_cancelled', syntheticEvent(event, {
      output,
      trace_id: data.trace_id ?? null,
      partial: Boolean(output),
      cancelled: true,
    }))
  } else {
    const error = asRecord(data.error)
    callbacks.onEvent('execution_failed', syntheticEvent(event, {
      code: data.failure_code ?? error.code ?? 'runtime_error',
      message: data.failure_detail ?? error.message ?? 'Network execution failed',
      uncertain: status === 'uncertain',
      trace_id: data.trace_id ?? null,
      root_partial_result_available: error.root_partial_result_available ?? false,
      completed_child_results_available: error.completed_child_results_available ?? false,
      completed_child_result_count: error.completed_child_result_count ?? 0,
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
    const runtime = parseRuntimeFrame(block)
    if (!runtime) return false
    const event = runtime.data as unknown as NetworkRuntimeEvent
    if (runtime.eventType === 'heartbeat') {
      callbacks.onHeartbeat?.(event)
      return false
    }
    if (!acceptRuntimeFrameSequence(runtime, streamState)) return false
    if (runtime.sequence !== null) {
      event.sequence = runtime.sequence
      input.lastEventId = runtime.sequence
    }
    if (runtime.eventType === 'run.state') {
      return applyRunState(runtime, event, callbacks, streamState)
    }

    if (runtime.eventType === 'token') {
      const content = eventData(event).content
      if (typeof content === 'string') streamState.output += content
    } else if (runtime.eventType === 'token_retract') {
      const length = eventData(event).content_length
      if (typeof length === 'number' && length > 0) {
        streamState.output = streamState.output.slice(
          0,
          Math.max(0, streamState.output.length - length),
        )
      }
    }

    callbacks.onEvent(runtime.eventType, event)
    return isTerminalNetworkEvent(runtime.eventType)
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

  for (let attempt = 0; attempt < RUNTIME_STREAM_MAX_ATTEMPTS; attempt += 1) {
    if (signal?.aborted) throw new DOMException('Network stream aborted', 'AbortError')
    try {
      const completed = stableInput.executionId
        ? await requestReattach(stableInput, callbacks, streamState, signal, false)
        : await requestInitialStream(stableInput, callbacks, streamState, signal, false)
      if (completed) return
    } catch (error) {
      if (signal?.aborted || attempt === RUNTIME_STREAM_MAX_ATTEMPTS - 1) throw error
      if (!stableInput.executionId && attempt > 0) throw error
    }
    await new Promise((resolve) => setTimeout(resolve, runtimeRetryDelayMs(attempt)))
  }
  throw new Error('Network stream ended before a terminal event')
}