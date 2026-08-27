import type { Agent } from '@/features/agents/types'

export type Environment = 'draft' | 'staging' | 'production'
export type ChatTarget = Environment
export type BindingSource = 'draft' | 'staging' | 'release'
export type AgentNodeId = string
export type NodeId = AgentNodeId | 'entry' | 'end'

export type NetworkSelection = {
  source: BindingSource
  ref: string
  version: string
  draftVersion: string
  draftBase?: string
  dirty: boolean
  snapshotOverride?: Record<string, unknown>
}

export type NetworkBinding = NetworkSelection & {
  nodeId: AgentNodeId
  agent: Agent
}

export type NetworkVersionOption = {
  source: BindingSource
  ref: string
  version: string
  note: string
  created: string
}

export type NetworkRun = {
  id: string
  title: string
  environment: Environment
  status: 'success' | 'error' | 'running' | 'cancelled'
  duration: string
  cost: string
  path: NodeId[]
  traceId?: string
}
