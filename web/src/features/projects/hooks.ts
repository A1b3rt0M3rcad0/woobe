import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  getProjects,
  getProject,
  createProject,
  updateProject,
  getProjectsForAccessManagement,
  getProjectMembers,
  grantProjectAccess,
  revokeProjectAccess,
} from './api'
import type { Project, CreateProjectRequest, UpdateProjectRequest } from './types'

export function upsertProject(current: Project[] | undefined, project: Project): Project[] {
  const projects = current ?? []
  const existingIndex = projects.findIndex((item) => item.id === project.id)

  if (existingIndex === -1) return [...projects, project]
  return projects.map((item, index) => index === existingIndex ? project : item)
}

export function useProjects(organizationId?: string) {
  return useQuery({
    queryKey: ['projects', organizationId],
    queryFn: () => getProjects(organizationId),
    enabled: Boolean(organizationId),
  })
}

export function useProject(id: string | undefined) {
  return useQuery({
    queryKey: ['project', id],
    queryFn: () => getProject(id!),
    enabled: Boolean(id),
  })
}

export function useCreateProject(organizationId?: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (data: CreateProjectRequest) => createProject(data),
    onSuccess: (project) => {
      queryClient.setQueryData<Project[]>(
        ['projects', organizationId],
        (current) => upsertProject(current, project),
      )
      queryClient.setQueryData(['project', project.id], project)
      void queryClient.invalidateQueries({ queryKey: ['projects', organizationId] })
      void queryClient.invalidateQueries({ queryKey: ['project-access', project.organization_id] })
    },
  })
}

export function useUpdateProject() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: UpdateProjectRequest }) =>
      updateProject(id, data),
    onSuccess: (project, { id }) => {
      queryClient.invalidateQueries({ queryKey: ['project', id] })
      queryClient.invalidateQueries({ queryKey: ['projects'] })
      queryClient.invalidateQueries({ queryKey: ['project-access', project.organization_id] })
    },
  })
}

export function useProjectsForAccessManagement(organizationId: string | undefined) {
  return useQuery({
    queryKey: ['project-access', organizationId],
    queryFn: () => getProjectsForAccessManagement(organizationId!),
    enabled: Boolean(organizationId),
    retry: false,
  })
}

export function useProjectMembers(projectId: string | undefined) {
  return useQuery({
    queryKey: ['project-members', projectId],
    queryFn: () => getProjectMembers(projectId!),
    enabled: Boolean(projectId),
  })
}

export function useGrantProjectAccess() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ projectId, email }: { projectId: string; email: string }) =>
      grantProjectAccess(projectId, email),
    onSuccess: (_, { projectId }) => {
      queryClient.invalidateQueries({ queryKey: ['project-members', projectId] })
      queryClient.invalidateQueries({ queryKey: ['project-access'] })
    },
  })
}

export function useRevokeProjectAccess() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ projectId, userId }: { projectId: string; userId: string }) =>
      revokeProjectAccess(projectId, userId),
    onSuccess: (_, { projectId }) => {
      queryClient.invalidateQueries({ queryKey: ['project-members', projectId] })
      queryClient.invalidateQueries({ queryKey: ['project-access'] })
    },
  })
}
