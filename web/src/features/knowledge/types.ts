import type { RagBuildConfig, RagChunkingConfig, RagParserConfig, VectorBuildPreview } from './ragConfigTypes'

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

export interface UpdateCollectionRequest {
  name?: string
  description?: string | null
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

export interface VectorSnapshot {
  id: string
  project_id: string
  collection_id: string
  version: string
  description?: string | null
  status: string
  build_stage?: string
  embedding_provider_model_id: string
  embedding_provider: string
  embedding_model: string
  embedding_dimensions: number
  chunk_size: number
  chunk_overlap: number
  chunking_strategy: string
  parser_config?: Record<string, unknown> | null
  build_config?: Record<string, unknown> | null
  snapshot_hash?: string | null
  build_config_hash?: string | null
  document_count: number
  chunk_count: number
  vector_count?: number
  total_document_count?: number
  processed_document_count?: number
  total_chunk_count?: number
  processed_chunk_count?: number
  embedded_chunk_count?: number
  current_document_id?: string | null
  error_message?: string | null
  created_by?: string | null
  started_at?: string | null
  completed_at?: string | null
  created_at?: string
  updated_at?: string
}

export interface CollectionOverview {
  collection_id: string
  project_id: string
  rag_status: string
  documents: { active: number; ready: number; failed: number; pending: number; deleted: number; total_size_bytes: number }
  latest_snapshot?: VectorSnapshot | null
  latest_ready_snapshot?: VectorSnapshot | null
  processing: { has_running_job: boolean; stage?: string | null; processed_documents: number; total_documents: number; processed_chunks: number; total_chunks: number; embedded_chunks: number }
  technology: { embedding_provider_model_id?: string | null; embedding_provider?: string | null; embedding_model?: string | null; embedding_dimensions?: number | null; chunking_strategy?: string | null; chunk_size?: number | null; chunk_overlap?: number | null; vector_store: string; distance_metric: string }
  warnings: string[]
}

export interface CreateVectorSnapshotRequest {
  project_id: string
  embedding_provider_model_id: string
  version?: string
  description?: string
  chunk_size?: number
  chunk_overlap?: number
  chunking_strategy?: string
  parser_config?: RagParserConfig
  build_config?: RagBuildConfig
}

export interface PreviewVectorSnapshotRequest {
  project_id: string
  parser: RagParserConfig
  chunking: RagChunkingConfig
}

export type { VectorBuildPreview }
