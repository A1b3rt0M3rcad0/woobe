import { del, get, getBlob, patch, post, put } from '@/lib/api/client'
import type {
  ArtifactCapabilities,
  ArtifactEnvironment,
  ArtifactFile,
  ArtifactPage,
  ArtifactRevisionHistoryPage,
  ArtifactUploadStatus,
  ArtifactWorkspace,
  ArtifactWorkspacePage,
  CreateArtifactWorkspaceRequest,
  DocumentIndex,
  DocumentNode,
  DocumentNodePage,
  RepresentationEntryPage,
  SourceRead,
} from './types'

interface Scope {
  projectId: string
  environment: ArtifactEnvironment
}

function scopeParams(scope: Scope) {
  return { project_id: scope.projectId, environment: scope.environment }
}

function workspacePath(workspaceId: string) {
  return `/v1/artifact-workspaces/${encodeURIComponent(workspaceId)}`
}

export function listArtifactWorkspaces(
  scope: Scope,
  options: { cursor?: string | null; limit?: number; externalNamespace?: string } = {},
) {
  return get<ArtifactWorkspacePage>('/v1/artifact-workspaces', {
    params: {
      ...scopeParams(scope),
      limit: options.limit ?? 50,
      cursor: options.cursor ?? undefined,
      external_namespace: options.externalNamespace,
    },
  })
}

export function getArtifactWorkspace(scope: Scope, workspaceId: string) {
  return get<ArtifactWorkspace>(workspacePath(workspaceId), { params: scopeParams(scope) })
}

export function resolveArtifactWorkspace(scope: Scope, externalNamespace: string, externalKey: string) {
  return get<ArtifactWorkspace>('/v1/artifact-workspaces/resolve', {
    params: { ...scopeParams(scope), external_namespace: externalNamespace, external_key: externalKey },
  })
}

export function createArtifactWorkspace(scope: Scope, body: CreateArtifactWorkspaceRequest) {
  return post<ArtifactWorkspace>('/v1/artifact-workspaces', body, { params: scopeParams(scope) })
}

export function getArtifactCapabilities(scope: Scope, signal?: AbortSignal) {
  return get<ArtifactCapabilities>('/v1/artifact-capabilities', { params: scopeParams(scope), signal })
}

export function getArtifactProcessingCapabilities(scope: Scope) {
  return get<{ schema_version: '1'; components: Array<{ name: string; role: string; ready: boolean; media_types?: string[]; reason?: string }>; store_only: boolean }>(
    '/v1/artifact-processing-capabilities', { params: scopeParams(scope) },
  )
}

export function listArtifacts(
  scope: Scope,
  workspaceId: string,
  options: { directory?: string; cursor?: string | null; limit?: number } = {},
) {
  return get<ArtifactPage>(`${workspacePath(workspaceId)}/artifacts`, {
    params: {
      ...scopeParams(scope),
      directory: options.directory ?? '',
      limit: options.limit ?? 100,
      cursor: options.cursor ?? undefined,
    },
  })
}

export function listArtifactRevisions(
  scope: Scope,
  workspaceId: string,
  artifactId: string,
  options: { cursor?: string | null; limit?: number } = {},
) {
  return get<ArtifactRevisionHistoryPage>(`${workspacePath(workspaceId)}/artifacts/${encodeURIComponent(artifactId)}/revisions`, {
    params: { ...scopeParams(scope), limit: options.limit ?? 50, cursor: options.cursor ?? undefined },
  })
}

export function createArtifactDirectory(
  scope: Scope,
  workspaceId: string,
  path: string,
  operationId: string,
) {
  return post<ArtifactFile>(`${workspacePath(workspaceId)}/artifacts`, {
    operation_id: operationId,
    kind: 'directory',
    path,
  }, { params: scopeParams(scope) })
}

export function moveArtifact(
  scope: Scope,
  workspaceId: string,
  artifactId: string,
  path: string,
  expectedVersion: number,
  operationId: string,
) {
  return patch<ArtifactFile>(`${workspacePath(workspaceId)}/artifacts/${encodeURIComponent(artifactId)}`, {
    operation_id: operationId,
    expected_version: expectedVersion,
    path,
  }, { params: scopeParams(scope) })
}

export function deleteArtifact(
  scope: Scope,
  workspaceId: string,
  artifactId: string,
  expectedVersion: number,
  operationId: string,
) {
  return del<ArtifactFile>(`${workspacePath(workspaceId)}/artifacts/${encodeURIComponent(artifactId)}`, {
    params: { ...scopeParams(scope), expected_version: expectedVersion },
    headers: { 'Idempotency-Key': operationId },
  })
}

export function beginArtifactUpload(
  scope: Scope,
  workspaceId: string,
  body: {
    schema_version: '1'
    operation_id: string
    path: string
    size_bytes: number
    sha256: string
    content_type: string
  },
  signal?: AbortSignal,
) {
  return post<ArtifactUploadStatus>(`${workspacePath(workspaceId)}/uploads`, body, {
    params: scopeParams(scope),
    sensitive: true,
    signal,
  })
}

export function getArtifactUploadStatus(scope: Scope, workspaceId: string, uploadId: string, signal?: AbortSignal) {
  return get<ArtifactUploadStatus>(
    `${workspacePath(workspaceId)}/uploads/${encodeURIComponent(uploadId)}`,
    { params: scopeParams(scope), signal },
  )
}

export function uploadArtifactPart(
  scope: Scope,
  workspaceId: string,
  uploadId: string,
  offset: number,
  bytes: Blob,
  signal?: AbortSignal,
) {
  return put<ArtifactUploadStatus>(
    `${workspacePath(workspaceId)}/uploads/${encodeURIComponent(uploadId)}/parts`,
    bytes,
    { params: { ...scopeParams(scope), offset }, sensitive: true, signal },
  )
}

export function finalizeArtifactUpload(scope: Scope, workspaceId: string, uploadId: string, signal?: AbortSignal) {
  return post<ArtifactUploadStatus>(
    `${workspacePath(workspaceId)}/uploads/${encodeURIComponent(uploadId)}/finalize`,
    undefined,
    { params: scopeParams(scope), sensitive: true, signal },
  )
}

export function abortArtifactUpload(scope: Scope, workspaceId: string, uploadId: string) {
  return del<ArtifactUploadStatus>(
    `${workspacePath(workspaceId)}/uploads/${encodeURIComponent(uploadId)}`,
    { params: scopeParams(scope) },
  )
}

export function getArtifactDocumentIndex(scope: Scope, workspaceId: string, artifactId: string, revisionId: string) {
  return get<DocumentIndex>(`${workspacePath(workspaceId)}/artifacts/${encodeURIComponent(artifactId)}/revisions/${encodeURIComponent(revisionId)}/document-index`, {
    params: scopeParams(scope),
  })
}

export function listDocumentNodes(
  scope: Scope,
  workspaceId: string,
  indexId: string,
  options: { parentId?: string | null; cursor?: string | null; titleQuery?: string } = {},
) {
  return get<DocumentNodePage>(`/v1/document-indexes/${encodeURIComponent(indexId)}/nodes`, {
    params: {
      ...scopeParams(scope), artifact_workspace_id: workspaceId,
      parent_id: options.parentId ?? undefined, cursor: options.cursor ?? undefined,
      title_query: options.titleQuery,
    },
  })
}

export function getDocumentNode(scope: Scope, workspaceId: string, indexId: string, nodeId: string) {
  return get<DocumentNode>(`/v1/document-indexes/${encodeURIComponent(indexId)}/nodes/${encodeURIComponent(nodeId)}`, {
    params: { ...scopeParams(scope), artifact_workspace_id: workspaceId },
  })
}

export function readDocumentNode(scope: Scope, workspaceId: string, indexId: string, nodeId: string, offset = 0) {
  return get<SourceRead>(`/v1/document-indexes/${encodeURIComponent(indexId)}/nodes/${encodeURIComponent(nodeId)}/content`, {
    params: { ...scopeParams(scope), artifact_workspace_id: workspaceId, offset, max_chars: 8192 },
  })
}

export function listRepresentationEntries(
  scope: Scope,
  workspaceId: string,
  artifactId: string,
  revisionId: string,
  representationSetId: string,
  options: { directory?: string; cursor?: string | null } = {},
) {
  return get<RepresentationEntryPage>(`/v1/artifacts/${encodeURIComponent(artifactId)}/revisions/${encodeURIComponent(revisionId)}/representations/${encodeURIComponent(representationSetId)}/entries`, {
    params: {
      ...scopeParams(scope), artifact_workspace_id: workspaceId,
      directory: options.directory ?? '', cursor: options.cursor ?? undefined, limit: 100,
    },
  })
}

export function downloadRepresentation(
  scope: Scope,
  workspaceId: string,
  artifactId: string,
  revisionId: string,
  representationSetId: string,
  entryId: string,
) {
  return getBlob(`/v1/artifacts/${encodeURIComponent(artifactId)}/revisions/${encodeURIComponent(revisionId)}/representations/${encodeURIComponent(representationSetId)}/entries/${encodeURIComponent(entryId)}/content`, {
    params: { ...scopeParams(scope), artifact_workspace_id: workspaceId },
  })
}

export function renderPdfPage(
  scope: Scope,
  workspaceId: string,
  artifactId: string,
  revisionId: string,
  representationSetId: string,
  pageIndex: number,
) {
  return getBlob(`/v1/artifacts/${encodeURIComponent(artifactId)}/revisions/${encodeURIComponent(revisionId)}/representations/${encodeURIComponent(representationSetId)}/pages/${pageIndex}/image`, {
    params: { ...scopeParams(scope), artifact_workspace_id: workspaceId },
  })
}

export function downloadArtifact(scope: Scope, workspaceId: string, artifactId: string, revisionId: string) {
  return getBlob(`/v1/artifacts/${encodeURIComponent(artifactId)}/revisions/${encodeURIComponent(revisionId)}/content`, {
    params: { ...scopeParams(scope), artifact_workspace_id: workspaceId },
  })
}
