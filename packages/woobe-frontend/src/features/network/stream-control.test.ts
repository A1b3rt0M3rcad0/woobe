import { runtimeTestEnvelope } from '@/lib/runtime-stream-test-fixtures'
import { afterEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/lib/api/client', () => ({
  API_BASE_URL: 'http://api.test',
  ensureCsrfToken: vi.fn(async () => undefined),
  getCsrfHeaders: vi.fn(() => ({})),
  refreshAuthSession: vi.fn(async () => undefined),
}))

import { streamNetworkExecution } from './stream'

afterEach(() => {
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

describe('Network runtime control frames', () => {
  it('keeps heartbeat outside semantic reducers while preserving liveness', async () => {
    const heartbeat = {
      protocol_version: 2,
      type: 'heartbeat',
      occurred_at: '2026-09-17T00:00:00Z',
    }
    const terminal = runtimeTestEnvelope('execution_completed', {
      execution_id: 'execution-1',
      sequence: 1,
      data: { trace_id: 'trace-1' },
    }, 'NETWORK')
    const response = new Response(
      `event: heartbeat\ndata: ${JSON.stringify(heartbeat)}\n\n`
        + `id: 1\nevent: execution_completed\ndata: ${JSON.stringify(terminal)}\n\n`,
      {
        status: 200,
        headers: {
          'Content-Type': 'text/event-stream',
          'X-Network-Execution-ID': 'execution-1',
        },
      },
    )
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(response))

    const onHeartbeat = vi.fn()
    const onEvent = vi.fn()
    await streamNetworkExecution(
      {
        networkId: 'network-1',
        projectId: 'project-1',
        networkSessionId: 'session-1',
        message: 'hello',
      },
      { onEvent, onHeartbeat },
    )

    expect(onHeartbeat).toHaveBeenCalledTimes(1)
    expect(onEvent).toHaveBeenCalledWith(
      'execution_completed',
      expect.objectContaining({ execution_id: 'execution-1' }),
    )
    expect(onEvent.mock.calls.some(([eventType]) => eventType === 'heartbeat')).toBe(false)
  })
})
