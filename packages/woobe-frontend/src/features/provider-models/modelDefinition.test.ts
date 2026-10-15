import { describe, expect, it } from 'vitest'
import { buildProviderModelDefinition, discoveredModelSpec, effectiveModelPricing, isAgentModel } from './modelDefinition'
import type { AvailableProviderModel, ProviderModel } from './types'

const spec = { provider: 'openai', model_id: 'test', model_type: 'language', operations: ['language.generate'],
  input_modalities: ['text'], output_modalities: ['text'], interaction: { supports_conversation: true },
  capabilities: { tool_calling: { supported: true, source: 'provider' } },
  pricing: { input_cost_per_1m_tokens: 1, output_cost_per_1m_tokens: 2, currency: 'USD', billing_unit: 'per_1m_tokens' },
  limits: { context_window: 1000, max_output_tokens: 100 } }
const catalog: AvailableProviderModel = { id: 'test', label: 'Test', provider: 'openai', source: 'provider', model_spec: spec }
const input = { projectId: 'project', credentialId: 'credential', modelId: 'test', name: 'Test' }
const model: ProviderModel = { id: 'installed', project_id: 'project', provider_credential_id: 'credential',
  name: 'Test', model: 'test', status: 'active', spec }

describe('shared ProviderModel authoring contract', () => {
  it('keeps catalog semantics equivalent across the four form inputs', () => {
    const metadata = [undefined, { source: 'remote', pricing: spec.pricing },
      { capabilities: { supports_tools: true }, pricing: spec.pricing, context_window: 1000, max_output_tokens: 100 },
      { capability: 'generation', provider_model_raw: { woobe_model_spec: spec }, pricing: spec.pricing }]
    for (const item of metadata) {
      const payload = buildProviderModelDefinition({ ...input, catalog, metadata: item })
      expect(payload.spec).toEqual(spec)
      expect(payload.metadata?.model_spec_baseline).toEqual(spec)
      expect(payload.metadata?.model_spec_overrides).toEqual({})
    }
  })

  it('preserves zero and sends inheritance when an override is cleared', () => {
    const existing = { ...model, metadata: { model_spec_baseline: spec,
      model_spec_overrides: { pricing: { input_cost_per_1m_tokens: 5 } } }, spec: { ...spec, pricing: { ...spec.pricing, input_cost_per_1m_tokens: 5 } } }
    const zero = buildProviderModelDefinition({ ...input, existing, metadata: { pricing: { input_cost_per_1m_tokens: 0 } } })
    expect(zero.metadata?.model_spec_overrides.pricing.input_cost_per_1m_tokens).toBe(0)
    const inherit = buildProviderModelDefinition({ ...input, existing, metadata: { pricing: { input_cost_per_1m_tokens: null } } })
    expect(inherit.metadata?.model_spec_overrides.pricing.input_cost_per_1m_tokens).toEqual({ action: 'inherit' })
    expect(effectiveModelPricing(existing).input_cost_per_1m_tokens).toBe(5)
  })

  it('invalidates catalog evidence when the authored ID changes', () => {
    const changed = buildProviderModelDefinition({ ...input, modelId: 'other', existing: model, catalog,
      metadata: { model_spec: spec, model_spec_baseline: spec, provider_model_raw: { woobe_model_spec: spec } } })
    expect(changed.spec).toBeUndefined()
    expect(changed.metadata?.model_spec_baseline).toBeUndefined()
    expect(changed.metadata?.provider_model_raw).toBeUndefined()
  })

  it('requires catalog evidence and rejects invalid prices', () => {
    expect(() => buildProviderModelDefinition({ ...input, catalog: { ...catalog, model_spec: null } })).toThrow('manual ModelSpec')
    for (const value of [NaN, Infinity, -1]) expect(() => buildProviderModelDefinition({ ...input, catalog,
      metadata: { pricing: { input_cost_per_1m_tokens: value } } })).toThrow('finite')
    expect(discoveredModelSpec({ ...catalog, model_spec: null, raw: { woobe_model_spec: spec } })).toEqual(spec)
  })

  it('filters Agents by operations even when names suggest another family', () => {
    expect(isAgentModel({ ...model, name: 'embed proxy' })).toBe(true)
    expect(isAgentModel({ ...model, spec: { ...spec, operations: ['embedding.create'], output_modalities: ['embedding'] } })).toBe(false)
    expect(isAgentModel({ ...model, spec: { ...spec, operations: ['image.generate'], output_modalities: ['image'] } })).toBe(false)
  })
})
