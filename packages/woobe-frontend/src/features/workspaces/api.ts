import { del, get, post, patch } from '@/lib/api/client'
import type {
  WorkspaceDetail,
  Member,
  Invite,
  PendingInvite,
  UpdateWorkspaceRequest,
  CreateWorkspaceRequest,
  CreateInviteRequest,
  RemoveWorkspaceMemberResult,
  CancelWorkspaceInviteResult,
} from './types'

export async function getWorkspace(id: string): Promise<WorkspaceDetail> {
  return get<WorkspaceDetail>(`/identity/workspaces/${id}`)
}

export async function updateWorkspace(id: string, data: UpdateWorkspaceRequest): Promise<WorkspaceDetail> {
  return patch<WorkspaceDetail>(`/identity/workspaces/${id}`, data)
}

export async function createWorkspaceFromApi(data: CreateWorkspaceRequest): Promise<WorkspaceDetail> {
  return post<WorkspaceDetail>('/identity/workspaces', data)
}

export async function getWorkspaceMembers(workspaceId: string): Promise<Member[]> {
  return get<Member[]>(`/identity/workspaces/${workspaceId}/members`)
}

export async function removeWorkspaceMember(workspaceId: string, userId: string): Promise<RemoveWorkspaceMemberResult> {
  return del<RemoveWorkspaceMemberResult>(`/identity/workspaces/${workspaceId}/members/${userId}`)
}

export async function getWorkspaceInvites(workspaceId: string): Promise<Invite[]> {
  return get<Invite[]>(`/identity/workspaces/${workspaceId}/invites`)
}

export async function createWorkspaceInvite(workspaceId: string, data: CreateInviteRequest): Promise<Invite> {
  return post<Invite>(`/identity/workspaces/${workspaceId}/invites`, data)
}

export async function cancelWorkspaceInvite(workspaceId: string, inviteId: string): Promise<CancelWorkspaceInviteResult> {
  return del<CancelWorkspaceInviteResult>(`/identity/workspaces/${workspaceId}/invites/${inviteId}`)
}

export async function getPendingWorkspaceInvites(): Promise<PendingInvite[]> {
  return get<PendingInvite[]>('/identity/invites/pending')
}

export async function acceptWorkspaceInvite(inviteId: string): Promise<WorkspaceDetail> {
  return post<WorkspaceDetail>(`/identity/invites/${inviteId}/accept`)
}
