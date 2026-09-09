import { describe, expect, it } from 'vitest'
import type { Agent } from './types'
import { outputContractError, validateAgentEditorState } from './editorValidation'
import { agentToEditorState, canonicalSnapshot } from '@/features/playground/AgentEditorContext'

const agent: Agent = {
  id: 'agent',
  project_id: 'project',
  name: 'Reviewer',
  description: 'Review invoices',
  provider: 'openai',
  model: 'test',
  status: 'active',
  session_mode: 'stateful',
}

function editorState() {
  return agentToEditorState(agent)
}

describe('Agent editor output validation', () => {
  it('preserves invalid raw JSON in the editor snapshot used for dirty tracking', () => {
    const state = editorState()
    state.responseFormat = {
      ...state.responseFormat,
      enabled: true,
      type: 'json',
      schema: '{ "answer": ',
    }

    const snapshot = canonicalSnapshot(state)
    expect((snapshot.response_format as Record<string, unknown>).schema).toBe('{ "answer": ')
    expect(snapshot.output_schema).toBe('{ "answer": ')
  })

  it('blocks an invalid JSON contract instead of inserting a fallback schema', () => {
    const state = editorState()
    state.responseFormat = {
      ...state.responseFormat,
      enabled: true,
      type: 'json',
      schema: '{ invalid',
    }

    const result = validateAgentEditorState(state)
    expect(result.valid).toBe(false)
    if (!result.valid) {
      expect(result.issue.section).toBe('output')
      expect(result.issue.code).toBe('output_contract_invalid')
    }
  })

  it('requires a contract when structured JSON output is enabled', () => {
    const state = editorState()
    state.responseFormat = {
      ...state.responseFormat,
      enabled: true,
      type: 'json',
      schema: '',
    }

    expect(outputContractError(state)).toMatch(/Define an Output contract/)
    const result = validateAgentEditorState(state)
    expect(result.valid).toBe(false)
    if (!result.valid) expect(result.issue.code).toBe('output_contract_required')
  })

  it('materializes valid JSON only at the save or run boundary', () => {
    const state = editorState()
    state.responseFormat = {
      ...state.responseFormat,
      enabled: true,
      type: 'json',
      schema: '{ "message": "string", "confidence": "float" }',
    }

    const result = validateAgentEditorState(state)
    expect(result.valid).toBe(true)
    if (result.valid) {
      expect((result.snapshot.response_format as Record<string, unknown>).schema).toEqual({
        message: 'string',
        confidence: 'float',
      })
      expect(result.snapshot.output_schema).toEqual({ message: 'string', confidence: 'float' })
    }

    expect(state.responseFormat.schema).toBe('{ "message": "string", "confidence": "float" }')
  })

  it('does not block text output even when a previous raw JSON draft is invalid', () => {
    const state = editorState()
    state.responseFormat = {
      ...state.responseFormat,
      enabled: false,
      type: 'text',
      schema: '{ unfinished',
    }

    const result = validateAgentEditorState(state)
    expect(result.valid).toBe(true)
    if (result.valid) {
      expect((result.snapshot.response_format as Record<string, unknown>).enabled).toBe(false)
      expect((result.snapshot.response_format as Record<string, unknown>).schema).toBe('{ unfinished')
    }
  })
})
