export interface Project {
  id: string
  organization_id: string
  name: string
  slug: string
  status?: string
  created_at?: string
  updated_at?: string
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
