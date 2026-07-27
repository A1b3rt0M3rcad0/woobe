export interface Project {
  id: string
  organization_id: string
  name: string
  slug: string
  status?: string
  created_at?: string
  updated_at?: string
}

export interface ProjectAccessSummary extends Project {
  member_count: number
}

export interface ProjectAccessMember {
  id: string | null
  user_id: string
  email: string
  status: string
  created_at?: string | null
  implicit_owner: boolean
}

export interface ProjectMembersResponse {
  members: ProjectAccessMember[]
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
