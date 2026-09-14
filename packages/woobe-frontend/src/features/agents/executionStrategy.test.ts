import { describe, expect, it } from 'vitest'

import {
  DEFAULT_EXECUTION_STRATEGY,
  executionStrategyFromRuntimeConfig,
  withExecutionStrategy,
} from './executionStrategy'


describe('Agent execution strategy config', () => {
  it('keeps historical runtime config on standard behavior', () => {
    expect(executionStrategyFromRuntimeConfig({})).toBe(DEFAULT_EXECUTION_STRATEGY)
    expect(executionStrategyFromRuntimeConfig({ context: { enabled: true } })).toBe('standard')
  })

  it('reads explicit standard selection', () => {
    expect(executionStrategyFromRuntimeConfig({ execution_strategy: 'standard' })).toBe('standard')
  })

  it('does not expose unknown strategy values as valid UI selections', () => {
    expect(executionStrategyFromRuntimeConfig({ execution_strategy: 'react' })).toBe('standard')
    expect(executionStrategyFromRuntimeConfig({ execution_strategy: 42 })).toBe('standard')
  })

  it('writes strategy without mutating or dropping unrelated runtime config', () => {
    const runtime = { context: { budget: { max_units: 12000 } } }
    const next = withExecutionStrategy(runtime, 'standard')

    expect(next).toEqual({
      context: { budget: { max_units: 12000 } },
      execution_strategy: 'standard',
    })
    expect(runtime).not.toHaveProperty('execution_strategy')
  })
})
