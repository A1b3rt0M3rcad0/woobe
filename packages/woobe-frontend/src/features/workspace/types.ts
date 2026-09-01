export interface WorkspaceShape {
  id: string
  name: string
  slug: string
  membership_role?: 'owner' | 'admin' | 'member' | 'viewer'
  can_manage_workspace?: boolean
  accessible_project_count?: number
  access_mode?: 'implicit_owner' | 'assigned_projects'
}

export interface ProjectShape {
  id: string
  workspace_id: string
  name: string
  slug: string
  workspace_role?: string
  access_source?: 'workspace_owner' | 'project_membership'
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
}
