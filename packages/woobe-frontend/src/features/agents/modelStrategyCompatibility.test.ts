import { describe, expect, it } from 'vitest'

import type { ExecutionStrategyDescriptor } from './types'
import { executionStrategyCompatibilityForModel } from './modelStrategyCompatibility'
import type { ProviderModel } from '@/features/provider-models/types'

const standard: ExecutionStrategyDescriptor = {
  name: 'standard',
  display_name: 'Standard',
  description: 'Conversation',
  behavior: 'Conversation',
  recommended_for: ['Language agents'],
  capabilities: ['Tools'],
  limitations: ['Text output'],
  compatibility: {
    operations: ['language.generate'],
    requires_conversation: true,
    allowed_input_modalities: ['text'],
    allowed_output_modalities: ['text'],
    required_capabilities: [],
    context_mode: 'required',
    knowledge_mode: 'optional',
    tools_mode: 'optional',
  },
  is_default: true,
}

function model(spec: Record<string, unknown> | null): ProviderModel {
  return {
    id: 'model-1',
    project_id: 'project-1',
    provider_credential_id: 'credential-1',
    name: 'Test',
    model: 'test-v1',
    status: 'active',
    spec,
  }
}

describe('ModelSpec × ExecutionStrategy compatibility', () => {
  it('accepts conversational language generation', () => {
    const result = executionStrategyCompatibilityForModel(model({
      source: 'catalog',
      model_type: 'language',
      operations: ['language.generate'],
      input_modalities: ['text', 'image'],
      output_modalities: ['text'],
      interaction: { mode: 'conversation', supports_conversation: true },
      capabilities: { tool_calling: { supported: true } },
    }), standard, { contextEnabled: true })

    expect(result.compatible).toBe(true)
    expect(result.known).toBe(true)
  })

  it('rejects embedding models before the user selects Standard', () => {
    const result = executionStrategyCompatibilityForModel(model({
      source: 'catalog',
      model_type: 'embedding',
      operations: ['embedding.create'],
      input_modalities: ['text'],
      output_modalities: ['embedding'],
      interaction: { mode: 'isolated', supports_conversation: false },
      capabilities: {},
    }), standard, { contextEnabled: true })

    expect(result.compatible).toBe(false)
    expect(result.issues.map((issue) => issue.code)).toEqual(expect.arrayContaining([
      'operation_not_supported',
      'conversation_not_supported',
      'execution_output_modality_not_supported',
    ]))
  })

  it('rejects enabled tools when the catalog explicitly lacks tool calling', () => {
    const result = executionStrategyCompatibilityForModel(model({
      source: 'catalog',
      operations: ['language.generate'],
      input_modalities: ['text'],
      output_modalities: ['text'],
      interaction: { mode: 'conversation', supports_conversation: true },
      capabilities: { tool_calling: { supported: false } },
    }), standard, { contextEnabled: true, toolsEnabled: true })

    expect(result.compatible).toBe(false)
    expect(result.issues.some((issue) => issue.code === 'model_capability_not_supported')).toBe(true)
  })

  it('keeps legacy models selectable when capability metadata is unknown', () => {
    const result = executionStrategyCompatibilityForModel(model({
      source: 'legacy',
      operations: ['language.generate'],
      input_modalities: ['text'],
      output_modalities: ['text'],
      interaction: { mode: 'conversation', supports_conversation: true },
      capabilities: {},
    }), standard, { contextEnabled: true, toolsEnabled: true })

    expect(result.compatible).toBe(true)
    expect(result.issues.some((issue) => issue.severity === 'warning')).toBe(true)
  })

  it('does not block legacy ProviderModels without a persisted ModelSpec', () => {
    const result = executionStrategyCompatibilityForModel(model(null), standard)

    expect(result.compatible).toBe(true)
    expect(result.known).toBe(false)
  })
})
