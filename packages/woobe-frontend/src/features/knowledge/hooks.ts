import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  getCollections,
  getCollection,
  createCollection,
  getAgentCollections,
  attachCollection,
  detachCollection,
  updateCollection,
  getDocuments,
  getDocumentsByCollection,
  getDocument,
  uploadDocument,
  uploadDocumentFile,
  deleteDocument,
} from './api'
import type {
  AttachCollectionRequest,
  CreateCollectionRequest,
  UpdateCollectionRequest,
  UploadDocumentFileRequest,
  UploadDocumentRequest,
} from './types'

export function useCollections(projectId?: string) {
  return useQuery({
    queryKey: ['collections', projectId],
    queryFn: () => getCollections(projectId!),
    enabled: Boolean(projectId),
  })
}

export function useCollection(id: string | undefined) {
  return useQuery({
    queryKey: ['collection', id],
    queryFn: () => getCollection(id!),
    enabled: Boolean(id),
  })
}

export function useCreateCollection() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (data: CreateCollectionRequest) => createCollection(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['collections'] })
    },
  })
}

export function useUpdateCollection() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: UpdateCollectionRequest }) => updateCollection(id, data),
    onSuccess: (collection) => {
      queryClient.invalidateQueries({ queryKey: ['collections'] })
      queryClient.invalidateQueries({ queryKey: ['collection', collection.id] })
    },
  })
}

export function useAgentCollections(agentId?: string) {
  return useQuery({
    queryKey: ['agent-collections', agentId],
    queryFn: () => getAgentCollections(agentId!),
    enabled: Boolean(agentId),
  })
}

export function useAttachCollection() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (data: AttachCollectionRequest) => attachCollection(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['agent-collections'] })
      queryClient.invalidateQueries({ queryKey: ['collections'] })
    },
  })
}

export function useDetachCollection() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => detachCollection(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['agent-collections'] })
    },
  })
}

export function useDocuments(projectId?: string) {
  return useQuery({
    queryKey: ['documents', projectId],
    queryFn: () => getDocuments(projectId!),
    enabled: Boolean(projectId),
  })
}

export function useDocumentsByCollection(collectionId?: string) {
  return useQuery({
    queryKey: ['documents', 'collection', collectionId],
    queryFn: () => getDocumentsByCollection(collectionId!),
    enabled: Boolean(collectionId),
  })
}

export function useDocument(id: string | undefined) {
  return useQuery({
    queryKey: ['document', id],
    queryFn: () => getDocument(id!),
    enabled: Boolean(id),
  })
}

export function useUploadDocument() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (data: UploadDocumentRequest) => uploadDocument(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['documents'] })
    },
  })
}

export function useUploadDocumentFile() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (data: UploadDocumentFileRequest) => uploadDocumentFile(data),
    onSuccess: (_document, variables) => {
      queryClient.invalidateQueries({ queryKey: ['documents'] })
      queryClient.invalidateQueries({ queryKey: ['documents', 'collection', variables.collectionId] })
      queryClient.invalidateQueries({ queryKey: ['collections'] })
    },
  })
}

export function useDeleteDocument() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => deleteDocument(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['documents'] })
      queryClient.invalidateQueries({ queryKey: ['collections'] })
    },
  })
}
