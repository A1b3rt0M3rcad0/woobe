import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { createVectorSnapshot, getCollectionOverview, getVectorSnapshots } from './vectorApi'
import type { CreateVectorSnapshotRequest } from './types'

export function useCollectionOverview(collectionId?: string, projectId?: string) {
  return useQuery({
    queryKey: ['collection-overview', collectionId, projectId],
    queryFn: () => getCollectionOverview(collectionId!, projectId!),
    enabled: Boolean(collectionId) && Boolean(projectId),
    refetchInterval: (query) => query.state.data?.rag_status === 'BUILDING' ? 3000 : false,
  })
}

export function useVectorSnapshots(collectionId?: string, projectId?: string) {
  return useQuery({
    queryKey: ['vector-snapshots', collectionId, projectId],
    queryFn: () => getVectorSnapshots(collectionId!, projectId!),
    enabled: Boolean(collectionId) && Boolean(projectId),
    refetchInterval: (query) => query.state.data?.some((snapshot) => snapshot.status === 'BUILDING') ? 3000 : false,
  })
}

export function useCreateVectorSnapshot(collectionId?: string, projectId?: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (data: CreateVectorSnapshotRequest) => createVectorSnapshot(collectionId!, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['collection-overview', collectionId, projectId] })
      queryClient.invalidateQueries({ queryKey: ['vector-snapshots', collectionId, projectId] })
      queryClient.invalidateQueries({ queryKey: ['collections'] })
    },
  })
}
