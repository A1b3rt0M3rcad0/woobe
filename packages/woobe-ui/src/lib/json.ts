export interface FormatSuccess {
  ok: true
  value: string
}

export interface FormatError {
  ok: false
  error: string
  line?: number
  col?: number
}

export type FormatResult = FormatSuccess | FormatError

export interface ValidationSuccess {
  valid: true
}

export interface ValidationError {
  valid: false
  error: string
  line?: number
  col?: number
}

export type ValidationResult = ValidationSuccess | ValidationError

export function formatJsonSafely(value: string): FormatResult {
  try {
    const parsed = JSON.parse(value)
    return { ok: true, value: JSON.stringify(parsed, null, 2) }
  } catch (error) {
    const message = error instanceof Error ? error.message : 'Invalid JSON'
    return { ok: false, error: message, line: parseErrorLine(message), col: parseErrorCol(message) }
  }
}

export function validateJson(value: string): ValidationResult {
  if (!value.trim()) return { valid: false, error: 'JSON cannot be empty' }
  try {
    JSON.parse(value)
    return { valid: true }
  } catch (error) {
    const message = error instanceof Error ? error.message : 'Invalid JSON'
    return { valid: false, error: message, line: parseErrorLine(message), col: parseErrorCol(message) }
  }
}

export function isValidJson(value: string): boolean {
  if (!value.trim()) return false
  try {
    JSON.parse(value)
    return true
  } catch {
    return false
  }
}

export function parseJsonSafe<T = unknown>(value: string): { data: T; ok: true } | { ok: false; error: string } {
  try {
    return { data: JSON.parse(value) as T, ok: true }
  } catch (error) {
    return { ok: false, error: error instanceof Error ? error.message : 'Invalid JSON' }
  }
}

export function tryFormatJson(value: string): string {
  const result = formatJsonSafely(value)
  return result.ok ? result.value : value
}

function parseErrorLine(message: string): number | undefined {
  const match = message.match(/line\s+(\d+)/i)
  return match ? parseInt(match[1], 10) : undefined
}

function parseErrorCol(message: string): number | undefined {
  const match = message.match(/column\s+(\d+)/i)
  return match ? parseInt(match[1], 10) : undefined
}

export function truncateJson(value: string, maxLength = 200): string {
  if (value.length <= maxLength) return value
  return `${value.slice(0, maxLength)}…`
}
