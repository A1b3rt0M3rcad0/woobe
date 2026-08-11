import {
  useMutation,
  useQuery,
  useQueryClient,
  type QueryClient,
} from '@tanstack/react-query'

import {
  activateChatSurface,
  archiveChatSurface,
  createChatSurface,
  createChatSurfaceAccessKey,
  disableChatSurface,
  getChatSurface,
  listChatSurfaceAccessKeys,
  listChatSurfaces,
  refreshChatSurfaceRelease,
  revokeChatSurfaceAccessKey,
  rotateChatSurfaceAccessKey,
  updateChatSurface,
} from './api'
import type {
  ChatSurface,
  ChatSurfaceAccessKey,
  CreateChatSurfaceInput,
  UpdateChatSurfaceInput,
} from './types'

export function useChatSurfaces(projectId?: string) {
  return useQuery({
    queryKey: ['chat-surfaces', projectId],
    queryFn: () => listChatSurfaces(projectId!),
    enabled: Boolean(projectId),
    staleTime: 15_000,
  })
}

export function useChatSurface(surfaceId?: string, projectId?: string) {
  const queryClient = useQueryClient()
  return useQuery({
    queryKey: ['chat-surface', surfaceId],
    queryFn: () => getChatSurface(surfaceId!),
    enabled: Boolean(surfaceId),
    staleTime: 15_000,
    initialData: () => {
      if (!surfaceId || !projectId) return undefined
      return queryClient
        .getQueryData<ChatSurface[]>(['chat-surfaces', projectId])
        ?.find((item) => item.id === surfaceId)
    },
  })
}

function replaceSurface(
  current: ChatSurface[] | undefined,
  updated: ChatSurface,
): ChatSurface[] {
  return (current ?? []).map((item) =>
    item.id === updated.id ? updated : item,
  )
}

function cacheSurface(queryClient: QueryClient, updated: ChatSurface) {
  queryClient.setQueryData<ChatSurface>(
    ['chat-surface', updated.id],
    updated,
  )
  queryClient.setQueryData<ChatSurface[]>(
    ['chat-surfaces', updated.project_id],
    (current) => replaceSurface(current, updated),
  )
}

function publicAccessKey(accessKey: ChatSurfaceAccessKey): ChatSurfaceAccessKey {
  const { access_key: _secret, ...safe } = accessKey
  return safe
}

export function useCreateChatSurface(projectId?: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (input: CreateChatSurfaceInput) =>
      createChatSurface(projectId!, input),
    onSuccess: (created) => {
      queryClient.setQueryData<ChatSurface[]>(
        ['chat-surfaces', projectId],
        (current = []) => [created, ...current],
      )
      queryClient.setQueryData<ChatSurface>(
        ['chat-surface', created.id],
        created,
      )
    },
  })
}

export function useUpdateChatSurface() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({
      surfaceId,
      input,
    }: {
      surfaceId: string
      input: UpdateChatSurfaceInput
    }) => updateChatSurface(surfaceId, input),
    onSuccess: (updated) => cacheSurface(queryClient, updated),
  })
}

export function useRefreshChatSurfaceRelease() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (surfaceId: string) => refreshChatSurfaceRelease(surfaceId),
    onSuccess: (updated) => cacheSurface(queryClient, updated),
  })
}

export type ChatSurfaceLifecycleAction = 'activate' | 'disable' | 'archive'

export function useChatSurfaceLifecycle() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({
      surfaceId,
      action,
    }: {
      surfaceId: string
      action: ChatSurfaceLifecycleAction
    }) => {
      if (action === 'activate') return activateChatSurface(surfaceId)
      if (action === 'disable') return disableChatSurface(surfaceId)
      return archiveChatSurface(surfaceId)
    },
    onSuccess: (updated) => cacheSurface(queryClient, updated),
  })
}

export function useChatSurfaceAccessKeys(surfaceId?: string) {
  return useQuery({
    queryKey: ['chat-surface-access-keys', surfaceId],
    queryFn: () => listChatSurfaceAccessKeys(surfaceId!),
    enabled: Boolean(surfaceId),
    staleTime: 15_000,
  })
}

export function useCreateChatSurfaceKey() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({
      surfaceId,
      name,
    }: {
      surfaceId: string
      name?: string
    }) => createChatSurfaceAccessKey(surfaceId, name),
    onSuccess: (created) => {
      queryClient.setQueryData<ChatSurfaceAccessKey[]>(
        ['chat-surface-access-keys', created.chat_surface_id],
        (current = []) => [publicAccessKey(created), ...current],
      )
    },
  })
}

export function useRotateChatSurfaceKey() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({
      surfaceId,
      apiKeyId,
    }: {
      surfaceId: string
      apiKeyId: string
    }) => rotateChatSurfaceAccessKey(surfaceId, apiKeyId),
    onSuccess: (replacement, variables) => {
      queryClient.setQueryData<ChatSurfaceAccessKey[]>(
        ['chat-surface-access-keys', variables.surfaceId],
        (current = []) => [
          publicAccessKey(replacement),
          ...current.map((item) =>
            item.id === variables.apiKeyId
              ? { ...item, status: 'revoked' }
              : item,
          ),
        ],
      )
    },
  })
}

export function useRevokeChatSurfaceKey() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({
      surfaceId,
      apiKeyId,
    }: {
      surfaceId: string
      apiKeyId: string
    }) => revokeChatSurfaceAccessKey(surfaceId, apiKeyId),
    onSuccess: (revoked, variables) => {
      queryClient.setQueryData<ChatSurfaceAccessKey[]>(
        ['chat-surface-access-keys', variables.surfaceId],
        (current = []) => current.map((item) =>
          item.id === revoked.id ? revoked : item,
        ),
      )
    },
  })
}
