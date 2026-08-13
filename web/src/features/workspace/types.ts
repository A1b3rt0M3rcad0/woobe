export interface WorkspaceShape {
  id: string
  name: string
  slug: string
  status?: string
  can_manage?: boolean
  membership_role?: 'owner' | 'admin' | 'member' | 'viewer'
  can_manage_organization?: boolean
  accessible_project_count?: number
}

export type OrgShape = WorkspaceShape

export interface ProjectShape {
  id: string
  workspace_id: string
  organization_id?: string
  name: string
  slug: string
  access_source?: 'instance_admin' | 'project_membership' | 'organization_owner'
  organization_role?: string
}

export interface WorkspaceContextValue {
  workspaces: WorkspaceShape[]
  currentWorkspace: WorkspaceShape | null
  projects: ProjectShape[]
  currentProject: ProjectShape | null
  selectWorkspace: (workspace: WorkspaceShape) => void
  selectProject: (project: ProjectShape) => void
  clearCurrentProject: () => void
  clearCurrentWorkspace: () => void
  isLoadingWorkspaces: boolean
  isLoadingProjects: boolean
  isFetchingProjects: boolean
  workspaceError: Error | null

  // Temporary internal aliases while remaining Project pages are migrated from
  // the former Organization route naming. They are not API/domain contracts.
  organizations: WorkspaceShape[]
  currentOrganization: WorkspaceShape | null
  selectOrganization: (workspace: WorkspaceShape) => void
  clearCurrentOrganization: () => void
  isLoadingOrganizations: boolean
  organizationError: Error | null
}
