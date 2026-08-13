export const ROUTES = {
  LOGIN: '/login',
  REGISTER: '/register',
  DASHBOARD: '/dashboard',
  WORKSPACES: '/workspaces',
  WORKSPACE_PROJECTS: (workspaceId: string) => `/workspaces/${workspaceId}/projects`,
  WORKSPACE_SETTINGS: (workspaceId: string) => `/workspaces/${workspaceId}/settings`,
  PROJECT_DETAIL: (workspaceId: string, projectId: string) => `/workspaces/${workspaceId}/projects/${projectId}`,
  SETTINGS: '/settings',
} as const

export function workspaceProjectPath(
  workspaceId: string | undefined,
  projectId: string,
  ...segments: string[]
): string {
  const normalizedSegments = segments.length === 1 && segments[0] === 'network' ? ['networks'] : segments
  if (workspaceId) {
    return `/workspaces/${workspaceId}/projects/${projectId}${normalizedSegments.length ? '/' + normalizedSegments.join('/') : ''}`
  }
  return `/projects/${projectId}${normalizedSegments.length ? '/' + normalizedSegments.join('/') : ''}`
}

/** @deprecated Project pages should use workspaceProjectPath. */
export const orgProjectPath = workspaceProjectPath
