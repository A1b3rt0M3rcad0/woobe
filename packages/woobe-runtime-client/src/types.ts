export type RuntimeTerminalStatus =
  | 'completed'
  | 'failed'
  | 'cancelled'
  | 'timed_out'
  | 'uncertain'

export interface RuntimeSequenceState {
  sequence: number | null
  runId?: string | null
  sessionId?: string | null
  runKind?: 'AGENT' | 'NETWORK' | null
}

interface RuntimeFrameBase {
  type: string
  eventType: string
  payload: Record<string, unknown>
  occurredAt: string
}

export interface WoobeEvent extends RuntimeFrameBase {
  kind: 'semantic'
  eventId: string
  runId: string
  sessionId: string
  runKind: 'AGENT' | 'NETWORK'
  sequence: number
}

export interface RuntimeControlFrame extends RuntimeFrameBase {
  kind: 'transport'
  sequence: null
}

export type ParsedRuntimeFrame = WoobeEvent | RuntimeControlFrame

export interface RuntimeOutputReconciliation {
  output: string
  append: string
  retract: number
  changed: boolean
}

export interface ArtifactReference {
  artifact_id: string
  revision_id: string
  [key: string]: unknown
}

export interface SourceLocator {
  block_id?: string | null
  page_index?: number | null
  page_number?: number | null
  line_start?: number | null
  line_end?: number | null
  char_start?: number | null
  char_end?: number | null
  page_label?: string | null
  [key: string]: unknown
}

export interface SourceRef extends ArtifactReference {
  source_sha256: string
  representation_set_id?: string | null
  document_index_id?: string | null
  node_id?: string | null
  locator?: SourceLocator | null
  excerpt_sha256?: string | null
  [key: string]: unknown
}

export type ContentPart =
  | { type: 'text'; text: string }
  | { type: 'artifact'; ref: ArtifactReference; media_type_hint?: string }

export interface ArtifactOutput {
  schema_version: '1'
  ref: ArtifactReference
  path: string
  content_type: string
  size_bytes: number
  sha256: string
  status: 'available'
  run_id?: string | null
  node_id?: string | null
  source_refs: SourceRef[]
  [key: string]: unknown
}

export interface ArtifactAvailable extends ArtifactOutput {
  producer_id?: string | null
  artifact_id: string
  revision_id: string
}

export type ArtifactProcessingStatus =
  | 'queued'
  | 'running'
  | 'succeeded'
  | 'failed'
  | 'cancel_requested'
  | 'cancelled'
  | 'uncertain'

export interface ArtifactProcessingJob {
  id: string
  source: ArtifactReference
  status: ArtifactProcessingStatus
  completed_stages?: string[]
  retryable?: boolean
  result?: Record<string, unknown> | null
  [key: string]: unknown
}

export interface ArtifactTransfer {
  operation_id: string
  state: 'started' | 'completed' | 'failed' | 'uncertain'
  mode?: string
  destination_host?: string
  input_refs: ArtifactReference[]
  file_hashes: Record<string, unknown>[]
  status_code?: number | null
  tool_id?: string | null
  [key: string]: unknown
}

/** Cursor tokens are opaque. `truncated` describes coverage, not pagination. */
export interface RuntimeCursorPage<T> {
  items: T[]
  has_more: boolean
  next_cursor: string
  truncated: boolean
  [key: string]: unknown
}
