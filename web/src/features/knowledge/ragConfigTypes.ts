export type RagChunkingPreset = 'precise' | 'balanced' | 'broad' | 'custom'
export type RagChunkingStrategy = 'recursive_text' | 'paragraph' | 'markdown_headings'
export type RagQueryMode = 'current_message' | 'conversation_context'
export type RagGroundingPolicy = 'optional' | 'required'

export interface RagParserConfig {
  implementation?: string
  version?: string
  normalize_whitespace: boolean
  preserve_page_boundaries: boolean
  include_docx_tables?: boolean
}

export interface RagChunkingConfig {
  preset: RagChunkingPreset
  strategy: RagChunkingStrategy
  chunk_size: number
  chunk_overlap: number
  min_chunk_size: number
  preserve_paragraphs: boolean
  preserve_headings: boolean
  preserve_page_boundaries: boolean
}

export interface RagRetrievalConfig {
  search_strategy: 'similarity'
  candidate_k: number
  top_k: number
  min_score: number | null
  max_context_chunks: number
  max_chunks_per_document: number
  max_context_chars: number
  query_mode: RagQueryMode
  history_turns: number
  grounding_policy: RagGroundingPolicy
}

export type RagRuntimeConfig = RagRetrievalConfig

export interface RagBuildConfig {
  parser: RagParserConfig
  chunking: RagChunkingConfig
}

export interface VectorBuildPreviewSample {
  document_id: string
  document_title: string
  chunk_index: number
  character_count: number
  preview: string
}

export interface VectorBuildPreview {
  document_count: number
  estimated_chunk_count: number
  estimated_vector_count: number
  sample_chunks: VectorBuildPreviewSample[]
}

export const CHUNKING_PRESETS: Record<RagChunkingPreset, Omit<RagChunkingConfig, 'preset'>> = {
  precise: {
    strategy: 'recursive_text',
    chunk_size: 500,
    chunk_overlap: 80,
    min_chunk_size: 80,
    preserve_paragraphs: true,
    preserve_headings: true,
    preserve_page_boundaries: true,
  },
  balanced: {
    strategy: 'recursive_text',
    chunk_size: 800,
    chunk_overlap: 120,
    min_chunk_size: 100,
    preserve_paragraphs: true,
    preserve_headings: true,
    preserve_page_boundaries: true,
  },
  broad: {
    strategy: 'recursive_text',
    chunk_size: 1200,
    chunk_overlap: 180,
    min_chunk_size: 150,
    preserve_paragraphs: true,
    preserve_headings: true,
    preserve_page_boundaries: true,
  },
  custom: {
    strategy: 'recursive_text',
    chunk_size: 800,
    chunk_overlap: 120,
    min_chunk_size: 100,
    preserve_paragraphs: true,
    preserve_headings: true,
    preserve_page_boundaries: true,
  },
}

export const DEFAULT_RETRIEVAL_CONFIG: RagRetrievalConfig = {
  search_strategy: 'similarity',
  candidate_k: 20,
  top_k: 5,
  min_score: null,
  max_context_chunks: 5,
  max_chunks_per_document: 2,
  max_context_chars: 24000,
  query_mode: 'conversation_context',
  history_turns: 3,
  grounding_policy: 'optional',
}
