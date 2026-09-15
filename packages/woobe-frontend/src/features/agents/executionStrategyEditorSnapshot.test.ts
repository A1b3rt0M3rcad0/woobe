import { describe, expect, it } from 'vitest'

import { canonicalSnapshot, agentToEditorState } from '@/features/playground/AgentEditorContext'
import { withExecutionStrategy } from './executionStrategy'
import type { Agent } from './types'

const agent: Agent = {
  id: 'agent-1',
  project_id: 'project-1',
  name: 'Agent',
  provider: 'openai',
  model: 'test-model',
  session_mode: 'stateless',
  status: 'active',
  settings: { runtime_config: {} },
}

describe('Execution Strategy editor snapshot', () => {
  it('carries a direct Playground Draft strategy selection into snapshot_override material', () => {
    const state = agentToEditorState(agent)
    state.runtimeConfig = withExecutionStrategy(state.runtimeConfig, 'react')

    const snapshot = canonicalSnapshot(state)
    const runtimeConfig = snapshot.runtime_config as Record<string, unknown>

    expect(runtimeConfig.execution_strategy).toBe('react')
  })

  it('keeps unrelated runtime configuration when strategy changes', () => {
    const state = agentToEditorState({
      ...agent,
      settings: {
        runtime_config: {
          context: { enabled: true },
          execution_strategy: 'standard',
        },
      },
    })
    state.runtimeConfig = withExecutionStrategy(state.runtimeConfig, 'standard')

    const runtimeConfig = canonicalSnapshot(state).runtime_config as Record<string, unknown>

    expect(runtimeConfig.execution_strategy).toBe('standard')
    expect(runtimeConfig.context).toEqual({ enabled: true })
  })
})
