import { afterEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/lib/api/client', () => ({
  API_BASE_URL: 'http://api.test',
  ensureCsrfToken: vi.fn(async () => undefined),
  getCsrfHeaders: vi.fn(() => ({})),
  refreshAuthSession: vi.fn(async () => undefined),
}))

import { streamNetworkExecution } from './stream'

const encoder = new TextEncoder()

function frame(sequence: number, event: string, data: Record<string, unknown>) {
  return encoder.encode(
    `id: ${sequence}\nevent: ${event}\ndata: ${JSON.stringify({
      protocol_version: 1,
      execution_id: 'execution-1',
      sequence,
      data,
    })}\n\n`,
  )
}

afterEach(() => {
  vi.restoreAllMocks()
  vi.unstubAllGlobals()
})

describe('Network reattach incremental output', () => {
  it('hydrates current output and continues the Root token tail before terminal completion', async () => {
    let streamController: ReadableStreamDefaultController<Uint8Array> | null = null
    const body = new ReadableStream<Uint8Array>({
      start(controller) {
        streamController = controller
        controller.enqueue(frame(12, 'run.state', {
          run_id: 'execution-1',
          kind: 'NETWORK',
          status: 'running',
          output: 'Hello',
          invocations: [],
          delegations: [],
          tools: [],
        }))
      },
    })
    const fetchMock = vi.fn().mockResolvedValue(new Response(body, {
      status: 200,
      headers: {
        'Content-Type': 'text/event-stream',
        'X-Network-Execution-ID': 'execution-1',
      },
    }))
    vi.stubGlobal('fetch', fetchMock)

    const onEvent = vi.fn()
    const streaming = streamNetworkExecution({
      networkId: 'network-1',
      projectId: 'project-1',
      networkSessionId: 'session-1',
      executionId: 'execution-1',
      message: 'resume me',
      idempotencyKey: 'stable-key',
    }, { onEvent })

    await vi.waitFor(() => {
      expect(onEvent).toHaveBeenCalledWith(
        'token',
        expect.objectContaining({ data: expect.objectContaining({ content: 'Hello' }) }),
      )
    })

    expect(onEvent).not.toHaveBeenCalledWith(
      'execution_completed',
      expect.anything(),
    )

    streamController?.enqueue(frame(13, 'token', {
      content: ' world',
      visibility: 'assistant',
      channel: 'final',
      phase: 'capability_response_generation',
    }))

    await vi.waitFor(() => {
      expect(onEvent).toHaveBeenCalledWith(
        'token',
        expect.objectContaining({ data: expect.objectContaining({ content: ' world' }) }),
      )
    })

    expect(onEvent).not.toHaveBeenCalledWith(
      'execution_completed',
      expect.anything(),
    )

    streamController?.enqueue(frame(14, 'execution_completed', {
      trace_id: 'trace-1',
      output: 'Hello world',
    }))
    streamController?.close()

    await streaming

    expect(fetchMock).toHaveBeenCalledTimes(1)
    expect(String(fetchMock.mock.calls[0]?.[0])).toBe(
      'http://api.test/network/executions/execution-1/stream',
    )
    expect((fetchMock.mock.calls[0]?.[1] as RequestInit).method).toBe('GET')
  })
})
