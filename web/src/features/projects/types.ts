export interface Project {
  id: string
  workspace_id: string
  name: string
  slug: string
  status?: string
  created_at?: string
  updated_at?: string
  access_source?: 'instance_admin' | 'project_membership'
}

export interface ProjectAccessSummary extends Project {
  member_count?: number
  pending_count?: number
}

export interface ProjectAccessSubject {
  user_id: string
  email: string
  project_access: 'active' | 'none'
}

export interface ProjectMembersResponse {
  subjects: ProjectAccessSubject[]
  can_manage: boolean
}

export interface CreateProjectRequest {
  workspace_id: string
  name: string
  slug: string
}

export interface UpdateProjectRequest {
  name?: string
  slug?: string
}
