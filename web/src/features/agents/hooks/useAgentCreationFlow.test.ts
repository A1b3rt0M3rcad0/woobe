import { describe, expect, it } from 'vitest'

import type { AvailableProviderModel, ProviderModel } from '@/features/provider-models/types'
import {
  buildModelMetadata,
  isEmbeddingProviderModel,
  providerLabel,
} from './useAgentCreationFlow'

function providerModel(overrides: Partial<ProviderModel> = {}): ProviderModel {
  return {
    id: 'model-1',
    project_id: 'project-1',
    provider_credential_id: 'credential-1',
    provider: 'openai',
    name: 'GPT generation model',
    model: 'gpt-4.1-mini',
    status: 'active',
    ...overrides,
  }
}

describe('agent creation flow helpers', () => {
  it('uses readable provider labels', () => {
    expect(providerLabel('openai')).toBe('OpenAI')
    expect(providerLabel('openrouter')).toBe('OpenRouter')
    expect(providerLabel('custom')).toBe('OpenAI Compatible')
    expect(providerLabel('internal')).toBe('internal')
  })

  it('filters explicit and inferred embedding models', () => {
    expect(isEmbeddingProviderModel(providerModel({ metadata: { capability: 'embedding' } }))).toBe(true)
    expect(isEmbeddingProviderModel(providerModel({ name: 'Text Embed 3', model: 'text-embedding-3-small' }))).toBe(true)
    expect(isEmbeddingProviderModel(providerModel())).toBe(false)
  })

  it('builds manual model metadata without remote catalog data', () => {
    expect(buildModelMetadata(null)).toMatchObject({
      capability: 'generation',
      source: 'manual',
      pricing: { source: 'manual' },
    })
  })

  it('preserves provider catalog capabilities and pricing', () => {
    const catalogModel: AvailableProviderModel = {
      id: 'anthropic/claude-sonnet-4',
      label: 'Claude Sonnet 4',
      provider: 'openrouter',
      source: 'remote',
      context_window: 200000,
      supports_tools: true,
      supports_json: true,
      supports_streaming: true,
      input_cost_per_1m_tokens: 3,
      output_cost_per_1m_tokens: 15,
      raw: { source: 'test' },
    }

    expect(buildModelMetadata(catalogModel)).toMatchObject({
      capability: 'generation',
      source: 'remote',
      catalog: {
        model_id: 'anthropic/claude-sonnet-4',
        label: 'Claude Sonnet 4',
        context_window: 200000,
      },
      capabilities: {
        supports_tools: true,
        supports_json: true,
        supports_streaming: true,
      },
      pricing: {
        input_cost_per_1m_tokens: 3,
        output_cost_per_1m_tokens: 15,
        source: 'provider_catalog',
      },
    })
  })
})
