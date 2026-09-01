import type { Agent } from '@/features/agents/types'
import type {
  NetworkAgentBindingSelector,
  NetworkAgentBindingSource,
  NetworkDefinition,
  NetworkEdge,
  NetworkNode,
} from '../types'

export type NetworkEditorIssueSeverity = 'error' | 'warning'

export interface NetworkEditorIssue {
  code: string
  severity: NetworkEditorIssueSeverity
  message: string
  nodeId?: string
  edgeId?: string
}

export interface NetworkEditorState {
  name: string
  description: string
  definition: NetworkDefinition
  revision: number
  dirty: boolean
}

export type NetworkAgentNodeData = {
  agent?: Agent
  node: NetworkNode
  binding?: {
    source: NetworkAgentBindingSource
    version: string
    dirty: boolean
    ref: string
  }
  isRoot: boolean
  readOnly: boolean
  activeInRun?: boolean
  issues: NetworkEditorIssue[]
} & Record<string, unknown>

export type NetworkEditorSelection =
  | { type: 'network' }
  | { type: 'node'; id: string }
  | { type: 'edge'; id: string }

export type NetworkDefinitionChange =
  | { type: 'add-node'; node: NetworkNode }
  | { type: 'remove-node'; nodeId: string }
  | { type: 'move-node'; nodeId: string; position: NetworkNode['position'] }
  | { type: 'rename-node'; nodeId: string; label: string }
  | { type: 'describe-node'; nodeId: string; description: string }
  | { type: 'set-binding'; nodeId: string; binding: NetworkAgentBindingSelector }
  | { type: 'add-edge'; edge: NetworkEdge }
  | { type: 'remove-edge'; edgeId: string }
  | { type: 'set-root'; nodeId: string }
  | { type: 'settings'; settings: NetworkDefinition['settings'] }
