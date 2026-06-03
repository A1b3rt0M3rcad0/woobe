export interface OrgShape {
  id: string
  name: string
  slug: string
}

export interface ProjectShape {
  id: string
  organization_id: string
  name: string
  slug: string
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
  workspaceError: Error | null
}
