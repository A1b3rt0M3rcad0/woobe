export type ToolProtocol = 'http' | 'mcp' | 'http_mcp' | 'api' | 'webhook' | string
export type ToolChildPermissionMode = 'allow' | 'deny' | 'review'
export type McpToolPermissionMode = ToolChildPermissionMode

export interface ToolContextBindingSource {
  kind: 'context' | 'project_environment'
  field: string
}

export interface ToolInputBinding {
  source: ToolContextBindingSource
}

export type ToolInputBindings = Record<string, ToolInputBinding>

export interface HttpHeader {
  key: string
  value?: string
  sensitive?: boolean
  mode?: 'set' | 'remove'
}

export interface HttpAuth {
  type: 'none' | 'api_key' | 'bearer' | 'basic'
  credentials?: string[]
}

export interface ToolChildPermission {
  mode: ToolChildPermissionMode
  risk_level?: string | null
}

export type McpToolPermission = ToolChildPermission

export interface HttpRouteConfig {
  id: string
  operation_id?: string
  name: string
  description: string
  method: string
  path: string
  headers?: HttpHeader[]
  body?: string | Record<string, unknown> | unknown[]
  variables?: Record<string, string>
  bindings?: ToolInputBindings
  input_schema?: Record<string, unknown>
  output_schema?: Record<string, unknown>
  risk_level?: string
  status?: 'active' | 'inactive' | string
  default_permission?: ToolChildPermissionMode
  permission?: ToolChildPermission
  timeout_ms?: number
  contract_version?: number
  contract_hash?: string
}

export interface HttpToolConfig {
  protocol?: 'http'
  mode?: 'single' | 'group'
  schema_version?: number
  base_url?: string
  routes?: HttpRouteConfig[]
  url?: string
  method?: string
  headers: HttpHeader[]
  body?: string | Record<string, unknown> | unknown[]
  variables?: Record<string, string>
  bindings?: ToolInputBindings
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

export interface McpProtectedResourceMetadata {
  resource?: string | null
  authorization_servers?: string[]
  scopes_supported?: string[]
  bearer_methods_supported?: string[]
  authorization_hints?: Record<string, unknown>
}

export interface McpOAuthDiscovery {
  status?: 'valid' | 'invalid_metadata' | 'provider_managed' | 'not_advertised' | string
  advertised?: boolean
  provider?: string | null
  resource_metadata_url?: string | null
  authorization_server_issuer?: string | null
  authorization_endpoint?: string | null
  token_endpoint?: string | null
  registration_endpoint?: string | null
  protected_resource_metadata?: McpProtectedResourceMetadata | null
  error?: string | null
  checked_urls?: string[]
  checked_at?: string | null
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
  authorization_endpoint?: string | null
  token_endpoint?: string | null
  token_endpoint_auth_method?: string | null
  oauth_metadata_status?: string | null
  oauth_metadata_error?: string | null
  managed_provider?: string | null
  resource_metadata_url?: string | null
  checked_at?: string | null
  www_authenticate?: string | null
}

export interface McpReadiness {
  state: 'ready' | 'needs_connection' | 'provider_not_supported' | 'provider_managed' | 'oauth_metadata_invalid' | 'needs_permission' | 'no_tools' | 'token_rejected' | 'needs_credentials' | 'scope_denied' | 'invalid_endpoint' | 'unavailable' | 'discovery_failed' | 'not_ready' | string
  label: string
  message: string
  action: 'connect' | 'device_code' | 'provider_credentials' | 'review_provider' | 'configure_credentials' | 'edit_endpoint' | 'configure_permissions' | 'refresh' | 'disconnect' | string
  can_use_tools: boolean
  oauth_connected: boolean
  mcp_ready: boolean
  discovered_count: number
  exposed_count: number
  supports_device_code: boolean
  needs_provider_client: boolean
}

export interface DiscoveredMcpTool {
  name: string
  title?: string | null
  description?: string | null
  input_schema?: Record<string, unknown> | null
  bindings?: ToolInputBindings
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
  bindings?: ToolInputBindings
  discovery_cache_ttl_seconds?: number
  timeout_ms?: number
  oauth?: Record<string, unknown>
  oauth_discovery_error?: string
  mcp_status?: string
  mcp_resource_metadata?: McpProtectedResourceMetadata
  mcp_oauth_discovery?: McpOAuthDiscovery
  mcp_discovery?: McpDiscoveryDiagnostic
  mcp_readiness?: McpReadiness
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

export interface McpOAuthDeviceStartRequest {
  tool_id: string
  scopes?: string[]
  client_id?: string
  client_secret?: string
  timeout_ms?: number
}

export interface McpOAuthDeviceStartResponse {
  status: string
  device_code_expires_at?: string | null
  interval_seconds: number
  user_code?: string | null
  verification_uri?: string | null
  verification_uri_complete?: string | null
  message?: string | null
}

export interface McpOAuthDevicePollRequest {
  tool_id: string
  timeout_ms?: number
}

export interface McpOAuthDevicePollResponse {
  status: string
  connected: boolean
  message?: string | null
  interval_seconds?: number | null
  discovered_count?: number | null
  error?: string | null
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
  status: 'active' | 'inactive' | 'deprecated'
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
  data?: Record<string, unknown>
}
