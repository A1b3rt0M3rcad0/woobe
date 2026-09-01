import type { HttpHeader, HttpRouteConfig, HttpToolConfig } from './types'

const PLACEHOLDER_PATTERN = /\{\{([A-Za-z_][A-Za-z0-9_]*)\}\}/g
const SINGLE_BRACE_PATTERN = /(^|[^\{])\{([A-Za-z_][A-Za-z0-9_]*)\}([^\}]|$)/

export interface HttpToolContractPreview {
  parameterNames: string[]
  inputSchema: Record<string, unknown>
  errors: string[]
}

export interface EffectiveHttpHeader extends HttpHeader {
  source: 'shared' | 'route'
  overridden?: boolean
}

export function isHttpToolGroup(config: HttpToolConfig | Record<string, unknown> | undefined): config is HttpToolConfig {
  if (!config || typeof config !== 'object') return false
  const raw = config as HttpToolConfig
  return raw.mode === 'group' || (Boolean(raw.base_url) && Array.isArray(raw.routes))
}

function bodyText(body: HttpRouteConfig['body'] | HttpToolConfig['body']): string {
  if (typeof body === 'string') return body
  return body == null ? '' : JSON.stringify(body)
}

function templateSources(config: { url?: string; body?: HttpToolConfig['body']; headers?: HttpHeader[] }): string[] {
  return [
    config.url || '',
    bodyText(config.body),
    ...(config.headers || []).filter((header) => header.mode !== 'remove').map((header) => header.value || ''),
  ]
}

function hasDefault(config: { variables?: Record<string, string> }, name: string): boolean {
  const value = config.variables?.[name]
  return value !== undefined && value !== null && value !== ''
}

export function effectiveHttpHeaders(shared: HttpHeader[] = [], route: HttpHeader[] = []): EffectiveHttpHeader[] {
  const effective = new Map<string, EffectiveHttpHeader>()
  const order: string[] = []

  shared.forEach((header) => {
    const key = header.key.trim()
    if (!key || header.mode === 'remove') return
    const normalized = key.toLowerCase()
    if (!effective.has(normalized)) order.push(normalized)
    effective.set(normalized, { ...header, key, mode: 'set', source: 'shared' })
  })

  route.forEach((header) => {
    const key = header.key.trim()
    if (!key) return
    const normalized = key.toLowerCase()
    if (header.mode === 'remove') {
      effective.delete(normalized)
      const index = order.indexOf(normalized)
      if (index >= 0) order.splice(index, 1)
      return
    }
    const inherited = effective.has(normalized)
    if (!inherited) order.push(normalized)
    effective.set(normalized, {
      ...header,
      key,
      mode: 'set',
      source: 'route',
      overridden: inherited,
    })
  })

  return order.flatMap((key) => {
    const header = effective.get(key)
    return header ? [header] : []
  })
}

function inspectContract(
  config: { url?: string; body?: HttpToolConfig['body']; headers?: HttpHeader[]; variables?: Record<string, string> },
  declaredSchema?: Record<string, unknown>,
): HttpToolContractPreview {
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

  const contentType = (config.headers || [])
    .find((header) => header.mode !== 'remove' && header.key.toLowerCase() === 'content-type')
    ?.value?.toLowerCase()
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

export function inspectHttpRouteContract(config: HttpToolConfig, route: HttpRouteConfig): HttpToolContractPreview {
  const baseUrl = String(config.base_url || '').replace(/\/+$/, '')
  const path = String(route.path || '').replace(/^\/+/, '')
  return inspectContract(
    {
      url: `${baseUrl}/${path}`,
      body: route.body,
      headers: effectiveHttpHeaders(config.headers || [], route.headers || []),
      variables: route.variables,
    },
    route.input_schema,
  )
}

export function inspectHttpToolContract(config: HttpToolConfig, declaredSchema?: Record<string, unknown>): HttpToolContractPreview {
  if (isHttpToolGroup(config)) {
    const errors: string[] = []
    for (const route of config.routes || []) {
      const preview = inspectHttpRouteContract(config, route)
      errors.push(...preview.errors.map((error) => `${route.name || route.operation_id || 'route'}: ${error}`))
    }
    return {
      parameterNames: [],
      inputSchema: { type: 'object', properties: {}, required: [], additionalProperties: false },
      errors,
    }
  }
  return inspectContract(config, declaredSchema)
}
