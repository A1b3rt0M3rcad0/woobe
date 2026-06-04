import { post, get } from '@/lib/api/client'
import type { CreateSessionRequest, Session, AskRequest, AskResponse, Message } from './types'

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
