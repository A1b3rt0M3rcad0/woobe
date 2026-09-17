import { runtimeTestEnvelope } from '@/lib/runtime-stream-test-fixtures'
import { afterEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/lib/api/client', () => ({
  ensureCsrfToken: vi.fn(async () => undefined),
  getCsrfHeaders: vi.fn(() => ({})),
  refreshAuthSession: vi.fn(async () => undefined),
}))

import { askStreamV1 } from './stream-client'
import type { AskRequest } from './types'

const encoder = new TextEncoder()

function frame(event: string, payload: Record<string, unknown>) {
  return `event: ${event}\ndata: ${JSON.stringify(runtimeTestEnvelope(event, {
    protocol_version: 2,
    type: event,
    ...payload,
  }, 'AGENT'))}\n\n`
}

function request(): AskRequest {
  return {
    project_id: 'project-1',
    agent_id: 'agent-1',
    message: 'stream this response',
    execution_context: 'playground',
  }
}

function token(content: string) {
  return frame('token', {
    content,
    visibility: 'assistant',
    channel: 'final',
    phase: 'capability_response_generation',
  })
}

function installPaintGate() {
  const pendingPaints: FrameRequestCallback[] = []
  vi.stubGlobal('requestAnimationFrame', vi.fn((callback: FrameRequestCallback) => {
    pendingPaints.push(callback)
    return pendingPaints.length
  }))
  return pendingPaints
}

afterEach(() => {
  vi.restoreAllMocks()
  vi.unstubAllGlobals()
})

describe('standalone SSE paint pacing', () => {
  it('does not collapse a coalesced HTTP burst into one browser paint', async () => {
    const body = new ReadableStream<Uint8Array>({
      start(controller) {
        controller.enqueue(encoder.encode([
          frame('meta', { run_id: 'run-1', trace_id: 'trace-1' }),
          ...['A', 'B', 'C', 'D', 'E', 'F', 'G'].map(token),
          frame('done', { run_id: 'run-1', answer: 'ABCDEFG' }),
        ].join('')))
        controller.close()
      },
    })
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(body, {
      status: 200,
      headers: { 'Content-Type': 'text/event-stream' },
    })))

    const pendingPaints = installPaintGate()
    const onToken = vi.fn()
    const onDone = vi.fn()
    const streaming = askStreamV1(request(), {
      onToken,
      onSources: vi.fn(),
      onMeta: vi.fn(),
      onDone,
      onError: vi.fn(),
    })

    await vi.waitFor(() => {
      expect(onToken).toHaveBeenCalledTimes(6)
    })
    expect(onDone).not.toHaveBeenCalled()
    expect(pendingPaints).toHaveLength(1)

    pendingPaints.shift()?.(0)
    await vi.waitFor(() => {
      expect(onToken).toHaveBeenCalledTimes(7)
      expect(pendingPaints).toHaveLength(1)
    })
    expect(onDone).not.toHaveBeenCalled()

    pendingPaints.shift()?.(16)
    await streaming

    expect(onToken.mock.calls.map(([item]) => item.content).join('')).toBe('ABCDEFG')
    expect(onDone).toHaveBeenCalledWith(expect.objectContaining({ answer: 'ABCDEFG' }))
  })

  it('keeps the paint budget across separate reader chunks that resolve without a browser paint', async () => {
    const body = new ReadableStream<Uint8Array>({
      start(controller) {
        controller.enqueue(encoder.encode(frame('meta', { run_id: 'run-2' })))
        for (const content of ['A', 'B', 'C', 'D', 'E', 'F', 'G']) {
          controller.enqueue(encoder.encode(token(content)))
        }
        controller.enqueue(encoder.encode(frame('done', { run_id: 'run-2', answer: 'ABCDEFG' })))
        controller.close()
      },
    })
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(body, {
      status: 200,
      headers: { 'Content-Type': 'text/event-stream' },
    })))

    const pendingPaints = installPaintGate()
    const onToken = vi.fn()
    const onDone = vi.fn()
    const streaming = askStreamV1(request(), {
      onToken,
      onSources: vi.fn(),
      onMeta: vi.fn(),
      onDone,
      onError: vi.fn(),
    })

    await vi.waitFor(() => {
      expect(onToken).toHaveBeenCalledTimes(6)
      expect(pendingPaints).toHaveLength(1)
    })
    expect(onDone).not.toHaveBeenCalled()

    pendingPaints.shift()?.(0)
    await vi.waitFor(() => {
      expect(onToken).toHaveBeenCalledTimes(7)
      expect(pendingPaints).toHaveLength(1)
    })
    expect(onDone).not.toHaveBeenCalled()

    pendingPaints.shift()?.(16)
    await streaming

    expect(onToken.mock.calls.map(([item]) => item.content).join('')).toBe('ABCDEFG')
    expect(onDone).toHaveBeenCalledWith(expect.objectContaining({ answer: 'ABCDEFG' }))
  })

  it('flushes a residual visual batch before dispatching the terminal event', async () => {
    const body = new ReadableStream<Uint8Array>({
      start(controller) {
        controller.enqueue(encoder.encode([
          frame('meta', { run_id: 'run-3' }),
          ...['A', 'B', 'C'].map(token),
          frame('done', { run_id: 'run-3', answer: 'ABC' }),
        ].join('')))
        controller.close()
      },
    })
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(body, {
      status: 200,
      headers: { 'Content-Type': 'text/event-stream' },
    })))

    const pendingPaints = installPaintGate()
    const onToken = vi.fn()
    const onDone = vi.fn()
    const streaming = askStreamV1(request(), {
      onToken,
      onSources: vi.fn(),
      onMeta: vi.fn(),
      onDone,
      onError: vi.fn(),
    })

    await vi.waitFor(() => {
      expect(onToken).toHaveBeenCalledTimes(3)
      expect(pendingPaints).toHaveLength(1)
    })
    expect(onDone).not.toHaveBeenCalled()

    pendingPaints.shift()?.(0)
    await streaming

    expect(onDone).toHaveBeenCalledWith(expect.objectContaining({ answer: 'ABC' }))
  })

  it('can be aborted while a browser paint is pending', async () => {
    let streamCancelled = false
    const body = new ReadableStream<Uint8Array>({
      start(controller) {
        controller.enqueue(encoder.encode([
          frame('meta', { run_id: 'run-4' }),
          ...['A', 'B', 'C', 'D', 'E', 'F'].map(token),
        ].join('')))
      },
      cancel() {
        streamCancelled = true
      },
    })
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(body, {
      status: 200,
      headers: { 'Content-Type': 'text/event-stream' },
    })))

    const pendingPaints = installPaintGate()
    const controller = new AbortController()
    const streaming = askStreamV1(request(), {
      onToken: vi.fn(),
      onSources: vi.fn(),
      onMeta: vi.fn(),
      onDone: vi.fn(),
      onError: vi.fn(),
    }, controller.signal)

    await vi.waitFor(() => {
      expect(pendingPaints).toHaveLength(1)
    })
    controller.abort()

    await expect(streaming).rejects.toMatchObject({ name: 'AbortError' })
    expect(streamCancelled).toBe(true)
  })

  it('does not wait for animation frames while the document is hidden', async () => {
    const body = new ReadableStream<Uint8Array>({
      start(controller) {
        controller.enqueue(encoder.encode([
          frame('meta', { run_id: 'run-5' }),
          ...['A', 'B', 'C', 'D', 'E', 'F', 'G'].map(token),
          frame('done', { run_id: 'run-5', answer: 'ABCDEFG' }),
        ].join('')))
        controller.close()
      },
    })
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(body, {
      status: 200,
      headers: { 'Content-Type': 'text/event-stream' },
    })))
    vi.stubGlobal('document', {
      visibilityState: 'hidden',
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    })
    const requestPaint = vi.fn()
    vi.stubGlobal('requestAnimationFrame', requestPaint)
    const onDone = vi.fn()

    await askStreamV1(request(), {
      onToken: vi.fn(),
      onSources: vi.fn(),
      onMeta: vi.fn(),
      onDone,
      onError: vi.fn(),
    })

    expect(requestPaint).not.toHaveBeenCalled()
    expect(onDone).toHaveBeenCalledWith(expect.objectContaining({ answer: 'ABCDEFG' }))
  })
})
