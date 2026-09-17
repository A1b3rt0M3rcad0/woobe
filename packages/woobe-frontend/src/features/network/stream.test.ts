import { runtimeTestEnvelope } from '@/lib/runtime-stream-test-fixtures'
import { afterEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/lib/api/client', () => ({
  API_BASE_URL: 'http://api.test',
  ensureCsrfToken: vi.fn(async () => undefined),
  getCsrfHeaders: vi.fn(() => ({})),
  refreshAuthSession: vi.fn(async () => undefined),
}))

import { refreshAuthSession } from '@/lib/api/client'
import { isTerminalNetworkEvent, parseSseBlock, streamNetworkExecution } from './stream'

const TERMINAL_EVENT = {
  event_id: 'event-1',
  execution_id: 'execution-1',
  sequence: 1,
  invocation_id: null,
  parent_invocation_id: null,
  node_id: null,
  agent_id: null,
  depth: 0,
  created_at: '2026-07-28T00:00:00Z',
  data: { trace_id: 'trace-1' },
}

function terminalResponse(): Response {
  return new Response(
    `id: 1\nevent: execution_completed\ndata: ${JSON.stringify(runtimeTestEnvelope('execution_completed', TERMINAL_EVENT, 'NETWORK'))}\n\n`,
    {
      status: 200,
      headers: {
        'Content-Type': 'text/event-stream',
        'X-Network-Execution-ID': 'execution-1',
      },
    },
  )
}

function nonTerminalResponse(): Response {
  return new Response(
    `id: 1\nevent: token\ndata: ${JSON.stringify(runtimeTestEnvelope('token', {
      ...TERMINAL_EVENT,
      data: { content: 'partial', visibility: 'assistant', channel: 'final' },
    }, 'NETWORK'))}\n\n`,
    {
      status: 200,
      headers: {
        'Content-Type': 'text/event-stream',
        'X-Network-Execution-ID': 'execution-1',
      },
    },
  )
}

function completedStateResponse(sequence = 7): Response {
  return new Response(
    `id: ${sequence}\nevent: run.state\ndata: ${JSON.stringify(runtimeTestEnvelope('run.state', {
      protocol_version: 2,
      execution_id: 'execution-1',
      sequence,
      data: {
        run_id: 'execution-1',
        kind: 'NETWORK',
        sequence,
        status: 'completed',
        output: 'partial answer',
        trace_id: 'trace-1',
      },
    }, 'NETWORK'))}\n\n`,
    {
      status: 200,
      headers: {
        'Content-Type': 'text/event-stream',
        'X-Network-Execution-ID': 'execution-1',
      },
    },
  )
}

function gapResponse(): Response {
  const state = {
    protocol_version: 2,
    execution_id: 'execution-1',
    sequence: 3,
    data: {
      run_id: 'execution-1',
      kind: 'NETWORK',
      sequence: 3,
      status: 'running',
      output: 'partial',
    },
  }
  const skipped = {
    ...TERMINAL_EVENT,
    sequence: 5,
    data: { content: 'must-not-apply', visibility: 'assistant', channel: 'final' },
  }
  return new Response(
    `id: 3\nevent: run.state\ndata: ${JSON.stringify(runtimeTestEnvelope('run.state', state, 'NETWORK'))}\n\nid: 5\nevent: token\ndata: ${JSON.stringify(runtimeTestEnvelope('token', skipped, 'NETWORK'))}\n\n`,
    {
      status: 200,
      headers: {
        'Content-Type': 'text/event-stream',
        'X-Network-Execution-ID': 'execution-1',
      },
    },
  )
}

function eventEnvelope(sequence: number, data: Record<string, unknown>) {
  return {
    ...TERMINAL_EVENT,
    sequence,
    data,
  }
}

function sseEvent(sequence: number, eventType: string, data: Record<string, unknown>) {
  return `id: ${sequence}\nevent: ${eventType}\ndata: ${JSON.stringify(runtimeTestEnvelope(eventType, eventEnvelope(sequence, data), 'NETWORK'))}\n\n`
}

function bodyFrom(fetchMock: ReturnType<typeof vi.fn>, index: number): Record<string, unknown> {
  const init = fetchMock.mock.calls[index]?.[1] as RequestInit | undefined
  return JSON.parse(String(init?.body)) as Record<string, unknown>
}

function streamInput(idempotencyKey?: string) {
  return {
    networkId: 'network-1',
    projectId: 'project-1',
    networkSessionId: 'session-1',
    message: 'Hello Network',
    idempotencyKey,
  }
}

afterEach(() => {
  vi.useRealTimers()
  vi.restoreAllMocks()
  vi.unstubAllGlobals()
})

describe('parseSseBlock', () => {
  it('parses typed events and sequence ids', () => {
    expect(parseSseBlock('id: 4\nevent: agent_activity\ndata: {"sequence":4}')).toEqual({
      id: '4',
      event: 'agent_activity',
      data: '{"sequence":4}',
    })
  })

  it('joins multiple data lines', () => {
    expect(parseSseBlock('event: token\ndata: first\ndata: second')?.data).toBe('first\nsecond')
  })
})

describe('isTerminalNetworkEvent', () => {
  it.each([
    'execution_completed',
    'execution_failed',
    'execution_cancelled',
  ])('recognizes %s as terminal', (eventType) => {
    expect(isTerminalNetworkEvent(eventType)).toBe(true)
  })

  it('does not treat invocation completion as terminal', () => {
    expect(isTerminalNetworkEvent('agent_invocation_completed')).toBe(false)
  })
})

describe('streamNetworkExecution token delivery', () => {
  it('preserves granular token events in sequence order', async () => {
    const body = [
      sseEvent(1, 'token', { content: 'A', visibility: 'assistant', channel: 'final' }),
      sseEvent(2, 'token', { content: 'B', visibility: 'assistant', channel: 'final' }),
      sseEvent(3, 'token', { content: 'C', visibility: 'assistant', channel: 'final' }),
      sseEvent(4, 'execution_completed', { trace_id: 'trace-1' }),
    ].join('')
    const fetchMock = vi.fn().mockResolvedValue(new Response(body, {
      status: 200,
      headers: {
        'Content-Type': 'text/event-stream',
        'X-Network-Execution-ID': 'execution-1',
      },
    }))
    vi.stubGlobal('fetch', fetchMock)
    const chunks: string[] = []

    await streamNetworkExecution(streamInput('stable-key'), {
      onEvent: (eventType, event) => {
        if (eventType === 'token' && typeof event.data.content === 'string') {
          chunks.push(event.data.content)
        }
      },
    })

    expect(chunks).toEqual(['A', 'B', 'C'])
  })

  it('preserves token retract ordering', async () => {
    const body = [
      sseEvent(1, 'token', { content: 'Hello', visibility: 'assistant', channel: 'final' }),
      sseEvent(2, 'token', { content: ' world', visibility: 'assistant', channel: 'final' }),
      sseEvent(3, 'token_retract', { content_length: 6, reason: 'tool_call_selected' }),
      sseEvent(4, 'token', { content: 'Woobe', visibility: 'assistant', channel: 'final' }),
      sseEvent(5, 'execution_completed', { trace_id: 'trace-1' }),
    ].join('')
    const fetchMock = vi.fn().mockResolvedValue(new Response(body, {
      status: 200,
      headers: {
        'Content-Type': 'text/event-stream',
        'X-Network-Execution-ID': 'execution-1',
      },
    }))
    vi.stubGlobal('fetch', fetchMock)
    let output = ''

    await streamNetworkExecution(streamInput('stable-key'), {
      onEvent: (eventType, event) => {
        if (eventType === 'token' && typeof event.data.content === 'string') {
          output += event.data.content
        }
        if (eventType === 'token_retract' && typeof event.data.content_length === 'number') {
          output = output.slice(0, Math.max(0, output.length - event.data.content_length))
        }
      },
    })

    expect(output).toBe('HelloWoobe')
  })

  it('reconciles current state before continuing the live tail', async () => {
    const state = {
      protocol_version: 2,
      execution_id: 'execution-1',
      sequence: 3,
      data: {
        run_id: 'execution-1',
        kind: 'NETWORK',
        sequence: 3,
        status: 'running',
        output: 'Hello wor',
      },
    }
    const body = [
      `id: 3\nevent: run.state\ndata: ${JSON.stringify(runtimeTestEnvelope('run.state', state, 'NETWORK'))}\n\n`,
      sseEvent(4, 'token', { content: 'ld', visibility: 'assistant', channel: 'final' }),
      sseEvent(5, 'execution_completed', { trace_id: 'trace-1' }),
    ].join('')
    const fetchMock = vi.fn().mockResolvedValue(new Response(body, {
      status: 200,
      headers: {
        'Content-Type': 'text/event-stream',
        'X-Network-Execution-ID': 'execution-1',
      },
    }))
    vi.stubGlobal('fetch', fetchMock)
    let output = ''

    await streamNetworkExecution(streamInput('stable-key'), {
      onEvent: (eventType, event) => {
        if (eventType === 'token' && typeof event.data.content === 'string') {
          output += event.data.content
        }
      },
    })

    expect(output).toBe('Hello world')
  })
})

describe('streamNetworkExecution idempotency and reattach', () => {
  it('sends a browser-safe UUID when randomUUID is unavailable', async () => {
    vi.stubGlobal('crypto', {
      getRandomValues: (bytes: Uint8Array) => {
        bytes.fill(0)
        return bytes
      },
    })
    const fetchMock = vi.fn().mockResolvedValue(terminalResponse())
    vi.stubGlobal('fetch', fetchMock)

    await streamNetworkExecution(streamInput(), { onEvent: vi.fn() })

    expect(fetchMock).toHaveBeenCalledTimes(1)
    expect(bodyFrom(fetchMock, 0).idempotency_key).toBe('00000000-0000-4000-8000-000000000000')
  })

  it('preserves an idempotency key supplied by the caller', async () => {
    const randomUUID = vi.fn(() => {
      throw new Error('randomUUID must not be called')
    })
    vi.stubGlobal('crypto', { randomUUID })
    const fetchMock = vi.fn().mockResolvedValue(terminalResponse())
    vi.stubGlobal('fetch', fetchMock)

    await streamNetworkExecution(streamInput('network-send-123'), { onEvent: vi.fn() })

    expect(randomUUID).not.toHaveBeenCalled()
    expect(bodyFrom(fetchMock, 0).idempotency_key).toBe('network-send-123')
  })

  it('reuses one generated key across transport retries before the execution id is known', async () => {
    vi.useFakeTimers()
    const randomUUID = vi.fn(() => '11111111-1111-4111-8111-111111111111')
    vi.stubGlobal('crypto', { randomUUID })
    const fetchMock = vi.fn()
      .mockRejectedValueOnce(new TypeError('temporary network failure'))
      .mockResolvedValueOnce(terminalResponse())
    vi.stubGlobal('fetch', fetchMock)

    const execution = streamNetworkExecution(streamInput(), { onEvent: vi.fn() })
    await vi.runAllTimersAsync()
    await execution

    expect(fetchMock).toHaveBeenCalledTimes(2)
    expect(randomUUID).toHaveBeenCalledTimes(1)
    expect(bodyFrom(fetchMock, 0).idempotency_key).toBe('11111111-1111-4111-8111-111111111111')
    expect(bodyFrom(fetchMock, 1).idempotency_key).toBe('11111111-1111-4111-8111-111111111111')
  })

  it('reuses the same key after refreshing an expired auth session', async () => {
    const randomUUID = vi.fn(() => '22222222-2222-4222-8222-222222222222')
    vi.stubGlobal('crypto', { randomUUID })
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response(null, { status: 401 }))
      .mockResolvedValueOnce(terminalResponse())
    vi.stubGlobal('fetch', fetchMock)

    await streamNetworkExecution(streamInput(), { onEvent: vi.fn() })

    expect(fetchMock).toHaveBeenCalledTimes(2)
    expect(randomUUID).toHaveBeenCalledTimes(1)
    expect(vi.mocked(refreshAuthSession)).toHaveBeenCalledTimes(1)
    expect(bodyFrom(fetchMock, 0).idempotency_key).toBe('22222222-2222-4222-8222-222222222222')
    expect(bodyFrom(fetchMock, 1).idempotency_key).toBe('22222222-2222-4222-8222-222222222222')
  })

  it('switches to GET reattach after the canonical Network Run id is known', async () => {
    vi.useFakeTimers()
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(nonTerminalResponse())
      .mockResolvedValueOnce(completedStateResponse())
    vi.stubGlobal('fetch', fetchMock)
    const onEvent = vi.fn()

    const execution = streamNetworkExecution(streamInput('stable-key'), { onEvent })
    await vi.runAllTimersAsync()
    await execution

    expect(fetchMock).toHaveBeenCalledTimes(2)
    expect(String(fetchMock.mock.calls[0]?.[0])).toBe('http://api.test/network/network-1/executions/stream')
    expect((fetchMock.mock.calls[0]?.[1] as RequestInit).method).toBe('POST')
    expect(String(fetchMock.mock.calls[1]?.[0])).toBe('http://api.test/network/executions/execution-1/stream')
    expect((fetchMock.mock.calls[1]?.[1] as RequestInit).method).toBe('GET')
    expect(onEvent).toHaveBeenCalledWith('run.state', expect.any(Object))
    expect(onEvent).toHaveBeenCalledWith('execution_completed', expect.any(Object))
  })

  it('rejects a live sequence gap and recovers through current-state reattach', async () => {
    vi.useFakeTimers()
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(gapResponse())
      .mockResolvedValueOnce(completedStateResponse(8))
    vi.stubGlobal('fetch', fetchMock)
    const onEvent = vi.fn()

    const execution = streamNetworkExecution(streamInput('stable-key'), { onEvent })
    await vi.runAllTimersAsync()
    await execution

    expect(fetchMock).toHaveBeenCalledTimes(2)
    expect((fetchMock.mock.calls[0]?.[1] as RequestInit).method).toBe('POST')
    expect((fetchMock.mock.calls[1]?.[1] as RequestInit).method).toBe('GET')
    expect(onEvent).not.toHaveBeenCalledWith(
      'token',
      expect.objectContaining({ data: expect.objectContaining({ content: 'must-not-apply' }) }),
    )
    expect(onEvent).toHaveBeenCalledWith('execution_completed', expect.any(Object))
  })
})
