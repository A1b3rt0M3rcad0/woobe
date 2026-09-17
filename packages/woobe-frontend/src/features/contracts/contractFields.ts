import type { ExternalContextContract, ExternalContextFieldContract } from '@/features/agents/types'

export type ContractFieldType = 'string' | 'integer' | 'number' | 'boolean'

export interface ContractFieldRow {
  name: string
  type: ContractFieldType
  required: boolean
  scope: 'run' | 'session'
  expose: boolean
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
  const legacy = record(raw.fields)
  return (Object.keys(legacy).length ? legacy : raw) as Record<string, ExternalContextFieldContract>
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
    scope: field.scope === 'session' ? 'session' : 'run',
    expose: Boolean(field.model?.expose),
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
          scope: row.scope,
          model: { expose: row.expose },
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
      scope: 'run',
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
      scope: 'run' as const,
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
  if (type === 'boolean') return Boolean(raw)
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
