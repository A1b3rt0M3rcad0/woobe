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
  network_id: string
  project_id: string
  kind: 'staging' | 'release'
  version: string
  composition_hash: string
  definition: NetworkDefinition
  resolved_bindings: Record<string, ResolvedNetworkBinding>
  source_draft_revision?: number | null
  source_staging_version_id?: string | null
  entry_agent_id?: string | null
  entry_agent_release_id?: string | null
  entry_agent_release_version?: string | null
  public_output_contract?: NetworkOutputContract | null
  public_output_contract_hash?: string | null
  agent_release_manifest?: NetworkAgentReleaseManifestItem[] | null
  agent_release_manifest_hash?: string | null
  runtime_settings_hash?: string | null
  release_fingerprint?: string | null
  change_kind?: ReleaseChangeKind | null
  created_at?: string | null
}

export interface NetworkProductionActivation {
  id: string
  network_id: string
  project_id: string
  version_id: string
  previous_version_id?: string | null
  activation_kind: 'publish' | 'reactivate' | 'rollback'
  change_description: string
  created_by?: string | null
  created_at: string
}

export interface NetworkPromotionAction {
  id: string
  kind: string
  severity: 'info' | 'warning' | 'critical'
  title: string
  description: string
  requires_confirmation: boolean
  details: Record<string, unknown>
}

export interface PromotionPreview {
  environment: NetworkPromotionEnvironment
  ready: boolean
  bindings: Record<string, ResolvedNetworkBinding>
  missing_agent_ids: string[]
  network_revision?: number
  network_version_id?: string | null
  actions?: NetworkPromotionAction[]
}

export interface PromoteNetworkInput {
  environment: NetworkPromotionEnvironment
  expected_revision?: number | null
  expected_network_version_id?: string | null
  approved_action_ids?: string[]
}

export interface ActivateNetworkProductionInput {
  source_version_id: string
  expected_current_production_version_id?: string | null
  change_description: string
}

export interface ActivateNetworkProductionResult {
  version: NetworkVersion
  activation: NetworkProductionActivation
}

export interface NetworkSessionResource {
  id: string
  network_id: string
  project_id: string
  environment: NetworkEnvironment
  network_version_id: string | null
  title: string
  external_session_id: string | null
  status: string
  created_at: string
  last_message_at?: string | null
  message_count?: number
  trace_count?: number
}

export interface NetworkMessageResource {
  id: string
  network_session_id: string
  role: 'user' | 'assistant' | 'system' | 'tool'
  content: string
  created_at: string
  execution_id?: string | null
  data?: Record<string, unknown>
}

export interface NetworkExecutionSnapshot {
  execution_id: string
  network_id: string
  network_session_id: string
  environment: NetworkEnvironment
  draft_revision: number | null
  network_version_id: string | null
  version_label: string | null
  composition_hash: string
  definition: NetworkDefinition
  resolved_bindings: Record<string, ResolvedNetworkBinding>
  snapshot_source: 'draft' | 'network_version'
  agent_contexts: Array<Record<string, unknown>>
}
