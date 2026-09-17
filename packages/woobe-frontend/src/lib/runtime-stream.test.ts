import { describe, expect, it } from 'vitest'

import {
  RUNTIME_STREAM_MAX_ATTEMPTS,
  RuntimeStreamGapError,
  RuntimeStreamProtocolError,
  acceptRuntimeFrameSequence,
  parseRuntimeFrame,
  reconcileRuntimeOutput,
  runtimeRetryDelayMs,
  runtimeTerminalStatus,
} from './runtime-stream'

describe('canonical runtime stream protocol', () => {
  it('accepts a replacement run.state jump and continues from its high watermark', () => {
    const state = { sequence: 125 }
    const projection = parseRuntimeFrame(
      'id: 131\nevent: run.state\ndata: {"protocol_version":2,"event_id":"e-131","run_id":"run-1","session_id":"session-1","run_kind":"AGENT","sequence":131,"type":"run.state","occurred_at":"2026-09-16T20:00:00Z","payload":{"type":"run.state","sequence":131,"status":"running","output":"current"}}',
    )
    expect(projection).not.toBeNull()
    expect(acceptRuntimeFrameSequence(projection!, state)).toBe(true)
    expect(state.sequence).toBe(131)

    const live = parseRuntimeFrame(
      'id: 132\nevent: token\ndata: {"protocol_version":2,"event_id":"e-132","run_id":"run-1","session_id":"session-1","run_kind":"AGENT","sequence":132,"type":"token","occurred_at":"2026-09-16T20:00:00Z","payload":{"type":"token","sequence":132,"content":"next"}}',
    )
    expect(live).not.toBeNull()
    expect(acceptRuntimeFrameSequence(live!, state)).toBe(true)
    expect(state.sequence).toBe(132)
  })

  it('parses the Network envelope through the same runtime frame contract', () => {
    const frame = parseRuntimeFrame(
      'id: 7\nevent: run.state\ndata: {"protocol_version":2,"event_id":"e-7","run_id":"run-1","session_id":"session-1","run_kind":"NETWORK","sequence":7,"type":"run.state","occurred_at":"2026-09-16T20:00:00Z","payload":{"status":"running","output":"hello","sequence":7}}',
    )
    expect(frame?.sequence).toBe(7)
    expect(frame).toMatchObject({ kind: 'semantic', runId: 'run-1', sessionId: 'session-1', runKind: 'NETWORK' })
    expect(frame?.payload.output).toBe('hello')
    expect(frame?.payload.status).toBe('running')
  })

  it('rejects incremental gaps without advancing the accepted sequence', () => {
    const state = { sequence: 10 }
    const skipped = parseRuntimeFrame(
      'id: 12\nevent: token\ndata: {"protocol_version":2,"event_id":"e-12","run_id":"run-1","session_id":"session-1","run_kind":"AGENT","sequence":12,"type":"token","occurred_at":"2026-09-16T20:00:00Z","payload":{"type":"token","sequence":12,"content":"gap"}}',
    )
    expect(skipped).not.toBeNull()
    expect(() => acceptRuntimeFrameSequence(skipped!, state)).toThrow(RuntimeStreamGapError)
    expect(state.sequence).toBe(10)
  })

  it('accepts durable run.state without rewinding the hot sequence cursor', () => {
    const state = { sequence: 20 }
    const durable = parseRuntimeFrame(
      'event: run.state\ndata: {"protocol_version":2,"event_id":"e-0","run_id":"run-1","session_id":"session-1","run_kind":"AGENT","sequence":0,"type":"run.state","occurred_at":"2026-09-16T20:00:00Z","payload":{"type":"run.state","status":"cancelled","output":"partial","realtime_available":false}}',
    )
    expect(durable).not.toBeNull()
    expect(acceptRuntimeFrameSequence(durable!, state)).toBe(true)
    expect(state.sequence).toBe(20)
    expect(runtimeTerminalStatus(durable!)).toBe('cancelled')
  })

  it('reconciles append and replacement snapshots with one policy', () => {
    expect(reconcileRuntimeOutput('Hello', 'Hello world')).toEqual({
      output: 'Hello world',
      append: ' world',
      retract: 0,
      changed: true,
    })
    expect(reconcileRuntimeOutput('old', 'new')).toEqual({
      output: 'new',
      append: 'new',
      retract: 3,
      changed: true,
    })
    expect(reconcileRuntimeOutput('same', 'same')).toEqual({
      output: 'same',
      append: '',
      retract: 0,
      changed: false,
    })
  })

  it('exposes one retry budget and deterministic backoff', () => {
    expect(RUNTIME_STREAM_MAX_ATTEMPTS).toBe(4)
    expect([0, 1, 2, 3].map(runtimeRetryDelayMs)).toEqual([250, 500, 750, 1000])
  })

  it('rejects unsupported declared protocol versions explicitly', () => {
    expect(() => parseRuntimeFrame(
      'id: 1\nevent: token\ndata: {"protocol_version":99,"sequence":1,"content":"x"}',
    )).toThrow(RuntimeStreamProtocolError)
  })

  it('classifies terminal Agent and Network events consistently', () => {
    const completed = parseRuntimeFrame(
      'event: run.state\ndata: {"protocol_version":2,"event_id":"e-3","run_id":"run-1","session_id":"session-1","run_kind":"AGENT","sequence":3,"type":"run.state","occurred_at":"2026-09-16T20:00:00Z","payload":{"type":"run.state","sequence":3,"status":"completed","output":"done"}}',
    )
    const failed = parseRuntimeFrame(
      'event: execution_failed\ndata: {"protocol_version":2,"event_id":"e-4","run_id":"run-1","session_id":"session-1","run_kind":"AGENT","sequence":4,"type":"execution_failed","occurred_at":"2026-09-16T20:00:00Z","payload":{"sequence":4,"message":"failed"}}',
    )
    const cancelled = parseRuntimeFrame(
      'event: cancelled\ndata: {"protocol_version":2,"event_id":"e-5","run_id":"run-1","session_id":"session-1","run_kind":"AGENT","sequence":5,"type":"cancelled","occurred_at":"2026-09-16T20:00:00Z","payload":{"sequence":5,"output":"partial","cancelled":true}}',
    )
    const timedOut = parseRuntimeFrame(
      'event: execution_timed_out\ndata: {"protocol_version":2,"event_id":"e-6","run_id":"run-1","session_id":"session-1","run_kind":"AGENT","sequence":6,"type":"execution_timed_out","occurred_at":"2026-09-16T20:00:00Z","payload":{"sequence":6,"message":"timeout"}}',
    )
    const uncertain = parseRuntimeFrame(
      'event: execution_failed\ndata: {"protocol_version":2,"event_id":"e-7","run_id":"run-1","session_id":"session-1","run_kind":"AGENT","sequence":7,"type":"execution_failed","occurred_at":"2026-09-16T20:00:00Z","payload":{"sequence":7,"uncertain":true}}',
    )

    expect(runtimeTerminalStatus(completed!)).toBe('completed')
    expect(runtimeTerminalStatus(failed!)).toBe('failed')
    expect(runtimeTerminalStatus(cancelled!)).toBe('cancelled')
    expect(runtimeTerminalStatus(timedOut!)).toBe('timed_out')
    expect(runtimeTerminalStatus(uncertain!)).toBe('uncertain')
  })
})


describe('protocol v2 identity validation', () => {
  const event = { protocol_version: 2, event_id: 'event-1', run_id: 'run-1', session_id: 'session-1',
    run_kind: 'AGENT', sequence: 1, type: 'token', occurred_at: '2026-09-16T20:00:00Z', payload: { content: 'hi' } }
  it.each(['event_id', 'run_id', 'session_id', 'sequence', 'occurred_at', 'payload'])('rejects missing %s', (field) => {
    const invalid: Record<string, unknown> = { ...event }
    delete invalid[field]
    expect(() => parseRuntimeFrame(`event: token\ndata: ${JSON.stringify(invalid)}`)).toThrow(RuntimeStreamProtocolError)
  })
  it('keeps heartbeat outside semantic ordering', () => {
    const heartbeat = parseRuntimeFrame('event: heartbeat\ndata: {"protocol_version":2,"type":"heartbeat","occurred_at":"2026-09-16T20:00:00Z"}')!
    expect(heartbeat.kind).toBe('transport')
    const state = { sequence: 8 }
    acceptRuntimeFrameSequence(heartbeat, state)
    expect(state.sequence).toBe(8)
    expect(runtimeTerminalStatus(heartbeat)).toBeNull()
  })
  it('rejects domain events that omit canonical Run and Session identity', () => {
    expect(() => parseRuntimeFrame(
      'event: agent_activity\ndata: {"protocol_version":2,"type":"agent_activity","occurred_at":"2026-09-16T20:00:00Z","payload":{"status":"thinking"}}',
    )).toThrow(RuntimeStreamProtocolError)
    expect(() => parseRuntimeFrame(
      'event: token\ndata: {"protocol_version":2,"type":"token","occurred_at":"2026-09-16T20:00:00Z","payload":{"content":"hello"}}',
    )).toThrow(RuntimeStreamProtocolError)
  })
  it('rejects mismatched SSE identity and legacy emission', () => {
    expect(() => parseRuntimeFrame(`id: 2\nevent: token\ndata: ${JSON.stringify(event)}`)).toThrow(RuntimeStreamProtocolError)
    expect(() => parseRuntimeFrame(`event: token\ndata: ${JSON.stringify({ ...event, protocol_version: 1 })}`)).toThrow(RuntimeStreamProtocolError)
  })
})