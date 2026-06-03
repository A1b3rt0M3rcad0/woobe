import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { getCredentials, createCredential } from './api'
import type { CreateProviderCredentialRequest } from './types'

export function useCredentials(projectId?: string) {
  return useQuery({
    queryKey: ['credentials', projectId],
    queryFn: () => getCredentials(projectId),
    enabled: Boolean(projectId),
  })
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
