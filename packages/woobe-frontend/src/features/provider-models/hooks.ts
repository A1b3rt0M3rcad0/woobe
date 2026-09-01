import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { createProviderModel, getAvailableProviderModels, getProviderModel, getProviderModels, updateProviderModel } from './api'
import type { CreateProviderModelRequest, UpdateProviderModelRequest } from './types'

export function useProviderModels(projectId?: string, credentialId?: string) {
  return useQuery({
    queryKey: ['provider-models', projectId, credentialId],
    queryFn: () => getProviderModels(projectId, credentialId),
    enabled: Boolean(projectId),
  })
}

export function useAvailableProviderModels(projectId?: string, credentialId?: string, capability?: string) {
  return useQuery({
    queryKey: ['available-provider-models', projectId, credentialId, capability],
    queryFn: () => getAvailableProviderModels(projectId, credentialId, capability),
    enabled: Boolean(projectId && credentialId),
    retry: false,
  })
}

export function useProviderModel(providerModelId?: string | null) {
  return useQuery({
    queryKey: ['provider-model', providerModelId],
    queryFn: () => getProviderModel(providerModelId as string),
    enabled: Boolean(providerModelId),
  })
}

export function useCreateProviderModel() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (data: CreateProviderModelRequest) => createProviderModel(data),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['provider-models'] })
      queryClient.invalidateQueries({ queryKey: ['provider-model', data.id] })
    },
  })
}

export function useUpdateProviderModel() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: UpdateProviderModelRequest }) => updateProviderModel(id, data),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['provider-models'] })
      queryClient.invalidateQueries({ queryKey: ['provider-model', data.id] })
    },
  })
}
