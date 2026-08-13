import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useAuth } from '@/features/auth/AuthProvider'
import {
  createProject,
  getProject,
  getProjectMembers,
  getProjects,
  getProjectsForAccessManagement,
  grantProjectAccess,
  revokeProjectAccess,
  updateProject,
} from './api'
import type { CreateProjectRequest, Project, UpdateProjectRequest } from './types'

export function upsertProject(current: Project[] | undefined, project: Project): Project[] {
  const projects = current ?? []
  const existingIndex = projects.findIndex((item) => item.id === project.id)
  if (existingIndex === -1) return [...projects, project]
  return projects.map((item, index) => index === existingIndex ? project : item)
}

export function useProjects(workspaceId?: string) {
  const { user } = useAuth()
  return useQuery({
    queryKey: ['projects', user?.id, workspaceId],
    queryFn: () => getProjects(workspaceId),
    enabled: Boolean(user?.id && workspaceId),
  })
}

export function useProject(id: string | undefined) {
  return useQuery({ queryKey: ['project', id], queryFn: () => getProject(id!), enabled: Boolean(id) })
}

export function useCreateProject(workspaceId?: string) {
  const queryClient = useQueryClient()
  const { user } = useAuth()
  return useMutation({
    mutationFn: (data: CreateProjectRequest) => createProject(data),
    onSuccess: (project) => {
      queryClient.setQueryData<Project[]>(['projects', user?.id, workspaceId], (current) => upsertProject(current, project))
      queryClient.setQueryData(['project', project.id], project)
      void queryClient.invalidateQueries({ queryKey: ['projects', user?.id, workspaceId] })
      void queryClient.invalidateQueries({ queryKey: ['project-access', project.workspace_id] })
      void queryClient.invalidateQueries({ queryKey: ['workspaces'] })
    },
  })
}

export function useUpdateProject() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: UpdateProjectRequest }) => updateProject(id, data),
    onSuccess: (project, { id }) => {
      queryClient.setQueryData(['project', id], project)
      void queryClient.invalidateQueries({ queryKey: ['projects'] })
      void queryClient.invalidateQueries({ queryKey: ['project-access', project.workspace_id] })
    },
  })
}

export function useProjectsForAccessManagement(workspaceId: string | undefined, enabled = true) {
  return useQuery({
    queryKey: ['project-access', workspaceId],
    queryFn: () => getProjectsForAccessManagement(workspaceId!),
    enabled: Boolean(workspaceId) && enabled,
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
    mutationFn: ({ projectId, email }: { projectId: string; email: string }) => grantProjectAccess(projectId, email),
    onSuccess: (_, { projectId }) => {
      void queryClient.invalidateQueries({ queryKey: ['project-members', projectId] })
      void queryClient.invalidateQueries({ queryKey: ['project-access'] })
    },
  })
}

export function useRevokeProjectAccess() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ projectId, userId }: { projectId: string; userId: string }) => revokeProjectAccess(projectId, userId),
    onSuccess: (_, { projectId }) => {
      void queryClient.invalidateQueries({ queryKey: ['project-members', projectId] })
      void queryClient.invalidateQueries({ queryKey: ['project-access'] })
    },
  })
}
