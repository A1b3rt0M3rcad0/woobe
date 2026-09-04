export type RuntimeEnvironment = 'draft' | 'staging' | 'production'

export interface RuntimeEnvironmentState {
  enabled: boolean
  updated_by?: string | null
  updated_at?: string | null
}

export type RuntimeEnvironmentStates = Record<RuntimeEnvironment, RuntimeEnvironmentState>

/** Backend-owned presentation contract for one registered Context Manager. */
export interface ContextAssemblerDescriptor {
  name: string
  version: string
  display_name: string
  description: string
  behavior: string
  is_default: boolean
}

export interface Agent {
  id: string
  project_id: string
  name: string
  provider: string
  model: string
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
  description?: string
  system_prompt?: string
  provider: string
  model: string
  temperature?: number
  max_output_tokens?: number
  session_mode?: string
  provider_model_id?: string | null
  provider_credential_id?: string | null
  fallback_provider?: string | null
  fallback_model?: string | null
  fallback_provider_model_id?: string | null
  fallback_credential_id?: string | null
  settings?: Record<string, unknown>
}

export type UpdateAgentRequest = Partial<Omit<CreateAgentRequest, 'project_id'>>

export interface AgentRelease {
  id: string
  project_id: string
  agent_id: string
  version: string
  status: string
  snapshot_kind?: string
  source_release_id?: string | null
  name?: string
  description?: string
  system_prompt?: string
  session_mode?: string
  provider?: string
  model?: string
  provider_model_id?: string | null
  provider_credential_id?: string | null
  fallback_provider?: string | null
  fallback_model?: string | null
  fallback_provider_model_id?: string | null
  fallback_credential_id?: string | null
  base_url?: string | null
  temperature?: number
  max_output_tokens?: number
  output_schema?: unknown
  response_format?: Record<string, unknown>
  runtime_config?: Record<string, unknown> | null
  knowledge_version_id?: string | null
  collection_ids?: string[]
  prompt_version_id?: string | null
  model_config_version_id?: string | null
  contract_version_id?: string | null
  release_notes?: string | null
  change_description?: string | null
  created_at?: string
  promoted_at?: string | null
}

export interface CreateReleaseRequest {
  project_id: string
  agent_id: string
  version: string
  [key: string]: unknown
}

export interface AgentReleaseActivation {
  id: string
  project_id: string
  agent_id: string
  release_id: string
  previous_release_id?: string | null
  action: 'deploy' | 'rollback' | 'reactivate' | string
  created_at?: string
}

export interface AgentReleaseTest {
  id: string
  project_id: string
  agent_id: string
  release_id: string
  status?: string
  [key: string]: unknown
}

export interface CreateReleaseTestRequest {
  project_id: string
  agent_id: string
  release_id: string
  [key: string]: unknown
}

export interface AgentPrompt {
  id: string
  agent_id: string
  version?: string
  [key: string]: unknown
}

export interface CreatePromptRequest {
  [key: string]: unknown
}

export interface AgentModelConfig {
  id: string
  agent_id: string
  [key: string]: unknown
}

export interface CreateModelConfigRequest {
  [key: string]: unknown
}

export interface AgentContract {
  id: string
  agent_id: string
  [key: string]: unknown
}

export interface CreateContractRequest {
  [key: string]: unknown
}

export type UpdateContractRequest = Partial<CreateContractRequest>

export interface KnowledgeVersion {
  id: string
  agent_id: string
  version?: string
  [key: string]: unknown
}

export interface CreateKnowledgeVersionRequest {
  [key: string]: unknown
}
