import { describe, expect, it } from 'vitest'

import type { AgentRelease, ExecutionStrategyDescriptor } from './types'
import {
  DEFAULT_EXECUTION_STRATEGY,
  executionStrategyDescriptor,
  executionStrategyForEnvironment,
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
  },
  {
    name: 'react',
    display_name: 'ReAct',
    description: 'Iterative reasoning and actions',
    behavior: 'Reason, act, observe, repeat',
    recommended_for: ['Iterative agents'],
    capabilities: ['Multiple reasoning loops'],
    limitations: ['Higher model usage'],
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
    is_default: false,
  },
]

const releases: AgentRelease[] = [
  {
    id: 'staging-release',
    project_id: 'project-1',
    agent_id: 'agent-1',
    version: 'staging-1',
    status: 'staging',
    runtime_config: { execution_strategy: 'standard' },
  },
  {
    id: 'production-release',
    project_id: 'project-1',
    agent_id: 'agent-1',
    version: 'production-1',
    status: 'production',
    runtime_config: { execution_strategy: 'plan_execute' },
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

  it('uses unsaved Draft strategy but immutable Release strategy in staging and production', () => {
    const draftRuntime = { execution_strategy: 'react' }

    expect(executionStrategyForEnvironment('draft', draftRuntime, releases)).toBe('react')
    expect(executionStrategyForEnvironment('staging', draftRuntime, releases)).toBe('standard')
    expect(executionStrategyForEnvironment('production', draftRuntime, releases)).toBe('plan_execute')
  })

  it('falls back to Standard when an immutable environment has no Release snapshot', () => {
    expect(executionStrategyForEnvironment('staging', { execution_strategy: 'react' }, [])).toBe('standard')
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

  it('keeps a readable Standard option while the catalog is loading', () => {
    expect(executionStrategySelectOptions([], 'standard')).toEqual([
      { value: 'standard', label: 'Standard' },
    ])
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
