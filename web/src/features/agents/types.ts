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
  settings?: Record<string, unknown>
  created_at?: string
  updated_at?: string
}

export interface CreateAgentRequest {
  project_id: string
  name: string
  provider?: string
  model: string
  system_prompt?: string
  description?: string
  temperature?: number
  max_output_tokens?: number
  provider_credential_id?: string
  settings?: Record<string, unknown>
}
