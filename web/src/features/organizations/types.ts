export interface OrganizationDetail {
  id: string
  name: string
  slug: string
  status: string
  created_at: string | null
}

export interface Member {
  id: string
  user_id: string
  organization_id: string
  role: string
  status: string
}

export interface Invite {
  id: string
  organization_id: string
  email: string
  role: string
  status: string
  expires_at: string | null
  created_at: string | null
}

export interface PendingInvite extends Invite {
  organization_name: string
  organization_slug: string
}

export interface UpdateOrganizationRequest {
  name?: string
  slug?: string
}

export interface CreateOrganizationRequest {
  name: string
  slug: string
}

export interface CreateInviteRequest {
  email: string
  role: string
}
