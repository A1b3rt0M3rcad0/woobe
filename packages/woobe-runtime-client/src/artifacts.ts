import { RuntimeStreamProtocolError } from './protocol'
import type {
  ArtifactAvailable,
  ArtifactOutput,
  ArtifactProcessingJob,
  ArtifactProcessingStatus,
  ArtifactReference,
  ArtifactTransfer,
  ContentPart,
  ParsedRuntimeFrame,
  RuntimeCursorPage,
  SourceRef,
} from './types'

const identifierPattern = /^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$/
const sha256Pattern = /^[0-9a-f]{64}$/
const processingStatuses = new Set<ArtifactProcessingStatus>([
  'queued', 'running', 'succeeded', 'failed', 'cancel_requested', 'cancelled', 'uncertain',
])
const transferStates = new Set(['started', 'completed', 'failed', 'uncertain'])

function record(value: unknown): Record<string, unknown> | null {
  return value !== null && typeof value === 'object' && !Array.isArray(value)
    ? value as Record<string, unknown>
    : null
}

function invalid(message: string): never {
  throw new RuntimeStreamProtocolError(message)
}

function exactReference(value: unknown, allowAdditive = false): ArtifactReference {
  const source = record(value)
  if (!source) invalid('Invalid Artifact revision reference')
  if (!allowAdditive && Object.keys(source).some(key => key !== 'artifact_id' && key !== 'revision_id')) {
    invalid('Artifact revision references cannot contain additional fields')
  }
  const artifactId = source.artifact_id
  const revisionId = source.revision_id
  if (typeof artifactId !== 'string' || !identifierPattern.test(artifactId)
      || typeof revisionId !== 'string' || !identifierPattern.test(revisionId)) {
    invalid('Artifact references require exact opaque artifact and revision IDs')
  }
  return { ...source, artifact_id: artifactId, revision_id: revisionId }
}

function validMediaType(value: unknown): value is string {
  if (typeof value !== 'string' || !value || value.length > 255 || /[^\x20-\x7e]/.test(value)) return false
  const [essence, ...parameters] = value.split(';')
  const token = "[!#$%&'*+.^_`|~0-9A-Za-z-]+"
  if (!new RegExp(`^${token}/${token}$`).test(essence.trim())) return false
  return parameters.every(parameter => {
    const match = parameter.trim().match(new RegExp(`^(${token})=(?:(${token})|"([^"\\\\]|\\\\[\\x20-\\x7e])*")$`))
    return match !== null
  })
}

/** Parse an exact opaque Artifact and revision identity. URLs and workspace IDs are not refs. */
export function parseArtifactReference(value: unknown): ArtifactReference {
  return exactReference(value)
}

export function parseSourceRef(value: unknown): SourceRef {
  const source = record(value)
  if (!source) invalid('Invalid Artifact SourceRef')
  const ref = exactReference(source, true)
  if (typeof source.source_sha256 !== 'string' || !sha256Pattern.test(source.source_sha256)) {
    invalid('Artifact SourceRef requires a lowercase SHA-256 digest')
  }
  if (source.excerpt_sha256 !== undefined && source.excerpt_sha256 !== null
      && (typeof source.excerpt_sha256 !== 'string' || !sha256Pattern.test(source.excerpt_sha256))) {
    invalid('Artifact SourceRef excerpt digest must be lowercase SHA-256')
  }
  if (source.locator !== undefined && source.locator !== null) {
    const locator = record(source.locator)
    if (!locator) invalid('Invalid Artifact SourceRef locator')
    for (const key of ['block_id', 'page_label']) {
      const item = locator[key]
      if (item !== undefined && item !== null && typeof item !== 'string') {
        invalid(`Invalid Artifact SourceRef locator ${key}`)
      }
    }
    for (const key of ['page_index', 'page_number', 'line_start', 'line_end', 'char_start', 'char_end']) {
      const item = locator[key]
      if (item !== undefined && item !== null && (!Number.isSafeInteger(item) || (item as number) < 0)) {
        invalid(`Invalid Artifact SourceRef locator ${key}`)
      }
    }
  }
  return { ...source, ...ref, source_sha256: source.source_sha256 } as SourceRef
}

function parseContentPart(value: unknown): ContentPart {
  const part = record(value)
  if (!part) invalid('Invalid runtime content part')
  const keys = Object.keys(part)
  if (keys.some(key => !['type', 'text', 'ref', 'media_type_hint'].includes(key))) {
    invalid('Runtime content parts cannot contain unknown fields')
  }
  if (part.type === 'text') {
    if (typeof part.text !== 'string' || part.text.length === 0 || part.ref !== undefined
        || part.media_type_hint !== undefined) {
      invalid('Text content parts require only non-empty text')
    }
    return { type: 'text', text: part.text }
  }
  if (part.type === 'artifact') {
    if (part.text !== undefined || part.ref === undefined) {
      invalid('Artifact content parts require exactly one revision reference')
    }
    let mediaTypeHint: string | undefined
    if (part.media_type_hint !== undefined) {
      if (!validMediaType(part.media_type_hint)) invalid('Invalid Artifact media type hint')
      mediaTypeHint = part.media_type_hint
    }
    return {
      type: 'artifact',
      ref: parseArtifactReference(part.ref),
      ...(mediaTypeHint === undefined ? {} : { media_type_hint: mediaTypeHint }),
    }
  }
  return invalid('Unsupported runtime content part type')
}

/** Validate bounded ordered text and Artifact references without performing I/O. */
export function parseContentParts(value: unknown): ContentPart[] {
  if (!Array.isArray(value) || value.length < 1 || value.length > 32) {
    invalid('content_parts must contain 1–32 parts')
  }
  const parts = value.map(parseContentPart)
  let textCharacters = 0
  let artifactCount = 0
  let hasContent = false
  for (const part of parts) {
    if (part.type === 'text') {
      const count = Array.from(part.text).length
      if (count > 32768) invalid('A text content part exceeds 32768 characters')
      textCharacters += count
      hasContent ||= part.text.trim().length > 0
    } else {
      artifactCount++
      hasContent = true
    }
  }
  if (textCharacters > 32768) invalid('Combined message text exceeds 32768 characters')
  if (artifactCount > 16) invalid('A message can reference at most 16 Artifacts')
  if (!hasContent) invalid('content_parts must contain text or an Artifact reference')
  return parts
}

export function parseArtifactOutput(value: unknown): ArtifactOutput {
  const output = record(value)
  if (!output || output.schema_version !== '1' || output.status !== 'available') {
    invalid('Invalid versioned Artifact output receipt')
  }
  if (typeof output.path !== 'string' || !output.path || !validMediaType(output.content_type)) {
    invalid('Artifact output requires a path and valid content type')
  }
  if (!Number.isSafeInteger(output.size_bytes) || (output.size_bytes as number) < 0) {
    invalid('Artifact output size_bytes must be a non-negative safe integer')
  }
  if (typeof output.sha256 !== 'string' || !sha256Pattern.test(output.sha256)) {
    invalid('Artifact output requires a lowercase SHA-256 digest')
  }
  const sourceRefs = output.source_refs === undefined ? [] : output.source_refs
  if (!Array.isArray(sourceRefs)) invalid('Artifact output source_refs must be an array')
  for (const field of ['run_id', 'node_id']) {
    const item = output[field]
    if (item !== undefined && item !== null && typeof item !== 'string') {
      invalid(`Artifact output ${field} must be a string or null`)
    }
  }
  return {
    ...output,
    schema_version: '1',
    ref: parseArtifactReference(output.ref),
    path: output.path,
    content_type: output.content_type,
    size_bytes: output.size_bytes as number,
    sha256: output.sha256,
    status: 'available',
    source_refs: sourceRefs.map(parseSourceRef),
  } as ArtifactOutput
}

/** Decode an availability event into its metadata receipt; never fetch artifact bytes. */
export function artifactAvailableFromFrame(frame: ParsedRuntimeFrame): ArtifactAvailable | null {
  if (frame.kind !== 'semantic' || !['artifact.available', 'artifact_available'].includes(frame.eventType)) {
    return null
  }
  const payload = frame.payload
  const nestedRef = payload.ref === undefined ? null : exactReference(payload.ref)
  const artifactId = payload.artifact_id ?? nestedRef?.artifact_id
  const revisionId = payload.revision_id ?? nestedRef?.revision_id
  const ref = exactReference({ artifact_id: artifactId, revision_id: revisionId })
  if (nestedRef && (nestedRef.artifact_id !== ref.artifact_id || nestedRef.revision_id !== ref.revision_id)) {
    invalid('artifact.available has conflicting revision identities')
  }
  if (payload.run_id !== undefined && payload.run_id !== null && payload.run_id !== frame.runId) {
    invalid('artifact.available Run identity differs from its event envelope')
  }
  const output = parseArtifactOutput({
    ...payload,
    schema_version: payload.schema_version ?? '1',
    ref,
    run_id: payload.run_id ?? frame.runId,
  })
  return {
    ...output,
    artifact_id: ref.artifact_id,
    revision_id: ref.revision_id,
  }
}

/** Return terminal or run.state receipts as a replacement collection, including an empty list. */
export function artifactOutputsFromFrame(frame: ParsedRuntimeFrame): ArtifactOutput[] {
  if (frame.kind !== 'semantic') return []
  if (!['done', 'execution_completed', 'run.state'].includes(frame.eventType)) return []
  const result = record(frame.payload.result)
  const value = frame.payload.output_artifacts ?? result?.output_artifacts ?? []
  if (!Array.isArray(value)) invalid('Runtime output_artifacts must be an array')
  return value.map(parseArtifactOutput)
}

/** A returned run.state payload is the complete current snapshot; callers should replace old state with it. */
export function runtimeRunStateSnapshot(frame: ParsedRuntimeFrame): Record<string, unknown> | null {
  return frame.kind === 'semantic' && frame.eventType === 'run.state'
    ? { ...frame.payload }
    : null
}

export function parseArtifactTransfer(value: unknown): ArtifactTransfer {
  const transfer = record(value)
  if (!transfer || typeof transfer.operation_id !== 'string' || !transfer.operation_id.trim()
      || typeof transfer.state !== 'string' || !transferStates.has(transfer.state)) {
    invalid('Artifact transfer is missing an operation identity or valid state')
  }
  const inputRefs = transfer.input_refs ?? []
  const fileHashes = transfer.file_hashes ?? []
  if (!Array.isArray(inputRefs) || !Array.isArray(fileHashes)
      || fileHashes.some(item => !record(item))) {
    invalid('Artifact transfer inputs are invalid')
  }
  if (transfer.status_code !== undefined && transfer.status_code !== null
      && (!Number.isSafeInteger(transfer.status_code) || (transfer.status_code as number) < 0)) {
    invalid('Artifact transfer status_code is invalid')
  }
  for (const field of ['mode', 'destination_host', 'tool_id']) {
    if (transfer[field] !== undefined && transfer[field] !== null && typeof transfer[field] !== 'string') {
      invalid(`Artifact transfer ${field} must be a string or null`)
    }
  }
  return {
    ...transfer,
    operation_id: transfer.operation_id,
    state: transfer.state as ArtifactTransfer['state'],
    input_refs: inputRefs.map(parseArtifactReference),
    file_hashes: fileHashes as Record<string, unknown>[],
  } as ArtifactTransfer
}

export function artifactTransferFromFrame(frame: ParsedRuntimeFrame): ArtifactTransfer | null {
  if (frame.kind !== 'semantic'
      || (frame.eventType !== 'artifact_transfer' && !frame.eventType.startsWith('artifact.transfer.'))) {
    return null
  }
  const stateByEvent: Record<string, string> = {
    'artifact.transfer.started': 'started',
    'artifact.transfer.completed': 'completed',
    'artifact.transfer.failed': 'failed',
    'artifact.transfer.uncertain': 'uncertain',
  }
  const transfer = parseArtifactTransfer(frame.payload)
  const expected = stateByEvent[frame.eventType]
  if (expected && transfer.state !== expected) invalid('Artifact transfer state differs from its event type')
  return transfer
}

export function parseArtifactProcessingJob(value: unknown): ArtifactProcessingJob {
  const job = record(value)
  if (!job || typeof job.id !== 'string' || !job.id.trim()
      || typeof job.status !== 'string' || !processingStatuses.has(job.status as ArtifactProcessingStatus)) {
    invalid('Invalid Artifact processing job identity or status')
  }
  const completedStages = job.completed_stages ?? []
  if (!Array.isArray(completedStages) || completedStages.some(stage => typeof stage !== 'string')) {
    invalid('Artifact processing completed_stages must be a string array')
  }
  if (job.retryable !== undefined && typeof job.retryable !== 'boolean') {
    invalid('Artifact processing retryable must be a boolean')
  }
  if (job.result !== undefined && job.result !== null && !record(job.result)) {
    invalid('Artifact processing result must be an object or null')
  }
  return {
    ...job,
    id: job.id,
    source: parseArtifactReference(job.source),
    status: job.status as ArtifactProcessingStatus,
    completed_stages: completedStages as string[],
  } as ArtifactProcessingJob
}

/** Validate a cursor page while leaving the cursor opaque and making no request. */
export function parseRuntimeCursorPage<T>(value: unknown, parseItem: (item: unknown) => T): RuntimeCursorPage<T> {
  const page = record(value)
  if (!page || !Array.isArray(page.items) || typeof page.has_more !== 'boolean'
      || typeof page.next_cursor !== 'string' || typeof page.truncated !== 'boolean') {
    invalid('Invalid runtime cursor page')
  }
  return { ...page, items: page.items.map(parseItem), has_more: page.has_more,
    next_cursor: page.next_cursor, truncated: page.truncated }
}

