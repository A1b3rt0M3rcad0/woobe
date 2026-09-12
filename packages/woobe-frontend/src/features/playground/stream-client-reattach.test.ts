// @vitest-environment jsdom
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

function setOnline(value: boolean) {
  vi.stubGlobal('navigator', { onLine: value })
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

  it('keeps observing the same Run after reload while cancellation is pending', async () => {
    const streamController = {
      current: null as ReadableStreamDefaultController<Uint8Array> | null,
    }
    const body = new ReadableStream<Uint8Array>({
      start(controller) {
        streamController.current = controller
        controller.enqueue(sse(21, 'run.state', {
          run_id: 'run-stopping',
          status: 'cancel_requested',
          output: 'partial answer',
        }))
      },
    })
    const fetchMock = vi.fn().mockResolvedValue(new Response(body, {
      status: 200,
      headers: { 'Content-Type': 'text/event-stream' },
    }))
    vi.stubGlobal('fetch', fetchMock)

    const onRunState = vi.fn()
    const onToken = vi.fn()
    const onCancelled = vi.fn()
    const onDone = vi.fn()
    const onError = vi.fn()
    const reattach = reattachAgentRunV1('run-stopping', {
      onToken,
      onSources: vi.fn(),
      onMeta: vi.fn(),
      onDone,
      onError,
      onCancelled,
      onRunState,
    })

    await vi.waitFor(() => {
      expect(onRunState).toHaveBeenCalledWith(expect.objectContaining({
        run_id: 'run-stopping',
        status: 'cancel_requested',
      }))
      expect(onToken).toHaveBeenCalledWith(expect.objectContaining({ content: 'partial answer' }))
    })

    expect(onDone).not.toHaveBeenCalled()
    expect(onCancelled).not.toHaveBeenCalled()
    expect(onError).not.toHaveBeenCalled()

    streamController.current?.enqueue(sse(22, 'cancelled', {
      run_id: 'run-stopping',
      status: 'cancelled',
      output: 'partial answer',
      partial: true,
      persisted: true,
    }))
    streamController.current?.close()

    await reattach

    expect(fetchMock).toHaveBeenCalledTimes(1)
    expect(onCancelled).toHaveBeenCalledWith(expect.objectContaining({
      run_id: 'run-stopping',
      output: 'partial answer',
      persisted: true,
    }))
    expect(onDone).not.toHaveBeenCalled()
    expect(onError).not.toHaveBeenCalled()
  })

  it('waits while the browser is offline and resumes the same Run after connectivity returns', async () => {
    setOnline(false)
    const recoveredBody = new ReadableStream<Uint8Array>({
      start(controller) {
        controller.enqueue(sse(31, 'run.state', {
          run_id: 'run-offline',
          status: 'running',
          output: 'partial recovered',
        }))
        controller.enqueue(sse(32, 'done', {
          run_id: 'run-offline',
          answer: 'partial recovered done',
        }))
        controller.close()
      },
    })
    const fetchMock = vi.fn()
      .mockRejectedValueOnce(new TypeError('Failed to fetch'))
      .mockResolvedValueOnce(new Response(recoveredBody, {
        status: 200,
        headers: { 'Content-Type': 'text/event-stream' },
      }))
    vi.stubGlobal('fetch', fetchMock)

    const onToken = vi.fn()
    const onDone = vi.fn()
    const reattach = reattachAgentRunV1('run-offline', {
      onToken,
      onSources: vi.fn(),
      onMeta: vi.fn(),
      onDone,
      onError: vi.fn(),
    })

    await vi.waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1))
    await new Promise((resolve) => setTimeout(resolve, 0))
    expect(fetchMock).toHaveBeenCalledTimes(1)

    setOnline(true)
    window.dispatchEvent(new Event('online'))
    await reattach

    expect(fetchMock).toHaveBeenCalledTimes(2)
    expect(fetchMock.mock.calls.every((call) =>
      String(call[0]).includes('/runtime/runs/run-offline/stream')
    )).toBe(true)
    expect(fetchMock.mock.calls.every((call) =>
      (call[1] as RequestInit).method === 'GET'
    )).toBe(true)
    expect(onToken).toHaveBeenCalledWith(expect.objectContaining({
      content: 'partial recovered',
    }))
    expect(onDone).toHaveBeenCalledWith(expect.objectContaining({
      answer: 'partial recovered done',
    }))
  })
})
