import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useAuth } from '@/features/auth/AuthProvider'
import { getProjects } from '@/features/projects/api'
import { getWorkspaces } from '@/features/workspaces/api'
import type { ProjectShape, WorkspaceContextValue, WorkspaceShape } from './types'

export const WorkspaceContext = createContext<WorkspaceContextValue | null>(null)

function storageKey(userId: string, resource: 'workspace' | 'project') {
  return `woobe_workspace:${userId}:${resource}`
}

function readStored<T>(key: string): T | null {
  try {
    const raw = localStorage.getItem(key)
    return raw ? JSON.parse(raw) : null
  } catch {
    return null
  }
}

function writeStored<T>(key: string, value: T | null) {
  if (value) localStorage.setItem(key, JSON.stringify(value))
  else localStorage.removeItem(key)
}

export function WorkspaceProvider({ children }: { children: ReactNode }) {
  const { isAuthenticated, user } = useAuth()
  const [currentWorkspaceState, setCurrentWorkspaceState] = useState<WorkspaceShape | null>(null)
  const [currentProjectState, setCurrentProjectState] = useState<ProjectShape | null>(null)
  const [hydratedUserId, setHydratedUserId] = useState<string | null>(null)

  useEffect(() => {
    if (!user?.id) {
      setCurrentWorkspaceState(null)
      setCurrentProjectState(null)
      setHydratedUserId(null)
      return
    }
    setCurrentWorkspaceState(readStored<WorkspaceShape>(storageKey(user.id, 'workspace')))
    setCurrentProjectState(readStored<ProjectShape>(storageKey(user.id, 'project')))
    setHydratedUserId(user.id)
  }, [user?.id])

  const workspaceQuery = useQuery({
    queryKey: ['workspaces', user?.id],
    queryFn: getWorkspaces,
    enabled: isAuthenticated && Boolean(user?.id) && hydratedUserId === user?.id,
  })
  const workspaces = useMemo(
    () => (workspaceQuery.data ?? []).map((workspace) => ({
      id: workspace.id,
      name: workspace.name,
      slug: workspace.slug,
      status: workspace.status,
      can_manage: workspace.can_manage,
    })),
    [workspaceQuery.data],
  )
  const currentWorkspace = useMemo(
    () => currentWorkspaceState ? workspaces.find((workspace) => workspace.id === currentWorkspaceState.id) ?? null : null,
    [currentWorkspaceState, workspaces],
  )

  const projectsQuery = useQuery({
    queryKey: ['projects', user?.id, currentWorkspace?.id],
    queryFn: () => getProjects(currentWorkspace?.id),
    enabled: isAuthenticated && Boolean(currentWorkspace?.id),
  })
  const projects = useMemo(
    () => (projectsQuery.data ?? []).map((project) => ({
      id: project.id,
      workspace_id: project.workspace_id,
      name: project.name,
      slug: project.slug,
      access_source: project.access_source,
    })),
    [projectsQuery.data],
  )
  const currentProject = useMemo(() => {
    if (!currentWorkspace || !currentProjectState) return null
    if (currentProjectState.workspace_id !== currentWorkspace.id) return null
    return projects.find((project) => project.id === currentProjectState.id) ?? null
  }, [currentProjectState, currentWorkspace, projects])

  const selectWorkspace = useCallback((workspace: WorkspaceShape) => {
    if (!user?.id) return
    setCurrentWorkspaceState(workspace)
    setCurrentProjectState(null)
    writeStored(storageKey(user.id, 'workspace'), workspace)
    writeStored(storageKey(user.id, 'project'), null)
  }, [user?.id])

  const selectProject = useCallback((project: ProjectShape) => {
    if (!user?.id) return
    setCurrentProjectState(project)
    writeStored(storageKey(user.id, 'project'), project)
  }, [user?.id])

  const clearCurrentProject = useCallback(() => {
    setCurrentProjectState(null)
    if (user?.id) writeStored(storageKey(user.id, 'project'), null)
  }, [user?.id])

  const clearCurrentWorkspace = useCallback(() => {
    setCurrentWorkspaceState(null)
    setCurrentProjectState(null)
    if (user?.id) {
      writeStored(storageKey(user.id, 'workspace'), null)
      writeStored(storageKey(user.id, 'project'), null)
    }
  }, [user?.id])

  useEffect(() => {
    if (!user?.id || hydratedUserId !== user.id || workspaceQuery.isLoading) return
    if (currentWorkspaceState && !currentWorkspace) {
      clearCurrentWorkspace()
      return
    }
    if (!currentWorkspace && workspaces.length === 1) selectWorkspace(workspaces[0])
  }, [clearCurrentWorkspace, currentWorkspace, currentWorkspaceState, hydratedUserId, selectWorkspace, user?.id, workspaceQuery.isLoading, workspaces])

  useEffect(() => {
    if (!user?.id || !currentProjectState || projectsQuery.isLoading || currentProject) return
    clearCurrentProject()
  }, [clearCurrentProject, currentProject, currentProjectState, projectsQuery.isLoading, user?.id])

  const value = useMemo<WorkspaceContextValue>(() => ({
    workspaces,
    currentWorkspace,
    projects,
    currentProject,
    selectWorkspace,
    selectProject,
    clearCurrentProject,
    clearCurrentWorkspace,
    isLoadingWorkspaces: workspaceQuery.isLoading || (Boolean(user?.id) && hydratedUserId !== user?.id),
    isLoadingProjects: projectsQuery.isLoading,
    isFetchingProjects: projectsQuery.isFetching,
    workspaceError: (workspaceQuery.error || projectsQuery.error) as Error | null,
  }), [clearCurrentProject, clearCurrentWorkspace, currentProject, currentWorkspace, hydratedUserId, projects, projectsQuery.error, projectsQuery.isFetching, projectsQuery.isLoading, selectProject, selectWorkspace, user?.id, workspaceQuery.error, workspaceQuery.isLoading, workspaces])

  return <WorkspaceContext.Provider value={value}>{children}</WorkspaceContext.Provider>
}

export function useWorkspace() {
  const ctx = useContext(WorkspaceContext)
  if (!ctx) throw new Error('useWorkspace must be used within WorkspaceProvider')
  return ctx
}
