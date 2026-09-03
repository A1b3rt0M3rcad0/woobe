import type {
  ParsedRuntimeFrame,
  RuntimeSequenceState,
  RuntimeTerminalStatus,
} from './types'

export class RuntimeStreamGapError extends Error {
  constructor(message: string) {
    super(message)
    this.name = 'RuntimeStreamGapError'
  }
}

export class RuntimeStreamProtocolError extends Error {
  constructor(message: string) {
    super(message)
    this.name = 'RuntimeStreamProtocolError'
  }
}

export const RUNTIME_STREAM_MAX_ATTEMPTS = 4
export const RUNTIME_STREAM_RETRY_BASE_MS = 250
export const RUNTIME_STREAM_PROTOCOL_VERSION = 1

export function validateRuntimeProtocolVersion(data: Record<string, unknown>): void {
  const value = data.protocol_version
  if (value === undefined || value === null) return
  if (value !== RUNTIME_STREAM_PROTOCOL_VERSION) {
    throw new RuntimeStreamProtocolError(
      `Unsupported runtime stream protocol version: ${String(value)}`,
    )
  }
}

export function acceptRuntimeFrameSequence(
  frame: ParsedRuntimeFrame,
  state: RuntimeSequenceState,
): boolean {
  if (
    frame.eventType === 'run.state'
    && frame.payload.realtime_available === false
  ) {
    return true
  }

  const sequence = frame.sequence
  if (sequence === null) return true

  if (frame.eventType === 'run.state') {
    if (state.sequence !== null && sequence < state.sequence) return false
    state.sequence = sequence
    return true
  }

  if (state.sequence !== null) {
    if (sequence <= state.sequence) return false
    const expected = state.sequence + 1
    if (sequence !== expected) {
      throw new RuntimeStreamGapError(
        `Runtime stream sequence gap: expected ${expected}, received ${sequence}`,
      )
    }
  }
  state.sequence = sequence
  return true
}

export function runtimeTerminalStatus(
  frame: ParsedRuntimeFrame,
): RuntimeTerminalStatus | null {
  if (frame.eventType === 'run.state') {
    const status = typeof frame.payload.status === 'string'
      ? frame.payload.status
      : ''
    if (
      status === 'completed'
      || status === 'failed'
      || status === 'cancelled'
      || status === 'timed_out'
      || status === 'uncertain'
    ) {
      return status
    }
    return null
  }

  if (frame.eventType === 'done' || frame.eventType === 'execution_completed') {
    return 'completed'
  }
  if (frame.eventType === 'cancelled' || frame.eventType === 'execution_cancelled') {
    return 'cancelled'
  }
  if (frame.eventType === 'execution_timed_out') return 'timed_out'
  if (frame.eventType === 'error' || frame.eventType === 'execution_failed') {
    return frame.payload.uncertain === true ? 'uncertain' : 'failed'
  }
  return null
}
