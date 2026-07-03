import { get, post } from '@/lib/api/client'
import type { CollectionOverview, CreateVectorSnapshotRequest, VectorSnapshot } from './types'

export async function getCollectionOverview(collectionId: string, projectId: string): Promise<CollectionOverview> {
  return get<CollectionOverview>(`/agent/knowledge/collections/${collectionId}/overview`, { params: { project_id: projectId } })
}

export async function getVectorSnapshots(collectionId: string, projectId: string): Promise<VectorSnapshot[]> {
  return get<VectorSnapshot[]>(`/agent/knowledge/collections/${collectionId}/vector-snapshots`, { params: { project_id: projectId } })
}

export async function createVectorSnapshot(collectionId: string, data: CreateVectorSnapshotRequest): Promise<VectorSnapshot> {
  return post<VectorSnapshot>(`/agent/knowledge/collections/${collectionId}/vector-snapshots`, data)
}
