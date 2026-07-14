export type NetworkEnvironment = 'staging' | 'production'

export interface NetworkNode {
  id: string
  agent_id: string
  label: string
  position: { x: number; y: number }
}

export interface NetworkEdge {
  id: string
  source_node_id: string
  target_node_id: string
}

export interface NetworkDefinition {
  schema_version: 1
  root_node_id: string
  nodes: NetworkNode[]
  edges: NetworkEdge[]
  settings: {
    session_mode: 'stateful' | 'stateless'
    max_depth: number
    max_invocations: number
    timeout_seconds: number
  }
}

export interface NetworkResource {
  id: string
  project_id: string
  name: string
  description: string
  draft_definition: NetworkDefinition | Record<string, never>
  draft_revision: number
  staging_version_id: string | null
  production_version_id: string | null
  created_at: string
  updated_at: string
}

export interface NetworkVersion {
  id: string
  kind: 'staging' | 'release'
  version: string
  composition_hash: string
  definition: NetworkDefinition
  resolved_bindings: Record<string, {
    node_id: string
    agent_id: string
    release_id: string
    release_version: string
    release_status: string
  }>
  created_at: string
}

export interface NetworkSessionResource {
  id: string
  network_id?: string
  network_version_id: string
  environment: NetworkEnvironment
  title: string
  status: 'active' | 'closed'
  last_message_at?: string | null
  created_at: string
}

export interface NetworkRuntimeEvent {
  protocol_version: 1
  event_id?: string
  sequence?: number
  execution_id: string
  network_session_id?: string
  invocation_id?: string | null
  parent_invocation_id?: string | null
  node_id?: string | null
  agent_id?: string | null
  depth?: number | null
  data: Record<string, unknown>
  created_at?: string
}

export interface PromotionPreview {
  environment: NetworkEnvironment
  ready: boolean
  bindings: Record<string, Record<string, unknown>>
  missing_agent_ids: string[]
}
