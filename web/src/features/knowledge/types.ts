export interface Collection {
  id: string
  project_id: string
  name: string
  description?: string
  status?: string
  documents_count?: number
  indexed_documents_count?: number
  created_at?: string
  updated_at?: string
}

export interface CreateCollectionRequest {
  project_id: string
  name: string
  description?: string
}

export interface AgentCollection {
  id: string
  agent_id: string
  collection_id: string
  collection?: Collection
  created_at?: string
  updated_at?: string
}

export interface AttachCollectionRequest {
  agent_id: string
  collection_id: string
}

export interface Document {
  id: string
  project_id: string
  collection_id: string
  title: string
  file_name: string
  content_type: string
  size_bytes: number
  storage_key?: string
  parser?: string
  status: string
  page_count?: number
  chunk_count?: number
  sha256?: string
  indexed_at?: string
  error?: string
  created_at?: string
  updated_at?: string
}

export interface UploadDocumentRequest {
  project_id: string
  collection_id: string
  title: string
  file_name: string
  content_type: string
  size_bytes: number
  storage_key?: string
}

export interface UploadDocumentFileRequest {
  projectId: string
  collectionId: string
  title?: string
  file: File
}
