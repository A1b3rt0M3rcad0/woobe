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
  email: string
  role: string
  status: string
  joined_at?: string | null
  access_mode: 'implicit_owner' | 'assigned_projects'
  project_access_count: number
}

export interface Invite {
  id: string
  organization_id: string
  email: string
  role: string
  status: string
  expires_at: string | null
  accepted_at?: string | null
  created_at: string | null
  project_ids: string[]
  project_count: number
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
  role: 'member' | 'admin'
  project_ids: string[]
}

export interface RemoveOrganizationMemberResult {
  organization_membership_removed: boolean
  project_accesses_removed: number
  pending_accesses_cancelled: number
}

export interface CancelOrganizationInviteResult {
  invite_cancelled: boolean
  pending_accesses_cancelled: number
}
