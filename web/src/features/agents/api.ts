import { get, post } from '@/lib/api/client'
import type { Agent, CreateAgentRequest } from './types'

export async function getAgents(projectId?: string): Promise<Agent[]> {
  return get<Agent[]>('/ai/agents', { params: { project_id: projectId } })
}

export async function getAgent(id: string): Promise<Agent> {
  return get<Agent>(`/ai/agents/${id}`)
}

export async function createAgent(data: CreateAgentRequest): Promise<Agent> {
  return post<Agent>('/ai/agents', data)
}
