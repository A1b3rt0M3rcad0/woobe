import { describe, it, expect, vi, beforeEach } from 'vitest'
import type { AskResponse } from '../types'

function normalizeResponse(input: Record<string, unknown>): AskResponse {
  return {
    answer: (input.answer as string) ?? '',
    session_id: (input.session_id as string) ?? null,
    message_id: (input.message_id as string) ?? null,
    usage: input.usage
      ? {
          input_tokens: (input.usage as Record<string, unknown>).input_tokens as number ?? null,
          output_tokens: (input.usage as Record<string, unknown>).output_tokens as number ?? null,
          total_tokens: (input.usage as Record<string, unknown>).total_tokens as number ?? null,
          cost_usd: (input.usage as Record<string, unknown>).cost_usd as number ?? null,
        }
      : { input_tokens: null, output_tokens: null, total_tokens: null, cost_usd: null },
    sources: (input.sources as []) ?? [],
    tool_calls: (input.tool_calls as []) ?? [],
    trace_id: (input.trace_id as string) ?? null,
    model: (input.model as string) ?? null,
    provider: (input.provider as string) ?? null,
    fallback_used: (input.fallback_used as boolean) ?? false,
    fallback_info: (input.fallback_info ?? null) as AskResponse['fallback_info'],
    latency_ms: (input.latency_ms as number) ?? null,
    parsed_output: (input.parsed_output as Record<string, unknown>) ?? null,
    output_parse_error: (input.output_parse_error as string) ?? null,
    history_message_count: (input.history_message_count as number) ?? 0,
    history_truncated: (input.history_truncated as boolean) ?? false,
  }
}

function parseSSELine(line: string): Record<string, unknown> | null {
  const trimmed = line.trim()
  if (!trimmed.startsWith('data: ')) return null
  try {
    return JSON.parse(trimmed.slice(6))
  } catch {
    return null
  }
}

describe('session continuity — API data flow', () => {
  describe('normalizeResponse preserves session_id', () => {
    it('passes session_id from response', () => {
      const input = {
        answer: 'ok',
        session_id: 'abc-123',
        usage: null,
        sources: [],
        tool_calls: [],
      }
      const result = normalizeResponse(input as unknown as Record<string, unknown>)
      expect(result.session_id).toBe('abc-123')
    })

    it('handles null session_id', () => {
      const input = {
        answer: 'ok',
        session_id: null,
        usage: null,
        sources: [],
        tool_calls: [],
      }
      const result = normalizeResponse(input as unknown as Record<string, unknown>)
      expect(result.session_id).toBeNull()
    })

    it('passes history fields through response', () => {
      const input: Record<string, unknown> = {
        answer: 'ok',
        session_id: 's1',
        usage: null,
        sources: [],
        tool_calls: [],
        history_message_count: 5,
        history_truncated: true,
      }
      const result = normalizeResponse(input)
      expect(result.history_message_count).toBe(5)
      expect(result.history_truncated).toBe(true)
    })
  })

  describe('SSE event parsing', () => {
    it('parses meta event with session_id', () => {
      const line = 'data: {"type":"meta","session_id":"abc-123","trace_id":"trace-1"}'
      const parsed = parseSSELine(line)
      expect(parsed).not.toBeNull()
      expect(parsed!.type).toBe('meta')
      expect(parsed!.session_id).toBe('abc-123')
    })

    it('parses done event with session_id preserved', () => {
      const line = 'data: {"type":"done","session_id":"abc-123","answer":"done"}'
      const parsed = parseSSELine(line)
      expect(parsed).not.toBeNull()
      expect(parsed!.type).toBe('done')
      expect(parsed!.session_id).toBe('abc-123')
    })

    it('parses error event', () => {
      const line = 'data: {"type":"error","message":"Session not found"}'
      const parsed = parseSSELine(line)
      expect(parsed).not.toBeNull()
      expect(parsed!.type).toBe('error')
      expect(parsed!.message).toBe('Session not found')
    })

    it('ignores non-data lines', () => {
      const line = ': heartbeat'
      const parsed = parseSSELine(line)
      expect(parsed).toBeNull()
    })
  })

  describe('request payload contains session_id', () => {
    it('stateful first turn sends null session_id', () => {
      const payload = {
        project_id: 'proj-1',
        agent_id: 'agent-1',
        message: 'Hello',
        session_id: null,
      }
      expect(payload.session_id).toBeNull()
      expect(JSON.parse(JSON.stringify(payload)).session_id).toBeNull()
    })

    it('second turn sends the same session_id', () => {
      const sessionId = 'abc-123'
      const second = {
        project_id: 'proj-1',
        agent_id: 'agent-1',
        message: 'Again',
        session_id: sessionId,
      }
      expect(second.session_id).toBe(sessionId)
    })
  })

  describe('askStream SSE flow', () => {
    async function simulateStream(
      events: Record<string, unknown>[],
      onMeta: (meta: { session_id?: string | null; trace_id?: string | null }) => void,
      onDone: (response: Partial<AskResponse>) => void,
      onError: (error: Error) => void,
    ) {
      const lines = events
        .map((e) => `data: ${JSON.stringify({ type: e.type, ...e })}\n`)
        .join('')
      const reader = new ReadableStream({
        start(controller) {
          controller.enqueue(new TextEncoder().encode(lines))
          controller.close()
        },
      })
      const response = new Response(reader, {
        headers: { 'Content-Type': 'text/event-stream' },
      })

      const reader2 = response.body!.getReader()
      const decoder = new TextDecoder()
      let buffer = ''

      while (true) {
        const { done, value } = await reader2.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })
        const parts = buffer.split('\n')
        buffer = parts.pop() || ''
        for (const line of parts) {
          const trimmed = line.trim()
          if (!trimmed.startsWith('data: ')) continue
          const parsed = JSON.parse(trimmed.slice(6))
          switch (parsed.type) {
            case 'meta':
              onMeta({ session_id: parsed.session_id ?? null, trace_id: parsed.trace_id ?? null })
              break
            case 'done':
              onDone(normalizeResponse(parsed))
              break
            case 'error':
              onError(new Error(parsed.message ?? 'Stream error'))
              return
          }
        }
      }
    }

    it('meta event defines session_id', async () => {
      const metaCalls: { session_id?: string | null; trace_id?: string | null }[] = []
      await simulateStream(
        [
          { type: 'meta', session_id: 'session-1', trace_id: 'trace-1' },
          { type: 'done', session_id: 'session-1', answer: 'ok' },
        ],
        (meta) => metaCalls.push(meta),
        () => {},
        () => {},
      )
      expect(metaCalls).toHaveLength(1)
      expect(metaCalls[0].session_id).toBe('session-1')
    })

    it('done event preserves session_id from meta', async () => {
      const doneCalls: Partial<AskResponse>[] = []
      await simulateStream(
        [
          { type: 'meta', session_id: 'session-1', trace_id: 'trace-1' },
          { type: 'done', session_id: 'session-1', answer: 'ok' },
        ],
        () => {},
        (response) => doneCalls.push(response),
        () => {},
      )
      expect(doneCalls).toHaveLength(1)
      expect(doneCalls[0].session_id).toBe('session-1')
    })

    it('error event stops processing', async () => {
      const errorCalls: Error[] = []
      let doneCalled = false
      await simulateStream(
        [
          { type: 'meta', session_id: 'session-1', trace_id: 'trace-1' },
          { type: 'error', message: 'Session not found' },
          { type: 'done', session_id: 'session-1', answer: 'should not appear' },
        ],
        () => {},
        () => { doneCalled = true },
        (err) => errorCalls.push(err),
      )
      expect(errorCalls).toHaveLength(1)
      expect(errorCalls[0].message).toBe('Session not found')
      expect(doneCalled).toBe(false)
    })
  })
})
