import { del, get, patch, post } from '@/lib/api/client'
import type {
  CreateProjectRequest,
  Project,
  ProjectAccessSummary,
  ProjectMembersResponse,
  UpdateProjectRequest,
} from './types'

export async function getProjects(workspaceId?: string): Promise<Project[]> {
  return get<Project[]>('/core/projects', { params: { workspace_id: workspaceId } })
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

export async function getProjectsForAccessManagement(workspaceId: string): Promise<ProjectAccessSummary[]> {
  return get<ProjectAccessSummary[]>(`/core/workspaces/${workspaceId}/project-access`)
}

export async function getProjectMembers(projectId: string): Promise<ProjectMembersResponse> {
  return get<ProjectMembersResponse>(`/core/projects/${projectId}/members`)
}

export async function grantProjectAccess(projectId: string, email: string): Promise<void> {
  await post(`/core/projects/${projectId}/members`, { email })
}

export async function revokeProjectAccess(projectId: string, userId: string): Promise<void> {
  await del(`/core/projects/${projectId}/members/${userId}`)
}
