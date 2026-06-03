import { get, post, patch } from '@/lib/api/client'
import type {
  OrganizationDetail,
  Member,
  Invite,
  UpdateOrganizationRequest,
  CreateOrganizationRequest,
  CreateInviteRequest,
} from './types'

export async function getOrganization(id: string): Promise<OrganizationDetail> {
  return get<OrganizationDetail>(`/identity/organizations/${id}`)
}

export async function updateOrganization(id: string, data: UpdateOrganizationRequest): Promise<OrganizationDetail> {
  return patch<OrganizationDetail>(`/identity/organizations/${id}`, data)
}

export async function createOrganizationFromApi(data: CreateOrganizationRequest): Promise<OrganizationDetail> {
  return post<OrganizationDetail>('/identity/organizations', data)
}

export async function getOrganizationMembers(orgId: string): Promise<Member[]> {
  return get<Member[]>(`/identity/organizations/${orgId}/members`)
}

export async function getOrganizationInvites(orgId: string): Promise<Invite[]> {
  return get<Invite[]>(`/identity/organizations/${orgId}/invites`)
}

export async function createOrganizationInvite(orgId: string, data: CreateInviteRequest): Promise<Invite> {
  return post<Invite>(`/identity/organizations/${orgId}/invites`, data)
}
