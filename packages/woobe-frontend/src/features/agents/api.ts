import { get, post, patch, del } from '@/lib/api/client'
import type { Agent, AgentContract, AgentModelConfig, AgentPrompt, AgentRelease, AgentReleaseActivation, AgentReleaseTest, ContextAssemblerDescriptor, CreateAgentRequest, CreateContractRequest, CreateKnowledgeVersionRequest, CreateModelConfigRequest, CreatePromptRequest, CreateReleaseRequest, CreateReleaseTestRequest, ExecutionStrategyDescriptor, KnowledgeVersion, RuntimeEnvironment, RuntimeEnvironmentState, RuntimeEnvironmentStates, UpdateAgentRequest, UpdateContractRequest } from './types'

export async function getContextAssemblers(): Promise<ContextAssemblerDescriptor[]> { return get<ContextAssemblerDescriptor[]>('/ai/context-assemblers') }
export async function getExecutionStrategies(): Promise<ExecutionStrategyDescriptor[]> { return get<ExecutionStrategyDescriptor[]>('/ai/execution-strategies') }
export async function getAgents(projectId?: string): Promise<Agent[]> { return get<Agent[]>('/ai/agents', { params: { project_id: projectId } }) }
export async function getAgent(id: string): Promise<Agent> { return get<Agent>(`/ai/agents/${id}`) }
export async function createAgent(data: CreateAgentRequest): Promise<Agent> { return post<Agent>('/ai/agents', data) }
export async function updateAgent(id: string, data: UpdateAgentRequest): Promise<Agent> { return patch<Agent>(`/ai/agents/${id}`, data) }
export async function getAgentRuntimeEnvironments(agentId: string, projectId: string): Promise<RuntimeEnvironmentStates> { return get<RuntimeEnvironmentStates>(`/ai/agents/${agentId}/runtime-environments`, { params: { project_id: projectId } }) }
export async function updateAgentRuntimeEnvironment(agentId: string, projectId: string, environment: RuntimeEnvironment, enabled: boolean): Promise<RuntimeEnvironmentState & { environment: RuntimeEnvironment }> { return patch<RuntimeEnvironmentState & { environment: RuntimeEnvironment }>(`/ai/agents/${agentId}/runtime-environments/${environment}`, { project_id: projectId, enabled }) }
export async function updateAgentRuntimeEnvironmentContext(agentId: string, projectId: string, environment: RuntimeEnvironment, externalContextValues: Record<string, unknown>): Promise<RuntimeEnvironmentState & { environment: RuntimeEnvironment }> { return patch<RuntimeEnvironmentState & { environment: RuntimeEnvironment }>(`/ai/agents/${agentId}/runtime-environments/${environment}`, { project_id: projectId, external_context_values: externalContextValues }) }
export async function getPrompts(agentId: string): Promise<AgentPrompt[]> { return get<AgentPrompt[]>(`/ai/agents/${agentId}/prompts`) }
export async function getPrompt(agentId: string, versionId: string): Promise<AgentPrompt> { return get<AgentPrompt>(`/ai/agents/${agentId}/prompts/${versionId}`) }
export async function createPrompt(agentId: string, data: CreatePromptRequest): Promise<AgentPrompt> { return post<AgentPrompt>(`/ai/agents/${agentId}/prompts`, data) }
export async function getContracts(agentId: string): Promise<AgentContract[]> { return get<AgentContract[]>(`/ai/agents/${agentId}/contracts`) }
export async function getContract(agentId: string, contractId: string): Promise<AgentContract> { return get<AgentContract>(`/ai/agents/${agentId}/contracts/${contractId}`) }
export async function createContract(agentId: string, data: CreateContractRequest): Promise<AgentContract> { return post<AgentContract>(`/ai/agents/${agentId}/contracts`, data) }
export async function updateContract(agentId: string, contractId: string, data: UpdateContractRequest): Promise<AgentContract> { return patch<AgentContract>(`/ai/agents/${agentId}/contracts/${contractId}`, data) }
export async function getModelConfigs(agentId: string): Promise<AgentModelConfig[]> { return get<AgentModelConfig[]>(`/ai/agents/${agentId}/model-configs`) }
export async function getModelConfig(agentId: string, configId: string): Promise<AgentModelConfig> { return get<AgentModelConfig>(`/ai/agents/${agentId}/model-configs/${configId}`) }
export async function createModelConfig(agentId: string, data: CreateModelConfigRequest): Promise<AgentModelConfig> { return post<AgentModelConfig>(`/ai/agents/${agentId}/model-configs`, data) }
export async function getKnowledgeVersions(agentId: string): Promise<KnowledgeVersion[]> { return get<KnowledgeVersion[]>(`/knowledge/agents/${agentId}/knowledge-versions`) }
export async function createKnowledgeVersion(agentId: string, data: CreateKnowledgeVersionRequest): Promise<KnowledgeVersion> { return post<KnowledgeVersion>(`/knowledge/agents/${agentId}/knowledge-versions`, data) }
export async function getReleases(agentId: string): Promise<AgentRelease[]> { return get<AgentRelease[]>(`/ai/agents/${agentId}/releases`) }
export async function getRelease(agentId: string, releaseId: string): Promise<AgentRelease> { return get<AgentRelease>(`/ai/agents/${agentId}/releases/${releaseId}`) }
export async function getReleaseActivations(agentId: string): Promise<AgentReleaseActivation[]> { return get<AgentReleaseActivation[]>(`/ai/agents/${agentId}/release-activations`) }
export async function createRelease(agentId: string, data: CreateReleaseRequest): Promise<AgentRelease> { return post<AgentRelease>(`/ai/agents/${agentId}/releases`, data) }
export type PromoteReleaseOptions = { userId?: string; targetStatus?: 'draft' | 'staging' | 'released' | 'production'; copySnapshot?: boolean; restoreExistingVersion?: boolean; releaseNotes?: string; changeDescription?: string }
export async function promoteRelease(agentId: string, releaseId: string, options: PromoteReleaseOptions | string = {}): Promise<AgentRelease> {
  const isLegacy = typeof options === 'string'
  const payload: Record<string, unknown> = {
    user_id: isLegacy ? options : options.userId,
    target_status: isLegacy ? 'production' : options.targetStatus ?? 'production',
    copy_snapshot: isLegacy ? false : options.copySnapshot ?? false,
    restore_existing_version: isLegacy ? true : options.restoreExistingVersion ?? false,
    release_notes: isLegacy ? undefined : options.releaseNotes,
    change_description: isLegacy ? undefined : options.changeDescription,
  }
  return post<AgentRelease>(`/ai/agents/${agentId}/releases/${releaseId}/promote`, payload)
}
export type RollbackReleaseOptions = { userId?: string; changeDescription?: string }
export async function rollbackRelease(agentId: string, releaseId: string, options: RollbackReleaseOptions | string = {}): Promise<AgentRelease> {
  const isLegacy = typeof options === 'string'
  return post<AgentRelease>(`/ai/agents/${agentId}/releases/${releaseId}/rollback`, {
    user_id: isLegacy ? options : options.userId,
    change_description: isLegacy ? undefined : options.changeDescription,
  })
}
export async function getReleaseTests(agentId: string, releaseId: string): Promise<AgentReleaseTest[]> { return get<AgentReleaseTest[]>(`/ai/agents/${agentId}/releases/${releaseId}/tests`) }
export async function createReleaseTest(agentId: string, data: CreateReleaseTestRequest): Promise<AgentReleaseTest> { return post<AgentReleaseTest>(`/ai/agents/${agentId}/release-tests`, data) }
export async function deleteRelease(agentId: string, releaseId: string): Promise<void> { return del<void>(`/ai/agents/${agentId}/releases/${releaseId}`) }
