import { useCallback, useRef } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import { createSession, getAgentSessions, ask, getSessionMessages, askStream, type StreamCallbacks } from './api'
import { getTraceDetail } from '@/features/traces/api'
import type { CreateSessionRequest, AskRequest, ExecutionEvent } from './types'

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' && !Array.isArray(value)
    ? value as Record<string, unknown>
    : {}
}

async function enrichDoneResponse(response: Parameters<StreamCallbacks['onDone']>[0]) {
  if (!response.trace_id) return response
  for (let attempt = 0; attempt < 10; attempt += 1) {
    try {
      const detail = await getTraceDetail(response.trace_id)
      const data = asRecord(detail.data)
      if (Array.isArray(data.execution_events)) {
        response.execution_events = data.execution_events as ExecutionEvent[]
        response.diagnostics = (data.diagnostics ?? null) as typeof response.diagnostics
        return response
      }
    } catch {
      // Projection can lag behind the runtime response.
    }
    await new Promise((resolve) => setTimeout(resolve, 150))
  }
  return response
}

export function useCreateSession() {
  return useMutation({ mutationFn: (data: CreateSessionRequest) => createSession(data) })
}

export function useAsk() {
  return useMutation({ mutationFn: (data: AskRequest) => ask(data) })
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
  const stream = useCallback(async (data: AskRequest, callbacks: StreamCallbacks) => {
    abortRef.current?.abort()
    abortRef.current = new AbortController()
    let completion: Promise<void> = Promise.resolve()
    await askStream(data, {
      ...callbacks,
      onDone: (response) => {
        completion = enrichDoneResponse(response).then(callbacks.onDone)
      },
    }, abortRef.current.signal)
    await completion
  }, [])
  const cancel = useCallback(() => abortRef.current?.abort(), [])
  return { stream, cancel }
}
