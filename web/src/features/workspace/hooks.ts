import { useWorkspace } from '@/features/workspace/WorkspaceProvider'
import type { OrgShape, ProjectShape } from '@/features/workspace/types'

export function useCurrentOrganization() {
  const { currentOrganization, organizations, selectOrganization, isLoadingOrganizations } = useWorkspace()
  return { currentOrganization, organizations, selectOrganization, isLoading: isLoadingOrganizations }
}

export function useCurrentProject() {
  const ws = useWorkspace()
  return {
    currentProject: ws.currentProject as ProjectShape | null,
    projects: ws.projects,
    selectProject: ws.selectProject,
    clearCurrentProject: ws.clearCurrentProject,
    isLoading: ws.isLoadingProjects,
    currentOrganization: ws.currentOrganization,
  }
}

export function useWorkspaceHelpers() {
  const ws = useWorkspace()
  return {
    clearCurrentProject: ws.clearCurrentProject,
    clearCurrentOrganization: ws.clearCurrentOrganization,
    selectOrganization: ws.selectOrganization,
    selectProject: ws.selectProject,
  }
}
