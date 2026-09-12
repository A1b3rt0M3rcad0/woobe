import { afterEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/lib/api/client', () => ({
  API_BASE_URL: 'http://api.test',
  ensureCsrfToken: vi.fn(async () => undefined),
  getCsrfHeaders: vi.fn(() => ({})),
  refreshAuthSession: vi.fn(async () => undefined),
}))

import { streamNetworkExecution } from './stream'

function completedStateResponse(agentRunId: string): Response {
  const state = {
    protocol_version: 1,
    execution_id: 'execution-1',
    sequence: 7,
    data: {
      run_id: 'execution-1',
      kind: 'NETWORK',
      sequence: 7,
      status: 'completed',
      output: 'done',
      trace_id: 'trace-1',
      invocations: [
        {
          id: 'invocation-1',
          agent_run_id: agentRunId,
          agent_id: 'agent-1',
          node_id: 'node-1',
          depth: 0,
          label: 'Billing Agent',
          status: 'completed',
          trace_id: 'agent-trace-1',
          started_at: '2026-09-10T20:00:00Z',
          completed_at: '2026-09-10T20:00:01Z',
        },
      ],
    },
  }
  return new Response(
    `id: 7\nevent: run.state\ndata: ${JSON.stringify(state)}\n\n`,
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

describe('Network durable Agent Run identity', () => {
  it('hydrates agent_run_id from run.state before opening Agent Run details', async () => {
    const agentRunId = '01993dc0-7a4a-7000-8000-000000000001'
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(completedStateResponse(agentRunId)))
    const onEvent = vi.fn()

    await streamNetworkExecution({
      networkId: 'network-1',
      projectId: 'project-1',
      networkSessionId: 'session-1',
      message: 'hello',
      idempotencyKey: 'stable-key',
      executionId: 'execution-1',
    }, { onEvent })

    expect(onEvent).toHaveBeenCalledWith(
      'agent_invocation_started',
      expect.objectContaining({
        invocation_id: 'invocation-1',
        data: expect.objectContaining({ agent_run_id: agentRunId }),
      }),
    )
  })
})
