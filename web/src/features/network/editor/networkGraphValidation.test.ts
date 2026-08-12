import { describe, expect, it } from 'vitest'
import type { NetworkDefinition } from '../types'
import { canConnectNetworkNodes, delegationToolName, validateNetworkGraph } from './networkGraphValidation'

function graph(): NetworkDefinition {
  return {
    schema_version: 2,
    root_node_id: '00000000-0000-4000-8000-000000000001',
    nodes: [
      {
        id: '00000000-0000-4000-8000-000000000001',
        agent_id: '10000000-0000-4000-8000-000000000001',
        label: 'Coordinator',
        capability_description: 'Coordinates requests.',
        position: { x: 0, y: 0 },
        binding: { source: 'draft', release_id: null },
      },
      {
        id: '00000000-0000-4000-8000-000000000002',
        agent_id: '10000000-0000-4000-8000-000000000002',
        label: 'Billing',
        capability_description: 'Answers billing questions.',
        position: { x: 300, y: 0 },
        binding: { source: 'draft', release_id: null },
      },
      {
        id: '00000000-0000-4000-8000-000000000003',
        agent_id: '10000000-0000-4000-8000-000000000003',
        label: 'Refunds',
        capability_description: 'Handles refund requests.',
        position: { x: 600, y: 0 },
        binding: { source: 'draft', release_id: null },
      },
    ],
    edges: [
      { id: '20000000-0000-4000-8000-000000000001', source_node_id: '00000000-0000-4000-8000-000000000001', target_node_id: '00000000-0000-4000-8000-000000000002' },
      { id: '20000000-0000-4000-8000-000000000002', source_node_id: '00000000-0000-4000-8000-000000000002', target_node_id: '00000000-0000-4000-8000-000000000003' },
    ],
    settings: { session_mode: 'stateful', max_depth: 4, max_invocations: 16, timeout_seconds: 90 },
  }
}

describe('network graph validation', () => {
  it('accepts a reachable hierarchy', () => {
    expect(validateNetworkGraph(graph())).toEqual([])
  })

  it('rejects links that create cycles', () => {
    expect(canConnectNetworkNodes(
      graph(),
      '00000000-0000-4000-8000-000000000003',
      '00000000-0000-4000-8000-000000000002',
    )).toContain('cycle')
  })

  it('reports unreachable Agents', () => {
    const value = graph()
    value.edges = value.edges.slice(0, 1)
    expect(validateNetworkGraph(value).some((issue) => issue.code === 'unreachable')).toBe(true)
  })

  it('generates safe delegation tool names', () => {
    expect(delegationToolName(graph().nodes[1])).toBe('delegate_to_billing')
  })
})
