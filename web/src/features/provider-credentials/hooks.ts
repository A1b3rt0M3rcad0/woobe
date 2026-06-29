import { useCallback, useRef } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { getCredentials, createCredential, updateCredential } from './api'
import type {
  CreateProviderCredentialRequest,
  ProviderCredential,
  UpdateProviderCredentialRequest,
} from './types'

function visibleCredentials(credentials: ProviderCredential[] | undefined) {
  return credentials ?? []
}

export function useCredentials(projectId?: string) {
  const query = useQuery({
    queryKey: ['credentials', projectId],
    queryFn: () => getCredentials(projectId),
    enabled: Boolean(projectId),
  })
  const stableData = useRef<ProviderCredential[]>([])
  const current = visibleCredentials(query.data)
  stableData.current.splice(0, stableData.current.length, ...current)

  const refetch = useCallback(async () => {
    const result = await query.refetch()
    const refreshed = visibleCredentials(result.data)
    stableData.current.splice(0, stableData.current.length, ...refreshed)
    return result
  }, [query])

  return { ...query, data: stableData.current, refetch }
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
