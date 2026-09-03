import { validateRuntimeProtocolVersion } from './protocol'
import type { ParsedRuntimeFrame } from './types'

function objectValue(value: unknown): Record<string, unknown> | null {
  return value && typeof value === 'object' && !Array.isArray(value)
    ? value as Record<string, unknown>
    : null
}

function sequenceValue(value: unknown): number | null {
  return typeof value === 'number' && Number.isInteger(value) && value >= 0
    ? value
    : null
}

export function parseRuntimeFrame(frame: string): ParsedRuntimeFrame | null {
  const lines = frame.split(/\r?\n/)
  const eventLine = lines.find((line) => line.startsWith('event:'))
  const idLine = lines.find((line) => line.startsWith('id:'))
  const dataLines = lines.filter((line) => line.startsWith('data:'))
  if (!dataLines.length) return null

  let parsed: unknown
  try {
    parsed = JSON.parse(
      dataLines.map((line) => line.slice(5).trimStart()).join('\n'),
    ) as unknown
  } catch {
    return null
  }

  const data = objectValue(parsed)
  if (!data) return null
  validateRuntimeProtocolVersion(data)

  const payload = objectValue(data.data) ?? data
  const eventType = eventLine?.slice(6).trim()
    || (typeof data.type === 'string' ? data.type : 'message')
  const headerSequence = sequenceValue(data.sequence)
  const payloadSequence = sequenceValue(payload.sequence)
  const id = idLine?.slice(3).trim() ?? ''
  const idSequence = /^\d+$/.test(id) ? Number(id) : null

  return {
    eventType,
    data,
    payload,
    sequence: headerSequence ?? payloadSequence ?? idSequence,
  }
}
