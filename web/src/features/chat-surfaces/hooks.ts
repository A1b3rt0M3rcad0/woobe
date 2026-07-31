import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import {
  activateChatSurface,
  createChatSurface,
  createChatSurfaceAccessKey,
  disableChatSurface,
  listChatSurfaces,
} from './api'
import type { ChatSurface, CreateChatSurfaceInput } from './types'

export function useChatSurfaces(projectId?: string) {
  return useQuery({
    queryKey: ['chat-surfaces', projectId],
    queryFn: () => listChatSurfaces(projectId!),
    enabled: Boolean(projectId),
    staleTime: 15_000,
  })
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
        (current = []) =>
          current.map((item) => (item.id === updated.id ? updated : item)),
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
