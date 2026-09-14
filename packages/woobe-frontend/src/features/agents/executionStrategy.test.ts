import { describe, expect, it } from 'vitest'

import type { ExecutionStrategyDescriptor } from './types'
import {
  DEFAULT_EXECUTION_STRATEGY,
  executionStrategyDescriptor,
  executionStrategyFromRuntimeConfig,
  executionStrategySelectOptions,
  withExecutionStrategy,
} from './executionStrategy'

const catalog: ExecutionStrategyDescriptor[] = [
  {
    name: 'standard',
    display_name: 'Standard',
    description: 'Default execution',
    behavior: 'Model and capability loop',
    recommended_for: ['General agents'],
    capabilities: ['Tool loops'],
    limitations: ['No explicit planning phase'],
    is_default: true,
  },
  {
    name: 'react',
    display_name: 'ReAct',
    description: 'Iterative reasoning and actions',
    behavior: 'Reason, act, observe, repeat',
    recommended_for: ['Iterative agents'],
    capabilities: ['Multiple reasoning loops'],
    limitations: ['Higher model usage'],
    is_default: false,
  },
]

describe('Agent execution strategy config', () => {
  it('keeps historical runtime config on standard behavior', () => {
    expect(executionStrategyFromRuntimeConfig({})).toBe(DEFAULT_EXECUTION_STRATEGY)
    expect(executionStrategyFromRuntimeConfig({ context: { enabled: true } })).toBe('standard')
    expect(executionStrategyFromRuntimeConfig({ execution_strategy: 42 })).toBe('standard')
  })

  it('preserves any non-empty snapshot strategy instead of hardcoding the frontend catalog', () => {
    expect(executionStrategyFromRuntimeConfig({ execution_strategy: '  REACT  ' })).toBe('react')
    expect(executionStrategyFromRuntimeConfig({ execution_strategy: 'plan_execute' })).toBe('plan_execute')
  })

  it('builds selectable options from backend-owned catalog metadata', () => {
    expect(executionStrategySelectOptions(catalog, 'react')).toEqual([
      { value: 'standard', label: 'Standard' },
      { value: 'react', label: 'ReAct' },
    ])
    expect(executionStrategyDescriptor(catalog, 'react')?.behavior).toBe('Reason, act, observe, repeat')
  })

  it('keeps a historical snapshot selection visible when it is absent from the active catalog', () => {
    expect(executionStrategySelectOptions(catalog, 'retired_strategy')).toEqual([
      { value: 'retired_strategy', label: 'retired_strategy' },
      { value: 'standard', label: 'Standard' },
      { value: 'react', label: 'ReAct' },
    ])
    expect(executionStrategyDescriptor(catalog, 'retired_strategy')).toBeUndefined()
  })

  it('writes selected strategy without mutating or dropping unrelated runtime config', () => {
    const runtime = { context: { budget: { max_units: 12000 } } }
    const next = withExecutionStrategy(runtime, '  REACT  ')

    expect(next).toEqual({
      context: { budget: { max_units: 12000 } },
      execution_strategy: 'react',
    })
    expect(runtime).not.toHaveProperty('execution_strategy')
  })
})
