import { afterEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/lib/api/client', () => ({
  API_BASE_URL: 'http://api.test',
  ensureCsrfToken: vi.fn(async () => undefined),
  getCsrfHeaders: vi.fn(() => ({})),
  refreshAuthSession: vi.fn(async () => undefined),
}))

import { streamNetworkExecution } from './stream'

type StateStatus = 'running' | 'cancel_requested' | 'completed' | 'cancelled'

function stateResponse(status: StateStatus = 'completed', output?: string) {
  const terminalOutput = output ?? (status === 'completed' ? 'network answer' : status === 'cancelled' ? 'partial answer' : '')
  const envelope = {
    protocol_version: 1,
    execution_id: 'execution-1',
    sequence: 12,
    data: {
      run_id: 'execution-1',
      kind: 'NETWORK',
      sequence: 12,
      status,
      output: terminalOutput,
      invocations: [
        {
          id: 'invocation-root',
          parent_invocation_id: null,
          node_id: 'node-root',
          agent_id: 'agent-root',
          label: 'Root Agent',
          depth: 0,
          status: status === 'completed' ? 'completed' : status === 'cancelled' ? 'cancelled' : 'running',
          started_at: '2026-08-27T22:00:00Z',
          completed_at: status === 'completed' || status === 'cancelled' ? '2026-08-27T22:00:10Z' : null,
          provider: 'custom',
          model: 'deepseek-v4-flash',
          source: 'draft',
          version: 'r4',
          usage: status === 'completed'
            ? { input_tokens: 10, output_tokens: 20, total_tokens: 30 }
            : null,
        },
        {
          id: 'invocation-child',
          parent_invocation_id: 'invocation-root',
          node_id: 'node-child',
          agent_id: 'agent-child',
          label: 'Billing Agent',
          depth: 1,
          status: 'completed',
          started_at: '2026-08-27T22:00:01Z',
          completed_at: '2026-08-27T22:00:05Z',
          provider: 'custom',
          model: 'deepseek-v4-flash',
          source: 'release',
          version: 'r4',
          usage: { input_tokens: 4, output_tokens: 6, total_tokens: 10 },
        },
      ],
      delegations: [
        {
          id: 'fingerprint-1',
          parent_invocation_id: 'invocation-root',
          target_node_id: 'node-child',
          target: 'Billing Agent',
          status: 'completed',
        },
      ],
    },
  }
  return new Response(
    `id: 12\nevent: run.state\ndata: ${JSON.stringify(envelope)}\n\n`,
    {
      status: 200,
      headers: {
        'Content-Type': 'text/event-stream',
        'X-Network-Execution-ID': 'execution-1',
      },
    },
  )
}

afterEach(() => {
  vi.restoreAllMocks()
  vi.unstubAllGlobals()
})

describe('Network structural reattach', () => {
  it('hydrates Agent invocations from current state before completing the observer', async () => {
    const fetchMock = vi.fn().mockResolvedValue(stateResponse('completed'))
    vi.stubGlobal('fetch', fetchMock)
    const observed: Array<{ type: string; invocationId?: string | null; parent?: string | null }> = []

    await streamNetworkExecution({
      networkId: 'network-1',
      projectId: 'project-1',
      networkSessionId: 'session-1',
      executionId: 'execution-1',
      message: 'resume me',
      idempotencyKey: 'stable-key',
    }, {
      onEvent: (type, event) => {
        observed.push({
          type,
          invocationId: event.invocation_id,
          parent: event.parent_invocation_id,
        })
      },
    })

    expect(fetchMock).toHaveBeenCalledTimes(1)
    expect(String(fetchMock.mock.calls[0]?.[0])).toBe(
      'http://api.test/network/executions/execution-1/stream',
    )
    expect((fetchMock.mock.calls[0]?.[1] as RequestInit).method).toBe('GET')

    expect(observed).toEqual(expect.arrayContaining([
      { type: 'agent_invocation_started', invocationId: 'invocation-root', parent: null },
      { type: 'agent_invocation_completed', invocationId: 'invocation-root', parent: null },
      { type: 'agent_invocation_started', invocationId: 'invocation-child', parent: 'invocation-root' },
      { type: 'agent_invocation_completed', invocationId: 'invocation-child', parent: 'invocation-root' },
      { type: 'run.state', invocationId: undefined, parent: undefined },
      { type: 'execution_completed', invocationId: undefined, parent: undefined },
    ]))
  })

  it('does not create a new Network execution when reattaching a running Run', async () => {
    const terminal = stateResponse('completed')
    const running = stateResponse('running')
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(running)
      .mockResolvedValueOnce(terminal)
    vi.stubGlobal('fetch', fetchMock)

    await streamNetworkExecution({
      networkId: 'network-1',
      projectId: 'project-1',
      networkSessionId: 'session-1',
      executionId: 'execution-1',
      message: 'resume me',
      idempotencyKey: 'stable-key',
    }, { onEvent: vi.fn() })

    expect(fetchMock).toHaveBeenCalledTimes(2)
    expect(fetchMock.mock.calls.every((call) =>
      String(call[0]) === 'http://api.test/network/executions/execution-1/stream'
    )).toBe(true)
    expect(fetchMock.mock.calls.every((call) =>
      (call[1] as RequestInit).method === 'GET'
    )).toBe(true)
  })

  it('keeps reattaching the same Network Run while cancellation is pending and preserves partial output', async () => {
    const pending = stateResponse('cancel_requested', 'partial answer')
    const cancelled = stateResponse('cancelled', 'partial answer')
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(pending)
      .mockResolvedValueOnce(cancelled)
    vi.stubGlobal('fetch', fetchMock)
    const observed: Array<{ type: string; data: Record<string, unknown> }> = []

    await streamNetworkExecution({
      networkId: 'network-1',
      projectId: 'project-1',
      networkSessionId: 'session-1',
      executionId: 'execution-1',
      message: 'stop me',
      idempotencyKey: 'stable-key',
    }, {
      onEvent: (type, event) => observed.push({ type, data: event.data }),
    })

    expect(fetchMock).toHaveBeenCalledTimes(2)
    expect(fetchMock.mock.calls.every((call) =>
      String(call[0]) === 'http://api.test/network/executions/execution-1/stream'
    )).toBe(true)
    expect(fetchMock.mock.calls.every((call) => (call[1] as RequestInit).method === 'GET')).toBe(true)
    expect(observed).toEqual(expect.arrayContaining([
      expect.objectContaining({ type: 'run.state', data: expect.objectContaining({ status: 'cancel_requested' }) }),
      expect.objectContaining({ type: 'execution_cancelled', data: expect.objectContaining({ output: 'partial answer', cancelled: true }) }),
    ]))
  })
})
