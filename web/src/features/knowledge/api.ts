import { get, post } from '@/lib/api/client'
import type { Collection, CreateCollectionRequest, Document, UploadDocumentRequest } from './types'

export async function getCollections(projectId?: string): Promise<Collection[]> {
  return get<Collection[]>('/knowledge/collections', { params: { project_id: projectId } })
}

export async function getCollection(id: string): Promise<Collection> {
  return get<Collection>(`/knowledge/collections/${id}`)
}

export async function createCollection(data: CreateCollectionRequest): Promise<Collection> {
  return post<Collection>('/knowledge/collections', data)
}

export async function getDocuments(projectId?: string): Promise<Document[]> {
  return get<Document[]>('/knowledge/documents', { params: { project_id: projectId } })
}

export async function getDocument(id: string): Promise<Document> {
  return get<Document>(`/knowledge/documents/${id}`)
}

export async function uploadDocument(data: UploadDocumentRequest): Promise<Document> {
  return post<Document>('/knowledge/documents', data)
}
