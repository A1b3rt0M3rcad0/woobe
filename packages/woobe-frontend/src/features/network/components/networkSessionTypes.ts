import type { AgentNodeId, BindingSource, Environment } from './networkWorkspaceTypes'

export type AgentContextState = 'created' | 'reused' | 'stateless'

export interface NetworkAgentContext {
  id: string
  networkSessionId: string
  nodeId: AgentNodeId
  agentId: string
  agentName: string
  sessionMode: 'stateful' | 'stateless'
  agentSessionId: string | null
  source: BindingSource
  version: string
  invocationCount: number
  messageCount: number
  createdAt: string | null
  lastInvokedAt: string | null
}

export interface NetworkSession {
  id: string
  projectId: string
  networkId: string
  title: string
  environment: Environment
  networkVersion: string | null
  versionLabel: string
  draftRevision: number | null
  compositionHash: string
  status: 'active' | 'closed'
  createdAt: string
  lastMessageAt: string | null
  messageCount: number
  traceCount: number
  agentContexts: NetworkAgentContext[]
}

export type NetworkSessionsByEnvironment = Record<Environment, NetworkSession[]>
export type ActiveSessionByEnvironment = Record<Environment, string | null>
