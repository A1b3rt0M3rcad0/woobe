export type NetworkEnvironment = 'draft' | 'staging' | 'production'
export type NetworkPromotionEnvironment = Exclude<NetworkEnvironment, 'draft'>
export type NetworkAgentBindingSource = 'draft' | 'staging' | 'release'
export type ReleaseChangeKind = 'compatibility' | 'feature' | 'change'

export type NetworkAgentBindingSelector =
  | { source: 'draft'; release_id: null }
  | { source: 'staging' | 'release'; release_id: string }

export interface NetworkNode {
  id: string
  agent_id: string
  label: string
  capability_description: string
  position: { x: number; y: number }
  binding: NetworkAgentBindingSelector
}

export interface NetworkEdge {
  id: string
  source_node_id: string
  target_node_id: string
}

export interface NetworkDefinition {
  schema_version: 2
  root_node_id: string
  nodes: NetworkNode[]
  edges: NetworkEdge[]
  settings: {
    session_mode: 'stateful' | 'stateless'
    max_depth: number
    max_invocations: number
    timeout_seconds: number
    tool_result_max_chars?: number
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
  agent_count?: number
  created_at: string
  updated_at: string
}

export interface ResolvedNetworkBinding {
  node_id: string
  agent_id: string
  binding_source?: NetworkAgentBindingSource
  release_id?: string | null
  draft_release_id?: string | null
  release_version?: string | null
  release_status?: string | null
  snapshot_kind?: 'staging' | 'release'
  snapshot_hash?: string
  snapshot_override?: Record<string, unknown> | null
}

export interface NetworkOutputContract {
  enabled: boolean
  type: 'json'
  strict: boolean
  schema: Record<string, unknown>
}

export interface NetworkAgentReleaseManifestItem {
  node_id: string
  role: 'entry' | 'specialist'
  agent_id: string
  release_id: string
  release_version: string
  snapshot_hash: string
  output_contract_hash: string
}

export interface NetworkVersion {
  id: string
  kind: 'staging' | 'release'
  version: string
  composition_hash: string
  definition: NetworkDefinition
  resolved_bindings: Record<string, ResolvedNetworkBinding>
  created_at: string
  created_by?: string | null
  source_version_id?: string | null
  activation_kind?: 'publish' | 'reactivate' | 'rollback' | null
  change_description?: string | null
  source_draft_revision?: number | null
  source_staging_version_id?: string | null
  entry_agent_id?: string | null
  entry_agent_release_id?: string | null
  entry_agent_release_version?: string | null
  public_output_contract?: NetworkOutputContract | null
  public_output_contract_hash?: string | null
  effective_external_context_contract?: Record<string, unknown> | null
  agent_release_manifest?: NetworkAgentReleaseManifestItem[] | null
  agent_release_manifest_hash?: string | null
  runtime_settings_hash?: string | null
  release_fingerprint?: string | null
  change_kind?: ReleaseChangeKind | null
}

export interface NetworkProductionActivation {
  id: string
  network_id: string
  version_id: string
  previous_version_id: string | null
  activation_kind: 'publish' | 'reactivate' | 'rollback'
  change_description: string
  created_by: string | null
  created_at: string
}

export interface ActivateNetworkProductionResult {
  version: NetworkVersion
  activation: NetworkProductionActivation
}

export interface NetworkSessionResource {
  id: string
  network_id?: string
  network_version_id: string | null
  environment: NetworkEnvironment
  title: string
  status: 'active' | 'closed'
  last_message_at?: string | null
  external_context_session_values?: Record<string, unknown> | null
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
  protocol_version: 2
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

export interface NetworkExecutionSnapshotAgentContext {
  node_id: string
  agent_id: string
  agent_session_id: string | null
  source?: NetworkAgentBindingSource
  version?: string
  provider?: string
  model?: string
}

export interface NetworkExecutionSnapshot {
  execution_id: string
  network_id: string
  network_session_id: string
  environment: NetworkEnvironment
  draft_revision: number | null
  network_version_id: string | null
  version_label: string | null
  composition_hash: string | null
  definition: NetworkDefinition
  resolved_bindings: Record<string, ResolvedNetworkBinding>
  snapshot_source: 'execution' | 'network_version'
  agent_contexts: NetworkExecutionSnapshotAgentContext[]
  parsed_output?: Record<string, unknown> | null
  output_parse_error?: string | null
}

export interface PromotionPreviewNode {
  node_id: string
  agent_id: string
  agent_name: string
  selected_source: NetworkAgentBindingSource
  selected_ref: string | null
  selected_version: string | null
  result_source: Exclude<NetworkAgentBindingSource, 'draft'>
  action_required: 'promote_draft_to_staging' | 'publish_staging_to_release' | null
  action_id: string | null
  blocking_reason: string | null
  reuse_reason?: string | null
  snapshot_hash?: string | null
}

export interface PromotionPreviewAction {
  id: string
  agent_id: string
  agent_name: string
  action: 'promote_draft_to_staging' | 'publish_staging_to_release'
  source_release_id: string
  source_version: string
}

export interface NetworkStagingPreview {
  next_version: string
  reused_agent_count: number
  promotion_count: number
}

export interface NetworkReleasePreview {
  change_kind: ReleaseChangeKind
  next_version: string
  entry_agent_id: string | null
  entry_agent_release_id: string | null
  entry_agent_release_version: string | null
  public_output_contract: NetworkOutputContract | null
  public_output_contract_hash: string
  effective_external_context_contract?: Record<string, unknown> | null
  effective_external_context_contract_hash?: string | null
  agent_release_manifest: NetworkAgentReleaseManifestItem[]
  internal_warnings: string[]
  reused_agent_count: number
  promotion_count: number
}

export interface PromotionPreview {
  environment: NetworkPromotionEnvironment
  network_revision: number
  network_version_id: string | null
  ready: boolean
  nodes: PromotionPreviewNode[]
  actions: PromotionPreviewAction[]
  missing_agent_ids: string[]
  reused_agent_count?: number
  staging_preview?: NetworkStagingPreview
  release_preview?: NetworkReleasePreview
}

export interface PromoteNetworkInput {
  environment: NetworkPromotionEnvironment
  expected_revision?: number | null
  expected_network_version_id?: string | null
  approved_action_ids?: string[]
}

export interface ActivateNetworkProductionInput {
  source_version_id: string
  expected_current_production_version_id: string | null
  change_description: string
}
