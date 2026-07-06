import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { createVectorSnapshot, getCollectionOverview, getVectorSnapshots, previewVectorSnapshot } from './vectorApi'
import type { CreateVectorSnapshotRequest, PreviewVectorSnapshotRequest } from './types'

export function useCollectionOverview(collectionId?: string, projectId?: string) {
  return useQuery({
    queryKey: ['collection-overview', collectionId, projectId],
    queryFn: () => {
      if (!collectionId || !projectId) throw new Error('Collection and Project are required')
      return getCollectionOverview(collectionId, projectId)
    },
    enabled: Boolean(collectionId && projectId),
    refetchInterval: (query) => query.state.data?.rag_status === 'BUILDING' ? 3000 : false,
  })
}

export function useVectorSnapshots(collectionId?: string, projectId?: string) {
  return useQuery({
    queryKey: ['vector-snapshots', collectionId, projectId],
    queryFn: () => {
      if (!collectionId || !projectId) throw new Error('Collection and Project are required')
      return getVectorSnapshots(collectionId, projectId)
    },
    enabled: Boolean(collectionId && projectId),
    refetchInterval: (query) => query.state.data?.some((snapshot) => snapshot.status === 'BUILDING') ? 3000 : false,
  })
}

export function usePreviewVectorSnapshot(collectionId?: string) {
  return useMutation({
    mutationFn: (data: PreviewVectorSnapshotRequest) => {
      if (!collectionId) throw new Error('Collection is required')
      return previewVectorSnapshot(collectionId, data)
    },
  })
}

export function useCreateVectorSnapshot(collectionId?: string, projectId?: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (data: CreateVectorSnapshotRequest) => {
      if (!collectionId) throw new Error('Collection is required')
      return createVectorSnapshot(collectionId, data)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['collection-overview', collectionId, projectId] })
      queryClient.invalidateQueries({ queryKey: ['vector-snapshots', collectionId, projectId] })
      queryClient.invalidateQueries({ queryKey: ['collections'] })
    },
  })
}
