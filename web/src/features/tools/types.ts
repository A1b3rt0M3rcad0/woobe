export interface Tool {
  id: string
  project_id: string
  agent_id: string
  name: string
  description?: string
  type: string
  config?: Record<string, unknown>
  input_schema?: Record<string, unknown>
  output_schema?: Record<string, unknown>
  risk_level: string
  timeout_ms?: number
  status: string
  created_at?: string
  updated_at?: string
}

export interface CreateToolRequest {
  project_id: string
  agent_id: string
  name: string
  description?: string
  type?: string
  config?: Record<string, unknown>
  input_schema?: Record<string, unknown>
  output_schema?: Record<string, unknown>
  risk_level?: string
  timeout_ms?: number
}

export interface Secret {
  id: string
  project_id: string
  name: string
  type: string
  data?: Record<string, unknown>
  created_at?: string
  updated_at?: string
}

export interface CreateSecretRequest {
  project_id: string
  name: string
  type?: string
  value: string
}
