import { useCallback, useRef } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import { createSession, getAgentSessions, ask, getSessionMessages, askStream, type StreamCallbacks } from './api'
import { getTraceDetail } from '@/features/traces/api'
import type { CreateSessionRequest, AskRequest } from './types'

void getTraceDetail

export function useCreateSession() {
  return useMutation({
    mutationFn: (data: CreateSessionRequest) => createSession(data),
  })
}

export function useAsk() {
  return useMutation({
    mutationFn: (data: AskRequest) => ask(data),
  })
}

export function useAgentSessions(agentId: string | undefined, projectId: string | undefined) {
  return useQuery({
    queryKey: ['agent-sessions', agentId],
    queryFn: () => getAgentSessions(agentId!, projectId!),
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
  const abortRef = useRef<AbortController | null>(null)

  const stream = useCallback(
    async (data: AskRequest, callbacks: StreamCallbacks) => {
      abortRef.current?.abort()
      abortRef.current = new AbortController()
      await askStream(data, callbacks, abortRef.current.signal)
    },
    [],
  )

  const cancel = useCallback(() => {
    abortRef.current?.abort()
  }, [])

  return { stream, cancel }
}
