import { get, post, patch, del } from '@/lib/api/client'
import type {
  Agent,
  AgentContract,
  AgentModelConfig,
  AgentPrompt,
  AgentRelease,
  AgentReleaseTest,
  CreateAgentRequest,
  CreateContractRequest,
  CreateKnowledgeVersionRequest,
  CreateModelConfigRequest,
  CreatePromptRequest,
  CreateReleaseRequest,
  CreateReleaseTestRequest,
  KnowledgeVersion,
  UpdateAgentRequest,
  UpdateContractRequest,
} from './types'

export async function getAgents(projectId?: string): Promise<Agent[]> {
  return get<Agent[]>('/ai/agents', { params: { project_id: projectId } })
}

export async function getAgent(id: string): Promise<Agent> {
  return get<Agent>(`/ai/agents/${id}`)
}

export async function createAgent(data: CreateAgentRequest): Promise<Agent> {
  return post<Agent>('/ai/agents', data)
}

export async function updateAgent(id: string, data: UpdateAgentRequest): Promise<Agent> {
  return patch<Agent>(`/ai/agents/${id}`, data)
}


// ── Agent Prompts ──────────────────────────────────────────────

export async function getPrompts(agentId: string): Promise<AgentPrompt[]> {
  return get<AgentPrompt[]>(`/ai/agents/${agentId}/prompts`)
}

export async function getPrompt(agentId: string, versionId: string): Promise<AgentPrompt> {
  return get<AgentPrompt>(`/ai/agents/${agentId}/prompts/${versionId}`)
}

export async function createPrompt(agentId: string, data: CreatePromptRequest): Promise<AgentPrompt> {
  return post<AgentPrompt>(`/ai/agents/${agentId}/prompts`, data)
}


// ── Agent Contracts ────────────────────────────────────────────

export async function getContracts(agentId: string): Promise<AgentContract[]> {
  return get<AgentContract[]>(`/ai/agents/${agentId}/contracts`)
}

export async function getContract(agentId: string, contractId: string): Promise<AgentContract> {
  return get<AgentContract>(`/ai/agents/${agentId}/contracts/${contractId}`)
}

export async function createContract(agentId: string, data: CreateContractRequest): Promise<AgentContract> {
  return post<AgentContract>(`/ai/agents/${agentId}/contracts`, data)
}

export async function updateContract(agentId: string, contractId: string, data: UpdateContractRequest): Promise<AgentContract> {
  return patch<AgentContract>(`/ai/agents/${agentId}/contracts/${contractId}`, data)
}


// ── Agent Model Configs ────────────────────────────────────────

export async function getModelConfigs(agentId: string): Promise<AgentModelConfig[]> {
  return get<AgentModelConfig[]>(`/ai/agents/${agentId}/model-configs`)
}

export async function getModelConfig(agentId: string, configId: string): Promise<AgentModelConfig> {
  return get<AgentModelConfig>(`/ai/agents/${agentId}/model-configs/${configId}`)
}

export async function createModelConfig(agentId: string, data: CreateModelConfigRequest): Promise<AgentModelConfig> {
  return post<AgentModelConfig>(`/ai/agents/${agentId}/model-configs`, data)
}


// ── Knowledge Versions ─────────────────────────────────────────

export async function getKnowledgeVersions(agentId: string): Promise<KnowledgeVersion[]> {
  return get<KnowledgeVersion[]>(`/knowledge/agents/${agentId}/knowledge-versions`)
}

export async function createKnowledgeVersion(agentId: string, data: CreateKnowledgeVersionRequest): Promise<KnowledgeVersion> {
  return post<KnowledgeVersion>(`/knowledge/agents/${agentId}/knowledge-versions`, data)
}


// ── Agent Releases ─────────────────────────────────────────────

export async function getReleases(agentId: string): Promise<AgentRelease[]> {
  return get<AgentRelease[]>(`/ai/agents/${agentId}/releases`)
}

export async function getRelease(agentId: string, releaseId: string): Promise<AgentRelease> {
  return get<AgentRelease>(`/ai/agents/${agentId}/releases/${releaseId}`)
}

export async function createRelease(agentId: string, data: CreateReleaseRequest): Promise<AgentRelease> {
  return post<AgentRelease>(`/ai/agents/${agentId}/releases`, data)
}

export async function promoteRelease(agentId: string, releaseId: string, userId?: string): Promise<AgentRelease> {
  return post<AgentRelease>(`/ai/agents/${agentId}/releases/${releaseId}/promote`, { user_id: userId })
}

export async function rollbackRelease(agentId: string, releaseId: string, userId?: string): Promise<AgentRelease> {
  return post<AgentRelease>(`/ai/agents/${agentId}/releases/${releaseId}/rollback`, { user_id: userId })
}


// ── Agent Release Tests ────────────────────────────────────────

export async function getReleaseTests(agentId: string, releaseId: string): Promise<AgentReleaseTest[]> {
  return get<AgentReleaseTest[]>(`/ai/agents/${agentId}/releases/${releaseId}/tests`)
}

export async function createReleaseTest(agentId: string, data: CreateReleaseTestRequest): Promise<AgentReleaseTest> {
  return post<AgentReleaseTest>(`/ai/agents/${agentId}/release-tests`, data)
}


// ── Delete Release ─────────────────────────────────────────────

export async function deleteRelease(agentId: string, releaseId: string): Promise<void> {
  return del<void>(`/ai/agents/${agentId}/releases/${releaseId}`)
}
