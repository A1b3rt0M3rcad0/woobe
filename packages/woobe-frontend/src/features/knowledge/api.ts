import { get, post, patch, del } from '@/lib/api/client'
import type {
  AgentCollection,
  AttachCollectionRequest,
  Collection,
  CreateCollectionRequest,
  Document,
  UploadDocumentFileRequest,
  UpdateCollectionRequest,
  UploadDocumentRequest,
} from './types'

export async function getCollections(projectId?: string): Promise<Collection[]> {
  return get<Collection[]>('/knowledge/collections', { params: { project_id: projectId } })
}

export async function getCollection(id: string): Promise<Collection> {
  return get<Collection>(`/knowledge/collections/${id}`)
}

export async function createCollection(data: CreateCollectionRequest): Promise<Collection> {
  return post<Collection>('/knowledge/collections', data)
}

export async function updateCollection(id: string, data: UpdateCollectionRequest): Promise<Collection> {
  return patch<Collection>(`/knowledge/collections/${id}`, data)
}

export async function getAgentCollections(agentId: string): Promise<AgentCollection[]> {
  return get<AgentCollection[]>('/knowledge/agent-collections', { params: { agent_id: agentId } })
}

export async function attachCollection(data: AttachCollectionRequest): Promise<AgentCollection> {
  return post<AgentCollection>('/knowledge/agent-collections', data)
}

export async function detachCollection(id: string): Promise<void> {
  return del<void>(`/knowledge/agent-collections/${id}`)
}

export async function getDocuments(projectId?: string): Promise<Document[]> {
  return get<Document[]>('/knowledge/documents', { params: { project_id: projectId } })
}

export async function getDocumentsByCollection(collectionId: string): Promise<Document[]> {
  return get<Document[]>('/knowledge/documents', { params: { collection_id: collectionId } })
}

export async function getDocument(id: string): Promise<Document> {
  return get<Document>(`/knowledge/documents/${id}`)
}

export async function uploadDocument(data: UploadDocumentRequest): Promise<Document> {
  return post<Document>('/knowledge/documents', data)
}

export async function uploadDocumentFile(data: UploadDocumentFileRequest): Promise<Document> {
  const formData = new FormData()
  formData.append('project_id', data.projectId)
  formData.append('collection_id', data.collectionId)
  if (data.title?.trim()) {
    formData.append('title', data.title.trim())
  }
  formData.append('file', data.file)

  return post<Document>('/knowledge/documents/upload', formData)
}

export async function deleteDocument(id: string): Promise<void> {
  return del<void>(`/knowledge/documents/${id}`)
}
