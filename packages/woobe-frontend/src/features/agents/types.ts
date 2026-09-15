export interface BehaviorSpecification {
  schema_version: 1
  objective: string
  responsibilities: string[]
  allowed_behaviors: string[]
  disallowed_behaviors: string[]
  operating_instructions: string
  response_guidelines: string
  additional_instructions: string
}

export type RuntimeEnvironment = 'draft' | 'staging' | 'production'

export interface RuntimeEnvironmentState {
  enabled: boolean
  updated_by?: string | null
  updated_at?: string | null
}

export type RuntimeEnvironmentStates = Record<RuntimeEnvironment, RuntimeEnvironmentState>

/** Backend-owned presentation contract for one registered Context Manager. */
export interface ContextAssemblerDescriptor {
  supports_skills?: boolean
  name: string
  version: string
  strategy_name: string
  strategy_version: string
  display_name: string
  description: string
  behavior: string
  recommended_for: string[]
  capabilities: string[]
  limitations: string[]
  configuration: string
  is_default: boolean
  is_system_default_alias: boolean
}

/** Backend-owned presentation contract for one selectable Execution Strategy. */
export interface ExecutionStrategyDescriptor {
  name: string
  display_name: string
  description: string
  behavior: string
  recommended_for: string[]
  capabilities: string[]
  limitations: string[]
  is_default: boolean
}

export interface Agent {
  id: string
  project_id: string
  name: string
  provider: string
  model: string
  behavior_spec?: BehaviorSpecification | null
  system_prompt?: string
  description?: string
  temperature?: number
  max_output_tokens?: number
  session_mode?: string
  status: string
  runtime_environments?: RuntimeEnvironmentStates
  provider_model_id?: string
  fallback_provider_model_id?: string
  provider_credential_id?: string
  fallback_provider?: string
  fallback_model?: string
  fallback_credential_id?: string
  settings?: Record<string, unknown>
  created_at?: string
  updated_at?: string
}

export interface CreateAgentRequest {
  project_id: string
  name: string
  provider?: string
  model?: string
  provider_model_id?: string
  fallback_provider_model_id?: string
  behavior_spec?: BehaviorSpecification | null
  system_prompt?: string
  description?: string
  temperature?: number
  max_output_tokens?: number
  provider_credential_id?: string
  fallback_provider?: string
  fallback_model?: string
  fallback_credential_id?: string
  session_mode: string
  settings?: Record<string, unknown>
}

export interface UpdateAgentRequest {
  name?: string
  description?: string
  behavior_spec?: BehaviorSpecification | null
  system_prompt?: string
  provider?: string
  model?: string
  provider_model_id?: string
  fallback_provider_model_id?: string
  provider_credential_id?: string
  fallback_provider?: string
  fallback_model?: string
  fallback_credential_id?: string
  temperature?: number
  max_output_tokens?: number
  session_mode?: string
  status?: string
  settings?: Record<string, unknown>
}


// ── Agent Prompt ───────────────────────────────────────────────

export interface AgentPrompt {
  id: string
  project_id: string
  agent_id: string
  version: string
  name: string
  content: string
  content_hash?: string
  status: 'draft' | 'released' | 'archived'
  created_by?: string
  created_at?: string
  updated_at?: string
}

export interface CreatePromptRequest {
  project_id: string
  agent_id: string
  version: string
  name?: string
  content?: string
}


// ── Agent Contract ──────────────────────────────────────────

export interface AgentContract {
  id: string
  project_id: string
  agent_id: string
  version: string
  name: string
  input_schema?: Record<string, unknown>
  output_schema?: Record<string, unknown>
  validation_mode: 'strict' | 'loose'
  repair_attempts: number
  additional_instructions?: string
  schema_hash?: string
  status: 'draft' | 'released' | 'archived'
  created_at?: string
  updated_at?: string
}

export interface CreateContractRequest {
  project_id: string
  agent_id: string
  version: string
  name?: string
  input_schema?: Record<string, unknown>
  output_schema?: Record<string, unknown>
  validation_mode?: 'strict' | 'loose'
  repair_attempts?: number
  additional_instructions?: string
}

export interface UpdateContractRequest {
  name?: string
  input_schema?: Record<string, unknown>
  output_schema?: Record<string, unknown>
  validation_mode?: 'strict' | 'loose'
  repair_attempts?: number
  additional_instructions?: string
  status?: 'draft' | 'released' | 'archived'
}


// ── Agent Model Config ─────────────────────────────────────────

export interface AgentModelConfig {
  id: string
  project_id: string
  agent_id: string
  version: string
  provider: string
  provider_credential_id?: string
  model: string
  base_url?: string
  temperature?: number
  max_output_tokens?: number
  session_mode?: string
  settings?: Record<string, unknown>
  status: 'draft' | 'released' | 'archived'
  created_at?: string
  updated_at?: string
}

export interface CreateModelConfigRequest {
  project_id: string
  agent_id: string
  version: string
  provider?: string
  provider_credential_id?: string
  model: string
  base_url?: string
  temperature?: number
  max_output_tokens?: number
  session_mode?: string
  settings?: Record<string, unknown>
}


// ── Knowledge Version ──────────────────────────────────────────

export interface KnowledgeVersion {
  id: string
  project_id: string
  agent_id: string
  version: string
  collection_ids: string[]
  document_ids?: string[]
  snapshot_metadata?: Record<string, unknown>
  status: 'draft' | 'released' | 'archived'
  created_at?: string
  updated_at?: string
}

export interface CreateKnowledgeVersionRequest {
  project_id: string
  agent_id: string
  version: string
  collection_ids?: string[]
  document_ids?: string[]
  snapshot_metadata?: Record<string, unknown>
}


// ── Agent Release ──────────────────────────────────────────────

export type ReleaseStatus = 'draft' | 'staging' | 'released' | 'production' | 'archived' | 'rolled_back'
export type ReleaseSnapshotKind = 'draft' | 'staging' | 'release'

export interface AgentRelease {
  id: string
  project_id: string
  agent_id: string
  version: string
  status: ReleaseStatus
  snapshot_kind?: ReleaseSnapshotKind
  prompt_version_id?: string
  contract_version_id?: string
  knowledge_version_id?: string
  model_config_version_id?: string
  provider_model_id?: string
  fallback_provider_model_id?: string
  // Snapshot fields — complete agent config
  name?: string
  description?: string
  behavior_spec?: BehaviorSpecification | null
  system_prompt?: string
  response_format?: Record<string, unknown>
  output_schema?: Record<string, unknown>
  provider?: string
  model?: string
  provider_credential_id?: string
  fallback_provider?: string
  fallback_model?: string
  fallback_credential_id?: string
  base_url?: string
  temperature?: number
  max_output_tokens?: number
  session_mode?: string
  agent_status?: string
  collection_ids?: string[]
  runtime_config?: Record<string, unknown>
  // Meta
  release_notes?: string
  risk_score?: number
  created_by?: string
  promoted_by?: string
  promoted_at?: string
  created_at?: string
  updated_at?: string
}

export interface AgentReleaseActivation {
  id: string
  project_id: string
  agent_id: string
  release_id: string
  previous_release_id?: string | null
  action: 'deploy' | 'reactivate' | 'rollback'
  change_description?: string | null
  created_by?: string | null
  created_at?: string
}

export interface CreateReleaseRequest {
  project_id: string
  agent_id: string
  version: string
  prompt_version_id?: string
  contract_version_id?: string
  knowledge_version_id?: string
  model_config_version_id?: string
  provider_model_id?: string
  fallback_provider_model_id?: string
  // Snapshot fields — complete agent config
  name?: string
  description?: string
  behavior_spec?: BehaviorSpecification | null
  system_prompt?: string
  response_format?: Record<string, unknown>
  output_schema?: Record<string, unknown>
  provider?: string
  model?: string
  provider_credential_id?: string
  fallback_provider?: string
  fallback_model?: string
  fallback_credential_id?: string
  base_url?: string
  temperature?: number
  max_output_tokens?: number
  session_mode?: string
  agent_status?: string
  collection_ids?: string[]
  runtime_config?: Record<string, unknown>
  // Meta
  release_notes?: string
  risk_score?: number
}


// ── Agent Release Test ─────────────────────────────────────────

export type ReleaseTestStatus = 'pending' | 'passed' | 'failed'

export interface AgentReleaseTest {
  id: string
  project_id: string
  agent_id: string
  release_id?: string
  contract_version_id?: string
  input_payload?: Record<string, unknown>
  expected_output?: Record<string, unknown>
  actual_output?: Record<string, unknown>
  status: ReleaseTestStatus
  validation_errors?: unknown[]
  latency_ms?: number
  created_at?: string
  updated_at?: string
}

export interface CreateReleaseTestRequest {
  project_id: string
  agent_id: string
  release_id?: string
  contract_version_id?: string
  input_payload?: Record<string, unknown>
  expected_output?: Record<string, unknown>
}
