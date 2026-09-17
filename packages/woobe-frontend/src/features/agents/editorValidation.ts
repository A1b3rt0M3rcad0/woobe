import { canonicalSnapshot, type AgentEditorState } from '@/features/playground/AgentEditorContext'

type ResponseFormatState = AgentEditorState['responseFormat']

export type AgentEditorValidationIssue = {
  section: 'output' | 'external-context'
  code:
    | 'output_contract_required'
    | 'output_contract_invalid'
    | 'external_context_contract_invalid'
  message: string
}

export type AgentEditorValidationResult =
  | { valid: true; issue: null; snapshot: Record<string, unknown> }
  | { valid: false; issue: AgentEditorValidationIssue; snapshot: null }

function invalid(
  section: AgentEditorValidationIssue['section'],
  code: AgentEditorValidationIssue['code'],
  message: string,
): AgentEditorValidationResult {
  return {
    valid: false,
    issue: { section, code, message },
    snapshot: null,
  }
}

function responseFormatState(state: AgentEditorState): ResponseFormatState {
  return state.responseFormat ?? {
    enabled: false,
    type: 'text',
    strict: true,
    schema: null,
  }
}

function normalizedInactiveSchema(schema: unknown): Record<string, unknown> | null {
  if (typeof schema === 'string') {
    if (!schema.trim()) return null
    try {
      const parsed = JSON.parse(schema)
      return parsed && typeof parsed === 'object' && !Array.isArray(parsed)
        ? parsed as Record<string, unknown>
        : null
    } catch {
      return null
    }
  }

  return schema && typeof schema === 'object' && !Array.isArray(schema)
    ? schema as Record<string, unknown>
    : null
}

function textOutputSnapshot(state: AgentEditorState): Record<string, unknown> {
  const snapshot = canonicalSnapshot(state)
  const currentFormat = responseFormatState(state)
  const dormantSchema = normalizedInactiveSchema(currentFormat.schema)
  const responseFormat = snapshot.response_format && typeof snapshot.response_format === 'object' && !Array.isArray(snapshot.response_format)
    ? snapshot.response_format as Record<string, unknown>
    : {}

  return {
    ...snapshot,
    response_format: {
      ...responseFormat,
      enabled: false,
      type: 'text',
      strict: true,
      schema: dormantSchema,
    },
    // output_schema is a legacy compatibility signal. Keeping it populated would
    // reactivate structured output even when response_format.enabled is false.
    output_schema: null,
  }
}

export function outputContractError(state: AgentEditorState): string | null {
  const responseFormat = responseFormatState(state)
  if (!responseFormat.enabled || responseFormat.type !== 'json') return null

  const schema = responseFormat.schema
  if (typeof schema === 'string') {
    if (!schema.trim()) return 'Define an Output contract before saving or running with JSON output.'
    try {
      const parsed = JSON.parse(schema)
      if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) return 'Output contract must be a JSON object.'
      return null
    } catch {
      return 'Output contract contains invalid JSON.'
    }
  }

  if (!schema || typeof schema !== 'object' || Array.isArray(schema)) {
    return 'Define a valid JSON object before saving or running with JSON output.'
  }

  return null
}

function parseExternalContextContract(state: AgentEditorState): Record<string, unknown> | null {
  const raw = state.externalContextContract
  if (typeof raw === 'string') {
    if (!raw.trim()) return { fields: {} }
    try {
      const parsed = JSON.parse(raw)
      return parsed && typeof parsed === 'object' && !Array.isArray(parsed)
        ? parsed as Record<string, unknown>
        : null
    } catch {
      return null
    }
  }
  return raw && typeof raw === 'object' && !Array.isArray(raw)
    ? raw as unknown as Record<string, unknown>
    : null
}

export function externalContextContractError(state: AgentEditorState): string | null {
  const contract = parseExternalContextContract(state)
  if (!contract) return 'External Context contract must be a valid JSON object.'
  if ('version' in contract) return 'External Context has no independent version. Version the Agent Release instead.'

  const unknownRootKeys = Object.keys(contract).filter((key) => key !== 'fields')
  if (unknownRootKeys.length > 0) return `External Context contract contains unsupported properties: ${unknownRootKeys.join(', ')}.`

  const fields = contract.fields ?? {}
  if (!fields || typeof fields !== 'object' || Array.isArray(fields)) return 'External Context contract fields must be a JSON object.'

  for (const [name, rawField] of Object.entries(fields as Record<string, unknown>)) {
    if (!name.trim()) return 'External Context field names cannot be blank.'
    if (!rawField || typeof rawField !== 'object' || Array.isArray(rawField)) return `External Context field '${name}' must be an object.`
    const field = rawField as Record<string, unknown>
    const supported = new Set(['schema', 'required', 'scope', 'default', 'model', 'description'])
    const unknown = Object.keys(field).filter((key) => !supported.has(key))
    if (unknown.length > 0) return `External Context field '${name}' contains unsupported properties: ${unknown.join(', ')}.`
    if (field.required !== undefined && typeof field.required !== 'boolean') return `External Context field '${name}'.required must be boolean.`
    if (field.scope !== undefined && field.scope !== 'run' && field.scope !== 'session') return `External Context field '${name}'.scope must be 'run' or 'session'.`
    if (field.schema !== undefined && (!field.schema || typeof field.schema !== 'object' || Array.isArray(field.schema))) return `External Context field '${name}'.schema must be an object.`
    if (field.model !== undefined) {
      if (!field.model || typeof field.model !== 'object' || Array.isArray(field.model)) return `External Context field '${name}'.model must be an object.`
      const model = field.model as Record<string, unknown>
      if (Object.keys(model).some((key) => key !== 'expose')) return `External Context field '${name}'.model only supports 'expose'.`
      if (model.expose !== undefined && typeof model.expose !== 'boolean') return `External Context field '${name}'.model.expose must be boolean.`
    }
  }

  return null
}

export function validateAgentEditorState(state: AgentEditorState): AgentEditorValidationResult {
  const externalContextError = externalContextContractError(state)
  if (externalContextError) {
    return invalid('external-context', 'external_context_contract_invalid', externalContextError)
  }

  const externalContextContract = parseExternalContextContract(state) ?? { fields: {} }
  const normalizedExternalState: AgentEditorState = {
    ...state,
    // Runtime validation above proves the parsed object satisfies the stricter
    // ExternalContextContract shape before it enters the canonical snapshot.
    externalContextContract: externalContextContract as unknown as AgentEditorState['externalContextContract'],
  }

  const responseFormat = responseFormatState(normalizedExternalState)
  if (!responseFormat.enabled || responseFormat.type !== 'json') {
    return { valid: true, issue: null, snapshot: textOutputSnapshot(normalizedExternalState) }
  }

  const error = outputContractError(normalizedExternalState)
  if (error) {
    return invalid(
      'output',
      responseFormat.schema == null || (typeof responseFormat.schema === 'string' && !responseFormat.schema.trim())
        ? 'output_contract_required'
        : 'output_contract_invalid',
      error,
    )
  }

  const schema = typeof responseFormat.schema === 'string'
    ? JSON.parse(responseFormat.schema)
    : responseFormat.schema
  const normalizedState: AgentEditorState = {
    ...normalizedExternalState,
    responseFormat: { ...responseFormat, strict: true, schema },
    outputSchema: schema,
  }

  return { valid: true, issue: null, snapshot: canonicalSnapshot(normalizedState) }
}