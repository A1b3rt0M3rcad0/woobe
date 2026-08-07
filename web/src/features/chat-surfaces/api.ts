import { get, patch, post } from '@/lib/api/client'

import type {
  ChatSurface,
  ChatSurfaceAccessKey,
  CreateChatSurfaceInput,
  UpdateChatSurfaceInput,
} from './types'

export function listChatSurfaces(projectId: string): Promise<ChatSurface[]> {
  return get<ChatSurface[]>(`/chat-surfaces/projects/${projectId}`)
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

export function createChatSurfaceAccessKey(
  surfaceId: string,
  name = 'Default ChatSurface key',
): Promise<ChatSurfaceAccessKey> {
  return post<ChatSurfaceAccessKey>(
    `/chat-surfaces/${surfaceId}/access-keys`,
    { name },
  )
}
