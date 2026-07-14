import { describe, expect, it } from 'vitest'
import { applyNetworkDefinitionChange, createEmptyNetworkDefinition, normalizeNetworkDefinition } from './networkDefinitionMapper'

describe('network definition mapper', () => {
  it('normalizes an empty persisted Draft', () => {
    expect(normalizeNetworkDefinition({})).toEqual(createEmptyNetworkDefinition())
  })

  it('upgrades legacy nodes to explicit Draft bindings', () => {
    const definition = normalizeNetworkDefinition({
      schema_version: 1,
      root_node_id: '00000000-0000-4000-8000-000000000001',
      nodes: [
        { id: '00000000-0000-4000-8000-000000000001', agent_id: '10000000-0000-4000-8000-000000000001', label: 'First', capability_description: '', position: { x: 0, y: 0 } },
      ],
      edges: [],
    })

    expect(definition.schema_version).toBe(2)
    expect(definition.nodes[0].binding).toEqual({ source: 'draft', release_id: null })
  })

  it('selects the first Agent as root and removes incident edges', () => {
    const first = { id: '00000000-0000-4000-8000-000000000001', agent_id: '10000000-0000-4000-8000-000000000001', label: 'First', capability_description: 'Coordinates work.', position: { x: 0, y: 0 }, binding: { source: 'draft' as const, release_id: null } }
    const second = { id: '00000000-0000-4000-8000-000000000002', agent_id: '10000000-0000-4000-8000-000000000002', label: 'Second', capability_description: 'Completes specialist work.', position: { x: 300, y: 0 }, binding: { source: 'draft' as const, release_id: null } }
    let definition = applyNetworkDefinitionChange(createEmptyNetworkDefinition(), { type: 'add-node', node: first })
    definition = applyNetworkDefinitionChange(definition, { type: 'add-node', node: second })
    definition = applyNetworkDefinitionChange(definition, { type: 'add-edge', edge: { id: 'edge', source_node_id: first.id, target_node_id: second.id } })
    definition = applyNetworkDefinitionChange(definition, { type: 'remove-node', nodeId: first.id })
    expect(definition.root_node_id).toBe(second.id)
    expect(definition.edges).toEqual([])
  })

  it('updates a node binding without changing the shared Agent', () => {
    const definition = normalizeNetworkDefinition({
      root_node_id: '00000000-0000-4000-8000-000000000001',
      nodes: [
        { id: '00000000-0000-4000-8000-000000000001', agent_id: '10000000-0000-4000-8000-000000000001', label: 'First', capability_description: '', position: { x: 0, y: 0 } },
      ],
      edges: [],
    })
    const changed = applyNetworkDefinitionChange(definition, {
      type: 'set-binding',
      nodeId: definition.nodes[0].id,
      binding: { source: 'release', release_id: '20000000-0000-4000-8000-000000000001' },
    })

    expect(changed.nodes[0].agent_id).toBe(definition.nodes[0].agent_id)
    expect(changed.nodes[0].binding).toEqual({ source: 'release', release_id: '20000000-0000-4000-8000-000000000001' })
  })

  it('removes inbound links when the entry point changes', () => {
    const definition = normalizeNetworkDefinition({
      root_node_id: '00000000-0000-4000-8000-000000000001',
      nodes: [
        { id: '00000000-0000-4000-8000-000000000001', agent_id: '10000000-0000-4000-8000-000000000001', label: 'First', capability_description: 'Coordinates work.', position: { x: 0, y: 0 } },
        { id: '00000000-0000-4000-8000-000000000002', agent_id: '10000000-0000-4000-8000-000000000002', label: 'Second', capability_description: 'Completes specialist work.', position: { x: 300, y: 0 } },
      ],
      edges: [{ id: 'edge', source_node_id: '00000000-0000-4000-8000-000000000001', target_node_id: '00000000-0000-4000-8000-000000000002' }],
    })
    const changed = applyNetworkDefinitionChange(definition, { type: 'set-root', nodeId: '00000000-0000-4000-8000-000000000002' })
    expect(changed.edges).toEqual([])
  })
})
