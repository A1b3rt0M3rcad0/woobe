import type { HttpToolConfig } from './types'

const PLACEHOLDER_PATTERN = /\{\{([A-Za-z_][A-Za-z0-9_]*)\}\}/g
const SINGLE_BRACE_PATTERN = /(^|[^\{])\{([A-Za-z_][A-Za-z0-9_]*)\}([^\}]|$)/

export interface HttpToolContractPreview {
  parameterNames: string[]
  inputSchema: Record<string, unknown>
  errors: string[]
}

function templateSources(config: HttpToolConfig): string[] {
  return [config.url || '', typeof config.body === 'string' ? config.body : config.body ? JSON.stringify(config.body) : '', ...(config.headers || []).map((header) => header.value || '')]
}

function hasDefault(config: HttpToolConfig, name: string): boolean {
  const value = config.variables?.[name]
  return value !== undefined && value !== null && value !== ''
}

export function inspectHttpToolContract(config: HttpToolConfig, declaredSchema?: Record<string, unknown>): HttpToolContractPreview {
  const errors: string[] = []
  const parameterNames: string[] = []
  for (const source of templateSources(config)) {
    const malformed = source.match(SINGLE_BRACE_PATTERN)
    if (malformed?.[2]) errors.push(`Invalid placeholder {${malformed[2]}}. Use {{${malformed[2]}}}.`)
    for (const match of source.matchAll(PLACEHOLDER_PATTERN)) {
      const name = match[1]
      if (!parameterNames.includes(name)) parameterNames.push(name)
    }
  }

  const contentType = (config.headers || []).find((header) => header.key.toLowerCase() === 'content-type')?.value.toLowerCase()
  if (config.body && contentType?.includes('application/json') && typeof config.body === 'string') {
    try { JSON.parse(config.body) } catch { errors.push('Body must be valid JSON when Content-Type is application/json.') }
  }

  const schema: Record<string, unknown> = declaredSchema ? { ...declaredSchema } : {}
  const rawProperties = schema.properties
  const properties: Record<string, unknown> = rawProperties && typeof rawProperties === 'object' && !Array.isArray(rawProperties) ? { ...(rawProperties as Record<string, unknown>) } : {}
  parameterNames.forEach((name) => {
    if (!properties[name]) properties[name] = { type: 'string', description: `Parameter ${name}` }
  })
  const rawRequired = Array.isArray(schema.required) ? schema.required.filter((name): name is string => typeof name === 'string') : []
  const required = [...rawRequired]
  parameterNames.forEach((name) => {
    if (!hasDefault(config, name) && !required.includes(name)) required.push(name)
  })
  return { parameterNames, inputSchema: { ...schema, type: 'object', properties, required, additionalProperties: false }, errors }
}
