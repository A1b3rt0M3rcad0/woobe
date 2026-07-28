export interface Project {
  id: string
  organization_id: string
  name: string
  slug: string
  status?: string
  created_at?: string
  updated_at?: string
  organization_role?: string
  access_source?: 'organization_owner' | 'project_membership'
}

export interface ProjectAccessSummary extends Project {
  member_count: number
  pending_count: number
}

export interface ProjectAccessSubject {
  subject_type: 'member' | 'invite'
  subject_id: string
  user_id: string | null
  invite_id: string | null
  email: string
  organization_role: string
  organization_status: 'active' | 'pending'
  project_access: 'implicit' | 'active' | 'pending' | 'none'
  project_member_id: string | null
  pending_access_id: string | null
}

export interface ProjectMembersResponse {
  subjects: ProjectAccessSubject[]
  can_manage: boolean
}

export interface CreateProjectRequest {
  organization_id: string
  name: string
  slug: string
}

export interface UpdateProjectRequest {
  name?: string
  slug?: string
}
