import { get, post } from '@/lib/api/client'
import type { Tool, CreateToolRequest, Secret, CreateSecretRequest } from './types'

export async function getTools(projectId?: string): Promise<Tool[]> {
  return get<Tool[]>('/tools/tools', { params: { project_id: projectId } })
}

export async function getAgentTools(agentId: string): Promise<Tool[]> {
  return get<Tool[]>(`/tools/agents/${agentId}/tools`)
}

export async function createTool(data: CreateToolRequest): Promise<Tool> {
  return post<Tool>('/tools/tools', data)
}

export async function getSecrets(projectId?: string): Promise<Secret[]> {
  return get<Secret[]>('/tools/secrets', { params: { project_id: projectId } })
}

export async function createSecret(data: CreateSecretRequest): Promise<Secret> {
  return post<Secret>('/tools/secrets', data)
}
