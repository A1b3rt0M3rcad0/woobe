import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { getAgents, getAgent, createAgent } from './api'
import type { CreateAgentRequest } from './types'

export function useAgents(projectId?: string) {
  return useQuery({
    queryKey: ['agents', projectId],
    queryFn: () => getAgents(projectId),
    enabled: Boolean(projectId),
  })
}

export function useAgent(id: string | undefined) {
  return useQuery({
    queryKey: ['agent', id],
    queryFn: () => getAgent(id!),
    enabled: Boolean(id),
  })
}

export function useCreateAgent(projectId?: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (data: CreateAgentRequest) => createAgent(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['agents', projectId] })
    },
  })
}
