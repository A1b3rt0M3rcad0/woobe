import type { ExternalContextContract, ExternalContextFieldContract } from '@/features/agents/types'

export type ContractFieldType = 'string' | 'integer' | 'number' | 'boolean'
export type ExternalContextScope = 'run' | 'session'

export interface ContractFieldRow {
  name: string
  type: ContractFieldType
  required: boolean
  expose: boolean
  scope?: ExternalContextScope
  description?: string
}

export const CONTRACT_FIELD_TYPE_OPTIONS = [
  { value: 'string', label: 'String' },
  { value: 'integer', label: 'Integer' },
  { value: 'number', label: 'Number' },
  { value: 'boolean', label: 'Boolean' },
]

function record(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' && !Array.isArray(value)
    ? value as Record<string, unknown>
    : {}
}

function normalizedExternalFields(value: unknown): Record<string, ExternalContextFieldContract> {
  const raw = record(value)
  const legacyValue = raw.fields
  const legacy = record(legacyValue)
  const isLegacy = Object.prototype.hasOwnProperty.call(raw, 'fields') && legacyValue !== null && typeof legacyValue === 'object' && !Array.isArray(legacyValue)
  return (isLegacy ? legacy : raw) as Record<string, ExternalContextFieldContract>
}

function schemaType(value: unknown): ContractFieldType {
  const raw = record(value)
  const type = raw.type
  return type === 'integer' || type === 'number' || type === 'boolean' ? type : 'string'
}

export function externalContractRows(value: unknown): ContractFieldRow[] {
  return Object.entries(normalizedExternalFields(value)).map(([name, field]) => ({
    name,
    type: schemaType(field.schema),
    required: Boolean(field.required),
    expose: Boolean(field.model?.expose),
    scope: field.scope === 'session' ? 'session' : 'run',
    ...(typeof field.description === 'string' ? { description: field.description } : {}),
  }))
}

export function externalContractFromRows(rows: ContractFieldRow[]): ExternalContextContract {
  return Object.fromEntries(
    rows
      .filter((row) => row.name.trim())
      .map((row) => [
        row.name.trim(),
        {
          schema: { type: row.type },
          required: row.required,
          model: { expose: row.expose },
          ...(row.scope === 'session' ? { scope: 'session' as const } : {}),
          ...(row.description?.trim() ? { description: row.description } : {}),
        },
      ]),
  )
}

export function outputSchemaRows(value: unknown): ContractFieldRow[] {
  const raw = record(value)
  const properties = record(raw.properties)
  if (raw.type === 'object' && Object.keys(properties).length) {
    const required = new Set(Array.isArray(raw.required) ? raw.required.filter((item): item is string => typeof item === 'string') : [])
    return Object.entries(properties).map(([name, schema]) => ({
      name,
      type: schemaType(schema),
      required: required.has(name),
      expose: true,
    }))
  }

  return Object.entries(raw).flatMap(([name, type]) => {
    if (typeof type !== 'string') return []
    const normalized = type === 'float' ? 'number' : type
    if (!['string', 'integer', 'number', 'boolean'].includes(normalized)) return []
    return [{
      name,
      type: normalized as ContractFieldType,
      required: true,
      expose: true,
    }]
  })
}

export function outputSchemaFromRows(rows: ContractFieldRow[]): Record<string, unknown> {
  const active = rows.filter((row) => row.name.trim())
  return {
    type: 'object',
    properties: Object.fromEntries(
      active.map((row) => [row.name.trim(), { type: row.type }]),
    ),
    required: active.filter((row) => row.required).map((row) => row.name.trim()),
    additionalProperties: false,
  }
}

export function contractFields(value: unknown): Record<string, ExternalContextFieldContract> {
  return normalizedExternalFields(value)
}

export function coerceContractValue(type: ContractFieldType, raw: string | boolean): unknown {
  if (type === 'boolean') {
    if (typeof raw === 'boolean') return raw
    if (raw === 'true') return true
    if (raw === 'false') return false
    return undefined
  }
  if (raw === '') return undefined
  if (type === 'integer') {
    const value = Number.parseInt(String(raw), 10)
    return Number.isFinite(value) ? value : undefined
  }
  if (type === 'number') {
    const value = Number(String(raw))
    return Number.isFinite(value) ? value : undefined
  }
  return String(raw)
}

export function filterContractValues(contract: unknown, values?: Record<string, unknown>): Record<string, unknown> {
  const names = new Set(Object.keys(normalizedExternalFields(contract)))
  return Object.fromEntries(Object.entries(values ?? {}).filter(([name]) => names.has(name)))
}


export function filterExternalContextInput(
  contract: unknown,
  values: Record<string, unknown>,
  locked: Record<string, unknown> = {},
): Record<string, unknown> {
  const fields = normalizedExternalFields(contract)
  return Object.fromEntries(
    Object.entries(values).filter(([name]) => {
      const field = fields[name]
      if (!field) return false
      return !(field.scope === 'session' && Object.prototype.hasOwnProperty.call(locked, name))
    }),
  )
}
