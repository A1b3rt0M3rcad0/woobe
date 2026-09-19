import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  getTools,
  getAgentTools,
  createTool,
  updateTool,
  updateToolStatus,
  deleteTool,
  testTool,
  discoverMcpTools,
  getSecrets,
  createSecret,
} from './api'
import type {
  CreateToolRequest,
  CreateSecretRequest,
  UpdateToolStatusRequest,
  TestToolRequest,
  DiscoverMcpToolsRequest,
} from './types'

export function useTools(projectId?: string) {
  return useQuery({
    queryKey: ['tools', projectId],
    queryFn: () => getTools(projectId!),
    enabled: Boolean(projectId),
  })
}

export function useAgentTools(agentId: string | undefined) {
  return useQuery({
    queryKey: ['agent-tools', agentId],
    queryFn: () => getAgentTools(agentId!),
    enabled: Boolean(agentId),
  })
}

export function useCreateTool() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (data: CreateToolRequest) => createTool(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['tools'] })
      queryClient.invalidateQueries({ queryKey: ['agent-tools'] })
      queryClient.invalidateQueries({ queryKey: ['project-environment-key-usage'] })
    },
  })
}

export function useUpdateTool() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ toolId, data }: { toolId: string; data: Partial<CreateToolRequest> }) => updateTool(toolId, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['tools'] })
      queryClient.invalidateQueries({ queryKey: ['agent-tools'] })
      queryClient.invalidateQueries({ queryKey: ['project-environment-key-usage'] })
    },
  })
}

export function useUpdateToolStatus() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ toolId, data }: { toolId: string; data: UpdateToolStatusRequest }) => updateToolStatus(toolId, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['tools'] })
      queryClient.invalidateQueries({ queryKey: ['agent-tools'] })
      queryClient.invalidateQueries({ queryKey: ['project-environment-key-usage'] })
    },
  })
}

export function useDeleteTool() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (toolId: string) => deleteTool(toolId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['tools'] })
      queryClient.invalidateQueries({ queryKey: ['agent-tools'] })
      queryClient.invalidateQueries({ queryKey: ['project-environment-key-usage'] })
    },
  })
}

export function useTestTool() {
  return useMutation({
    mutationFn: (data: TestToolRequest) => testTool(data),
  })
}

export function useDiscoverMcpTools() {
  return useMutation({
    mutationFn: (data: DiscoverMcpToolsRequest) => discoverMcpTools(data),
  })
}

export function useSecrets(projectId?: string) {
  return useQuery({
    queryKey: ['secrets', projectId],
    queryFn: () => getSecrets(projectId!),
    enabled: Boolean(projectId),
  })
}

export function useCreateSecret() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (data: CreateSecretRequest) => createSecret(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['secrets'] })
    },
  })
}
