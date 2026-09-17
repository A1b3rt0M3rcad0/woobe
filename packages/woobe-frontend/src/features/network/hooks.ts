import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useParams } from 'react-router-dom'

import type { RuntimeEnvironment, RuntimeEnvironmentStates } from '@/features/agents/types'
import {
  activateNetworkProduction,
  createNetwork,
  createNetworkSession,
  getNetwork,
  getNetworkProductionActivations,
  getNetworkRuntimeEnvironments,
  getNetworkSessionMessages,
  getNetworkSessions,
  getNetworkVersions,
  listNetworks,
  promoteNetwork,
  rollbackNetworkProduction,
  saveNetworkDraft,
  updateNetworkMetadata,
  updateNetworkRuntimeEnvironment,
  updateNetworkRuntimeEnvironmentContext,
} from './api'
import type {
  ActivateNetworkProductionInput,
  NetworkDefinition,
  NetworkEnvironment,
  NetworkResource,
  NetworkVersion,
  PromoteNetworkInput,
} from './types'

function sessionTitle(environment: NetworkEnvironment) {
  const timestamp = new Intl.DateTimeFormat(undefined, {
    day: '2-digit',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
  }).format(new Date())
  return `${environment.charAt(0).toUpperCase()}${environment.slice(1)} · ${timestamp}`
}

export function useNetworks(projectId?: string) {
  return useQuery({
    queryKey: ['networks', projectId],
    queryFn: () => listNetworks(projectId!),
    enabled: Boolean(projectId),
    staleTime: 30_000,
  })
}

export function useCreateNetwork(projectId?: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (input: { name: string; description?: string }) => createNetwork(projectId!, input),
    onSuccess: (created) => {
      queryClient.setQueryData<NetworkResource[]>(['networks', projectId], (current = []) => [created, ...current])
      queryClient.setQueryData<NetworkResource>(['network', projectId, created.id], created)
    },
  })
}

export function useUpdateNetworkMetadata(projectId?: string, networkId?: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (input: { name?: string; description?: string }) => updateNetworkMetadata(projectId!, networkId!, input),
    onSuccess: (updated) => {
      queryClient.setQueryData<NetworkResource>(['network', projectId, networkId], updated)
      queryClient.setQueryData<NetworkResource[]>(['networks', projectId], (current = []) => current.map((item) => item.id === updated.id ? updated : item))
    },
  })
}

export function useNetwork(projectId?: string, _projectName = 'Project Network') {
  const { networkId } = useParams<{ networkId: string }>()
  return useQuery({
    queryKey: ['network', projectId, networkId],
    queryFn: () => getNetwork(projectId!, networkId!),
    enabled: Boolean(projectId && networkId),
    staleTime: 30_000,
  })
}

export function useNetworkRuntimeEnvironments(networkId?: string, projectId?: string) {
  return useQuery({
    queryKey: ['network-runtime-environments', projectId, networkId],
    queryFn: () => getNetworkRuntimeEnvironments(networkId!, projectId!),
    enabled: Boolean(networkId && projectId),
    staleTime: 15_000,
  })
}

export function useUpdateNetworkRuntimeEnvironment(networkId?: string, projectId?: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ environment, enabled }: { environment: RuntimeEnvironment; enabled: boolean }) => updateNetworkRuntimeEnvironment(networkId!, projectId!, environment, enabled),
    onSuccess: (updated) => {
      queryClient.setQueryData<RuntimeEnvironmentStates>(['network-runtime-environments', projectId, networkId], (current) => current ? {
        ...current,
        [updated.environment]: {
          enabled: updated.enabled,
          external_context_values: updated.external_context_values,
          updated_by: updated.updated_by,
          updated_at: updated.updated_at,
        },
      } : current)
      queryClient.invalidateQueries({ queryKey: ['network-runtime-environments', projectId, networkId] })
    },
  })
}

export function useUpdateNetworkRuntimeEnvironmentContext(networkId?: string, projectId?: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ environment, values }: { environment: RuntimeEnvironment; values: Record<string, unknown> }) => updateNetworkRuntimeEnvironmentContext(networkId!, projectId!, environment, values),
    onSuccess: (updated) => {
      queryClient.setQueryData<RuntimeEnvironmentStates>(['network-runtime-environments', projectId, networkId], (current) => current ? {
        ...current,
        [updated.environment]: {
          enabled: updated.enabled,
          external_context_values: updated.external_context_values,
          updated_by: updated.updated_by,
          updated_at: updated.updated_at,
        },
      } : current)
    },
  })
}

export function useNetworkVersions(networkId?: string, projectId?: string) {
  return useQuery({
    queryKey: ['network-versions', projectId, networkId],
    queryFn: () => getNetworkVersions(networkId!, projectId!),
    enabled: Boolean(networkId && projectId),
  })
}

export function useNetworkProductionActivations(networkId?: string, projectId?: string) {
  return useQuery({
    queryKey: ['network-production-activations', projectId, networkId],
    queryFn: () => getNetworkProductionActivations(networkId!, projectId!),
    enabled: Boolean(networkId && projectId),
  })
}

export function useNetworkSessions(networkId?: string, projectId?: string) {
  return useQuery({
    queryKey: ['network-sessions', projectId, networkId],
    queryFn: () => getNetworkSessions(networkId!, projectId!),
    enabled: Boolean(networkId && projectId),
  })
}

export function useNetworkSessionMessages(networkId?: string, sessionId?: string, projectId?: string) {
  return useQuery({
    queryKey: ['network-session-messages', projectId, networkId, sessionId],
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
      queryClient.setQueryData<NetworkResource>(['network', projectId, networkId], saved)
      queryClient.setQueryData<NetworkResource[]>(['networks', projectId], (current = []) => current.map((item) => item.id === saved.id ? saved : item))
      queryClient.invalidateQueries({ queryKey: ['network', projectId, networkId] })
    },
  })
}

export function usePromoteNetwork(networkId?: string, projectId?: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (input: PromoteNetworkInput) => promoteNetwork(networkId!, projectId!, input),
    onSuccess: (saved, input) => {
      queryClient.setQueryData<NetworkVersion[]>(['network-versions', projectId, networkId], (current = []) => {
        const next = current.filter((version) => version.id !== saved.id)
        return [saved, ...next]
      })
      queryClient.setQueryData<NetworkResource>(['network', projectId, networkId], (current) => current ? {
        ...current,
        staging_version_id: input.environment === 'staging' ? saved.id : current.staging_version_id,
        production_version_id: input.environment === 'production' ? saved.id : current.production_version_id,
      } : current)
      queryClient.invalidateQueries({ queryKey: ['network', projectId, networkId] })
      queryClient.invalidateQueries({ queryKey: ['network-versions', projectId, networkId] })
      queryClient.invalidateQueries({ queryKey: ['networks', projectId] })
      queryClient.invalidateQueries({ queryKey: ['releases'] })
    },
  })
}

export function useActivateNetworkProduction(networkId?: string, projectId?: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (input: ActivateNetworkProductionInput) => activateNetworkProduction(networkId!, projectId!, input),
    onSuccess: (result) => {
      queryClient.setQueryData<NetworkResource>(['network', projectId, networkId], (current) => current ? {
        ...current,
        production_version_id: result.version.id,
      } : current)
      queryClient.invalidateQueries({ queryKey: ['network', projectId, networkId] })
      queryClient.invalidateQueries({ queryKey: ['network-versions', projectId, networkId] })
      queryClient.invalidateQueries({ queryKey: ['network-production-activations', projectId, networkId] })
      queryClient.invalidateQueries({ queryKey: ['networks', projectId] })
    },
  })
}

export function useRollbackNetworkProduction(networkId?: string, projectId?: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (targetVersionId: string) => rollbackNetworkProduction(networkId!, projectId!, targetVersionId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['network', projectId, networkId] })
      queryClient.invalidateQueries({ queryKey: ['network-versions', projectId, networkId] })
      queryClient.invalidateQueries({ queryKey: ['networks', projectId] })
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
      queryClient.invalidateQueries({ queryKey: ['network-sessions', projectId, networkId] })
    },
  })
}
