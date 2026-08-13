import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  acceptWorkspaceInvite,
  cancelWorkspaceInvite,
  createWorkspace,
  createWorkspaceInvite,
  getPendingWorkspaceInvites,
  getWorkspace,
  getWorkspaceInvites,
  getWorkspaceMembers,
  getWorkspaces,
  removeWorkspaceMember,
  updateWorkspace,
} from './api'
import type { CreateWorkspaceInviteRequest, CreateWorkspaceRequest, UpdateWorkspaceRequest } from './types'

export function useWorkspaces() {
  return useQuery({ queryKey: ['workspaces'], queryFn: getWorkspaces })
}

export function useWorkspaceDetail(id: string | undefined) {
  return useQuery({ queryKey: ['workspace', id], queryFn: () => getWorkspace(id!), enabled: Boolean(id) })
}

export function useCreateWorkspace() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (data: CreateWorkspaceRequest) => createWorkspace(data),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ['workspaces'] }),
  })
}

export function useUpdateWorkspace() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: UpdateWorkspaceRequest }) => updateWorkspace(id, data),
    onSuccess: (_, { id }) => {
      void queryClient.invalidateQueries({ queryKey: ['workspace', id] })
      void queryClient.invalidateQueries({ queryKey: ['workspaces'] })
    },
  })
}

export function useWorkspaceMembers(id: string | undefined, enabled = true) {
  return useQuery({ queryKey: ['workspace-members', id], queryFn: () => getWorkspaceMembers(id!), enabled: Boolean(id) && enabled })
}

export function useRemoveWorkspaceMember() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ workspaceId, userId }: { workspaceId: string; userId: string }) => removeWorkspaceMember(workspaceId, userId),
    onSuccess: (_, { workspaceId }) => {
      void queryClient.invalidateQueries({ queryKey: ['workspace-members', workspaceId] })
      void queryClient.invalidateQueries({ queryKey: ['projects'] })
    },
  })
}

export function useWorkspaceInvites(id: string | undefined, enabled = true) {
  return useQuery({ queryKey: ['workspace-invites', id], queryFn: () => getWorkspaceInvites(id!), enabled: Boolean(id) && enabled })
}

export function useCreateWorkspaceInvite() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (data: CreateWorkspaceInviteRequest) => createWorkspaceInvite(data),
    onSuccess: (_, data) => {
      void queryClient.invalidateQueries({ queryKey: ['workspace-invites', data.workspace_id] })
      void queryClient.invalidateQueries({ queryKey: ['project-members'] })
    },
  })
}

export function useCancelWorkspaceInvite() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ workspaceId, inviteId }: { workspaceId: string; inviteId: string }) => cancelWorkspaceInvite(inviteId),
    onSuccess: (_, { workspaceId }) => void queryClient.invalidateQueries({ queryKey: ['workspace-invites', workspaceId] }),
  })
}

export function usePendingWorkspaceInvites() {
  return useQuery({ queryKey: ['workspace-invites', 'pending-for-user'], queryFn: getPendingWorkspaceInvites })
}

export function useAcceptWorkspaceInvite() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (inviteId: string) => acceptWorkspaceInvite(inviteId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['workspace-invites'] })
      void queryClient.invalidateQueries({ queryKey: ['workspaces'] })
      void queryClient.invalidateQueries({ queryKey: ['projects'] })
    },
  })
}
