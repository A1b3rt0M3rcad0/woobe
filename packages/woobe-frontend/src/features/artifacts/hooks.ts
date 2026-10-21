import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  createArtifactDirectory,
  createArtifactWorkspace,
  deleteArtifact,
  getArtifactCapabilities,
  getArtifactProcessingCapabilities,
  getArtifactWorkspace,
  resolveArtifactWorkspace,
  listArtifactWorkspaces,
  listArtifacts,
  listArtifactRevisions,
  getArtifactDocumentIndex,
  listDocumentNodes,
  getDocumentNode,
  readDocumentNode,
  listRepresentationEntries,
  downloadRepresentation,
  renderPdfPage,
  moveArtifact,
} from './api'
import type { ArtifactEnvironment, CreateArtifactWorkspaceRequest } from './types'

export function useArtifactWorkspaces(
  projectId: string | undefined,
  environment: ArtifactEnvironment,
  cursor: string | null,
) {
  return useQuery({
    queryKey: ['artifact-workspaces', projectId, environment, cursor],
    queryFn: () => listArtifactWorkspaces({ projectId: projectId!, environment }, { cursor, limit: 50 }),
    enabled: Boolean(projectId),
  })
}

export function useArtifactWorkspace(projectId: string | undefined, environment: ArtifactEnvironment, workspaceId: string | undefined) {
  return useQuery({
    queryKey: ['artifact-workspace', projectId, environment, workspaceId],
    queryFn: () => getArtifactWorkspace({ projectId: projectId!, environment }, workspaceId!),
    enabled: Boolean(projectId && workspaceId),
  })
}

export function useArtifactWorkspaceByIdentity(projectId: string | undefined, environment: ArtifactEnvironment, namespace: string | undefined, externalKey: string | undefined) {
  return useQuery({
    queryKey: ['artifact-workspace-resolve', projectId, environment, namespace, externalKey],
    queryFn: () => resolveArtifactWorkspace({ projectId: projectId!, environment }, namespace!, externalKey!),
    enabled: Boolean(projectId && namespace && externalKey),
    staleTime: 0,
  })
}

export function useArtifactCapabilities(projectId: string | undefined, environment: ArtifactEnvironment, enabled = true) {
  return useQuery({
    queryKey: ['artifact-capabilities', projectId, environment],
    queryFn: () => getArtifactCapabilities({ projectId: projectId!, environment }),
    enabled: Boolean(projectId && enabled),
    staleTime: 60_000,
  })
}

export function useArtifactProcessingCapabilities(projectId: string, environment: ArtifactEnvironment, enabled = true) {
  return useQuery({
    queryKey: ['artifact-processing-capabilities', projectId, environment],
    queryFn: () => getArtifactProcessingCapabilities({ projectId, environment }),
    enabled: Boolean(enabled && projectId),
    staleTime: 60_000,
  })
}

export function useArtifacts(
  projectId: string | undefined,
  environment: ArtifactEnvironment,
  workspaceId: string | undefined,
  directory: string,
  cursor: string | null,
) {
  return useQuery({
    queryKey: ['artifacts', projectId, environment, workspaceId, directory, cursor],
    queryFn: () => listArtifacts(
      { projectId: projectId!, environment }, workspaceId!, { directory, cursor, limit: 100 },
    ),
    enabled: Boolean(projectId && workspaceId),
  })
}

export function useArtifactRevisionHistory(
  projectId: string,
  environment: ArtifactEnvironment,
  workspaceId: string,
  artifactId: string,
  cursor: string | null,
) {
  return useQuery({
    queryKey: ['artifact-revisions', projectId, environment, workspaceId, artifactId, cursor],
    queryFn: () => listArtifactRevisions({ projectId, environment }, workspaceId, artifactId, { cursor, limit: 50 }),
    enabled: Boolean(projectId && workspaceId && artifactId),
  })
}

export function useCreateArtifactWorkspace(projectId: string, environment: ArtifactEnvironment) {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (body: CreateArtifactWorkspaceRequest) => createArtifactWorkspace({ projectId, environment }, body),
    onSuccess: () => client.invalidateQueries({ queryKey: ['artifact-workspaces', projectId, environment] }),
  })
}

export function useCreateArtifactDirectory(projectId: string, environment: ArtifactEnvironment, workspaceId: string) {
  const client = useQueryClient()
  return useMutation({
    mutationFn: ({ path, operationId }: { path: string; operationId: string }) =>
      createArtifactDirectory({ projectId, environment }, workspaceId, path, operationId),
    onSuccess: () => client.invalidateQueries({ queryKey: ['artifacts', projectId, environment, workspaceId] }),
  })
}

export function useMoveArtifact(projectId: string, environment: ArtifactEnvironment, workspaceId: string) {
  const client = useQueryClient()
  return useMutation({
    mutationFn: ({ artifactId, path, expectedVersion, operationId }: {
      artifactId: string; path: string; expectedVersion: number; operationId: string
    }) => moveArtifact({ projectId, environment }, workspaceId, artifactId, path, expectedVersion, operationId),
    onSuccess: () => client.invalidateQueries({ queryKey: ['artifacts', projectId, environment, workspaceId] }),
  })
}

export function useDeleteArtifact(projectId: string, environment: ArtifactEnvironment, workspaceId: string) {
  const client = useQueryClient()
  return useMutation({
    mutationFn: ({ artifactId, expectedVersion, operationId }: {
      artifactId: string; expectedVersion: number; operationId: string
    }) => deleteArtifact({ projectId, environment }, workspaceId, artifactId, expectedVersion, operationId),
    onSuccess: () => client.invalidateQueries({ queryKey: ['artifacts', projectId, environment, workspaceId] }),
  })
}

export function useArtifactDocumentIndex(projectId: string, environment: ArtifactEnvironment, workspaceId: string, artifactId: string, revisionId: string) {
  return useQuery({
    queryKey: ['artifact-document-index', projectId, environment, workspaceId, artifactId, revisionId],
    queryFn: () => getArtifactDocumentIndex({ projectId, environment }, workspaceId, artifactId, revisionId),
    enabled: Boolean(projectId && workspaceId && artifactId && revisionId),
  })
}

export function useDocumentNodes(projectId: string, environment: ArtifactEnvironment, workspaceId: string, indexId: string, parentId: string | null, cursor: string | null = null, titleQuery?: string, enabled = true) {
  return useQuery({
    queryKey: ['artifact-document-nodes', projectId, environment, workspaceId, indexId, parentId, cursor, titleQuery],
    queryFn: () => listDocumentNodes({ projectId, environment }, workspaceId, indexId, { parentId, cursor, titleQuery }),
    enabled: Boolean(enabled && projectId && workspaceId && indexId),
  })
}

export function useDocumentNode(projectId: string, environment: ArtifactEnvironment, workspaceId: string, indexId: string, nodeId: string) {
  return useQuery({
    queryKey: ['artifact-document-node', projectId, environment, workspaceId, indexId, nodeId],
    queryFn: () => getDocumentNode({ projectId, environment }, workspaceId, indexId, nodeId),
    enabled: Boolean(projectId && workspaceId && indexId && nodeId),
  })
}

export function useDocumentNodeContent(projectId: string, environment: ArtifactEnvironment, workspaceId: string, indexId: string, nodeId: string, offset = 0, enabled = true) {
  return useQuery({
    queryKey: ['artifact-document-node-content', projectId, environment, workspaceId, indexId, nodeId, offset],
    queryFn: () => readDocumentNode({ projectId, environment }, workspaceId, indexId, nodeId, offset),
    enabled: Boolean(enabled && projectId && workspaceId && indexId && nodeId),
  })
}

export function useRepresentationEntries(projectId: string, environment: ArtifactEnvironment, workspaceId: string, artifactId: string, revisionId: string, representationSetId: string) {
  return useQuery({
    queryKey: ['artifact-representation-entries', projectId, environment, workspaceId, artifactId, revisionId, representationSetId],
    queryFn: () => listRepresentationEntries({ projectId, environment }, workspaceId, artifactId, revisionId, representationSetId),
    enabled: Boolean(projectId && workspaceId && artifactId && revisionId && representationSetId),
  })
}

export function useDownloadRepresentation(projectId: string, environment: ArtifactEnvironment, workspaceId: string, artifactId: string, revisionId: string, representationSetId: string) {
  return useMutation({
    mutationFn: (entryId: string) => downloadRepresentation({ projectId, environment }, workspaceId, artifactId, revisionId, representationSetId, entryId),
  })
}

export function useRenderPdfPage(projectId: string, environment: ArtifactEnvironment, workspaceId: string, artifactId: string, revisionId: string, representationSetId: string, pageIndex: number, enabled: boolean) {
  return useQuery({
    queryKey: ['artifact-pdf-page', projectId, environment, workspaceId, artifactId, revisionId, representationSetId, pageIndex],
    queryFn: () => renderPdfPage({ projectId, environment }, workspaceId, artifactId, revisionId, representationSetId, pageIndex),
    enabled: Boolean(enabled && projectId && workspaceId && artifactId && revisionId && representationSetId),
    staleTime: 60_000,
  })
}
