import { sha256 } from '@noble/hashes/sha256'
import { bytesToHex } from '@noble/hashes/utils'
import { createUuid } from '@/lib/uuid'
import {
  beginArtifactUpload,
  finalizeArtifactUpload,
  getArtifactUploadStatus,
  uploadArtifactPart,
} from './api'
import type { ArtifactCapabilities, ArtifactEnvironment } from './types'

interface UploadScope {
  projectId: string
  environment: ArtifactEnvironment
}

export async function sha256File(file: File, chunkBytes = 1024 * 1024, signal?: AbortSignal): Promise<string> {
  const hash = sha256.create()
  for (let offset = 0; offset < file.size; offset += chunkBytes) {
    signal?.throwIfAborted()
    const bytes = new Uint8Array(await file.slice(offset, offset + chunkBytes).arrayBuffer())
    hash.update(bytes)
  }
  return bytesToHex(hash.digest())
}

export async function uploadArtifactFile(
  scope: UploadScope,
  workspaceId: string,
  file: File,
  path: string,
  capabilities: ArtifactCapabilities,
  onProgress?: (uploadedBytes: number) => void,
  operationId = createUuid(),
  signal?: AbortSignal,
) {
  signal?.throwIfAborted()
  if (file.size > capabilities.max_upload_bytes) {
    throw new Error(`File exceeds the ${capabilities.max_upload_bytes} byte upload limit`)
  }
  const partBytes = capabilities.max_upload_part_bytes
  if (!Number.isSafeInteger(partBytes) || partBytes < 1) throw new Error('Server upload part limit is unavailable')
  const partCount = Math.ceil(file.size / partBytes)
  if (partCount > capabilities.max_upload_parts) throw new Error('File requires more upload parts than the server allows')

  const digest = await sha256File(file, 1024 * 1024, signal)
  signal?.throwIfAborted()
  const upload = await beginArtifactUpload(scope, workspaceId, {
    schema_version: '1',
    operation_id: operationId,
    path,
    size_bytes: file.size,
    sha256: digest,
    content_type: file.type || 'application/octet-stream',
  }, signal)
  if (upload.status === 'committed') return upload
  if (!['created', 'uploading'].includes(upload.status)) {
    throw new Error(`Upload cannot continue from ${upload.status}`)
  }

  let offset = upload.offset
  if (offset < 0 || offset > file.size) throw new Error('Upload receipt has an invalid offset')
  onProgress?.(offset)
  while (offset < file.size) {
    signal?.throwIfAborted()
    const end = Math.min(file.size, offset + partBytes)
    const chunk = file.slice(offset, end)
    try {
      const updated = await uploadArtifactPart(scope, workspaceId, upload.id, offset, chunk, signal)
      if (updated.offset !== end) throw new Error('Server acknowledged an unexpected upload offset')
      offset = end
    } catch (error) {
      if (signal?.aborted) throw error
      // Resolve a lost ACK by asking the server for the committed offset before
      // repeating a mutation. The same byte range is safe to retry only when
      // the server confirms it has not advanced.
      const current = await getArtifactUploadStatus(scope, workspaceId, upload.id, signal)
      if (current.offset === end) offset = end
      else if (current.offset === offset) {
        const retried = await uploadArtifactPart(scope, workspaceId, upload.id, offset, chunk, signal)
        if (retried.offset !== end) throw new Error('Server acknowledged an unexpected upload offset')
        offset = end
      } else {
        throw error
      }
    }
    onProgress?.(offset)
  }

  try {
    signal?.throwIfAborted()
    return await finalizeArtifactUpload(scope, workspaceId, upload.id, signal)
  } catch (error) {
    if (signal?.aborted) throw error
    const current = await getArtifactUploadStatus(scope, workspaceId, upload.id, signal)
    if (current.status === 'committed' && current.receipt) return current
    throw error
  }
}
