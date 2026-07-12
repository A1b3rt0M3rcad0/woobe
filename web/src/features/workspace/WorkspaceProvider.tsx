import { createContext, useContext, useCallback, useEffect, useMemo, useState, type ReactNode } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useAuth } from '@/features/auth/AuthProvider'
import { getOrganizations } from '@/features/auth/api'
import { getProjects } from '@/features/projects/api'
import type { WorkspaceContextValue, OrgShape, ProjectShape } from './types'

const WorkspaceContext = createContext<WorkspaceContextValue | null>(null)

const STORED_ORG_KEY = 'projectrai_org'
const STORED_PROJECT_KEY = 'projectrai_project'

function readStored<T>(key: string): T | null {
  try {
    const raw = localStorage.getItem(key)
    return raw ? JSON.parse(raw) : null
  } catch {
    return null
  }
}

function writeStored<T>(key: string, value: T | null) {
  if (value) {
    localStorage.setItem(key, JSON.stringify(value))
  } else {
    localStorage.removeItem(key)
  }
}

export function WorkspaceProvider({ children }: { children: ReactNode }) {
  const { isAuthenticated } = useAuth()

  const [currentOrgState, setCurrentOrgState] = useState<OrgShape | null>(() => readStored(STORED_ORG_KEY))
  const [currentProjState, setCurrentProjState] = useState<ProjectShape | null>(() => readStored(STORED_PROJECT_KEY))

  const {
    data: organizations = [],
    isLoading: isLoadingOrganizations,
    error: orgError,
  } = useQuery({
    queryKey: ['organizations'],
    queryFn: getOrganizations,
    enabled: isAuthenticated,
  })

  const orgs = useMemo(() => organizations.map((o: OrgShape) => ({ id: o.id, name: o.name, slug: o.slug })), [organizations])

  const validatedOrg = useMemo(() => {
    if (currentOrgState && orgs.find((o) => o.id === currentOrgState.id)) {
      return currentOrgState
    }
    return null
  }, [currentOrgState, orgs])

  const {
    data: projects = [],
    isLoading: isLoadingProjects,
    isFetching: isFetchingProjects,
    error: projError,
  } = useQuery({
    queryKey: ['projects', validatedOrg?.id],
    queryFn: () => getProjects(validatedOrg?.id),
    enabled: isAuthenticated && !!validatedOrg?.id,
  })

  const projs = useMemo(() => projects.map((p: ProjectShape) => ({
    id: p.id,
    organization_id: p.organization_id,
    name: p.name,
    slug: p.slug,
  })), [projects])

  const validatedProject = useMemo(() => {
    if (!validatedOrg) return null
    if (currentProjState && currentProjState.organization_id === validatedOrg.id && projs.find((p) => p.id === currentProjState.id)) {
      return currentProjState
    }
    return null
  }, [currentProjState, validatedOrg, projs])

  const selectOrganization = useCallback((org: OrgShape) => {
    setCurrentOrgState(org)
    setCurrentProjState(null)
    writeStored(STORED_ORG_KEY, org)
    writeStored(STORED_PROJECT_KEY, null)
  }, [])

  const selectProject = useCallback((project: ProjectShape) => {
    setCurrentProjState(project)
    writeStored(STORED_PROJECT_KEY, project)
  }, [])

  const clearCurrentProject = useCallback(() => {
    setCurrentProjState(null)
    writeStored(STORED_PROJECT_KEY, null)
  }, [])

  const clearCurrentOrganization = useCallback(() => {
    setCurrentOrgState(null)
    setCurrentProjState(null)
    writeStored(STORED_ORG_KEY, null)
    writeStored(STORED_PROJECT_KEY, null)
  }, [])

  useEffect(() => {
    if (
      isAuthenticated
      && !isLoadingOrganizations
      && !validatedOrg
      && orgs.length === 1
    ) {
      selectOrganization(orgs[0])
    }
  }, [isAuthenticated, isLoadingOrganizations, orgs, selectOrganization, validatedOrg])

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
    isLoadingOrganizations,
    isLoadingProjects,
    isFetchingProjects,
    workspaceError,
  }), [orgs, validatedOrg, projs, validatedProject, selectOrganization, selectProject, clearCurrentProject, clearCurrentOrganization, isLoadingOrganizations, isLoadingProjects, isFetchingProjects, workspaceError])

  return (
    <WorkspaceContext.Provider value={value}>
      {children}
    </WorkspaceContext.Provider>
  )
}

export function useWorkspace() {
  const ctx = useContext(WorkspaceContext)
  if (!ctx) throw new Error('useWorkspace must be used within WorkspaceProvider')
  return ctx
}
