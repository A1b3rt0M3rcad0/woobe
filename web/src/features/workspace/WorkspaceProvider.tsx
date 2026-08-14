import { createContext, useContext, useCallback, useEffect, useMemo, useState, type ReactNode } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useAuth } from '@/features/auth/AuthProvider'
import { getWorkspaces } from '@/features/auth/api'
import { getProjects } from '@/features/projects/api'
import type { WorkspaceContextValue, WorkspaceShape, ProjectShape } from './types'

export const WorkspaceContext = createContext<WorkspaceContextValue | null>(null)

function workspaceKey(userId: string, resource: 'workspace' | 'project') {
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
  const [currentProjState, setCurrentProjState] = useState<ProjectShape | null>(null)
  const [hydratedUserId, setHydratedUserId] = useState<string | null>(null)

  useEffect(() => {
    if (!user?.id) {
      setCurrentWorkspaceState(null)
      setCurrentProjState(null)
      setHydratedUserId(null)
      return
    }
    setCurrentWorkspaceState(readStored<WorkspaceShape>(workspaceKey(user.id, 'workspace')))
    setCurrentProjState(readStored<ProjectShape>(workspaceKey(user.id, 'project')))
    setHydratedUserId(user.id)
  }, [user?.id])

  const {
    data: workspaceResults = [],
    isLoading: isLoadingWorkspaces,
    error: workspaceQueryError,
  } = useQuery({
    queryKey: ['workspaces', user?.id],
    queryFn: getWorkspaces,
    enabled: isAuthenticated && Boolean(user?.id) && hydratedUserId === user?.id,
  })

  const workspaces = useMemo(() => workspaceResults.map((workspace: WorkspaceShape) => ({
    id: workspace.id,
    name: workspace.name,
    slug: workspace.slug,
    membership_role: workspace.membership_role,
    can_manage_workspace: workspace.can_manage_workspace,
    accessible_project_count: workspace.accessible_project_count,
    access_mode: workspace.access_mode,
  })), [workspaceResults])

  const validatedWorkspace = useMemo(() => {
    if (!currentWorkspaceState) return null
    return workspaces.find((workspace) => workspace.id === currentWorkspaceState.id) ?? null
  }, [currentWorkspaceState, workspaces])

  const {
    data: projects = [],
    isLoading: isLoadingProjects,
    isFetching: isFetchingProjects,
    error: projError,
  } = useQuery({
    queryKey: ['projects', user?.id, validatedWorkspace?.id],
    queryFn: () => getProjects(validatedWorkspace?.id),
    enabled: isAuthenticated && Boolean(user?.id) && hydratedUserId === user?.id && Boolean(validatedWorkspace?.id),
  })

  const projs = useMemo(() => projects.map((p: ProjectShape) => ({
    id: p.id,
    workspace_id: p.workspace_id,
    name: p.name,
    slug: p.slug,
    workspace_role: p.workspace_role,
    access_source: p.access_source,
  })), [projects])

  const validatedProject = useMemo(() => {
    if (!validatedWorkspace || !currentProjState) return null
    if (currentProjState.workspace_id !== validatedWorkspace.id) return null
    return projs.find((project) => project.id === currentProjState.id) ?? null
  }, [currentProjState, validatedWorkspace, projs])

  const selectWorkspace = useCallback((workspace: WorkspaceShape) => {
    if (!user?.id) return
    setCurrentWorkspaceState(workspace)
    setCurrentProjState(null)
    writeStored(workspaceKey(user.id, 'workspace'), workspace)
    writeStored(workspaceKey(user.id, 'project'), null)
  }, [user?.id])

  const selectProject = useCallback((project: ProjectShape) => {
    if (!user?.id) return
    setCurrentProjState(project)
    writeStored(workspaceKey(user.id, 'project'), project)
  }, [user?.id])

  const clearCurrentProject = useCallback(() => {
    setCurrentProjState(null)
    if (user?.id) writeStored(workspaceKey(user.id, 'project'), null)
  }, [user?.id])

  const clearCurrentWorkspace = useCallback(() => {
    setCurrentWorkspaceState(null)
    setCurrentProjState(null)
    if (user?.id) {
      writeStored(workspaceKey(user.id, 'workspace'), null)
      writeStored(workspaceKey(user.id, 'project'), null)
    }
  }, [user?.id])

  useEffect(() => {
    if (!user?.id || hydratedUserId !== user.id || isLoadingWorkspaces) return
    if (currentWorkspaceState && !validatedWorkspace) {
      setCurrentWorkspaceState(null)
      setCurrentProjState(null)
      writeStored(workspaceKey(user.id, 'workspace'), null)
      writeStored(workspaceKey(user.id, 'project'), null)
      return
    }
    if (!validatedWorkspace && workspaces.length === 1) selectWorkspace(workspaces[0])
  }, [currentWorkspaceState, hydratedUserId, isLoadingWorkspaces, workspaces, selectWorkspace, user?.id, validatedWorkspace])

  useEffect(() => {
    if (!user?.id || !currentProjState || isLoadingProjects || validatedProject) return
    setCurrentProjState(null)
    writeStored(workspaceKey(user.id, 'project'), null)
  }, [currentProjState, isLoadingProjects, user?.id, validatedProject])

  const workspaceError = (workspaceQueryError || projError) as Error | null
  const value = useMemo(() => ({
    workspaces: workspaces,
    currentWorkspace: validatedWorkspace,
    projects: projs,
    currentProject: validatedProject,
    selectWorkspace,
    selectProject,
    clearCurrentProject,
    clearCurrentWorkspace,
    isLoadingWorkspaces: isLoadingWorkspaces || (Boolean(user?.id) && hydratedUserId !== user?.id),
    isLoadingProjects,
    isFetchingProjects,
    workspaceError,
  }), [workspaces, validatedWorkspace, projs, validatedProject, selectWorkspace, selectProject, clearCurrentProject, clearCurrentWorkspace, isLoadingWorkspaces, user?.id, hydratedUserId, isLoadingProjects, isFetchingProjects, workspaceError])

  return <WorkspaceContext.Provider value={value}>{children}</WorkspaceContext.Provider>
}

export function useWorkspace() {
  const ctx = useContext(WorkspaceContext)
  if (!ctx) throw new Error('useWorkspace must be used within WorkspaceProvider')
  return ctx
}
