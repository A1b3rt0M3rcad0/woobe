import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useAuth } from '@/features/auth/AuthProvider'
import {
  getProjects,
  getProject,
  createProject,
  updateProject,
  getProjectsForAccessManagement,
  getProjectMembers,
  grantProjectSubjectAccess,
  revokeProjectSubjectAccess,
} from './api'
import type { Project, ProjectAccessSubject, CreateProjectRequest, UpdateProjectRequest } from './types'

export function upsertProject(current: Project[] | undefined, project: Project): Project[] {
  const projects = current ?? []
  const existingIndex = projects.findIndex((item) => item.id === project.id)
  if (existingIndex === -1) return [...projects, project]
  return projects.map((item, index) => index === existingIndex ? project : item)
}

export function useProjects(organizationId?: string) {
  const { user } = useAuth()
  return useQuery({
    queryKey: ['projects', user?.id, organizationId],
    queryFn: () => getProjects(organizationId),
    enabled: Boolean(user?.id && organizationId),
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
  const { user } = useAuth()
  return useMutation({
    mutationFn: (data: CreateProjectRequest) => createProject(data),
    onSuccess: (project) => {
      queryClient.setQueryData<Project[]>(
        ['projects', user?.id, organizationId],
        (current) => upsertProject(current, project),
      )
      queryClient.setQueryData(['project', project.id], project)
      void queryClient.invalidateQueries({ queryKey: ['projects', user?.id, organizationId] })
      void queryClient.invalidateQueries({ queryKey: ['project-access', project.organization_id] })
      void queryClient.invalidateQueries({ queryKey: ['organizations', user?.id] })
    },
  })
}

export function useUpdateProject() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: UpdateProjectRequest }) => updateProject(id, data),
    onSuccess: (project, { id }) => {
      void queryClient.invalidateQueries({ queryKey: ['project', id] })
      void queryClient.invalidateQueries({ queryKey: ['projects'] })
      void queryClient.invalidateQueries({ queryKey: ['project-access', project.organization_id] })
    },
  })
}

export function useProjectsForAccessManagement(organizationId: string | undefined, enabled = true) {
  return useQuery({
    queryKey: ['project-access', organizationId],
    queryFn: () => getProjectsForAccessManagement(organizationId!),
    enabled: Boolean(organizationId) && enabled,
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
    mutationFn: ({
      projectId,
      subjectType,
      subjectId,
    }: {
      projectId: string
      subjectType: ProjectAccessSubject['subject_type']
      subjectId: string
    }) => grantProjectSubjectAccess(projectId, subjectType, subjectId),
    onSuccess: (_, { projectId }) => {
      void queryClient.invalidateQueries({ queryKey: ['project-members', projectId] })
      void queryClient.invalidateQueries({ queryKey: ['project-access'] })
      void queryClient.invalidateQueries({ queryKey: ['organization-members'] })
      void queryClient.invalidateQueries({ queryKey: ['organization-invites'] })
    },
  })
}

export function useRevokeProjectAccess() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({
      projectId,
      subjectType,
      subjectId,
    }: {
      projectId: string
      subjectType: ProjectAccessSubject['subject_type']
      subjectId: string
    }) => revokeProjectSubjectAccess(projectId, subjectType, subjectId),
    onSuccess: (_, { projectId }) => {
      void queryClient.invalidateQueries({ queryKey: ['project-members', projectId] })
      void queryClient.invalidateQueries({ queryKey: ['project-access'] })
      void queryClient.invalidateQueries({ queryKey: ['organization-members'] })
      void queryClient.invalidateQueries({ queryKey: ['organization-invites'] })
    },
  })
}
