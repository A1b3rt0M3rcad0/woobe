import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { getProjects, getProject, createProject, updateProject } from './api'
import type { CreateProjectRequest, UpdateProjectRequest } from './types'

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
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['projects', organizationId] })
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
