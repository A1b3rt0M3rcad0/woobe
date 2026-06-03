import { post, get } from '@/lib/api/client'
import type { CreateSessionRequest, Session, AskRequest, AskResponse, Message } from './types'

function normalizeResponse(response: AskResponse): AskResponse {
  if (response.usage) {
    response.usage = {
      input_tokens: response.usage.input_tokens ?? null,
      output_tokens: response.usage.output_tokens ?? null,
      cost_usd: response.usage.cost_usd ?? null,
    }
  }
  response.latency_ms = response.latency_ms ?? null
  response.sources = response.sources ?? []
  response.tool_calls = response.tool_calls ?? []
  return response
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
