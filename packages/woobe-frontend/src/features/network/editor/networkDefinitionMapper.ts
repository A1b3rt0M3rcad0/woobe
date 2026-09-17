import type { Agent } from '@/features/agents/types'
import { createUuid } from '@/lib/uuid'
import type { NetworkAgentBindingSelector, NetworkDefinition, NetworkEdge, NetworkNode } from '../types'
import type { NetworkDefinitionChange } from './types'

export const DEFAULT_NETWORK_SETTINGS: NetworkDefinition['settings'] = {
  session_mode: 'stateful',
  max_depth: 4,
  max_invocations: 16,
  timeout_seconds: 90,
  max_tool_result_chars: 16_000,
}

const DRAFT_BINDING: NetworkAgentBindingSelector = { source: 'draft', release_id: null }

export function createEmptyNetworkDefinition(): NetworkDefinition {
  return {
    schema_version: 2,
    root_node_id: '',
    nodes: [],
    edges: [],
    settings: { ...DEFAULT_NETWORK_SETTINGS },
  }
}

function validPosition(value: unknown): NetworkNode['position'] {
  if (!value || typeof value !== 'object') return { x: 260, y: 220 }
  const position = value as Record<string, unknown>
  return {
    x: typeof position.x === 'number' ? position.x : 260,
    y: typeof position.y === 'number' ? position.y : 220,
  }
}

function validBinding(value: unknown): NetworkAgentBindingSelector {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return { ...DRAFT_BINDING }
  const binding = value as Record<string, unknown>
  if (
    (binding.source === 'staging' || binding.source === 'release')
    && typeof binding.release_id === 'string'
    && binding.release_id
  ) {
    return { source: binding.source, release_id: binding.release_id }
  }
  return { ...DRAFT_BINDING }
}

export function normalizeNetworkDefinition(value: unknown): NetworkDefinition {
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    return createEmptyNetworkDefinition()
  }
  const source = value as Record<string, unknown>
  const rawNodes = Array.isArray(source.nodes) ? source.nodes : []
  const rawEdges = Array.isArray(source.edges) ? source.edges : []
  const nodes: NetworkNode[] = rawNodes.flatMap((item) => {
    if (!item || typeof item !== 'object') return []
    const node = item as Record<string, unknown>
    if (typeof node.id !== 'string' || typeof node.agent_id !== 'string') return []
    return [{
      id: node.id,
      agent_id: node.agent_id,
      label: typeof node.label === 'string' && node.label.trim() ? node.label.trim() : 'Agent',
      capability_description: typeof node.capability_description === 'string'
        ? node.capability_description.trim().slice(0, 2000)
        : '',
      position: validPosition(node.position),
      binding: validBinding(node.binding),
    }]
  })
  const nodeIds = new Set(nodes.map((node) => node.id))
  const edges: NetworkEdge[] = rawEdges.flatMap((item) => {
    if (!item || typeof item !== 'object') return []
    const edge = item as Record<string, unknown>
    if (
      typeof edge.id !== 'string'
      || typeof edge.source_node_id !== 'string'
      || typeof edge.target_node_id !== 'string'
      || !nodeIds.has(edge.source_node_id)
      || !nodeIds.has(edge.target_node_id)
    ) return []
    return [{ id: edge.id, source_node_id: edge.source_node_id, target_node_id: edge.target_node_id }]
  })
  const rawSettings = source.settings && typeof source.settings === 'object'
    ? source.settings as Record<string, unknown>
    : {}
  const root = typeof source.root_node_id === 'string' && nodeIds.has(source.root_node_id)
    ? source.root_node_id
    : nodes[0]?.id ?? ''
  return {
    schema_version: 2,
    root_node_id: root,
    nodes,
    edges,
    settings: {
      session_mode: rawSettings.session_mode === 'stateless' ? 'stateless' : 'stateful',
      max_depth: Number.isFinite(rawSettings.max_depth) ? Number(rawSettings.max_depth) : DEFAULT_NETWORK_SETTINGS.max_depth,
      max_invocations: Number.isFinite(rawSettings.max_invocations) ? Number(rawSettings.max_invocations) : DEFAULT_NETWORK_SETTINGS.max_invocations,
      timeout_seconds: Number.isFinite(rawSettings.timeout_seconds) ? Number(rawSettings.timeout_seconds) : DEFAULT_NETWORK_SETTINGS.timeout_seconds,
      max_tool_result_chars: Number.isFinite(rawSettings.max_tool_result_chars) ? Number(rawSettings.max_tool_result_chars) : DEFAULT_NETWORK_SETTINGS.max_tool_result_chars,
    },
  }
}

export function createNodeForAgent(agent: Agent, index: number): NetworkNode {
  const column = index % 3
  const row = Math.floor(index / 3)
  return {
    id: createUuid(),
    agent_id: agent.id,
    label: agent.name,
    capability_description: (agent.description ?? '').trim().slice(0, 2000),
    position: { x: 180 + column * 300, y: 140 + row * 220 },
    binding: { ...DRAFT_BINDING },
  }
}

export function applyNetworkDefinitionChange(
  definition: NetworkDefinition,
  change: NetworkDefinitionChange,
): NetworkDefinition {
  switch (change.type) {
    case 'add-node':
      return {
        ...definition,
        root_node_id: definition.root_node_id || change.node.id,
        nodes: [...definition.nodes, change.node],
      }
    case 'remove-node': {
      const nodes = definition.nodes.filter((node) => node.id !== change.nodeId)
      return {
        ...definition,
        nodes,
        edges: definition.edges.filter((edge) => edge.source_node_id !== change.nodeId && edge.target_node_id !== change.nodeId),
        root_node_id: definition.root_node_id === change.nodeId ? nodes[0]?.id ?? '' : definition.root_node_id,
      }
    }
    case 'move-node':
      return { ...definition, nodes: definition.nodes.map((node) => node.id === change.nodeId ? { ...node, position: change.position } : node) }
    case 'rename-node':
      return { ...definition, nodes: definition.nodes.map((node) => node.id === change.nodeId ? { ...node, label: change.label } : node) }
    case 'describe-node':
      return { ...definition, nodes: definition.nodes.map((node) => node.id === change.nodeId ? { ...node, capability_description: change.description.slice(0, 2000) } : node) }
    case 'set-binding':
      return { ...definition, nodes: definition.nodes.map((node) => node.id === change.nodeId ? { ...node, binding: change.binding } : node) }
    case 'add-edge':
      return { ...definition, edges: [...definition.edges, change.edge] }
    case 'remove-edge':
      return { ...definition, edges: definition.edges.filter((edge) => edge.id !== change.edgeId) }
    case 'set-root':
      return {
        ...definition,
        root_node_id: change.nodeId,
        edges: definition.edges.filter((edge) => edge.target_node_id !== change.nodeId),
      }
    case 'settings':
      return { ...definition, settings: { ...change.settings } }
  }
}
