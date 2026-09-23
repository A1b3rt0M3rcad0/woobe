import { describe, expect, it } from 'vitest'

import type { Agent } from '@/features/agents/types'
import type { NetworkDefinition } from './types'
import { previewNetworkDraftExternalContextContract } from './externalContextContractPreview'

const agent = (id: string, contract: Record<string, unknown>): Agent => ({
  id,
  project_id: 'project',
  name: id,
  provider: 'openai',
  model: 'model',
  status: 'active',
  settings: { external_context_contract: contract },
})

const definition = (nodes: NetworkDefinition['nodes']): NetworkDefinition => ({
  schema_version: 2,
  root_node_id: nodes[0]?.id ?? '',
  nodes,
  edges: [],
  settings: {
    session_mode: 'stateful',
    max_depth: 4,
    max_invocations: 16,
    timeout_seconds: 90,
  },
})

describe('Network Draft External Context preview', () => {
  it('replaces a persisted Agent contribution with the live unsaved Draft contract', () => {
    const result = previewNetworkDraftExternalContextContract({
      persistedEffectiveContract: {
        old_name: {
          schema: { type: 'string' },
          consumers: {
            root: { required: true, model: { expose: false } },
          },
        },
      },
      definition: definition([{
        id: 'root',
        agent_id: 'agent-1',
        label: 'Root',
        capability_description: '',
        position: { x: 0, y: 0 },
        binding: { source: 'draft', release_id: null },
      }]),
      agents: [agent('agent-1', {
        old_name: {
          schema: { type: 'string' },
          required: true,
          model: { expose: false },
        },
      })],
      liveDraftContractsByAgentId: {
        'agent-1': {
          client_id: {
            schema: { type: 'string' },
            required: true,
            scope: 'session',
            model: { expose: false },
          },
        },
      },
    })

    expect(result).not.toHaveProperty('old_name')
    expect(result).toEqual({
      client_id: {
        schema: { type: 'string' },
        scope: 'session',
        consumers: {
          root: {
            required: true,
            model: { expose: false },
          },
        },
      },
    })
  })

  it('drops removed Network consumers while preserving unchanged pinned consumers', () => {
    const result = previewNetworkDraftExternalContextContract({
      persistedEffectiveContract: {
        customer_id: {
          schema: { type: 'string' },
          consumers: {
            removed: { required: true, model: { expose: false } },
            pinned: { required: false, model: { expose: false } },
          },
        },
      },
      definition: definition([{
        id: 'pinned',
        agent_id: 'agent-2',
        label: 'Pinned',
        capability_description: '',
        position: { x: 0, y: 0 },
        binding: { source: 'release', release_id: 'release-1' },
      }]),
      agents: [agent('agent-2', {})],
    })

    expect(result).toEqual({
      customer_id: {
        schema: { type: 'string' },
        consumers: {
          pinned: { required: false, model: { expose: false } },
        },
      },
    })
  })

  it('uses the current saved Agent Draft when no live editor override exists', () => {
    const result = previewNetworkDraftExternalContextContract({
      persistedEffectiveContract: {},
      definition: definition([{
        id: 'root',
        agent_id: 'agent-1',
        label: 'Root',
        capability_description: '',
        position: { x: 0, y: 0 },
        binding: { source: 'draft', release_id: null },
      }]),
      agents: [agent('agent-1', {
        age: {
          schema: { type: 'integer' },
          required: true,
          model: { expose: true },
        },
      })],
    })

    expect(result).toEqual({
      age: {
        schema: { type: 'integer' },
        consumers: {
          root: {
            required: true,
            model: { expose: true },
          },
        },
      },
    })
  })
})
