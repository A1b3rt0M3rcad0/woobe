export type NetworkEnvironment = 'draft' | 'staging' | 'production'
export type NetworkPromotionEnvironment = Exclude<NetworkEnvironment, 'draft'>

export interface NetworkNode {
  id: string
  agent_id: string
  label: string
  capability_description: string
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
  network_version_id: string | null
  environment: NetworkEnvironment
  title: string
  status: 'active' | 'closed'
  last_message_at?: string | null
  message_count: number
  trace_count: number
  created_at: string
}

export interface NetworkExecutionHistoryResource {
  id: string
  status: 'queued' | 'running' | 'completed' | 'failed' | 'cancelled' | 'timed_out' | 'uncertain'
  draft_revision: number | null
  network_version_id: string | null
  root_trace_id: string | null
  failure_code: string | null
  failure: {
    code?: string
    stage?: string
    message?: string
    retryable?: boolean
    cause_invocation_id?: string | null
    cause_node_id?: string | null
    cause_agent_id?: string | null
  } | null
  started_at: string | null
  completed_at: string | null
  events: Array<{
    id: string
    sequence: number
    event_type: string
    invocation_id: string | null
    parent_invocation_id: string | null
    node_id: string | null
    agent_id: string | null
    depth: number | null
    data: Record<string, unknown>
    created_at: string
  }>
}

export interface NetworkMessageResource {
  id: string
  network_execution_id: string | null
  role: 'user' | 'assistant' | 'system'
  content: string
  data: Record<string, unknown> | null
  created_at: string
  execution: NetworkExecutionHistoryResource | null
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
  environment: NetworkPromotionEnvironment
  ready: boolean
  bindings: Record<string, Record<string, unknown>>
  missing_agent_ids: string[]
}
