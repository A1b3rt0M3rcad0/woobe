export type ToolProtocol = 'http' | 'mcp' | 'http_mcp' | 'api' | 'webhook' | string
export type McpToolPermissionMode = 'allow' | 'deny' | 'review'

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
  transport: 'streamable_http'
  url?: string
  command?: string
  args?: string[]
  headers?: HttpHeader[]
  env_secret_refs?: Record<string, string>
  name?: string
}

export interface McpToolPermission {
  mode: McpToolPermissionMode
  risk_level?: string | null
}

export interface McpProtectedResourceMetadata {
  resource?: string | null
  authorization_servers?: string[]
  scopes_supported?: string[]
  bearer_methods_supported?: string[]
  authorization_hints?: Record<string, unknown>
}

export interface McpDiscoveryDiagnostic {
  status?: string | null
  phase?: string | null
  http_status?: number | null
  initialized?: boolean | null
  error?: string | null
  server_url?: string | null
  oauth_resource?: string | null
  protected_resource?: string | null
  authorization_hints?: Record<string, unknown>
  authorization_server_issuer?: string | null
  token_endpoint_auth_method?: string | null
  checked_at?: string | null
  www_authenticate?: string | null
}

export interface DiscoveredMcpTool {
  name: string
  title?: string | null
  description?: string | null
  input_schema?: Record<string, unknown> | null
  permission?: McpToolPermission
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
  oauth?: Record<string, unknown>
  oauth_discovery_error?: string
  mcp_status?: string
  mcp_resource_metadata?: McpProtectedResourceMetadata
  mcp_discovery?: McpDiscoveryDiagnostic
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
  output?: Record<string, unknown>
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

export interface McpOAuthStartRequest {
  tool_id: string
  redirect_uri: string
  scopes?: string[]
  authorization_endpoint?: string
  token_endpoint?: string
  registration_endpoint?: string
  authorization_server_issuer?: string
  client_id?: string
  client_secret?: string
  timeout_ms?: number
}

export interface McpOAuthStartResponse {
  authorization_url: string
  state: string
  status: string
}

export interface McpOAuthCompleteRequest {
  tool_id: string
  code: string
  state: string
  timeout_ms?: number
}

export interface McpOAuthStatusRequest {
  tool_id: string
}

export interface McpOAuthStatusResponse {
  status: string
  connected: boolean
  authorization_server_issuer?: string | null
  scopes: string[]
  expires_at?: string | null
}

export interface RefreshMcpToolsRequest {
  tool_id: string
  timeout_ms?: number
}

export interface RefreshMcpToolsResponse {
  tool_id: string
  discovered_count: number
  initialized: boolean
  status: string
  error?: string | null
  http_status?: number | null
  phase?: string | null
}

export interface McpToolPermissionUpdate {
  remote_tool_name: string
  mode: McpToolPermissionMode
  risk_level?: string
}

export interface UpdateMcpToolPermissionsRequest {
  tool_id: string
  permissions: McpToolPermissionUpdate[]
}

export interface BulkUpdateMcpToolPermissionsRequest {
  tool_id: string
  mode: McpToolPermissionMode
  risk_level?: string
}

export interface McpToolPermissionsResponse {
  tool_id: string
  permissions: Array<{ name: string; mode: McpToolPermissionMode; risk_level?: string | null }>
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
