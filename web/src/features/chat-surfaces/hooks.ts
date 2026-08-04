import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import {
  activateChatSurface,
  createChatSurface,
  createChatSurfaceAccessKey,
  disableChatSurface,
  listChatSurfaces,
  refreshChatSurfaceRelease,
  updateChatSurface,
} from './api'
import type {
  ChatSurface,
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

function replaceSurface(
  current: ChatSurface[] | undefined,
  updated: ChatSurface,
): ChatSurface[] {
  return (current ?? []).map((item) =>
    item.id === updated.id ? updated : item,
  )
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
    },
  })
}

export function useUpdateChatSurface(projectId?: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({
      surfaceId,
      input,
    }: {
      surfaceId: string
      input: UpdateChatSurfaceInput
    }) => updateChatSurface(surfaceId, input),
    onSuccess: (updated) => {
      queryClient.setQueryData<ChatSurface[]>(
        ['chat-surfaces', projectId],
        (current) => replaceSurface(current, updated),
      )
    },
  })
}

export function useRefreshChatSurfaceRelease(projectId?: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (surfaceId: string) => refreshChatSurfaceRelease(surfaceId),
    onSuccess: (updated) => {
      queryClient.setQueryData<ChatSurface[]>(
        ['chat-surfaces', projectId],
        (current) => replaceSurface(current, updated),
      )
    },
  })
}

export function useSetChatSurfaceStatus(projectId?: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({
      surfaceId,
      active,
    }: {
      surfaceId: string
      active: boolean
    }) =>
      active
        ? activateChatSurface(surfaceId)
        : disableChatSurface(surfaceId),
    onSuccess: (updated) => {
      queryClient.setQueryData<ChatSurface[]>(
        ['chat-surfaces', projectId],
        (current) => replaceSurface(current, updated),
      )
    },
  })
}

export function useCreateChatSurfaceKey() {
  return useMutation({
    mutationFn: ({
      surfaceId,
      name,
    }: {
      surfaceId: string
      name?: string
    }) => createChatSurfaceAccessKey(surfaceId, name),
  })
}
