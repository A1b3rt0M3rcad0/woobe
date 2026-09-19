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
  getProjectEnvironmentKeys,
  getProjectEnvironmentKeyUsage,
  upsertProjectEnvironmentKey,
  deleteProjectEnvironmentKey,
} from './api'
import type {
  Project,
  ProjectAccessSubject,
  CreateProjectRequest,
  UpdateProjectRequest,
  UpsertProjectEnvironmentKeyRequest,
} from './types'

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
  return useQuery({
    queryKey: ['project', id],
    queryFn: () => getProject(id!),
    enabled: Boolean(id),
  })
}

export function useCreateProject(workspaceId?: string) {
  const queryClient = useQueryClient()
  const { user } = useAuth()
  return useMutation({
    mutationFn: (data: CreateProjectRequest) => createProject(data),
    onSuccess: (project) => {
      queryClient.setQueryData<Project[]>(
        ['projects', user?.id, workspaceId],
        (current) => upsertProject(current, project),
      )
      queryClient.setQueryData(['project', project.id], project)
      void queryClient.invalidateQueries({ queryKey: ['projects', user?.id, workspaceId] })
      void queryClient.invalidateQueries({ queryKey: ['project-access', project.workspace_id] })
      void queryClient.invalidateQueries({ queryKey: ['workspaces', user?.id] })
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
      void queryClient.invalidateQueries({ queryKey: ['workspace-members'] })
      void queryClient.invalidateQueries({ queryKey: ['workspace-invites'] })
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
      void queryClient.invalidateQueries({ queryKey: ['workspace-members'] })
      void queryClient.invalidateQueries({ queryKey: ['workspace-invites'] })
    },
  })
}


export function useProjectEnvironmentKeyUsage(
  projectId: string | undefined,
  key: string | undefined,
) {
  return useQuery({
    queryKey: ['project-environment-key-usage', projectId, key],
    queryFn: () => getProjectEnvironmentKeyUsage(projectId!, key!),
    enabled: Boolean(projectId && key),
  })
}


export function useProjectEnvironmentKeys(projectId: string | undefined) {
  return useQuery({
    queryKey: ['project-environment-keys', projectId],
    queryFn: () => getProjectEnvironmentKeys(projectId!),
    enabled: Boolean(projectId),
  })
}

export function useUpsertProjectEnvironmentKey() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({
      projectId,
      key,
      data,
    }: {
      projectId: string
      key: string
      data: UpsertProjectEnvironmentKeyRequest
    }) => upsertProjectEnvironmentKey(projectId, key, data),
    onSuccess: (_, { projectId }) => {
      void queryClient.invalidateQueries({ queryKey: ['project-environment-keys', projectId] })
    },
  })
}

export function useDeleteProjectEnvironmentKey() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ projectId, key }: { projectId: string; key: string }) => (
      deleteProjectEnvironmentKey(projectId, key)
    ),
    onSuccess: (_, { projectId }) => {
      void queryClient.invalidateQueries({ queryKey: ['project-environment-keys', projectId] })
    },
  })
}
