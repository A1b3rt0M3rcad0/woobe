import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import {
  createNetworkSession,
  ensureNetwork,
  getNetworkSessions,
  getNetworkVersions,
  promoteNetwork,
  saveNetworkDraft,
} from './api'
import type { NetworkDefinition, NetworkEnvironment } from './types'

export function useNetwork(projectId?: string, projectName = 'Project Network') {
  return useQuery({
    queryKey: ['network', projectId],
    queryFn: () => ensureNetwork(projectId!, `${projectName} Network`),
    enabled: Boolean(projectId),
  })
}

export function useNetworkVersions(networkId?: string, projectId?: string) {
  return useQuery({
    queryKey: ['network-versions', networkId, projectId],
    queryFn: () => getNetworkVersions(networkId!, projectId!),
    enabled: Boolean(networkId && projectId),
  })
}

export function useNetworkSessions(networkId?: string, projectId?: string) {
  return useQuery({
    queryKey: ['network-sessions', networkId, projectId],
    queryFn: () => getNetworkSessions(networkId!, projectId!),
    enabled: Boolean(networkId && projectId),
  })
}

export function useSaveNetworkDraft(networkId?: string, projectId?: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (input: {
      expectedRevision: number
      name: string
      description: string
      definition: NetworkDefinition
    }) => saveNetworkDraft(networkId!, {
      project_id: projectId!,
      expected_revision: input.expectedRevision,
      name: input.name,
      description: input.description,
      definition: input.definition,
    }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['network', projectId] }),
  })
}

export function usePromoteNetwork(networkId?: string, projectId?: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (environment: NetworkEnvironment) => promoteNetwork(
      networkId!,
      projectId!,
      environment,
    ),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['network', projectId] })
      queryClient.invalidateQueries({ queryKey: ['network-versions', networkId, projectId] })
    },
  })
}

export function useCreateNetworkSession(networkId?: string, projectId?: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (environment: NetworkEnvironment) => createNetworkSession(networkId!, {
      project_id: projectId!,
      environment,
      title: `New ${environment} session`,
    }),
    onSuccess: () => queryClient.invalidateQueries({
      queryKey: ['network-sessions', networkId, projectId],
    }),
  })
}
