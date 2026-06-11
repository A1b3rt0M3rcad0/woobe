export interface HttpHeader {
  key: string
  value: string
  sensitive?: boolean
}

export interface HttpAuth {
  type: 'none' | 'api_key' | 'bearer' | 'basic'
  credentials?: string[]
}

export interface HttpToolConfig {
  url: string
  method: string
  headers: HttpHeader[]
  body?: string
  variables?: Record<string, string>
  auth?: HttpAuth
  timeout_ms?: number
}

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

export interface TestToolRequest {
  config: Record<string, unknown>
  input_data?: Record<string, unknown>
}

export interface TestToolResponse {
  success: boolean
  status_code?: number
  headers?: Record<string, string>
  body?: string
  duration_ms?: number
  error?: string
}

export interface UpdateToolStatusRequest {
  status: 'active' | 'inactive'
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
