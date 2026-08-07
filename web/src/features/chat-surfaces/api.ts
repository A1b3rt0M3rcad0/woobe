import { get, patch, post } from '@/lib/api/client'

import type {
  ChatSurface,
  ChatSurfaceAccessKey,
  ChatSurfaceTestSession,
  CreateChatSurfaceInput,
  UpdateChatSurfaceInput,
} from './types'

export function listChatSurfaces(projectId: string): Promise<ChatSurface[]> {
  return get<ChatSurface[]>(`/chat-surfaces/projects/${projectId}`)
}

export function getChatSurface(surfaceId: string): Promise<ChatSurface> {
  return get<ChatSurface>(`/chat-surfaces/${surfaceId}`)
}

export function createChatSurface(
  projectId: string,
  input: CreateChatSurfaceInput,
): Promise<ChatSurface> {
  return post<ChatSurface>(`/chat-surfaces/projects/${projectId}`, input)
}

export function updateChatSurface(
  surfaceId: string,
  input: UpdateChatSurfaceInput,
): Promise<ChatSurface> {
  return patch<ChatSurface>(`/chat-surfaces/${surfaceId}`, input)
}

export function refreshChatSurfaceRelease(surfaceId: string): Promise<ChatSurface> {
  return post<ChatSurface>(`/chat-surfaces/${surfaceId}/release`)
}

export function activateChatSurface(surfaceId: string): Promise<ChatSurface> {
  return post<ChatSurface>(`/chat-surfaces/${surfaceId}/activate`)
}

export function disableChatSurface(surfaceId: string): Promise<ChatSurface> {
  return post<ChatSurface>(`/chat-surfaces/${surfaceId}/disable`)
}

export function archiveChatSurface(surfaceId: string): Promise<ChatSurface> {
  return post<ChatSurface>(`/chat-surfaces/${surfaceId}/archive`)
}

export function createChatSurfaceTestSession(
  surfaceId: string,
): Promise<ChatSurfaceTestSession> {
  return post<ChatSurfaceTestSession>(`/chat-surfaces/${surfaceId}/test-sessions`)
}

export function listChatSurfaceAccessKeys(
  surfaceId: string,
): Promise<ChatSurfaceAccessKey[]> {
  return get<ChatSurfaceAccessKey[]>(`/chat-surfaces/${surfaceId}/access-keys`)
}

export function createChatSurfaceAccessKey(
  surfaceId: string,
  name = 'Default ChatSurface key',
): Promise<ChatSurfaceAccessKey> {
  return post<ChatSurfaceAccessKey>(
    `/chat-surfaces/${surfaceId}/access-keys`,
    { name },
  )
}

export function rotateChatSurfaceAccessKey(
  surfaceId: string,
  apiKeyId: string,
): Promise<ChatSurfaceAccessKey> {
  return post<ChatSurfaceAccessKey>(
    `/chat-surfaces/${surfaceId}/access-keys/${apiKeyId}/rotate`,
  )
}

export function revokeChatSurfaceAccessKey(
  surfaceId: string,
  apiKeyId: string,
): Promise<ChatSurfaceAccessKey> {
  return post<ChatSurfaceAccessKey>(
    `/chat-surfaces/${surfaceId}/access-keys/${apiKeyId}/revoke`,
  )
}
