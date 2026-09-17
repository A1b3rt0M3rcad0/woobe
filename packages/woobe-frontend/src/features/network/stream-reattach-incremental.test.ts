// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from 'vitest'

import { runtimeTestEnvelope } from '@/lib/runtime-stream-test-fixtures'

vi.mock('@/lib/api/client', () => ({
  API_BASE_URL: 'http://api.test',
  ensureCsrfToken: vi.fn(async () => undefined),
  getCsrfHeaders: vi.fn(() => ({})),
  refreshAuthSession: vi.fn(async () => undefined),
}))

import { streamNetworkExecution } from './stream'

const encoder = new TextEncoder()

function frame(
  sequence: number,
  event: string,
  data: Record<string, unknown>,
  executionId = 'execution-1',
) {
  return encoder.encode(
    `id: ${sequence}\nevent: ${event}\ndata: ${JSON.stringify(runtimeTestEnvelope(event, {
      execution_id: executionId,
      network_session_id: 'session-1',
      sequence,
      data,
    }, 'NETWORK'))}\n\n`,
  )
}

function setOnline(value: boolean) {
  vi.stubGlobal('navigator', { onLine: value })
}

afterEach(() => {
  vi.restoreAllMocks()
  vi.unstubAllGlobals()
})

describe('Network reattach incremental output', () => {
  it('hydrates current output and continues the Root token tail before terminal completion', async () => {
    const streamController = {
      current: null as ReadableStreamDefaultController<Uint8Array> | null,
    }
    const body = new ReadableStream<Uint8Array>({
      start(controller) {
        streamController.current = controller
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

    streamController.current?.enqueue(frame(13, 'token', {
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

    streamController.current?.enqueue(frame(14, 'execution_completed', {
      trace_id: 'trace-1',
      output: 'Hello world',
    }))
    streamController.current?.close()

    await streaming

    expect(fetchMock).toHaveBeenCalledTimes(1)
    expect(String(fetchMock.mock.calls[0]?.[0])).toBe(
      'http://api.test/network/executions/execution-1/stream',
    )
    expect((fetchMock.mock.calls[0]?.[1] as RequestInit).method).toBe('GET')
  })

  it('waits while offline and resumes the same Network execution after reconnect', async () => {
    setOnline(false)
    const recoveredBody = new ReadableStream<Uint8Array>({
      start(controller) {
        controller.enqueue(frame(41, 'run.state', {
          run_id: 'execution-offline',
          kind: 'NETWORK',
          status: 'running',
          output: 'partial recovered',
          invocations: [],
          delegations: [],
          tools: [],
        }, 'execution-offline'))
        controller.enqueue(frame(42, 'execution_completed', {
          trace_id: 'trace-offline',
          output: 'partial recovered done',
        }, 'execution-offline'))
        controller.close()
      },
    })
    const fetchMock = vi.fn()
      .mockRejectedValueOnce(new TypeError('Failed to fetch'))
      .mockResolvedValueOnce(new Response(recoveredBody, {
        status: 200,
        headers: {
          'Content-Type': 'text/event-stream',
          'X-Network-Execution-ID': 'execution-offline',
        },
      }))
    vi.stubGlobal('fetch', fetchMock)

    const onEvent = vi.fn()
    const streaming = streamNetworkExecution({
      networkId: 'network-1',
      projectId: 'project-1',
      networkSessionId: 'session-1',
      executionId: 'execution-offline',
      message: 'resume after offline',
      idempotencyKey: 'stable-offline-key',
    }, { onEvent })

    await vi.waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1))
    await new Promise((resolve) => setTimeout(resolve, 0))
    expect(fetchMock).toHaveBeenCalledTimes(1)

    setOnline(true)
    window.dispatchEvent(new Event('online'))
    await streaming

    expect(fetchMock).toHaveBeenCalledTimes(2)
    expect(fetchMock.mock.calls.every((call) =>
      String(call[0]) === 'http://api.test/network/executions/execution-offline/stream'
    )).toBe(true)
    expect(fetchMock.mock.calls.every((call) =>
      (call[1] as RequestInit).method === 'GET'
    )).toBe(true)
    expect(onEvent).toHaveBeenCalledWith(
      'token',
      expect.objectContaining({
        data: expect.objectContaining({ content: 'partial recovered' }),
      }),
    )
    expect(onEvent).toHaveBeenCalledWith(
      'execution_completed',
      expect.objectContaining({
        data: expect.objectContaining({ output: 'partial recovered done' }),
      }),
    )
  })
})