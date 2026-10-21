import { describe, expect, it } from 'vitest'

import type { Agent, AgentRelease } from '@/features/agents/types'
import { agentToEditorState, canonicalSnapshot, releaseToEditorState } from '../AgentEditorContext'

function makeAgent(settings: Record<string, unknown> = {}): Agent {
  return {
    id: 'agent-1',
    project_id: 'project-1',
    name: 'Agent',
    provider: 'openai',
    model: 'gpt-test',
    status: 'active',
    settings,
  }
}

describe('AgentEditorContext snapshot state', () => {
  it('restores the saved knowledge version from agent settings', () => {
    const state = agentToEditorState(makeAgent({ knowledge_version_id: 'knowledge-7' }))

    expect(state.knowledgeVersionId).toBe('knowledge-7')
  })

  it('restores MCP permission policies from release tool snapshots', () => {
    const current = agentToEditorState(makeAgent())
    const release: AgentRelease = {
      id: 'release-1',
      project_id: 'project-1',
      agent_id: 'agent-1',
      version: 'draft',
      status: 'draft',
      runtime_config: {
        tools: {
          tool_ids: ['tool-1'],
          snapshots: [
            {
              id: 'tool-1',
              config: {
                discovered_tools: [
                  { name: 'search', permission: { mode: 'allow' } },
                  { name: 'admin', permission: { mode: 'deny' } },
                ],
              },
            },
          ],
        },
      },
    }

    const state = releaseToEditorState(release, current)

    expect(state.toolIds).toEqual(['tool-1'])
    expect(state.toolPermissions).toEqual({
      'tool-1': {
        search: { mode: 'allow' },
        admin: { mode: 'deny' },
      },
    })
  })

  it('includes draft permissions and knowledge in the canonical snapshot', () => {
    const state = agentToEditorState(makeAgent())
    state.knowledgeVersionId = 'knowledge-9'
    state.toolIds = ['tool-1']
    state.toolPermissions = {
      'tool-1': {
        search: { mode: 'allow' },
        admin: { mode: 'review', risk_level: 'unknown' },
      },
    }

    const snapshot = canonicalSnapshot(state)
    const runtimeConfig = snapshot.runtime_config as Record<string, unknown>
    const tools = runtimeConfig.tools as Record<string, unknown>

    expect(snapshot.knowledge_version_id).toBe('knowledge-9')
    expect(tools.tool_ids).toEqual(['tool-1'])
    expect(tools.permissions).toEqual(state.toolPermissions)
  })

  it('round-trips artifact capability and its pinned runtime configuration', () => {
    const artifactCapability = {
      schema_version: 1, enabled: true,
      workspace_binding: { field: 'artifact_workspace', namespace: 'course-files', scope: 'session' },
      actions: ['read', 'search'],
      limits: { max_search_results: 8, max_read_chars: 2048, max_total_read_chars: 12000, max_context_units: 3000, max_writes: 0 },
      processing_profile: null,
    }
    const state = agentToEditorState(makeAgent({ runtime_config: { artifacts: artifactCapability } }))
    const snapshot = canonicalSnapshot(state)

    expect((snapshot.runtime_config as Record<string, unknown>).artifacts).toEqual(artifactCapability)
    const releaseState = releaseToEditorState({
      id: 'release-artifacts', project_id: 'project-1', agent_id: 'agent-1', version: 'staging-1',
      status: 'staging', runtime_config: { artifacts: artifactCapability },
    }, state)
    expect((canonicalSnapshot(releaseState).runtime_config as Record<string, unknown>).artifacts).toEqual(artifactCapability)
  })
})
