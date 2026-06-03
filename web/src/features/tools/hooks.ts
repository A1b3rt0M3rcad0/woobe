import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { getTools, getAgentTools, createTool, getSecrets, createSecret } from './api'
import type { CreateToolRequest, CreateSecretRequest } from './types'

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
    },
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
