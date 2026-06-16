import { describe, it, expect } from 'vitest'
import type { AskResponse } from '../types'

describe('history observability — response fields', () => {
  it('AskResponse contains history fields', () => {
    const response: AskResponse = {
      answer: 'test answer',
      session_id: null,
      message_id: null,
      usage: null,
      sources: [],
      tool_calls: [],
      trace_id: null,
      model: null,
      provider: null,
      fallback_used: false,
      latency_ms: null,
      history_message_count: 5,
      history_truncated: true,
    }

    expect(response.history_message_count).toBe(5)
    expect(response.history_truncated).toBe(true)
  })

  it('default history values are zero and false', () => {
    const response: AskResponse = {
      answer: '',
      session_id: null,
      message_id: null,
      usage: null,
      sources: [],
      tool_calls: [],
      trace_id: null,
      model: null,
      provider: null,
      fallback_used: false,
      latency_ms: null,
      history_message_count: 0,
      history_truncated: false,
    }

    expect(response.history_message_count).toBe(0)
    expect(response.history_truncated).toBe(false)
  })

  it('history fields survive serialization round-trip', () => {
    const original: AskResponse = {
      answer: 'test',
      session_id: null,
      message_id: null,
      usage: null,
      sources: [],
      tool_calls: [],
      trace_id: null,
      model: null,
      provider: null,
      fallback_used: false,
      latency_ms: null,
      history_message_count: 3,
      history_truncated: false,
    }

    const json = JSON.stringify(original)
    const parsed = JSON.parse(json) as AskResponse

    expect(parsed.history_message_count).toBe(3)
    expect(parsed.history_truncated).toBe(false)
  })
})
