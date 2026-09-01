import type { Agent } from '@/features/agents/types'
import type { AgentNodeId, ChatTarget, NetworkBinding, NetworkRun, NetworkSelection } from './networkWorkspaceTypes'

export const fallbackAgents: [Agent, Agent, Agent] = [
  { id: 'mock-coordinator', project_id: 'mock', name: 'Coordinator', description: 'Routes requests to the correct specialist.', provider: 'openai', model: 'gpt-5.2', status: 'active' },
  { id: 'mock-billing', project_id: 'mock', name: 'Billing Specialist', description: 'Handles invoices, payments and subscriptions.', provider: 'openai', model: 'gpt-5.2-mini', status: 'active' },
  { id: 'mock-technical', project_id: 'mock', name: 'Technical Support', description: 'Investigates incidents and technical questions.', provider: 'anthropic', model: 'claude-sonnet-4.5', status: 'active' },
]

export const DRAFT: Record<AgentNodeId, NetworkSelection> = {
  coordinator: { source: 'draft', ref: 'draft-coordinator', version: 'Revision 14', draftVersion: 'Revision 14', dirty: false },
  billing: { source: 'staging', ref: 'staging-billing-v3', version: 'v0.3.20260713.01', draftVersion: 'Revision 9', dirty: false },
  technical: { source: 'release', ref: 'release-technical-v1', version: 'v0.1.20260712.00', draftVersion: 'Revision 7', dirty: false },
}

export const STAGING: Record<AgentNodeId, NetworkSelection> = {
  coordinator: { source: 'staging', ref: 'staging-coordinator-v4', version: 'v0.4.20260713.02', draftVersion: 'Revision 14', dirty: false },
  billing: { source: 'staging', ref: 'staging-billing-v3', version: 'v0.3.20260713.01', draftVersion: 'Revision 9', dirty: false },
  technical: { source: 'release', ref: 'release-technical-v1', version: 'v0.1.20260712.00', draftVersion: 'Revision 7', dirty: false },
}

export const PRODUCTION: Record<AgentNodeId, NetworkSelection> = {
  coordinator: { source: 'release', ref: 'release-coordinator-v5', version: 'v0.5.20260713.00', draftVersion: 'Revision 14', dirty: false },
  billing: { source: 'release', ref: 'release-billing-v4', version: 'v0.4.20260713.00', draftVersion: 'Revision 9', dirty: false },
  technical: { source: 'release', ref: 'release-technical-v1', version: 'v0.1.20260712.00', draftVersion: 'Revision 7', dirty: false },
}

export const HISTORY: Record<AgentNodeId, NetworkSelection> = {
  coordinator: { source: 'release', ref: 'release-coordinator-v3', version: 'v0.3.20260701.00', draftVersion: 'Revision 14', dirty: false },
  billing: { source: 'release', ref: 'release-billing-v2', version: 'v0.2.20260629.01', draftVersion: 'Revision 9', dirty: false },
  technical: { source: 'release', ref: 'release-technical-v1', version: 'v0.1.20260712.00', draftVersion: 'Revision 7', dirty: false },
}

export const runHistory: NetworkRun[] = [
  { id: 'run-1', title: 'Invoice status request', environment: 'production', status: 'success', duration: '1.84s', cost: '$0.012', path: ['entry', 'coordinator', 'billing', 'end'] },
  { id: 'run-2', title: 'Password reset guidance', environment: 'staging', status: 'success', duration: '2.21s', cost: '$0.017', path: ['entry', 'coordinator', 'technical', 'end'] },
  { id: 'run-3', title: 'API timeout investigation', environment: 'staging', status: 'error', duration: '0.73s', cost: '$0.004', path: ['entry', 'coordinator', 'technical'] },
]

export function clone(value: Record<AgentNodeId, NetworkSelection>): Record<AgentNodeId, NetworkSelection> {
  return {
    coordinator: { ...value.coordinator },
    billing: { ...value.billing },
    technical: { ...value.technical },
  }
}

export function bind(agents: [Agent, Agent, Agent], value: Record<AgentNodeId, NetworkSelection>): Record<AgentNodeId, NetworkBinding> {
  return {
    coordinator: { nodeId: 'coordinator', agent: agents[0], ...value.coordinator },
    billing: { nodeId: 'billing', agent: agents[1], ...value.billing },
    technical: { nodeId: 'technical', agent: agents[2], ...value.technical },
  }
}

export function signature(target: ChatTarget, bindings: Record<AgentNodeId, NetworkBinding>) {
  return `${target}|${(['coordinator', 'billing', 'technical'] as AgentNodeId[])
    .map((id) => `${id}:${bindings[id].ref}:${bindings[id].dirty ? 'preview' : 'saved'}`)
    .join('|')}`
}

export function sourceLabel(source: NetworkBinding['source']) {
  if (source === 'draft') return 'Agent Draft'
  if (source === 'staging') return 'Agent Staging'
  return 'Agent Release'
}
