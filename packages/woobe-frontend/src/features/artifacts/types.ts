export type ArtifactEnvironment = 'draft' | 'staging' | 'production'
export type ArtifactWorkspaceStatus = 'active' | 'archived' | 'deletion_pending' | 'purged'
export type ArtifactKind = 'file' | 'directory'

export interface ArtifactComposerContext {
  projectId: string
  environment: ArtifactEnvironment
  workspaceId: string
  accountWorkspaceId?: string
  actions?: string[]
}

export interface ArtifactWorkspace {
  schema_version: '1'
  id: string
  project_id: string
  environment: ArtifactEnvironment
  external_namespace: string
  external_key: string
  name: string
  storage_profile: string
  quota_bytes: number
  retention_days: number
  labels: Record<string, string>
  status: ArtifactWorkspaceStatus
  version: number
  catalog_version: number
  used_bytes: number
  reserved_bytes: number
  default_profile_id?: string | null
  default_profile_revision?: number | null
}

export interface ArtifactWorkspacePage {
  schema_version: '1'
  items: ArtifactWorkspace[]
  has_more: boolean
  next_cursor: string | null
  truncated: boolean
}

export interface ArtifactRevision {
  schema_version: '1'
  id: string
  artifact_id: string
  content_type: string
  size_bytes: number
  sha256: string
  origin: 'upload' | 'application' | 'agent' | 'tool' | 'processing' | 'copy'
  producer_id?: string | null
  operation_id?: string | null
  run_id?: string | null
  node_id?: string | null
  source_representation_set_id?: string | null
  source_representation_entry_id?: string | null
}

export interface ArtifactFile {
  schema_version: '1'
  id: string
  workspace_id: string
  path: string
  kind: ArtifactKind
  revision_id: string | null
  version: number
  deleted: boolean
  revision: ArtifactRevision | null
}

export interface ArtifactPage {
  schema_version: '1'
  items: ArtifactFile[]
  has_more: boolean
  next_cursor: string | null
  truncated: boolean
}

export interface ArtifactRevisionHistoryPage {
  schema_version: '1'
  items: Array<ArtifactRevision & { created_at: string }>
  has_more: boolean
  next_cursor: string | null
  truncated: boolean
}

export interface ArtifactCapabilities {
  schema_version: '1'
  max_upload_bytes: number
  max_upload_part_bytes: number
  max_upload_parts: number
  max_inline_bytes: number
  max_request_bytes: number
  storage_readiness: 'not_probed' | 'ready' | 'unavailable'
  media_types: string[]
  downloads: string[]
}

export interface ArtifactUploadStatus {
  schema_version: '1'
  id: string
  workspace_id: string
  operation_id: string
  expected_size: number
  offset: number
  status: 'created' | 'uploading' | 'verifying' | 'committed' | 'failed' | 'aborted' | 'expired'
  expires_at: string
  receipt: { artifact_id: string; revision_id: string } | null
}

export interface CreateArtifactWorkspaceRequest {
  schema_version: '1'
  environment: ArtifactEnvironment
  external_namespace: string
  external_key: string
  name: string
  storage_profile?: string
  quota_bytes?: number
  retention_days?: number
  labels?: Record<string, string>
}

export interface DocumentIndex {
  schema_version: '1'
  id: string
  workspace_id: string
  artifact_id: string
  revision_id: string
  representation_set_id: string
  source_sha256: string
  recipe_fingerprint: string
  processing_fingerprint: string
  engine: string
  engine_version: string
  status: 'ready'
  tree_kind: 'headings' | 'canonical' | 'pages' | 'blocks' | 'empty'
  coverage: 'complete' | 'partial' | 'needs_ocr' | 'unsupported'
  root_node_id: string
  node_count: number
  source_block_count: number
  max_depth: number
  manifest_sha256: string
  created_at: string
}

export interface SourceLocator {
  block_id?: string | null
  page_index?: number | null
  page_number?: number | null
  line_start?: number | null
  line_end?: number | null
  char_start?: number | null
  char_end?: number | null
  bbox?: [number, number, number, number] | null
  page_label?: string | null
}

export interface SourceReference {
  artifact_id: string
  revision_id: string
  source_sha256: string
  representation_set_id?: string | null
  document_index_id?: string | null
  node_id?: string | null
  locator?: SourceLocator | null
  excerpt_sha256?: string | null
}

export interface DocumentNode {
  schema_version: '1'
  id: string
  document_index_id: string
  representation_set_id: string
  parent_id: string | null
  title: string
  kind: 'root' | 'section' | 'page' | 'block'
  ordinal: number
  depth: number
  children_count: number
  source_ranges: [number, number][]
  source: SourceReference | null
  has_own_text: boolean
  inferred: boolean
  extraction_method: 'native' | 'ocr' | 'model' | null
}

export interface DocumentNodePage {
  schema_version: '1'
  items: DocumentNode[]
  has_more: boolean
  next_cursor: string | null
  truncated: boolean
}

export interface SourceRead {
  schema_version: '1'
  source: SourceReference
  text: string
  offset: number
  next_offset: number | null
  truncated: boolean
  coverage: 'complete' | 'partial' | 'needs_ocr' | 'unsupported'
  page_label: string | null
}

export interface RepresentationEntry {
  schema_version: '1'
  id: string
  representation_set_id: string
  path: string
  kind: string
  size_bytes: number
  sha256: string
  content_type: string
  asset_id: string | null
}

export interface RepresentationEntryPage {
  schema_version: '1'
  items: RepresentationEntry[]
  has_more: boolean
  next_cursor: string | null
  truncated: boolean
}
