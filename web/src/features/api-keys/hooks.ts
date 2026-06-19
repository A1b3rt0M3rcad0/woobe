import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { createApiKey, getApiKeys, revokeApiKey, rotateApiKey } from './api'
import type { CreateApiKeyRequest, RotateApiKeyRequest } from './types'

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

export function useRevokeApiKey(projectId: string | undefined) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (apiKeyId: string) => revokeApiKey(projectId!, apiKeyId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['api-keys', projectId] })
    },
  })
}

export function useRotateApiKey(projectId: string | undefined) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ apiKeyId, data }: { apiKeyId: string; data?: RotateApiKeyRequest }) =>
      rotateApiKey(projectId!, apiKeyId, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['api-keys', projectId] })
    },
  })
}
