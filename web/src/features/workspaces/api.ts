import { del, get, patch, post } from '@/lib/api/client'
import type {
  CreateWorkspaceInviteRequest,
  CreateWorkspaceRequest,
  PendingWorkspaceInvite,
  UpdateWorkspaceRequest,
  Workspace,
  WorkspaceInvite,
  WorkspaceMember,
} from './types'

export async function getWorkspaces(): Promise<Workspace[]> {
  return get<Workspace[]>('/core/workspaces')
}

export async function getWorkspace(id: string): Promise<Workspace> {
  return get<Workspace>(`/core/workspaces/${id}`)
}

export async function createWorkspace(data: CreateWorkspaceRequest): Promise<Workspace> {
  return post<Workspace>('/core/workspaces', data)
}

export async function updateWorkspace(id: string, data: UpdateWorkspaceRequest): Promise<Workspace> {
  return patch<Workspace>(`/core/workspaces/${id}`, data)
}

export async function getWorkspaceMembers(id: string): Promise<WorkspaceMember[]> {
  return get<WorkspaceMember[]>(`/core/workspaces/${id}/members`)
}

export async function removeWorkspaceMember(workspaceId: string, userId: string): Promise<void> {
  return del<void>(`/core/workspaces/${workspaceId}/members/${userId}`)
}

export async function getWorkspaceInvites(workspaceId: string): Promise<WorkspaceInvite[]> {
  return get<WorkspaceInvite[]>('/identity/invites', { params: { workspace_id: workspaceId } })
}

export async function createWorkspaceInvite(data: CreateWorkspaceInviteRequest): Promise<WorkspaceInvite> {
  return post<WorkspaceInvite>('/identity/invites', data)
}

export async function cancelWorkspaceInvite(inviteId: string): Promise<void> {
  return del<void>(`/identity/invites/${inviteId}`)
}

export async function getPendingWorkspaceInvites(): Promise<PendingWorkspaceInvite[]> {
  return get<PendingWorkspaceInvite[]>('/identity/invites/pending')
}

export async function acceptWorkspaceInvite(inviteId: string): Promise<Workspace> {
  return post<Workspace>(`/identity/invites/${inviteId}/accept`)
}
