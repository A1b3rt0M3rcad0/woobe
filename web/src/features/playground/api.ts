import { post, get } from '@/lib/api/client'
import { getToken } from '@/lib/auth/token'
import type { CreateSessionRequest, Session, AskRequest, AskResponse, Message, SourceInfo } from './types'

const BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

function normalizeResponse(response: AskResponse): AskResponse {
  return {
    ...response,
    usage: response.usage
      ? {
          input_tokens: response.usage.input_tokens ?? null,
          output_tokens: response.usage.output_tokens ?? null,
          total_tokens: response.usage.total_tokens ?? null,
          cost_usd: response.usage.cost_usd ?? null,
        }
      : null,
    sources: response.sources ?? [],
    tool_calls: response.tool_calls ?? [],
    latency_ms: response.latency_ms ?? null,
    trace_id: response.trace_id ?? null,
    model: response.model ?? null,
    provider: response.provider ?? null,
    fallback_used: response.fallback_used ?? false,
    session_id: response.session_id ?? null,
    message_id: response.message_id ?? null,
  }
}

export async function createSession(data: CreateSessionRequest): Promise<Session> {
  return post<Session>('/runtime/sessions', data)
}

export async function ask(data: AskRequest): Promise<AskResponse> {
  const response = await post<AskResponse>('/runtime/ask', data)
  return normalizeResponse(response)
}

export async function getSessionMessages(sessionId: string, params?: { offset?: number; limit?: number }): Promise<Message[]> {
  return get<Message[]>(`/runtime/sessions/${sessionId}/messages`, { params: params as Record<string, string | number | undefined> })
}

export interface StreamCallbacks {
  onToken: (content: string) => void
  onSources: (sources: SourceInfo[]) => void
  onMeta: (meta: { session_id?: string | null; trace_id?: string | null }) => void
  onDone: (response: Partial<AskResponse>) => void
  onError: (error: Error) => void
}

export async function askStream(
  data: AskRequest,
  callbacks: StreamCallbacks,
  signal?: AbortSignal,
): Promise<void> {
  const token = getToken()
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  }
  if (token) {
    headers['Authorization'] = `Bearer ${token}`
  }

  const response = await fetch(`${BASE_URL}/runtime/ask/stream`, {
    method: 'POST',
    headers,
    body: JSON.stringify(data),
    signal,
  })

  if (!response.ok) {
    let errorMsg = `Stream request failed (${response.status})`
    try {
      const errBody = await response.json()
      errorMsg = errBody?.message || errorMsg
    } catch {
      // ignore parse error
    }
    throw new Error(errorMsg)
  }

  const reader = response.body!.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break

    buffer += decoder.decode(value, { stream: true })
    const lines = buffer.split('\n')
    buffer = lines.pop() || ''

    for (const line of lines) {
      const trimmed = line.trim()
      if (!trimmed.startsWith('data: ')) continue

      try {
        const parsed = JSON.parse(trimmed.slice(6))
        const type = parsed.type

        switch (type) {
          case 'token':
            callbacks.onToken(parsed.content ?? '')
            break
          case 'sources':
            callbacks.onSources(parsed.sources ?? [])
            break
          case 'meta':
            callbacks.onMeta({
              session_id: parsed.session_id ?? null,
              trace_id: parsed.trace_id ?? null,
            })
            break
          case 'done':
            callbacks.onDone(normalizeResponse(parsed as AskResponse))
            break
          case 'error':
            callbacks.onError(new Error(parsed.message ?? 'Stream error'))
            return
        }
      } catch (e) {
        console.warn('[askStream] Failed to parse SSE line:', line, e)
      }
    }
  }
}
