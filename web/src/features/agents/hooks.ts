import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  createAgent,
  createContract,
  createKnowledgeVersion,
  createModelConfig,
  createPrompt,
  createRelease,
  createReleaseTest,
  deleteRelease,
  getAgent,
  getAgents,
  getContract,
  getContracts,
  getKnowledgeVersions,
  getModelConfig,
  getModelConfigs,
  getPrompt,
  getPrompts,
  getRelease,
  getReleaseTests,
  getReleases,
  promoteRelease,
  rollbackRelease,
  updateAgent,
  updateContract,
} from './api'
import type { PromoteReleaseOptions } from './api'
import type {
  CreateAgentRequest,
  CreateContractRequest,
  CreateKnowledgeVersionRequest,
  CreateModelConfigRequest,
  CreatePromptRequest,
  CreateReleaseRequest,
  CreateReleaseTestRequest,
  UpdateAgentRequest,
  UpdateContractRequest,
} from './types'

export function useAgents(projectId?: string) {
  return useQuery({ queryKey: ['agents', projectId], queryFn: () => getAgents(projectId), enabled: Boolean(projectId) })
}
export function useAgent(id: string | undefined) {
  return useQuery({ queryKey: ['agent', id], queryFn: () => getAgent(id!), enabled: Boolean(id) })
}
export function useCreateAgent(projectId?: string) {
  const queryClient = useQueryClient()
  return useMutation({ mutationFn: (data: CreateAgentRequest) => createAgent(data), onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['agents', projectId] }) } })
}
export function useUpdateAgent(agentId?: string) {
  const queryClient = useQueryClient()
  return useMutation({ mutationFn: (data: UpdateAgentRequest) => updateAgent(agentId!, data), onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['agent', agentId] }); queryClient.invalidateQueries({ queryKey: ['agents'] }) } })
}
export function usePrompts(agentId: string | undefined) {
  return useQuery({ queryKey: ['prompts', agentId], queryFn: () => getPrompts(agentId!), enabled: Boolean(agentId) })
}
export function useCreatePrompt(agentId?: string) {
  const queryClient = useQueryClient()
  return useMutation({ mutationFn: (data: CreatePromptRequest) => createPrompt(agentId!, data), onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['prompts', agentId] }) } })
}
export function useContracts(agentId: string | undefined) {
  return useQuery({ queryKey: ['contracts', agentId], queryFn: () => getContracts(agentId!), enabled: Boolean(agentId) })
}
export function useCreateContract(agentId?: string) {
  const queryClient = useQueryClient()
  return useMutation({ mutationFn: (data: CreateContractRequest) => createContract(agentId!, data), onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['contracts', agentId] }) } })
}
export function useUpdateContract(agentId?: string) {
  const queryClient = useQueryClient()
  return useMutation({ mutationFn: ({ contractId, data }: { contractId: string; data: UpdateContractRequest }) => updateContract(agentId!, contractId, data), onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['contracts', agentId] }) } })
}
export function useModelConfigs(agentId: string | undefined) {
  return useQuery({ queryKey: ['model-configs', agentId], queryFn: () => getModelConfigs(agentId!), enabled: Boolean(agentId) })
}
export function useCreateModelConfig(agentId?: string) {
  const queryClient = useQueryClient()
  return useMutation({ mutationFn: (data: CreateModelConfigRequest) => createModelConfig(agentId!, data), onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['model-configs', agentId] }) } })
}
export function useKnowledgeVersions(agentId: string | undefined) {
  return useQuery({ queryKey: ['knowledge-versions', agentId], queryFn: () => getKnowledgeVersions(agentId!), enabled: Boolean(agentId) })
}
export function useCreateKnowledgeVersion(agentId?: string) {
  const queryClient = useQueryClient()
  return useMutation({ mutationFn: (data: CreateKnowledgeVersionRequest) => createKnowledgeVersion(agentId!, data), onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['knowledge-versions', agentId] }) } })
}
export function useReleases(agentId: string | undefined) {
  return useQuery({ queryKey: ['releases', agentId], queryFn: () => getReleases(agentId!), enabled: Boolean(agentId) })
}
export function useCreateRelease(agentId?: string) {
  const queryClient = useQueryClient()
  return useMutation({ mutationFn: (data: CreateReleaseRequest) => createRelease(agentId!, data), onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['releases', agentId] }) } })
}
export function usePromoteRelease(agentId?: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ releaseId, ...options }: { releaseId: string } & PromoteReleaseOptions) => promoteRelease(agentId!, releaseId, options),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['releases', agentId] }); queryClient.invalidateQueries({ queryKey: ['agent', agentId] }) },
  })
}
export function useRollbackRelease(agentId?: string) {
  const queryClient = useQueryClient()
  return useMutation({ mutationFn: ({ releaseId, userId }: { releaseId: string; userId?: string }) => rollbackRelease(agentId!, releaseId, userId), onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['releases', agentId] }); queryClient.invalidateQueries({ queryKey: ['agent', agentId] }) } })
}
export function useReleaseTests(agentId: string | undefined, releaseId: string | undefined) {
  return useQuery({ queryKey: ['release-tests', agentId, releaseId], queryFn: () => getReleaseTests(agentId!, releaseId!), enabled: Boolean(agentId) && Boolean(releaseId) })
}
export function useDeleteRelease(agentId?: string) {
  const queryClient = useQueryClient()
  return useMutation({ mutationFn: ({ releaseId }: { releaseId: string }) => deleteRelease(agentId!, releaseId), onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['releases', agentId] }) } })
}
export function useCreateReleaseTest(agentId?: string) {
  const queryClient = useQueryClient()
  return useMutation({ mutationFn: (data: CreateReleaseTestRequest) => createReleaseTest(agentId!, data), onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['release-tests', agentId] }) } })
}
