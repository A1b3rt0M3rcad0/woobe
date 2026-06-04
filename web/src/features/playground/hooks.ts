import { useCallback, useRef } from 'react'
import { useMutation } from '@tanstack/react-query'
import { createSession, ask, getSessionMessages, askStream, type StreamCallbacks } from './api'
import type { CreateSessionRequest, AskRequest } from './types'

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

export function useSessionMessages(sessionId: string | undefined) {
  return useMutation({
    mutationKey: ['session-messages', sessionId],
    mutationFn: () => getSessionMessages(sessionId!),
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
