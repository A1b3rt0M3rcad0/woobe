import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { getProjects, getProject, createProject, updateProject } from './api'
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
    },
  })
}

export function useUpdateProject() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: UpdateProjectRequest }) =>
      updateProject(id, data),
    onSuccess: (_, { id }) => {
      queryClient.invalidateQueries({ queryKey: ['project', id] })
      queryClient.invalidateQueries({ queryKey: ['projects'] })
    },
  })
}
