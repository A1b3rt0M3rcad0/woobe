import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  getOrganization,
  updateOrganization,
  createOrganizationFromApi,
  getOrganizationMembers,
  getOrganizationInvites,
  createOrganizationInvite,
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
    mutationFn: ({ id, data }: { id: string; data: UpdateOrganizationRequest }) =>
      updateOrganization(id, data),
    onSuccess: (_, { id }) => {
      queryClient.invalidateQueries({ queryKey: ['organization', id] })
      queryClient.invalidateQueries({ queryKey: ['organizations'] })
    },
  })
}

export function useCreateOrganization() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (data: CreateOrganizationRequest) => createOrganizationFromApi(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['organizations'] })
    },
  })
}

export function useOrganizationMembers(orgId: string | undefined) {
  return useQuery({
    queryKey: ['organization-members', orgId],
    queryFn: () => getOrganizationMembers(orgId!),
    enabled: Boolean(orgId),
  })
}

export function useOrganizationInvites(orgId: string | undefined) {
  return useQuery({
    queryKey: ['organization-invites', orgId],
    queryFn: () => getOrganizationInvites(orgId!),
    enabled: Boolean(orgId),
  })
}

export function useCreateInvite() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ orgId, data }: { orgId: string; data: CreateInviteRequest }) =>
      createOrganizationInvite(orgId, data),
    onSuccess: (_, { orgId }) => {
      queryClient.invalidateQueries({ queryKey: ['organization-invites', orgId] })
    },
  })
}
