import { get, post, patch, del } from '@/lib/api/client'

import type {
  Tool,
  CreateToolRequest,
  Secret,
  CreateSecretRequest,
  TestToolRequest,
  TestToolResponse,
  UpdateToolStatusRequest,
  DiscoverMcpToolsRequest,
  DiscoverMcpToolsResponse,
  McpOAuthCompleteRequest,
  McpOAuthDevicePollRequest,
  McpOAuthDevicePollResponse,
  McpOAuthDeviceStartRequest,
  McpOAuthDeviceStartResponse,
  McpOAuthStartRequest,
  McpOAuthStartResponse,
  McpOAuthStatusRequest,
  McpOAuthStatusResponse,
  UpdateMcpToolPermissionsRequest,
  BulkUpdateMcpToolPermissionsRequest,
  McpToolPermissionsResponse,
  RefreshMcpToolsRequest,
  RefreshMcpToolsResponse,
} from './types'

export interface ToolUsageImpact {
  tool_id: string
  status: string
  in_use: boolean
  can_delete: boolean
  can_retire: boolean
  draft_agents: number
  staging_agents: number
  production_agents: number
  historical_releases: number
  total_references: number
}

export async function getTools(projectId?: string): Promise<Tool[]> {
  return get<Tool[]>('/tools/tools', { params: { project_id: projectId } })
}

export async function getAgentTools(agentId: string): Promise<Tool[]> {
  return get<Tool[]>(`/tools/agents/${agentId}/tools`)
}

export async function createTool(data: CreateToolRequest): Promise<Tool> {
  return post<Tool>('/tools/tools', data)
}

export async function updateTool(toolId: string, data: Partial<CreateToolRequest>): Promise<Tool> {
  return patch<Tool>(`/tools/tools/${toolId}`, data)
}

export async function updateToolStatus(toolId: string, data: UpdateToolStatusRequest): Promise<Tool> {
  return patch<Tool>(`/tools/tools/${toolId}/status`, data)
}

export async function getToolUsageImpact(toolId: string): Promise<ToolUsageImpact> {
  return get<ToolUsageImpact>(`/tools/tools/${toolId}/usage-impact`)
}

export async function deleteTool(toolId: string): Promise<void> {
  return del<void>(`/tools/tools/${toolId}`)
}

export async function testTool(data: TestToolRequest): Promise<TestToolResponse> {
  return post<TestToolResponse>('/tools/tools/test', data)
}

export async function discoverMcpTools(data: DiscoverMcpToolsRequest): Promise<DiscoverMcpToolsResponse> {
  return post<DiscoverMcpToolsResponse>('/tools/mcp/discover', data)
}

export async function refreshMcpTools(data: RefreshMcpToolsRequest): Promise<RefreshMcpToolsResponse> {
  return post<RefreshMcpToolsResponse>('/tools/mcp/refresh', data)
}

export async function updateMcpToolPermissions(data: UpdateMcpToolPermissionsRequest): Promise<McpToolPermissionsResponse> {
  return patch<McpToolPermissionsResponse>('/tools/mcp/permissions', data)
}

export async function bulkUpdateMcpToolPermissions(data: BulkUpdateMcpToolPermissionsRequest): Promise<McpToolPermissionsResponse> {
  return post<McpToolPermissionsResponse>('/tools/mcp/permissions/bulk', data)
}

export async function startMcpOAuth(data: McpOAuthStartRequest): Promise<McpOAuthStartResponse> {
  return post<McpOAuthStartResponse>('/tools/mcp/oauth/start', data)
}

export async function startMcpDeviceOAuth(data: McpOAuthDeviceStartRequest): Promise<McpOAuthDeviceStartResponse> {
  return post<McpOAuthDeviceStartResponse>('/tools/mcp/oauth/device/start', data)
}

export async function pollMcpDeviceOAuth(data: McpOAuthDevicePollRequest): Promise<McpOAuthDevicePollResponse> {
  return post<McpOAuthDevicePollResponse>('/tools/mcp/oauth/device/poll', data)
}

export async function completeMcpOAuth(data: McpOAuthCompleteRequest): Promise<McpOAuthStatusResponse> {
  return post<McpOAuthStatusResponse>('/tools/mcp/oauth/complete', data)
}

export async function getMcpOAuthStatus(data: McpOAuthStatusRequest): Promise<McpOAuthStatusResponse> {
  return post<McpOAuthStatusResponse>('/tools/mcp/oauth/status', data)
}

export async function disconnectMcpOAuth(data: McpOAuthStatusRequest): Promise<{ status: string }> {
  return post<{ status: string }>('/tools/mcp/oauth/disconnect', data)
}

export async function getSecrets(projectId?: string): Promise<Secret[]> {
  return get<Secret[]>('/tools/secrets', { params: { project_id: projectId } })
}

export async function createSecret(data: CreateSecretRequest): Promise<Secret> {
  return post<Secret>('/tools/secrets', data)
}
