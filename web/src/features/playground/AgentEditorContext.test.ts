import { describe, expect, it } from 'vitest'

import type { Agent } from '@/features/agents/types'
import { agentToEditorState, canonicalSnapshot, releaseToEditorState } from './AgentEditorContext'

const agent: Agent = {
  id: 'agent-1',
  project_id: 'project-1',
  name: 'Router',
  provider: 'openai',
  model: 'gpt-test',
  status: 'active',
  session_mode: 'stateless',
  settings: {},
}

describe('AgentEditorContext session mode', () => {
  it('hydrates and serializes the Agent Draft session mode', () => {
    const state = agentToEditorState(agent)

    expect(state.sessionMode).toBe('stateless')
    expect(canonicalSnapshot(state).session_mode).toBe('stateless')
  })

  it('hydrates an immutable release session mode', () => {
    const current = agentToEditorState({ ...agent, session_mode: 'stateful' })
    const state = releaseToEditorState({
      id: 'release-1',
      project_id: 'project-1',
      agent_id: 'agent-1',
      version: 'v1.0.0',
      status: 'production',
      session_mode: 'stateless',
    }, current)

    expect(state.sessionMode).toBe('stateless')
  })
})
