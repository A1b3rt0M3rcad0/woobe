import { describe, expect, it } from 'vitest'

import type { Agent } from '@/features/agents/types'
import {
  agentToEditorState,
  canonicalSnapshot,
  childPermissionsFromToolConfig,
  releaseToEditorState,
  toolPermissionsFromSnapshots,
} from './AgentEditorContext'

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

describe('AgentEditorContext context manager snapshot', () => {
  it('preserves the selected manager in the Agent Draft snapshot', () => {
    const state = agentToEditorState({
      ...agent,
      settings: {
        runtime_config: {
          context_assembler: { name: 'adaptive', version: 'v1' },
        },
      },
    })

    expect(state.runtimeConfig.context_assembler).toEqual({ name: 'adaptive', version: 'v1' })
    expect((canonicalSnapshot(state).runtime_config as Record<string, unknown>).context_assembler).toEqual({
      name: 'adaptive',
      version: 'v1',
    })
  })

  it('hydrates the exact manager identity from an immutable release snapshot', () => {
    const current = agentToEditorState(agent)
    const state = releaseToEditorState({
      id: 'release-1',
      project_id: 'project-1',
      agent_id: 'agent-1',
      version: 'v1.0.0',
      status: 'production',
      runtime_config: {
        context_assembler: { name: 'default', version: 'v1' },
      },
    }, current)

    expect(state.runtimeConfig.context_assembler).toEqual({ name: 'default', version: 'v1' })
  })
})

describe('AgentEditorContext Tool permissions', () => {
  it('reads HTTP route permissions from a Tool snapshot', () => {
    const permissions = toolPermissionsFromSnapshots([
      {
        id: 'tool-http',
        config: {
          protocol: 'http',
          mode: 'group',
          routes: [
            {
              id: 'route-search',
              operation_id: 'search_employee',
              permission: { mode: 'allow', risk_level: 'low' },
            },
            {
              id: 'route-delete',
              operation_id: 'delete_employee',
              permission: { mode: 'deny', risk_level: 'high' },
            },
          ],
        },
      },
    ])

    expect(permissions).toEqual({
      'tool-http': {
        'route-search': { mode: 'allow', risk_level: 'low' },
        'route-delete': { mode: 'deny', risk_level: 'high' },
      },
    })
  })

  it('uses the route default only when the snapshot has no explicit permission', () => {
    const permissions = childPermissionsFromToolConfig({
      protocol: 'http',
      mode: 'group',
      routes: [
        {
          id: 'route-review',
          default_permission: 'review',
          risk_level: 'medium',
        },
      ],
    })

    expect(permissions['route-review']).toEqual({
      mode: 'review',
      risk_level: 'medium',
    })
  })

  it('continues to read MCP discovered Tool permissions', () => {
    const permissions = childPermissionsFromToolConfig({
      protocol: 'mcp',
      discovered_tools: [
        {
          name: 'search_documents',
          permission: { mode: 'allow', risk_level: 'low' },
        },
      ],
    })

    expect(permissions.search_documents).toEqual({
      mode: 'allow',
      risk_level: 'low',
    })
  })
})
