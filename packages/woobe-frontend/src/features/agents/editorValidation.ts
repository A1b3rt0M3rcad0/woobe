import { canonicalSnapshot, type AgentEditorState } from '@/features/playground/AgentEditorContext'

type ResponseFormatState = AgentEditorState['responseFormat']

export type AgentEditorValidationIssue = {
  section: 'output' | 'external-context' | 'artifacts'
  code:
    | 'output_contract_required'
    | 'output_contract_invalid'
    | 'external_context_contract_invalid'
    | 'artifact_capability_invalid'
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

function readExternalContextContract(state: AgentEditorState): Record<string, unknown> | null {
  const raw = state.externalContextContract
  if (raw == null) return null
  if (typeof raw === 'string') {
    if (!raw.trim()) return null
    try {
      const parsed = JSON.parse(raw)
      if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) return null
      const object = parsed as Record<string, unknown>
      const legacyFields = object.fields
      return legacyFields && typeof legacyFields === 'object' && !Array.isArray(legacyFields)
        ? legacyFields as Record<string, unknown>
        : object
    } catch {
      return null
    }
  }
  if (!raw || typeof raw !== 'object' || Array.isArray(raw)) return null
  const object = raw as unknown as Record<string, unknown>
  const legacyFields = object.fields
  return legacyFields && typeof legacyFields === 'object' && !Array.isArray(legacyFields)
    ? legacyFields as Record<string, unknown>
    : object
}

function parseExternalContextContract(state: AgentEditorState): Record<string, unknown> | null {
  return readExternalContextContract(state)
}

function recordValue(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : {}
}

export function artifactCapabilityError(state: AgentEditorState): string | null {
  const runtime = recordValue(state.runtimeConfig)
  if (!Object.prototype.hasOwnProperty.call(runtime, 'artifacts')) return null
  const capability = recordValue(runtime.artifacts)
  if (capability.enabled !== true) return null
  const binding = recordValue(capability.workspace_binding)
  const fieldName = binding.field
  const scope = binding.scope
  if (typeof fieldName !== 'string' || !/^[A-Za-z_][A-Za-z0-9_]*$/.test(fieldName) || typeof binding.namespace !== 'string' || !binding.namespace.trim()) {
    return 'Artifact capability requires a valid External Context field and namespace.'
  }
  if (scope !== 'run' && scope !== 'session') return 'Artifact Workspace binding scope must be Run or Session.'
  const contract = readExternalContextContract(state)
  const field = contract ? recordValue(contract[fieldName]) : {}
  const schema = recordValue(field.schema)
  const model = recordValue(field.model)
  if (!contract || field.required !== true || schema.type !== 'string' || field.scope !== scope || Object.prototype.hasOwnProperty.call(field, 'default') || model.expose !== false) {
    return 'Artifact Workspace binding must match a required, non-model-exposed string External Context field with no default.'
  }
  const actions = Array.isArray(capability.actions) ? capability.actions : []
  const allowed = new Set(['read', 'search', 'write', 'delete', 'process', 'transfer'])
  if (!actions.length || actions.some(action => typeof action !== 'string' || !allowed.has(action)) || new Set(actions).size !== actions.length) {
    return 'Artifact capability actions must be unique supported operations.'
  }
  const limits = recordValue(capability.limits)
  const limitBounds: Record<string, [number, number]> = {
    max_search_results: [1, 200], max_read_chars: [1, 65_536],
    max_total_read_chars: [1, 1_048_576], max_context_units: [64, 1_000_000], max_writes: [0, 100],
  }
  for (const [name, [minimum, maximum]] of Object.entries(limitBounds)) {
    const value = limits[name]
    if (typeof value !== 'number' || !Number.isInteger(value) || value < minimum || value > maximum) {
      return `Artifact budget '${name}' must be an integer between ${minimum} and ${maximum}.`
    }
  }
  const maxWrites = limits.max_writes
  if (typeof maxWrites !== 'number' || !Number.isInteger(maxWrites) || maxWrites < 0 || actions.includes('write') !== (maxWrites > 0)) {
    return 'Artifact write permission requires a positive max_writes limit, and disabled writes require zero.'
  }
  const profile = capability.processing_profile
  if (profile != null) {
    const reference = recordValue(profile)
    if (!actions.includes('process') || typeof reference.ref !== 'string' || !/^[A-Za-z][A-Za-z0-9_-]{0,63}$/.test(reference.ref) || typeof reference.revision !== 'number' || !Number.isInteger(reference.revision) || reference.revision < 1) {
      return 'Artifact processing profile requires the process action, a portable reference and a positive revision.'
    }
  }
  return null
}

export function externalContextContractError(state: AgentEditorState): string | null {
  if (state.externalContextContract == null || state.externalContextContract === '') return null
  const contract = readExternalContextContract(state)
  if (!contract) return 'External Context contract is invalid.'

  for (const [name, rawField] of Object.entries(contract)) {
    if (!name.trim()) return 'External Context field names cannot be blank.'
    if (!rawField || typeof rawField !== 'object' || Array.isArray(rawField)) return `External Context field '${name}' must be an object.`
    const field = rawField as Record<string, unknown>
    const supported = new Set(['schema', 'required', 'default', 'model', 'description', 'scope'])
    const unknown = Object.keys(field).filter((key) => !supported.has(key))
    if (unknown.length > 0) return `External Context field '${name}' contains unsupported properties: ${unknown.join(', ')}.`
    if (field.scope !== undefined && field.scope !== 'run' && field.scope !== 'session') return `External Context field '${name}'.scope must be 'run' or 'session'.`
    if (field.required !== undefined && typeof field.required !== 'boolean') return `External Context field '${name}'.required must be boolean.`
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
  const artifactsError = artifactCapabilityError(state)
  if (artifactsError) return invalid('artifacts', 'artifact_capability_invalid', artifactsError)

  const externalContextContract = parseExternalContextContract(state)
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
