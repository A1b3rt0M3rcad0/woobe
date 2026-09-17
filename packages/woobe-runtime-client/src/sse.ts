import { RuntimeStreamProtocolError, validateRuntimeProtocolVersion } from './protocol'
import type { ParsedRuntimeFrame } from './types'

function objectValue(value: unknown): Record<string, unknown> | null {
  return value && typeof value === 'object' && !Array.isArray(value)
    ? value as Record<string, unknown>
    : null
}

function requiredText(data: Record<string, unknown>, name: string): string {
  const value = data[name]
  if (typeof value !== 'string' || !value.trim()) {
    throw new RuntimeStreamProtocolError(`Missing runtime event ${name}`)
  }
  return value
}

export function parseRuntimeFrame(frame: string): ParsedRuntimeFrame | null {
  const lines = frame.split(/\r?\n/)
  const eventLine = lines.find((line) => line.startsWith('event:'))
  const idLine = lines.find((line) => line.startsWith('id:'))
  const dataLines = lines.filter((line) => line.startsWith('data:'))
  if (!dataLines.length) return null
  let parsed: unknown
  try {
    parsed = JSON.parse(dataLines.map((line) => line.slice(5).trimStart()).join('\n'))
  } catch {
    return null
  }
  const data = objectValue(parsed)
  if (!data) return null
  validateRuntimeProtocolVersion(data)
  const type = requiredText(data, 'type')
  const occurredAt = requiredText(data, 'occurred_at')
  if (!Number.isFinite(Date.parse(occurredAt))) {
    throw new RuntimeStreamProtocolError('Invalid runtime event occurred_at')
  }
  if (eventLine && eventLine.slice(6).trim() !== type) {
    throw new RuntimeStreamProtocolError('SSE event type differs from its envelope')
  }
  const payload = objectValue(data.payload)
  const control = data.event_id === undefined && data.run_id === undefined
    && data.session_id === undefined && data.sequence === undefined
  if (control) {
    if (idLine || !['heartbeat', 'run.realtime_unavailable', 'error', 'protocol.control'].includes(type)) {
      throw new RuntimeStreamProtocolError('Invalid transport frame')
    }
    return { kind: 'transport', type, eventType: type, occurredAt, payload: payload ?? {}, sequence: null }
  }
  const sequence = data.sequence
  if (!Number.isSafeInteger(sequence) || (sequence as number) < 0 || !payload
      || !['AGENT', 'NETWORK'].includes(String(data.run_kind))
      || ['heartbeat', 'run.realtime_unavailable'].includes(type)) {
    throw new RuntimeStreamProtocolError('Invalid semantic runtime event envelope')
  }
  if (idLine && idLine.slice(3).trim() !== String(sequence)) {
    throw new RuntimeStreamProtocolError('SSE cursor differs from semantic sequence')
  }
  return {
    kind: 'semantic', type, eventType: type, occurredAt, payload,
    eventId: requiredText(data, 'event_id'), runId: requiredText(data, 'run_id'),
    sessionId: requiredText(data, 'session_id'), runKind: data.run_kind as 'AGENT' | 'NETWORK',
    sequence: sequence as number,
  }
}
