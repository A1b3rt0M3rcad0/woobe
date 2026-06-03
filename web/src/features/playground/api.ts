import { post, get } from '@/lib/api/client'
import type { CreateSessionRequest, Session, AskRequest, AskResponse, Message } from './types'

export async function createSession(data: CreateSessionRequest): Promise<Session> {
  return post<Session>('/runtime/sessions', data)
}

export async function ask(data: AskRequest): Promise<AskResponse> {
  return post<AskResponse>('/runtime/ask', data)
}

export async function getSessionMessages(sessionId: string, params?: { offset?: number; limit?: number }): Promise<Message[]> {
  return get<Message[]>(`/runtime/sessions/${sessionId}/messages`, { params: params as Record<string, string | number | undefined> })
}
