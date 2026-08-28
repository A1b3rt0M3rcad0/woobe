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
  return `event: ${event}\ndata: ${JSON.stringify({
    protocol_version: 1,
    type: event,
    ...payload,
  })}\n\n`
}

function request(): AskRequest {
  return {
    project_id: 'project-1',
    agent_id: 'agent-1',
    message: 'stream this response',
    execution_context: 'playground',
  }
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
          ...['A', 'B', 'C', 'D', 'E', 'F', 'G'].map((content) => frame('token', {
            content,
            visibility: 'assistant',
            channel: 'final',
            phase: 'capability_response_generation',
          })),
          frame('done', { run_id: 'run-1', answer: 'ABCDEFG' }),
        ].join('')))
        controller.close()
      },
    })
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(body, {
      status: 200,
      headers: { 'Content-Type': 'text/event-stream' },
    })))

    const pendingPaints: FrameRequestCallback[] = []
    vi.stubGlobal('requestAnimationFrame', vi.fn((callback: FrameRequestCallback) => {
      pendingPaints.push(callback)
      return pendingPaints.length
    }))

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
    await streaming

    expect(onToken).toHaveBeenCalledTimes(7)
    expect(onToken.mock.calls.map(([token]) => token.content).join('')).toBe('ABCDEFG')
    expect(onDone).toHaveBeenCalledWith(expect.objectContaining({ answer: 'ABCDEFG' }))
  })
})
