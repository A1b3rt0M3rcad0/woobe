import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import {
  activateNetworkProduction,
  createNetworkSession,
  ensureNetwork,
  getNetwork,
  getNetworkProductionActivations,
  getNetworkSessionMessages,
  getNetworkSessions,
  getNetworkVersions,
  promoteNetwork,
  rollbackNetworkProduction,
  saveNetworkDraft,
} from './api'
import type {
  ActivateNetworkProductionInput,
  NetworkDefinition,
  NetworkEnvironment,
  NetworkResource,
  NetworkVersion,
  PromoteNetworkInput,
} from './types'
import { ApiError } from '@/lib/api/errors'

function sessionTitle(environment: NetworkEnvironment) {
  const timestamp = new Intl.DateTimeFormat(undefined, {
    day: '2-digit',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
  }).format(new Date())
  return `${environment.charAt(0).toUpperCase()}${environment.slice(1)} · ${timestamp}`
}

export function useNetwork(projectId?: string, projectName = 'Project Network') {
  return useQuery({
    queryKey: ['network', projectId],
    queryFn: async () => {
      try {
        return await getNetwork(projectId!)
      } catch (error) {
        if (!(error instanceof ApiError) || error.status !== 404) throw error
        return ensureNetwork(projectId!, `${projectName} Network`)
      }
    },
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

export function useNetworkProductionActivations(networkId?: string, projectId?: string) {
  return useQuery({
    queryKey: ['network-production-activations', networkId, projectId],
    queryFn: () => getNetworkProductionActivations(networkId!, projectId!),
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

export function useNetworkSessionMessages(networkId?: string, sessionId?: string, projectId?: string) {
  return useQuery({
    queryKey: ['network-session-messages', networkId, sessionId, projectId],
    queryFn: () => getNetworkSessionMessages(networkId!, sessionId!, projectId!),
    enabled: Boolean(networkId && sessionId && projectId),
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
    onSuccess: (saved) => {
      queryClient.setQueryData<NetworkResource>(['network', projectId], saved)
      queryClient.invalidateQueries({ queryKey: ['network', projectId] })
    },
  })
}

export function usePromoteNetwork(networkId?: string, projectId?: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (input: PromoteNetworkInput) => promoteNetwork(networkId!, projectId!, input),
    onSuccess: (saved, input) => {
      queryClient.setQueryData<NetworkVersion[]>(['network-versions', networkId, projectId], (current = []) => {
        const next = current.filter((version) => version.id !== saved.id)
        return [saved, ...next]
      })
      queryClient.setQueryData<NetworkResource>(['network', projectId], (current) => current ? {
        ...current,
        staging_version_id: input.environment === 'staging' ? saved.id : current.staging_version_id,
        production_version_id: input.environment === 'production' ? saved.id : current.production_version_id,
      } : current)
      queryClient.invalidateQueries({ queryKey: ['network', projectId] })
      queryClient.invalidateQueries({ queryKey: ['network-versions', networkId, projectId] })
      queryClient.invalidateQueries({ queryKey: ['releases'] })
    },
  })
}

export function useActivateNetworkProduction(networkId?: string, projectId?: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (input: ActivateNetworkProductionInput) => activateNetworkProduction(networkId!, projectId!, input),
    onSuccess: (result) => {
      queryClient.setQueryData<NetworkResource>(['network', projectId], (current) => current ? {
        ...current,
        production_version_id: result.version.id,
      } : current)
      queryClient.invalidateQueries({ queryKey: ['network', projectId] })
      queryClient.invalidateQueries({ queryKey: ['network-versions', networkId, projectId] })
      queryClient.invalidateQueries({ queryKey: ['network-production-activations', networkId, projectId] })
    },
  })
}

export function useRollbackNetworkProduction(networkId?: string, projectId?: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (targetVersionId: string) => rollbackNetworkProduction(networkId!, projectId!, targetVersionId),
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
      title: sessionTitle(environment),
    }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['network-sessions', networkId, projectId] })
    },
  })
}
