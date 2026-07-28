import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useAuth } from '@/features/auth/AuthProvider'
import type { Organization } from '@/features/auth/types'
import {
  getOrganization,
  updateOrganization,
  createOrganizationFromApi,
  getOrganizationMembers,
  removeOrganizationMember,
  getOrganizationInvites,
  createOrganizationInvite,
  cancelOrganizationInvite,
  getPendingOrganizationInvites,
  acceptOrganizationInvite,
} from './api'
import type {
  PendingInvite,
  UpdateOrganizationRequest,
  CreateOrganizationRequest,
  CreateInviteRequest,
} from './types'

export function useOrganization(id: string | undefined) {
  return useQuery({
    queryKey: ['organization', id],
    queryFn: () => getOrganization(id!),
    enabled: Boolean(id),
  })
}

export function useUpdateOrganization() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: UpdateOrganizationRequest }) => updateOrganization(id, data),
    onSuccess: (_, { id }) => {
      void queryClient.invalidateQueries({ queryKey: ['organization', id] })
      void queryClient.invalidateQueries({ queryKey: ['organizations'] })
    },
  })
}

export function useCreateOrganization() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (data: CreateOrganizationRequest) => createOrganizationFromApi(data),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ['organizations'] }),
  })
}

export function useOrganizationMembers(orgId: string | undefined) {
  return useQuery({
    queryKey: ['organization-members', orgId],
    queryFn: () => getOrganizationMembers(orgId!),
    enabled: Boolean(orgId),
  })
}

export function useRemoveOrganizationMember() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ orgId, userId }: { orgId: string; userId: string }) => removeOrganizationMember(orgId, userId),
    onSuccess: (_, { orgId }) => {
      void queryClient.invalidateQueries({ queryKey: ['organization-members', orgId] })
      void queryClient.invalidateQueries({ queryKey: ['organization-invites', orgId] })
      void queryClient.invalidateQueries({ queryKey: ['project-access', orgId] })
      void queryClient.invalidateQueries({ queryKey: ['project-members'] })
    },
  })
}

export function useOrganizationInvites(orgId: string | undefined, enabled = true) {
  return useQuery({
    queryKey: ['organization-invites', orgId],
    queryFn: () => getOrganizationInvites(orgId!),
    enabled: Boolean(orgId) && enabled,
  })
}

export function useCreateInvite() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ orgId, data }: { orgId: string; data: CreateInviteRequest }) => createOrganizationInvite(orgId, data),
    onSuccess: (_, { orgId }) => {
      void queryClient.invalidateQueries({ queryKey: ['organization-invites', orgId] })
      void queryClient.invalidateQueries({ queryKey: ['project-members'] })
      void queryClient.invalidateQueries({ queryKey: ['project-access', orgId] })
    },
  })
}

export function useCancelOrganizationInvite() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ orgId, inviteId }: { orgId: string; inviteId: string }) => cancelOrganizationInvite(orgId, inviteId),
    onSuccess: (_, { orgId }) => {
      void queryClient.invalidateQueries({ queryKey: ['organization-invites', orgId] })
      void queryClient.invalidateQueries({ queryKey: ['project-members'] })
      void queryClient.invalidateQueries({ queryKey: ['project-access', orgId] })
    },
  })
}

export function usePendingOrganizationInvites() {
  return useQuery({
    queryKey: ['organization-invites', 'pending-for-user'],
    queryFn: getPendingOrganizationInvites,
  })
}

export function useAcceptOrganizationInvite() {
  const queryClient = useQueryClient()
  const { user } = useAuth()
  return useMutation({
    mutationFn: (inviteId: string) => acceptOrganizationInvite(inviteId),
    onSuccess: (organization, inviteId) => {
      const pendingInvites = queryClient.getQueryData<PendingInvite[]>(['organization-invites', 'pending-for-user']) ?? []
      const acceptedInvite = pendingInvites.find((invite) => invite.id === inviteId)
      const membershipRole: Organization['membership_role'] = acceptedInvite?.role === 'admin' ? 'admin' : 'member'
      if (user?.id) {
        queryClient.setQueryData<Organization[]>(['organizations', user.id], (current = []) => {
          const summary: Organization = {
            ...organization,
            membership_role: membershipRole,
            can_manage_organization: membershipRole === 'admin',
            accessible_project_count: acceptedInvite?.project_count ?? 0,
            access_mode: 'assigned_projects',
          }
          return [...current.filter((item) => item.id !== organization.id), summary]
        })
      }
      queryClient.setQueryData<PendingInvite[]>(
        ['organization-invites', 'pending-for-user'],
        (current = []) => current.filter((invite) => invite.id !== inviteId),
      )
      void queryClient.invalidateQueries({ queryKey: ['organizations'] })
      void queryClient.invalidateQueries({ queryKey: ['projects'] })
    },
  })
}
