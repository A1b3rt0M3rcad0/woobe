export interface WorkspaceShape {
  id: string
  name: string
  slug: string
  status?: string
  can_manage?: boolean
}

export interface ProjectShape {
  id: string
  workspace_id: string
  name: string
  slug: string
  access_source?: 'instance_admin' | 'project_membership'
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
