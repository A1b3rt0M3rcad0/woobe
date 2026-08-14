import { useWorkspace } from '@/features/workspace/WorkspaceProvider'
import type { WorkspaceShape, ProjectShape } from '@/features/workspace/types'

export function useCurrentWorkspace() {
  const { currentWorkspace, workspaces, selectWorkspace, isLoadingWorkspaces } = useWorkspace()
  return { currentWorkspace, workspaces, selectWorkspace, isLoading: isLoadingWorkspaces }
}

export function useCurrentProject() {
  const ws = useWorkspace()
  return {
    currentProject: ws.currentProject as ProjectShape | null,
    projects: ws.projects,
    selectProject: ws.selectProject,
    clearCurrentProject: ws.clearCurrentProject,
    isLoading: ws.isLoadingProjects,
    currentWorkspace: ws.currentWorkspace,
  }
}

export function useWorkspaceHelpers() {
  const ws = useWorkspace()
  return {
    clearCurrentProject: ws.clearCurrentProject,
    clearCurrentWorkspace: ws.clearCurrentWorkspace,
    selectWorkspace: ws.selectWorkspace,
    selectProject: ws.selectProject,
  }
}
