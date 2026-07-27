import { del, get, post, patch } from '@/lib/api/client'
import type {
  Project,
  ProjectAccessMember,
  ProjectAccessSummary,
  ProjectMembersResponse,
  CreateProjectRequest,
  UpdateProjectRequest,
} from './types'

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

export async function getProjectsForAccessManagement(organizationId: string): Promise<ProjectAccessSummary[]> {
  return get<ProjectAccessSummary[]>(`/core/organizations/${organizationId}/project-access`)
}

export async function getProjectMembers(projectId: string): Promise<ProjectMembersResponse> {
  return get<ProjectMembersResponse>(`/core/projects/${projectId}/members`)
}

export async function grantProjectAccess(projectId: string, email: string): Promise<ProjectAccessMember> {
  return post<ProjectAccessMember>(`/core/projects/${projectId}/members`, { email })
}

export async function revokeProjectAccess(projectId: string, userId: string): Promise<void> {
  return del<void>(`/core/projects/${projectId}/members/${userId}`)
}
