import { canonicalSnapshot, type AgentEditorState } from '@/features/playground/AgentEditorContext'

export type AgentEditorValidationIssue = {
  section: 'output'
  code: 'output_contract_required' | 'output_contract_invalid'
  message: string
}

export type AgentEditorValidationResult =
  | { valid: true; issue: null; snapshot: Record<string, unknown> }
  | { valid: false; issue: AgentEditorValidationIssue; snapshot: null }

function invalid(code: AgentEditorValidationIssue['code'], message: string): AgentEditorValidationResult {
  return {
    valid: false,
    issue: { section: 'output', code, message },
    snapshot: null,
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
  const schema = normalizedInactiveSchema(state.responseFormat.schema)
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
      schema,
    },
    output_schema: schema,
  }
}

export function outputContractError(state: AgentEditorState): string | null {
  if (!state.responseFormat.enabled || state.responseFormat.type !== 'json') return null

  const schema = state.responseFormat.schema
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

export function validateAgentEditorState(state: AgentEditorState): AgentEditorValidationResult {
  if (!state.responseFormat.enabled || state.responseFormat.type !== 'json') {
    return { valid: true, issue: null, snapshot: textOutputSnapshot(state) }
  }

  const error = outputContractError(state)
  if (error) {
    return invalid(
      state.responseFormat.schema == null || (typeof state.responseFormat.schema === 'string' && !state.responseFormat.schema.trim())
        ? 'output_contract_required'
        : 'output_contract_invalid',
      error,
    )
  }

  const schema = typeof state.responseFormat.schema === 'string'
    ? JSON.parse(state.responseFormat.schema)
    : state.responseFormat.schema
  const normalizedState: AgentEditorState = {
    ...state,
    responseFormat: { ...state.responseFormat, strict: true, schema },
    outputSchema: schema,
  }

  return { valid: true, issue: null, snapshot: canonicalSnapshot(normalizedState) }
}
