import { describe, expect, it } from 'vitest'

import {
  calculateContextCapacity,
  presetInputBudget,
  providerModelCapabilities,
  readContextBudget,
  withContextBudget,
} from './contextBudget'

const providerModel = (metadata: Record<string, unknown>) => ({
  id: 'model-1',
  project_id: 'project-1',
  provider_credential_id: 'credential-1',
  provider: 'openrouter',
  name: 'Model',
  model: 'provider/model',
  status: 'active',
  metadata,
})

describe('Context Budget configuration', () => {
  it('preserves unrelated Context Policy and runtime keys while updating budget', () => {
    const runtimeConfig = {
      timeout_seconds: 30,
      context: {
        allowed_sources: ['SYSTEM', 'USER_INPUT', 'SKILL'],
        skills: { max_units: 8000 },
        budget: { max_input_units: 12000, runtime_reserve_units: 1000 },
      },
      skills: { bindings: [{ enabled: true }] },
    }

    const next = withContextBudget(runtimeConfig, {
      maxInputUnits: 64000,
      runtimeReserveUnits: 2000,
    })

    expect(readContextBudget(next)).toEqual({
      maxInputUnits: 64000,
      runtimeReserveUnits: 2000,
    })
    expect(next.timeout_seconds).toBe(30)
    expect((next.context as Record<string, unknown>).allowed_sources).toEqual(['SYSTEM', 'USER_INPUT', 'SKILL'])
    expect((next.context as Record<string, unknown>).skills).toEqual({ max_units: 8000 })
    expect(next.skills).toEqual({ bindings: [{ enabled: true }] })
  })

  it('resolves ProviderModel context and output capabilities from persisted metadata', () => {
    const capabilities = providerModelCapabilities(providerModel({
      catalog: { context_window: 131072, max_output_tokens: 8192 },
    }))

    expect(capabilities).toEqual({
      contextWindow: 131072,
      maxOutputTokens: 8192,
    })
  })

  it('clamps output and fixed Context Budget to the invoked model capability', () => {
    const capacity = calculateContextCapacity({
      contextWindow: 32000,
      modelMaxOutputTokens: 4096,
      configuredOutputTokens: 8192,
      runtimeReserveUnits: 2000,
      configuredInputBudget: 64000,
    })

    expect(capacity.effectiveOutputReserve).toBe(4096)
    expect(capacity.modelUsableInput).toBe(25904)
    expect(capacity.effectiveInputBudget).toBe(25904)
    expect(capacity.budgetClamped).toBe(true)
    expect(capacity.budgetPreservationRatio).toBeCloseTo(25904 / 64000)
  })

  it('uses model usable input directly when Context Budget is Auto', () => {
    const capacity = calculateContextCapacity({
      contextWindow: 128000,
      modelMaxOutputTokens: 16000,
      configuredOutputTokens: 8000,
      runtimeReserveUnits: 2000,
      configuredInputBudget: null,
    })

    expect(capacity.modelUsableInput).toBe(118000)
    expect(capacity.effectiveInputBudget).toBe(118000)
    expect(capacity.budgetClamped).toBe(false)
  })

  it('converts percentage presets to deterministic absolute budget values', () => {
    expect(presetInputBudget(118000, 0.5)).toBe(59000)
    expect(presetInputBudget(null, 0.5)).toBeNull()
  })
})
