import { afterEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/lib/api/client', () => ({
  ensureCsrfToken: vi.fn(async () => undefined),
  getCsrfHeaders: vi.fn(() => ({})),
  refreshAuthSession: vi.fn(async () => undefined),
}))

import { askStreamV1 } from './stream-client'
import type { AskRequest } from './types'

const encoder = new TextEncoder()

function request(): AskRequest {
  return {
    project_id: 'project-1',
    agent_id: 'agent-1',
    message: 'Me conte uma história grande',
    execution_context: 'playground',
  }
}

function frame(event: string, payload: Record<string, unknown>) {
  return `event: ${event}\ndata: ${JSON.stringify({
    protocol_version: 1,
    type: event,
    ...payload,
  })}\n\n`
}

function token(content: string) {
  return frame('token', {
    run_id: 'run-boundary',
    content,
    visibility: 'assistant',
    channel: 'final',
    phase: 'final_response_generation',
  })
}

function callbacks() {
  return {
    onToken: vi.fn(),
    onSources: vi.fn(),
    onMeta: vi.fn(),
    onDone: vi.fn(),
    onError: vi.fn(),
    onProtocolError: vi.fn(),
  }
}

function response(body: ReadableStream<Uint8Array>) {
  return new Response(body, {
    status: 200,
    headers: {
      'Content-Type': 'text/event-stream',
      'X-Woobe-Run-ID': 'run-boundary',
    },
  })
}

afterEach(() => {
  vi.restoreAllMocks()
  vi.unstubAllGlobals()
})

describe('standalone ReadableStream boundaries', () => {
  it('dispatches the first token while the HTTP body is still open', async () => {
    let controller!: ReadableStreamDefaultController<Uint8Array>
    const body = new ReadableStream<Uint8Array>({
      start(nextController) {
        controller = nextController
        controller.enqueue(encoder.encode(frame('meta', { run_id: 'run-boundary' })))
        controller.enqueue(encoder.encode(token('Era')))
      },
    })
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(response(body)))
    const handlers = callbacks()

    const streaming = askStreamV1(request(), handlers)

    await vi.waitFor(() => {
      expect(handlers.onToken).toHaveBeenCalledWith(expect.objectContaining({ content: 'Era' }))
    })
    expect(handlers.onDone).not.toHaveBeenCalled()
    expect(handlers.onError).not.toHaveBeenCalled()

    controller.enqueue(encoder.encode(token(' uma vez')))
    controller.enqueue(encoder.encode(frame('done', {
      run_id: 'run-boundary',
      answer: 'Era uma vez',
    })))
    controller.close()

    await streaming

    expect(handlers.onToken.mock.calls.map(([item]) => item.content).join('')).toBe('Era uma vez')
    expect(handlers.onDone).toHaveBeenCalledWith(expect.objectContaining({ answer: 'Era uma vez' }))
  })

  it('reassembles an SSE frame split across arbitrary reader chunks without waiting for EOF', async () => {
    let controller!: ReadableStreamDefaultController<Uint8Array>
    const completeToken = token('fragmentado')
    const splitAt = Math.floor(completeToken.length / 2)
    const body = new ReadableStream<Uint8Array>({
      start(nextController) {
        controller = nextController
        controller.enqueue(encoder.encode(
          `${frame('meta', { run_id: 'run-boundary' })}${completeToken.slice(0, splitAt)}`,
        ))
      },
    })
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(response(body)))
    const handlers = callbacks()

    const streaming = askStreamV1(request(), handlers)

    await vi.waitFor(() => {
      expect(handlers.onMeta).toHaveBeenCalled()
    })
    expect(handlers.onToken).not.toHaveBeenCalled()

    controller.enqueue(encoder.encode(completeToken.slice(splitAt)))

    await vi.waitFor(() => {
      expect(handlers.onToken).toHaveBeenCalledWith(expect.objectContaining({ content: 'fragmentado' }))
    })
    expect(handlers.onDone).not.toHaveBeenCalled()

    controller.enqueue(encoder.encode(frame('done', {
      run_id: 'run-boundary',
      answer: 'fragmentado',
    })))
    controller.close()

    await streaming
    expect(handlers.onProtocolError).not.toHaveBeenCalled()
  })

  it('dispatches multiple SSE frames coalesced into one reader chunk before the terminal frame exists', async () => {
    let controller!: ReadableStreamDefaultController<Uint8Array>
    const body = new ReadableStream<Uint8Array>({
      start(nextController) {
        controller = nextController
        controller.enqueue(encoder.encode([
          frame('meta', { run_id: 'run-boundary' }),
          token('A'),
          token('B'),
          token('C'),
        ].join('')))
      },
    })
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(response(body)))
    const handlers = callbacks()

    const streaming = askStreamV1(request(), handlers)

    await vi.waitFor(() => {
      expect(handlers.onToken).toHaveBeenCalledTimes(3)
    })
    expect(handlers.onToken.mock.calls.map(([item]) => item.content).join('')).toBe('ABC')
    expect(handlers.onDone).not.toHaveBeenCalled()

    controller.enqueue(encoder.encode(frame('done', {
      run_id: 'run-boundary',
      answer: 'ABC',
    })))
    controller.close()

    await streaming
    expect(handlers.onDone).toHaveBeenCalledWith(expect.objectContaining({ answer: 'ABC' }))
  })
})
