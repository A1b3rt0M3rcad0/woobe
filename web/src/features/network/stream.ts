import {
  API_BASE_URL,
  ensureCsrfToken,
  getCsrfHeaders,
  refreshAuthSession,
} from '@/lib/api/client'

import type { NetworkRuntimeEvent } from './types'

export interface NetworkStreamInput {
  networkId: string
  projectId: string
  networkSessionId: string
  message: string
  idempotencyKey?: string
  lastEventId?: number
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

async function requestStream(
  input: NetworkStreamInput,
  callbacks: NetworkStreamCallbacks,
  signal: AbortSignal | undefined,
  retriedAuth: boolean,
): Promise<boolean> {
  await ensureCsrfToken()
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...getCsrfHeaders('POST'),
  }
  if (input.lastEventId != null) headers['Last-Event-ID'] = String(input.lastEventId)
  const response = await fetch(`${API_BASE_URL}/network/${input.networkId}/executions/stream`, {
    method: 'POST',
    credentials: 'include',
    headers,
    signal,
    body: JSON.stringify({
      project_id: input.projectId,
      network_session_id: input.networkSessionId,
      message: input.message,
      idempotency_key: input.idempotencyKey ?? crypto.randomUUID(),
    }),
  })
  if (response.status === 401 && !retriedAuth) {
    await refreshAuthSession()
    return requestStream(input, callbacks, signal, true)
  }
  if (!response.ok) {
    const error = await response.json().catch(() => null)
    throw new Error(error?.message ?? `Network stream failed (${response.status})`)
  }
  const executionId = response.headers.get('X-Network-Execution-ID')
  if (executionId) callbacks.onExecutionId?.(executionId)
  if (!response.body) throw new Error('Network streaming response is unavailable')

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  let terminalEventReceived = false
  while (true) {
    const { value, done } = await reader.read()
    buffer += decoder.decode(value, { stream: !done })
    const blocks = buffer.split(/\r?\n\r?\n/)
    buffer = blocks.pop() ?? ''
    for (const block of blocks) {
      const parsed = parseSseBlock(block)
      if (!parsed) continue
      const event = JSON.parse(parsed.data) as NetworkRuntimeEvent
      if (parsed.id) {
        input.lastEventId = Number(parsed.id)
        if (event.sequence == null) event.sequence = input.lastEventId
      }
      if (parsed.event === 'heartbeat') callbacks.onHeartbeat?.(event)
      else {
        callbacks.onEvent(parsed.event, event)
        if (['execution_completed', 'execution_failed', 'execution_cancelled'].includes(parsed.event)) {
          terminalEventReceived = true
        }
      }
    }
    if (done) break
  }
  return terminalEventReceived
}

export async function streamNetworkExecution(
  input: NetworkStreamInput,
  callbacks: NetworkStreamCallbacks,
  signal?: AbortSignal,
): Promise<void> {
  const stableInput: NetworkStreamInput = {
    ...input,
    idempotencyKey: input.idempotencyKey ?? crypto.randomUUID(),
  }
  for (let attempt = 0; attempt < 4; attempt += 1) {
    if (signal?.aborted) throw new DOMException('Network stream aborted', 'AbortError')
    try {
      const completed = await requestStream(stableInput, callbacks, signal, false)
      if (completed) return
    } catch (error) {
      if (signal?.aborted || attempt === 3) throw error
    }
    await new Promise((resolve) => setTimeout(resolve, 250 * (attempt + 1)))
  }
  throw new Error('Network stream ended before a terminal event')
}
