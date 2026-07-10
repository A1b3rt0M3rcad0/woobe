import type { AgentRelease } from '@/features/agents/types'

export type RuntimeSlot = 'production' | 'staging'

export const PUBLIC_RUNTIME_ENDPOINTS = {
  http: '/v1/run',
  stream: '/v1/run/stream',
  jobs: '/v1/jobs',
} as const

type ResponseFormat = {
  enabled?: boolean
  type?: string
  strict?: boolean
  schema?: unknown
}

interface BuildApiReferenceInput {
  slot: RuntimeSlot
  release: AgentRelease | null | undefined
}

function asRecord(value: unknown): Record<string, unknown> | null {
  return value && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : null
}

function parseJsonObject(value: unknown): Record<string, unknown> | null {
  if (typeof value === 'string') {
    try {
      const parsed = JSON.parse(value)
      return asRecord(parsed)
    } catch {
      return null
    }
  }
  return asRecord(value)
}

function getResponseFormat(release: AgentRelease | null | undefined): ResponseFormat {
  return (release?.response_format || {}) as ResponseFormat
}

function getOutputSchema(release: AgentRelease | null | undefined): Record<string, unknown> | null {
  const responseFormat = getResponseFormat(release)
  return parseJsonObject(responseFormat.schema) || parseJsonObject(release?.output_schema)
}

function normalizeType(value: string): string {
  const lower = value.toLowerCase()
  if (['float', 'double', 'decimal', 'number'].includes(lower)) return 'number'
  if (['int', 'integer'].includes(lower)) return 'integer'
  if (['bool', 'boolean'].includes(lower)) return 'boolean'
  if (['str', 'string', 'text'].includes(lower)) return 'string'
  if (['dict', 'object'].includes(lower)) return 'object'
  if (['list', 'array'].includes(lower)) return 'array'
  return lower
}

function contractValueFromType(type: string): unknown {
  switch (normalizeType(type)) {
    case 'string': return '<string>'
    case 'number': return '<number>'
    case 'integer': return '<integer>'
    case 'boolean': return '<boolean>'
    case 'array': return []
    case 'object': return {}
    default: return `<${type}>`
  }
}

function exampleValueFromType(type: string): unknown {
  switch (normalizeType(type)) {
    case 'string': return 'ok'
    case 'number': return 0.87
    case 'integer': return 1
    case 'boolean': return true
    case 'array': return []
    case 'object': return {}
    default: return null
  }
}

function buildFromSchema(schema: unknown, mode: 'contract' | 'example'): unknown {
  if (typeof schema === 'string') {
    return mode === 'contract' ? contractValueFromType(schema) : exampleValueFromType(schema)
  }
  if (Array.isArray(schema)) {
    if (schema.length === 0) return []
    return [buildFromSchema(schema[0], mode)]
  }
  const record = asRecord(schema)
  if (!record) return mode === 'contract' ? '<value>' : null
  if (typeof record.type === 'string') {
    const type = normalizeType(record.type)
    if (type === 'object') {
      const properties = asRecord(record.properties)
      if (properties) {
        return Object.entries(properties).reduce<Record<string, unknown>>((acc, [key, value]) => {
          acc[key] = buildFromSchema(value, mode)
          return acc
        }, {})
      }
      return {}
    }
    if (type === 'array') {
      return record.items ? [buildFromSchema(record.items, mode)] : []
    }
    if (Array.isArray(record.enum) && record.enum.length > 0) {
      return mode === 'contract' ? `<${record.enum.join(' | ')}>` : record.enum[0]
    }
    return mode === 'contract' ? contractValueFromType(type) : exampleValueFromType(type)
  }
  return Object.entries(record).reduce<Record<string, unknown>>((acc, [key, value]) => {
    acc[key] = buildFromSchema(value, mode)
    return acc
  }, {})
}

function buildParsedOutputContract(schema: Record<string, unknown> | null): Record<string, unknown> | null {
  if (!schema) return null
  const value = buildFromSchema(schema, 'contract')
  return asRecord(value) || null
}

function buildParsedOutputExample(schema: Record<string, unknown> | null): Record<string, unknown> | null {
  if (!schema) return null
  const value = buildFromSchema(schema, 'example')
  return asRecord(value) || null
}

function buildAnswerExample(parsedOutput: Record<string, unknown> | null, jsonEnabled: boolean): string {
  if (jsonEnabled && parsedOutput) return JSON.stringify(parsedOutput)
  return '<assistant answer>'
}

function buildUsageContract() {
  return {
    input_tokens: '<number | null>',
    output_tokens: '<number | null>',
    total_tokens: '<number | null>',
    cost_usd: '<number | null>',
  }
}

function buildSourceContract() {
  return {
    document_id: '<string | null>',
    document_title: '<string | null>',
    chunk_id: '<string | null>',
    page_number: '<number | null>',
    score: '<number | null>',
    content_preview: '<string | null>',
  }
}

function buildToolCallContract() {
  return {
    tool_name: '<string>',
    input: '<object | null>',
    output: '<object | null>',
    duration_ms: '<number | null>',
    success: '<boolean>',
    error: '<string | null>',
  }
}

export function buildApiReferenceForSlot({ slot, release }: BuildApiReferenceInput) {
  const responseFormat = getResponseFormat(release)
  const jsonEnabled = Boolean(responseFormat.enabled && responseFormat.type === 'json')
  const strict = Boolean(responseFormat.strict)
  const schema = getOutputSchema(release)
  const parsedOutputContract = jsonEnabled ? buildParsedOutputContract(schema) : null
  const parsedOutputExample = jsonEnabled ? buildParsedOutputExample(schema) : null
  const provider = release?.provider ?? '<provider | null>'
  const model = release?.model ?? '<model | null>'
  const warnings: string[] = []

  if (!release) warnings.push(`No ${slot} release is deployed for this agent.`)
  if (jsonEnabled && !schema) {
    warnings.push('Structured output is enabled, but no valid output schema was found on this release snapshot.')
  }

  const request = { message: 'Hello!' }
  const requestWithSession = { message: 'Hello!', session_id: '<uuid>' }
  const dataContract = {
    answer: '<string>',
    session_id: '<uuid | null>',
    message_id: '<uuid | null>',
    usage: buildUsageContract(),
    sources: [buildSourceContract()],
    tool_calls: [buildToolCallContract()],
    trace_id: '<uuid | null>',
    model,
    provider,
    fallback_used: '<boolean>',
    latency_ms: '<number | null>',
    parsed_output: parsedOutputContract,
    output_parse_error: '<string | null>',
  }
  const dataExample = {
    answer: buildAnswerExample(parsedOutputExample, jsonEnabled),
    session_id: '<uuid | null>',
    message_id: '<uuid | null>',
    usage: buildUsageContract(),
    sources: [],
    tool_calls: [],
    trace_id: '<uuid | null>',
    model,
    provider,
    fallback_used: false,
    latency_ms: '<number | null>',
    parsed_output: parsedOutputExample,
    output_parse_error: null,
  }

  return {
    slot,
    available: Boolean(release),
    release: release ? {
      id: release.id,
      version: release.version,
      status: release.status,
      provider,
      model,
      fallback_provider: release.fallback_provider ?? null,
      fallback_model: release.fallback_model ?? null,
      session_mode: release.session_mode ?? null,
      structured_output_enabled: jsonEnabled,
      strict_json: strict,
    } : null,
    warnings,
    request,
    request_with_session: requestWithSession,
    sync_response_contract: { success: true, data: dataContract },
    sync_response_example: { success: true, data: dataExample },
    stream_events: {
      token: {
        event: 'token',
        data: {
          type: 'token',
          protocol_version: 1,
          request_id: '<uuid>',
          occurred_at: '<iso datetime>',
          content: '<partial token>',
          phase: '<runtime phase>',
          provider,
          model,
        },
      },
      done: { event: 'done', data: { type: 'done', ...dataExample } },
      error: { event: 'error', data: { type: 'error', message: '<error message>' } },
      heartbeat: { event: 'heartbeat', data: { type: 'heartbeat', ts: '<iso datetime>' } },
      cancelled: { event: 'cancelled', data: { type: 'cancelled', reason: '<reason>' } },
    },
    job_create_response: {
      success: true,
      data: { job_id: '<uuid>', status: 'pending' },
    },
    job_status_response: {
      success: true,
      data: {
        job_id: '<uuid>',
        status: '<pending | processing | completed | failed>',
        result: dataExample,
        error: '<string | null>',
        trace_id: '<uuid | null>',
      },
    },
    structured_output: {
      enabled: jsonEnabled,
      strict,
      source: release ? `${slot} release snapshot` : null,
      schema: schema ?? null,
      parsed_output_contract: parsedOutputContract,
      parsed_output_example: parsedOutputExample,
    },
  }
}

function publicCurl(baseUrl: string, path: string, body: Record<string, unknown>, stream = false) {
  return `curl ${stream ? '-N ' : ''}-X POST ${baseUrl}${path} \\
  -H "Authorization: Bearer $WOOBE_API_KEY" \\
  -H "Content-Type: application/json" \\
  -d '${JSON.stringify(body, null, 2)}'`
}

export function runtimeCurl(baseUrl: string, stream = false) {
  return publicCurl(
    baseUrl,
    stream ? PUBLIC_RUNTIME_ENDPOINTS.stream : PUBLIC_RUNTIME_ENDPOINTS.http,
    { message: 'Hello!' },
    stream,
  )
}

export function createJobCurl(baseUrl: string) {
  return publicCurl(baseUrl, PUBLIC_RUNTIME_ENDPOINTS.jobs, { message: 'Hello!' })
}

export function getJobCurl(baseUrl: string) {
  return `curl -X GET ${baseUrl}${PUBLIC_RUNTIME_ENDPOINTS.jobs}/$JOB_ID \\
  -H "Authorization: Bearer $WOOBE_API_KEY"`
}
