import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useAuth } from '@/features/auth/AuthProvider'
import type { Workspace } from '@/features/auth/types'
import {
  getWorkspace,
  updateWorkspace,
  createWorkspaceFromApi,
  getWorkspaceMembers,
  removeWorkspaceMember,
  getWorkspaceInvites,
  createWorkspaceInvite,
  cancelWorkspaceInvite,
  getPendingWorkspaceInvites,
  acceptWorkspaceInvite,
} from './api'
import type {
  PendingInvite,
  UpdateWorkspaceRequest,
  CreateWorkspaceRequest,
  CreateInviteRequest,
} from './types'

export function useWorkspaceDetail(id: string | undefined) {
  return useQuery({
    queryKey: ['workspace', id],
    queryFn: () => getWorkspace(id!),
    enabled: Boolean(id),
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

export function useCreateWorkspace() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (data: CreateWorkspaceRequest) => createWorkspaceFromApi(data),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ['workspaces'] }),
  })
}

export function useWorkspaceMembers(workspaceId: string | undefined) {
  return useQuery({
    queryKey: ['workspace-members', workspaceId],
    queryFn: () => getWorkspaceMembers(workspaceId!),
    enabled: Boolean(workspaceId),
  })
}

export function useRemoveWorkspaceMember() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ workspaceId, userId }: { workspaceId: string; userId: string }) => removeWorkspaceMember(workspaceId, userId),
    onSuccess: (_, { workspaceId }) => {
      void queryClient.invalidateQueries({ queryKey: ['workspace-members', workspaceId] })
      void queryClient.invalidateQueries({ queryKey: ['workspace-invites', workspaceId] })
      void queryClient.invalidateQueries({ queryKey: ['project-access', workspaceId] })
      void queryClient.invalidateQueries({ queryKey: ['project-members'] })
    },
  })
}

export function useWorkspaceInvites(workspaceId: string | undefined, enabled = true) {
  return useQuery({
    queryKey: ['workspace-invites', workspaceId],
    queryFn: () => getWorkspaceInvites(workspaceId!),
    enabled: Boolean(workspaceId) && enabled,
  })
}

export function useCreateInvite() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ workspaceId, data }: { workspaceId: string; data: CreateInviteRequest }) => createWorkspaceInvite(workspaceId, data),
    onSuccess: (_, { workspaceId }) => {
      void queryClient.invalidateQueries({ queryKey: ['workspace-invites', workspaceId] })
      void queryClient.invalidateQueries({ queryKey: ['project-members'] })
      void queryClient.invalidateQueries({ queryKey: ['project-access', workspaceId] })
    },
  })
}

export function useCancelWorkspaceInvite() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ workspaceId, inviteId }: { workspaceId: string; inviteId: string }) => cancelWorkspaceInvite(workspaceId, inviteId),
    onSuccess: (_, { workspaceId }) => {
      void queryClient.invalidateQueries({ queryKey: ['workspace-invites', workspaceId] })
      void queryClient.invalidateQueries({ queryKey: ['project-members'] })
      void queryClient.invalidateQueries({ queryKey: ['project-access', workspaceId] })
    },
  })
}

export function usePendingWorkspaceInvites() {
  return useQuery({
    queryKey: ['workspace-invites', 'pending-for-user'],
    queryFn: getPendingWorkspaceInvites,
  })
}

export function useAcceptWorkspaceInvite() {
  const queryClient = useQueryClient()
  const { user } = useAuth()
  return useMutation({
    mutationFn: (inviteId: string) => acceptWorkspaceInvite(inviteId),
    onSuccess: (workspace, inviteId) => {
      const pendingInvites = queryClient.getQueryData<PendingInvite[]>(['workspace-invites', 'pending-for-user']) ?? []
      const acceptedInvite = pendingInvites.find((invite) => invite.id === inviteId)
      const membershipRole: Workspace['membership_role'] = acceptedInvite?.role === 'admin' ? 'admin' : 'member'
      if (user?.id) {
        queryClient.setQueryData<Workspace[]>(['workspaces', user.id], (current = []) => {
          const summary: Workspace = {
            ...workspace,
            membership_role: membershipRole,
            can_manage_workspace: membershipRole === 'admin',
            accessible_project_count: acceptedInvite?.project_count ?? 0,
            access_mode: 'assigned_projects',
          }
          return [...current.filter((item) => item.id !== workspace.id), summary]
        })
      }
      queryClient.setQueryData<PendingInvite[]>(
        ['workspace-invites', 'pending-for-user'],
        (current = []) => current.filter((invite) => invite.id !== inviteId),
      )
      void queryClient.invalidateQueries({ queryKey: ['workspaces'] })
      void queryClient.invalidateQueries({ queryKey: ['projects'] })
    },
  })
}
