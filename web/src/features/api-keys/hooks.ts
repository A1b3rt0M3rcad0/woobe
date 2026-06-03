import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { getApiKeys, createApiKey } from './api'
import type { CreateApiKeyRequest } from './types'

export function useApiKeys(projectId: string | undefined) {
  return useQuery({
    queryKey: ['api-keys', projectId],
    queryFn: () => getApiKeys(projectId!),
    enabled: Boolean(projectId),
  })
}

export function useCreateApiKey(projectId: string | undefined) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (data: CreateApiKeyRequest) => createApiKey(projectId!, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['api-keys', projectId] })
    },
  })
}
