import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
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
  return useMutation({
    mutationFn: (inviteId: string) => acceptOrganizationInvite(inviteId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['organization-invites', 'pending-for-user'] })
      void queryClient.invalidateQueries({ queryKey: ['organizations'] })
      void queryClient.invalidateQueries({ queryKey: ['projects'] })
    },
  })
}
