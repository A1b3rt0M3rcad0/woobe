import { get, post, patch } from '@/lib/api/client'
import type { Project, CreateProjectRequest, UpdateProjectRequest } from './types'

export async function getProjects(organizationId?: string): Promise<Project[]> {
  return get<Project[]>('/core/projects', { params: { organization_id: organizationId } })
}

export async function getProject(id: string): Promise<Project> {
  return get<Project>(`/core/projects/${id}`)
}

export async function createProject(data: CreateProjectRequest): Promise<Project> {
  return post<Project>('/core/projects', data)
}

export async function updateProject(id: string, data: UpdateProjectRequest): Promise<Project> {
  return patch<Project>(`/core/projects/${id}`, data)
}
