import { afterEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/lib/api/client', () => ({
  ensureCsrfToken: vi.fn(async () => undefined),
  getCsrfHeaders: vi.fn(() => ({})),
  refreshAuthSession: vi.fn(async () => undefined),
}))

import { reattachAgentRunV1 } from './stream-client'

const encoder = new TextEncoder()

function sse(sequence: number, event: string, payload: Record<string, unknown>) {
  return encoder.encode(
    `id: ${sequence}\nevent: ${event}\ndata: ${JSON.stringify({
      protocol_version: 1,
      type: event,
      sequence,
      ...payload,
    })}\n\n`,
  )
}

afterEach(() => {
  vi.restoreAllMocks()
  vi.unstubAllGlobals()
})

describe('standalone Agent Run reattach streaming', () => {
  it('hydrates current output immediately and keeps capability-aware tail incremental', async () => {
    const streamController = {
      current: null as ReadableStreamDefaultController<Uint8Array> | null,
    }
    const body = new ReadableStream<Uint8Array>({
      start(controller) {
        streamController.current = controller
        controller.enqueue(sse(12, 'run.state', {
          run_id: 'run-1',
          status: 'running',
          output: 'Hello',
        }))
      },
    })
    const fetchMock = vi.fn().mockResolvedValue(new Response(body, {
      status: 200,
      headers: { 'Content-Type': 'text/event-stream' },
    }))
    vi.stubGlobal('fetch', fetchMock)

    const onToken = vi.fn()
    const onDone = vi.fn()
    const reattach = reattachAgentRunV1('run-1', {
      onToken,
      onSources: vi.fn(),
      onMeta: vi.fn(),
      onDone,
      onError: vi.fn(),
    })

    await vi.waitFor(() => {
      expect(onToken).toHaveBeenCalledWith(expect.objectContaining({ content: 'Hello' }))
    })

    expect(onDone).not.toHaveBeenCalled()

    streamController.current?.enqueue(sse(13, 'token', {
      content: ' world',
      visibility: 'assistant',
      channel: 'final',
      phase: 'capability_response_generation',
      provider: 'test-provider',
      model: 'test-model',
    }))

    await vi.waitFor(() => {
      expect(onToken).toHaveBeenCalledWith(expect.objectContaining({
        content: ' world',
        phase: 'capability_response_generation',
      }))
    })

    expect(onDone).not.toHaveBeenCalled()

    streamController.current?.enqueue(sse(14, 'done', {
      answer: 'Hello world',
      run_id: 'run-1',
    }))
    streamController.current?.close()

    await reattach

    expect(fetchMock).toHaveBeenCalledTimes(1)
    expect(String(fetchMock.mock.calls[0]?.[0])).toContain('/runtime/runs/run-1/stream')
    expect((fetchMock.mock.calls[0]?.[1] as RequestInit).method).toBe('GET')
    expect(onDone).toHaveBeenCalledWith(expect.objectContaining({ answer: 'Hello world' }))
  })
})
