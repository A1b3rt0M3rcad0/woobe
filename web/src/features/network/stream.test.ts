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
    `id: 1\nevent: execution_completed\ndata: ${JSON.stringify(TERMINAL_EVENT)}\n\n`,
    {
      status: 200,
      headers: {
        'Content-Type': 'text/event-stream',
        'X-Network-Execution-ID': 'execution-1',
      },
    },
  )
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

describe('streamNetworkExecution idempotency', () => {
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

  it('reuses one generated key across transport retries', async () => {
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
})
