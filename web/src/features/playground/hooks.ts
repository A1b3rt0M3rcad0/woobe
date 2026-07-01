import { useCallback } from 'react'
import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  createSession,
  getAgentSessions,
  ask,
  getSessionMessages,
} from './api'
import { askStreamV1, type StreamCallbacks } from './stream-client'
import type { CreateSessionRequest, AskRequest } from './types'

let activeStreamController: AbortController | null = null

const AGENT_SESSIONS_PAGE_SIZE = 20

export function cancelActiveAskStream() {
  activeStreamController?.abort()
}

export function useCreateSession() {
  return useMutation({ mutationFn: (data: CreateSessionRequest) => createSession(data) })
}

export function useAsk() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (data: AskRequest) => ask(data),
    onSettled: () => queryClient.invalidateQueries({ queryKey: ['project-overview'] }),
  })
}

export function useAgentSessions(agentId: string | undefined, projectId: string | undefined) {
  return useInfiniteQuery({
    queryKey: ['agent-sessions', agentId, projectId],
    queryFn: ({ pageParam }) => getAgentSessions(agentId!, projectId!, {
      limit: AGENT_SESSIONS_PAGE_SIZE,
      cursor: pageParam,
    }),
    initialPageParam: null as string | null,
    getNextPageParam: (lastPage) => lastPage.has_next ? lastPage.next_cursor : undefined,
    enabled: !!agentId && !!projectId,
  })
}

export function useSessionMessages(sessionId: string | undefined) {
  return useQuery({
    queryKey: ['session-messages', sessionId],
    queryFn: () => getSessionMessages(sessionId!),
    enabled: !!sessionId,
  })
}

export function useAskStream() {
  const queryClient = useQueryClient()
  const stream = useCallback(async (
    data: AskRequest,
    callbacks: StreamCallbacks,
  ) => {
    activeStreamController?.abort()
    const controller = new AbortController()
    activeStreamController = controller
    try {
      await askStreamV1(data, callbacks, controller.signal)
    } finally {
      if (activeStreamController === controller) activeStreamController = null
      await queryClient.invalidateQueries({ queryKey: ['project-overview'] })
    }
  }, [queryClient])
  const cancel = useCallback(() => cancelActiveAskStream(), [])
  return { stream, cancel }
}
