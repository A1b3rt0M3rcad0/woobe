import type { NetworkDefinition, NetworkNode } from '../types'
import type { NetworkEditorIssue } from './types'

export function delegationToolName(node: NetworkNode): string {
  let slug = node.label.trim().toLowerCase().replace(/-/g, '_').replace(/[^a-z0-9_]+/g, '_')
  slug = slug.replace(/_+/g, '_').replace(/^_+|_+$/g, '') || `agent_${node.id.slice(0, 8)}`
  if (/^[0-9]/.test(slug)) slug = `agent_${slug}`
  return `delegate_to_${slug}`.slice(0, 64)
}

function hasPath(definition: NetworkDefinition, from: string, to: string): boolean {
  const outgoing = new Map<string, string[]>()
  definition.nodes.forEach((node) => outgoing.set(node.id, []))
  definition.edges.forEach((edge) => outgoing.get(edge.source_node_id)?.push(edge.target_node_id))
  const pending = [from]
  const visited = new Set<string>()
  while (pending.length) {
    const current = pending.pop()!
    if (current === to) return true
    if (visited.has(current)) continue
    visited.add(current)
    pending.push(...(outgoing.get(current) ?? []))
  }
  return false
}

export function canConnectNetworkNodes(definition: NetworkDefinition, source: string, target: string): string | null {
  if (!source || !target) return 'Choose two valid Agents'
  if (source === target) return 'An Agent cannot delegate directly to itself'
  if (target === definition.root_node_id) return 'The entry Agent cannot be a delegation target'
  if (definition.edges.some((edge) => edge.source_node_id === source && edge.target_node_id === target)) return 'This delegation already exists'
  if (hasPath(definition, target, source)) return 'This delegation would create a cycle'
  return null
}

export function validateNetworkGraph(definition: NetworkDefinition): NetworkEditorIssue[] {
  const issues: NetworkEditorIssue[] = []
  const nodeIds = new Set(definition.nodes.map((node) => node.id))
  if (!definition.nodes.length) issues.push({ code: 'empty', severity: 'error', message: 'Add at least one Agent to the Network.' })
  if (!definition.root_node_id || !nodeIds.has(definition.root_node_id)) issues.push({ code: 'root', severity: 'error', message: 'Choose one Agent as the entry point.' })

  const edgeKeys = new Set<string>()
  for (const edge of definition.edges) {
    if (!nodeIds.has(edge.source_node_id) || !nodeIds.has(edge.target_node_id)) {
      issues.push({ code: 'missing-edge-node', severity: 'error', message: 'A delegation references an Agent that no longer exists.', edgeId: edge.id })
      continue
    }
    const reason = edge.target_node_id === definition.root_node_id
      ? 'The entry Agent cannot be a delegation target.'
      : edge.source_node_id === edge.target_node_id
        ? 'An Agent cannot delegate directly to itself.'
        : null
    if (reason) issues.push({ code: 'invalid-edge', severity: 'error', message: reason, edgeId: edge.id })
    const key = `${edge.source_node_id}:${edge.target_node_id}`
    if (edgeKeys.has(key)) issues.push({ code: 'duplicate-edge', severity: 'error', message: 'Remove the duplicated delegation.', edgeId: edge.id })
    edgeKeys.add(key)
  }

  if (definition.root_node_id && nodeIds.has(definition.root_node_id)) {
    for (const node of definition.nodes) {
      if (!hasPath(definition, definition.root_node_id, node.id)) {
        issues.push({ code: 'unreachable', severity: 'error', message: `${node.label} is not reachable from the entry Agent.`, nodeId: node.id })
      }
    }
  }

  const tools = new Map<string, string>()
  for (const node of definition.nodes) {
    if (node.capability_description.length > 2000) issues.push({ code: 'capability-description', severity: 'error', message: `${node.label} has a delegation description longer than 2000 characters.`, nodeId: node.id })
    if (node.binding.source === 'draft' && node.binding.release_id !== null) issues.push({ code: 'draft-binding', severity: 'error', message: `${node.label} has an invalid Draft binding.`, nodeId: node.id })
    if (node.binding.source !== 'draft' && !node.binding.release_id) issues.push({ code: 'stable-binding', severity: 'error', message: `${node.label} must reference an exact Agent snapshot.`, nodeId: node.id })
    const tool = delegationToolName(node)
    const previous = tools.get(tool)
    if (previous) issues.push({ code: 'tool-name', severity: 'error', message: `${node.label} generates the same delegation tool as another Agent.`, nodeId: node.id })
    tools.set(tool, node.id)
  }

  const { max_depth, max_invocations, timeout_seconds } = definition.settings
  if (max_depth < 1 || max_depth > 8) issues.push({ code: 'max-depth', severity: 'error', message: 'Maximum depth must be between 1 and 8.' })
  if (max_invocations < 1 || max_invocations > 64) issues.push({ code: 'max-invocations', severity: 'error', message: 'Maximum invocations must be between 1 and 64.' })
  if (timeout_seconds < 1 || timeout_seconds > 300) issues.push({ code: 'timeout', severity: 'error', message: 'Timeout must be between 1 and 300 seconds.' })
  return issues
}
