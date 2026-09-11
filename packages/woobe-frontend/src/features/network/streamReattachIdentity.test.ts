import { afterEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/lib/api/client', () => ({
  API_BASE_URL: 'http://api.test',
  ensureCsrfToken: vi.fn(async () => undefined),
  getCsrfHeaders: vi.fn(() => ({})),
  refreshAuthSession: vi.fn(async () => undefined),
}))

import { streamNetworkExecution } from './stream'

afterEach(() => {
  vi.restoreAllMocks()
  vi.unstubAllGlobals()
})

describe('Network durable reattach identity', () => {
  it('hydrates the canonical Agent Run id from run.state before the terminal event', async () => {
    const state = {
      protocol_version: 1,
      execution_id: 'execution-1',
      sequence: 7,
      data: {
        run_id: 'execution-1',
        kind: 'NETWORK',
        sequence: 7,
        status: 'completed',
        output: 'durable answer',
        trace_id: 'network-trace-1',
        invocations: [
          {
            id: 'network-span-1',
            agent_run_id: 'agent-run-1',
            parent_invocation_id: null,
            node_id: 'node-root',
            agent_id: 'agent-root',
            label: 'Root Agent',
            depth: 0,
            status: 'completed',
            provider: 'openai',
            model: 'gpt-test',
            usage: {
              input_tokens: 5,
              output_tokens: 3,
              total_tokens: 8,
              cost_usd: 0.01,
            },
            trace_id: 'agent-trace-1',
            started_at: '2026-09-11T03:00:00.000Z',
            completed_at: '2026-09-11T03:00:01.000Z',
          },
        ],
      },
    }
    const fetchMock = vi.fn().mockResolvedValue(new Response(
      `id: 7\nevent: run.state\ndata: ${JSON.stringify(state)}\n\n`,
      {
        status: 200,
        headers: {
          'Content-Type': 'text/event-stream',
          'X-Network-Execution-ID': 'execution-1',
        },
      },
    ))
    vi.stubGlobal('fetch', fetchMock)

    const events: Array<{ type: string; data: Record<string, unknown>; invocationId?: string | null }> = []
    await streamNetworkExecution({
      networkId: 'network-1',
      projectId: 'project-1',
      networkSessionId: 'session-1',
      executionId: 'execution-1',
      message: 'resume me',
      idempotencyKey: 'stable-key',
    }, {
      onEvent: (type, event) => events.push({
        type,
        data: event.data,
        invocationId: event.invocation_id,
      }),
    })

    expect(fetchMock).toHaveBeenCalledTimes(1)
    expect((fetchMock.mock.calls[0]?.[1] as RequestInit).method).toBe('GET')

    const started = events.find((event) => event.type === 'agent_invocation_started')
    const completed = events.find((event) => event.type === 'agent_invocation_completed')
    expect(started).toEqual(expect.objectContaining({
      invocationId: 'network-span-1',
      data: expect.objectContaining({ agent_run_id: 'agent-run-1' }),
    }))
    expect(completed).toEqual(expect.objectContaining({
      invocationId: 'network-span-1',
      data: expect.objectContaining({
        agent_run_id: 'agent-run-1',
        trace_id: 'agent-trace-1',
      }),
    }))
    expect(events.map((event) => event.type)).toContain('execution_completed')
  })
})
