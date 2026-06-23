export type ToolProtocol = 'http' | 'mcp' | 'http_mcp' | 'api' | 'webhook' | string

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
  protocol?: 'http'
  url: string
  method: string
  headers: HttpHeader[]
  body?: string
  variables?: Record<string, string>
  auth?: HttpAuth
  timeout_ms?: number
}

export interface McpServerConfig {
  transport: 'streamable_http' | 'sse' | 'stdio'
  url?: string
  command?: string
  args?: string[]
  headers?: HttpHeader[]
  env_secret_refs?: Record<string, string>
  name?: string
}

export interface DiscoveredMcpTool {
  name: string
  title?: string | null
  description?: string | null
  input_schema?: Record<string, unknown> | null
}

export interface McpToolConfig {
  protocol?: 'mcp'
  mode?: 'tool' | 'server'
  exposure?: 'single' | 'all_discovered'
  server: McpServerConfig
  tool_name?: string
  server_headers?: HttpHeader[]
  input_schema_source?: 'discovered' | 'manual'
  discovered_input_schema?: Record<string, unknown>
  discovered_tools?: DiscoveredMcpTool[]
  discovery_cache_ttl_seconds?: number
  timeout_ms?: number
}

export type ToolConfig = HttpToolConfig | McpToolConfig | Record<string, unknown>

export interface Tool {
  id: string
  project_id: string
  agent_id?: string | null
  name: string
  description?: string
  type: ToolProtocol
  config?: ToolConfig
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
  agent_id?: string | null
  name: string
  description?: string
  type?: ToolProtocol
  config?: ToolConfig
  input_schema?: Record<string, unknown>
  output_schema?: Record<string, unknown>
  risk_level?: string
  timeout_ms?: number
}

export interface TestToolRequest {
  type?: ToolProtocol
  config: ToolConfig
  input_data?: Record<string, unknown>
  timeout_ms?: number
}

export interface TestToolResponse {
  success: boolean
  status_code?: number
  headers?: Record<string, string>
  body?: string
  duration_ms?: number
  error?: string
}

export interface DiscoverMcpToolsRequest {
  server_url: string
  headers?: Record<string, string>
  timeout_ms?: number
}

export interface DiscoverMcpToolsResponse {
  tools: DiscoveredMcpTool[]
  initialized: boolean
  error?: string | null
}

export interface UpdateToolStatusRequest {
  status: 'active' | 'inactive'
}

export interface Secret {
  id: string
  project_id: string
  name: string
  type: string
  status?: string
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
