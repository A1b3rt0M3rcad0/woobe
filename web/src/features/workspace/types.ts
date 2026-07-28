export interface OrgShape {
  id: string
  name: string
  slug: string
  membership_role?: 'owner' | 'admin' | 'member' | 'viewer'
  can_manage_organization?: boolean
  accessible_project_count?: number
  access_mode?: 'implicit_owner' | 'assigned_projects'
}

export interface ProjectShape {
  id: string
  organization_id: string
  name: string
  slug: string
  organization_role?: string
  access_source?: 'organization_owner' | 'project_membership'
}

export interface WorkspaceContextValue {
  organizations: OrgShape[]
  currentOrganization: OrgShape | null
  projects: ProjectShape[]
  currentProject: ProjectShape | null
  selectOrganization: (org: OrgShape) => void
  selectProject: (project: ProjectShape) => void
  clearCurrentProject: () => void
  clearCurrentOrganization: () => void
  isLoadingOrganizations: boolean
  isLoadingProjects: boolean
  isFetchingProjects: boolean
  workspaceError: Error | null
}
