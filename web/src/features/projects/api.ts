import { del, get, post, patch } from '@/lib/api/client'
import type {
  Project,
  ProjectAccessSummary,
  ProjectMembersResponse,
  ProjectAccessSubject,
  CreateProjectRequest,
  UpdateProjectRequest,
} from './types'

interface ProjectAccessMutationResponse {
  subject_type: string
  subject_id: string
  project_access: string
  access_id: string
}

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

export async function grantProjectSubjectAccess(
  projectId: string,
  subjectType: ProjectAccessSubject['subject_type'],
  subjectId: string,
): Promise<ProjectAccessMutationResponse> {
  return post<ProjectAccessMutationResponse>(`/core/projects/${projectId}/access`, {
    subject_type: subjectType,
    subject_id: subjectId,
  })
}

export async function revokeProjectSubjectAccess(
  projectId: string,
  subjectType: ProjectAccessSubject['subject_type'],
  subjectId: string,
): Promise<void> {
  return del<void>(`/core/projects/${projectId}/access/${subjectType}/${subjectId}`)
}
