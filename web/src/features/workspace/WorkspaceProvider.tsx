import { createContext, useContext, useCallback, useEffect, useMemo, useState, type ReactNode } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useAuth } from '@/features/auth/AuthProvider'
import { getOrganizations } from '@/features/auth/api'
import { getProjects } from '@/features/projects/api'
import type { WorkspaceContextValue, OrgShape, ProjectShape } from './types'

export const WorkspaceContext = createContext<WorkspaceContextValue | null>(null)

function workspaceKey(userId: string, resource: 'organization' | 'project') {
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
  const [currentOrgState, setCurrentOrgState] = useState<OrgShape | null>(null)
  const [currentProjState, setCurrentProjState] = useState<ProjectShape | null>(null)
  const [hydratedUserId, setHydratedUserId] = useState<string | null>(null)

  useEffect(() => {
    if (!user?.id) {
      setCurrentOrgState(null)
      setCurrentProjState(null)
      setHydratedUserId(null)
      return
    }
    setCurrentOrgState(readStored<OrgShape>(workspaceKey(user.id, 'organization')))
    setCurrentProjState(readStored<ProjectShape>(workspaceKey(user.id, 'project')))
    setHydratedUserId(user.id)
  }, [user?.id])

  const {
    data: organizations = [],
    isLoading: isLoadingOrganizations,
    error: orgError,
  } = useQuery({
    queryKey: ['organizations', user?.id],
    queryFn: getOrganizations,
    enabled: isAuthenticated && Boolean(user?.id) && hydratedUserId === user?.id,
  })

  const orgs = useMemo(() => organizations.map((o: OrgShape) => ({
    id: o.id,
    name: o.name,
    slug: o.slug,
    membership_role: o.membership_role,
    can_manage_organization: o.can_manage_organization,
    accessible_project_count: o.accessible_project_count,
    access_mode: o.access_mode,
  })), [organizations])

  const validatedOrg = useMemo(() => {
    if (!currentOrgState) return null
    return orgs.find((organization) => organization.id === currentOrgState.id) ?? null
  }, [currentOrgState, orgs])

  const {
    data: projects = [],
    isLoading: isLoadingProjects,
    isFetching: isFetchingProjects,
    error: projError,
  } = useQuery({
    queryKey: ['projects', user?.id, validatedOrg?.id],
    queryFn: () => getProjects(validatedOrg?.id),
    enabled: isAuthenticated && Boolean(user?.id) && hydratedUserId === user?.id && Boolean(validatedOrg?.id),
  })

  const projs = useMemo(() => projects.map((p: ProjectShape) => ({
    id: p.id,
    organization_id: p.organization_id,
    name: p.name,
    slug: p.slug,
    organization_role: p.organization_role,
    access_source: p.access_source,
  })), [projects])

  const validatedProject = useMemo(() => {
    if (!validatedOrg || !currentProjState) return null
    if (currentProjState.organization_id !== validatedOrg.id) return null
    return projs.find((project) => project.id === currentProjState.id) ?? null
  }, [currentProjState, validatedOrg, projs])

  const selectOrganization = useCallback((org: OrgShape) => {
    if (!user?.id) return
    setCurrentOrgState(org)
    setCurrentProjState(null)
    writeStored(workspaceKey(user.id, 'organization'), org)
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

  const clearCurrentOrganization = useCallback(() => {
    setCurrentOrgState(null)
    setCurrentProjState(null)
    if (user?.id) {
      writeStored(workspaceKey(user.id, 'organization'), null)
      writeStored(workspaceKey(user.id, 'project'), null)
    }
  }, [user?.id])

  useEffect(() => {
    if (!user?.id || hydratedUserId !== user.id || isLoadingOrganizations) return
    if (currentOrgState && !validatedOrg) {
      setCurrentOrgState(null)
      setCurrentProjState(null)
      writeStored(workspaceKey(user.id, 'organization'), null)
      writeStored(workspaceKey(user.id, 'project'), null)
      return
    }
    if (!validatedOrg && orgs.length === 1) selectOrganization(orgs[0])
  }, [currentOrgState, hydratedUserId, isLoadingOrganizations, orgs, selectOrganization, user?.id, validatedOrg])

  useEffect(() => {
    if (!user?.id || !currentProjState || isLoadingProjects || validatedProject) return
    setCurrentProjState(null)
    writeStored(workspaceKey(user.id, 'project'), null)
  }, [currentProjState, isLoadingProjects, user?.id, validatedProject])

  const workspaceError = (orgError || projError) as Error | null
  const value = useMemo(() => ({
    organizations: orgs,
    currentOrganization: validatedOrg,
    projects: projs,
    currentProject: validatedProject,
    selectOrganization,
    selectProject,
    clearCurrentProject,
    clearCurrentOrganization,
    isLoadingOrganizations: isLoadingOrganizations || (Boolean(user?.id) && hydratedUserId !== user?.id),
    isLoadingProjects,
    isFetchingProjects,
    workspaceError,
  }), [orgs, validatedOrg, projs, validatedProject, selectOrganization, selectProject, clearCurrentProject, clearCurrentOrganization, isLoadingOrganizations, user?.id, hydratedUserId, isLoadingProjects, isFetchingProjects, workspaceError])

  return <WorkspaceContext.Provider value={value}>{children}</WorkspaceContext.Provider>
}

export function useWorkspace() {
  const ctx = useContext(WorkspaceContext)
  if (!ctx) throw new Error('useWorkspace must be used within WorkspaceProvider')
  return ctx
}
