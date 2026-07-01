import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { getCredentials, createCredential, updateCredential } from './api'
import type {
  CreateProviderCredentialRequest,
  UpdateProviderCredentialRequest,
} from './types'

export function useCredentials(projectId?: string) {
  const query = useQuery({
    queryKey: ['credentials', projectId],
    queryFn: () => getCredentials(projectId),
    enabled: Boolean(projectId),
  })

  return {
    ...query,
    data: query.data ?? [],
  }
}

export function useCreateCredential() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (data: CreateProviderCredentialRequest) => createCredential(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['credentials'] })
    },
  })
}

export function useUpdateCredential() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: UpdateProviderCredentialRequest }) => updateCredential(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['credentials'] })
    },
  })
}
