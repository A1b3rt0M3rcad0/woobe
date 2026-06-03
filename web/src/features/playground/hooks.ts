import { useMutation } from '@tanstack/react-query'
import { createSession, ask, getSessionMessages } from './api'
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
