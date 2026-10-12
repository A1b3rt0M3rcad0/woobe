import { useQuery, type QueryClient } from '@tanstack/react-query'
import { get } from '@/lib/api/client'
import { getRelease } from '@/features/agents/api'
import type { AgentRelease } from '@/features/agents/types'
import { ownerPath, type ResourceKind } from './api'

export type SelectedEnvironment = 'staging' | 'production'
export interface EnvironmentCurrent {
  resource_id: string
  kind: ResourceKind
  environment: SelectedEnvironment
  snapshot_id: string | null
  environment_generation: number | null
  selection_authority: string
  remote_status: 'verified'
  complete: true
}
export const environmentSelectionKey = (projectId?: string, kind?: ResourceKind, resourceId?: string, environment?: SelectedEnvironment) =>
  ['environment-selection', projectId, kind, resourceId, environment] as const

// Environment assignment is independent of an immutable snapshot's stored status.
export function useEnvironmentSelection(projectId: string | undefined, kind: ResourceKind, resourceId: string | undefined, environment: SelectedEnvironment, enabled = true) {
  const query = useQuery({
    queryKey: environmentSelectionKey(projectId, kind, resourceId, environment),
    queryFn: async () => {
      const current = await get<EnvironmentCurrent>(ownerPath(projectId!, kind, resourceId!) + '/current', { params: { environment } })
      if (current.complete !== true || current.remote_status !== 'verified' || current.resource_id !== resourceId
          || current.kind !== kind || current.environment !== environment
          || !(current.snapshot_id === null || (typeof current.snapshot_id === 'string' && current.snapshot_id.length > 0))) {
        throw new Error('Environment selection could not be verified. Refresh before operating this environment.')
      }
      return current
    },
    enabled: enabled && Boolean(projectId && resourceId),
    staleTime: 15_000,
    refetchInterval: 30_000,
    refetchOnWindowFocus: 'always',
    refetchOnMount: 'always',
    retry: false,
  })
  const state = query.isError ? 'unknown' : !query.data ? 'loading' : query.data.snapshot_id === null ? 'empty' : 'selected'
  return { ...query, state, snapshotId: state === 'selected' ? query.data!.snapshot_id : null } as const
}

export function useSelectedAgentEnvironment(projectId: string | undefined, agentId: string | undefined, environment: SelectedEnvironment, enabled = true) {
  const selection = useEnvironmentSelection(projectId, 'Agent', agentId, environment, enabled)
  const details = useQuery({
    queryKey: ['environment-snapshot', projectId, 'Agent', agentId, selection.snapshotId],
    queryFn: async () => {
      const release = await getRelease(agentId!, selection.snapshotId!)
      if (release.id !== selection.snapshotId || release.agent_id !== agentId || release.project_id !== projectId) {
        throw new Error('Selected snapshot details do not match this Agent and Project.')
      }
      return release
    },
    enabled: enabled && selection.state === 'selected',
    staleTime: Infinity, // Immutable details; never substitute mutable Draft or latest Release.
    retry: false,
  })
  const snapshot: AgentRelease | null = selection.state === 'selected' && !details.isError ? details.data ?? null : null
  const detailState = details.isError ? 'unknown' : snapshot ? 'ready' : 'loading'
  return { ...selection, snapshot, detailState, retry: async () => {
    const refreshed = await selection.refetch()
    if (selection.snapshotId && refreshed.data?.snapshot_id === selection.snapshotId && details.isError) await details.refetch()
  } } as const
}

export function selectionMessage(selection: { state: string; snapshotId: string | null; detailState?: string }, environment: string): string {
  if (selection.state === 'loading') return `Checking ${environment} selection…`
  if (selection.state === 'unknown') return `${environment} selection unavailable. Retry to verify the current deployment.`
  if (selection.state === 'empty') return `No ${environment} deployment. Publish an immutable Release, then deploy it to this environment.`
  if (selection.detailState === 'unknown') return `${environment} selected snapshot ${selection.snapshotId}; details unavailable. Retry to load its configuration.`
  return `${environment} selected snapshot ${selection.snapshotId}; loading configuration…`
}

export function invalidateEnvironmentSelection(client: QueryClient) {
  // A lifecycle write may affect both environments, catalogs, keys and embedded views.
  return Promise.all([
    client.invalidateQueries({ queryKey: ['environment-selection'] }),
    client.invalidateQueries({ queryKey: ['environment-snapshot'] }),
    client.invalidateQueries({ queryKey: ['agent-runtime-environments'] }),
    client.invalidateQueries({ queryKey: ['agents'] }),
  ])
}
