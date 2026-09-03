import { describe, expect, it } from 'vitest'

import {
  RuntimeStreamGapError,
  RuntimeStreamProtocolError,
  acceptRuntimeFrameSequence,
  parseRuntimeFrame,
  runtimeTerminalStatus,
} from './runtime-stream'

describe('canonical runtime stream protocol', () => {
  it('accepts a replacement run.state jump and continues from its high watermark', () => {
    const state = { sequence: 125 }
    const projection = parseRuntimeFrame(
      'id: 131\nevent: run.state\ndata: {"type":"run.state","sequence":131,"status":"running","output":"current"}',
    )
    expect(projection).not.toBeNull()
    expect(acceptRuntimeFrameSequence(projection!, state)).toBe(true)
    expect(state.sequence).toBe(131)

    const live = parseRuntimeFrame(
      'id: 132\nevent: token\ndata: {"type":"token","sequence":132,"content":"next"}',
    )
    expect(live).not.toBeNull()
    expect(acceptRuntimeFrameSequence(live!, state)).toBe(true)
    expect(state.sequence).toBe(132)
  })

  it('parses the Network envelope through the same runtime frame contract', () => {
    const frame = parseRuntimeFrame(
      'id: 7\nevent: run.state\ndata: {"protocol_version":1,"sequence":7,"execution_id":"run-1","data":{"status":"running","output":"hello","sequence":7}}',
    )
    expect(frame?.sequence).toBe(7)
    expect(frame?.payload.output).toBe('hello')
    expect(frame?.payload.status).toBe('running')
  })

  it('rejects incremental gaps without advancing the accepted sequence', () => {
    const state = { sequence: 10 }
    const skipped = parseRuntimeFrame(
      'id: 12\nevent: token\ndata: {"type":"token","sequence":12,"content":"gap"}',
    )
    expect(skipped).not.toBeNull()
    expect(() => acceptRuntimeFrameSequence(skipped!, state)).toThrow(RuntimeStreamGapError)
    expect(state.sequence).toBe(10)
  })

  it('accepts durable run.state without rewinding the hot sequence cursor', () => {
    const state = { sequence: 20 }
    const durable = parseRuntimeFrame(
      'event: run.state\ndata: {"type":"run.state","status":"cancelled","output":"partial","realtime_available":false}',
    )
    expect(durable).not.toBeNull()
    expect(acceptRuntimeFrameSequence(durable!, state)).toBe(true)
    expect(state.sequence).toBe(20)
    expect(runtimeTerminalStatus(durable!)).toBe('cancelled')
  })

  it('rejects unsupported declared protocol versions explicitly', () => {
    expect(() => parseRuntimeFrame(
      'id: 1\nevent: token\ndata: {"protocol_version":99,"sequence":1,"content":"x"}',
    )).toThrow(RuntimeStreamProtocolError)
  })

  it('classifies terminal Agent and Network events consistently', () => {
    const completed = parseRuntimeFrame(
      'event: run.state\ndata: {"type":"run.state","sequence":3,"status":"completed","output":"done"}',
    )
    const failed = parseRuntimeFrame(
      'event: execution_failed\ndata: {"sequence":4,"message":"failed"}',
    )
    const cancelled = parseRuntimeFrame(
      'event: cancelled\ndata: {"sequence":5,"output":"partial","cancelled":true}',
    )
    const timedOut = parseRuntimeFrame(
      'event: execution_timed_out\ndata: {"sequence":6,"message":"timeout"}',
    )
    const uncertain = parseRuntimeFrame(
      'event: execution_failed\ndata: {"sequence":7,"uncertain":true}',
    )

    expect(runtimeTerminalStatus(completed!)).toBe('completed')
    expect(runtimeTerminalStatus(failed!)).toBe('failed')
    expect(runtimeTerminalStatus(cancelled!)).toBe('cancelled')
    expect(runtimeTerminalStatus(timedOut!)).toBe('timed_out')
    expect(runtimeTerminalStatus(uncertain!)).toBe('uncertain')
  })
})
