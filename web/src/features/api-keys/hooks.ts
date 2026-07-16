import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  createApiKey,
  createRuntimeApiKey,
  getApiKeys,
  revokeApiKey,
  rotateApiKey,
  updateApiKeyCredential,
} from './api'
import type {
  CreateApiKeyRequest,
  CreateRuntimeApiKeyRequest,
  RotateApiKeyRequest,
  UpdateApiKeyCredentialRequest,
} from './types'

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

export function useCreateRuntimeApiKey(projectId: string | undefined) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (data: CreateRuntimeApiKeyRequest) => createRuntimeApiKey(projectId!, data),
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

export function useUpdateApiKeyCredential(projectId: string | undefined) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({
      apiKeyId,
      data,
    }: {
      apiKeyId: string
      data: UpdateApiKeyCredentialRequest
    }) => updateApiKeyCredential(projectId!, apiKeyId, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['api-keys', projectId] })
    },
  })
}
