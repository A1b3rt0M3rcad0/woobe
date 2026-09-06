export const ROUTES = {
  LOGIN: '/login',
  REGISTER: '/register',
  DASHBOARD: '/dashboard',
  WORKSPACES: '/workspaces',
  WORKSPACE_DETAIL: (id: string) => `/workspaces/${id}`,
  WORKSPACE_PROJECTS: (workspaceId: string) => `/workspaces/${workspaceId}/projects`,
  WORKSPACE_OVERVIEW: (workspaceId: string, projectId: string) => `/workspaces/${workspaceId}/projects/${projectId}`,
  WORKSPACE_PROJECT_DETAIL: (workspaceId: string, projectId: string) => `/workspaces/${workspaceId}/projects/${projectId}`,
  WORKSPACE_NETWORKS: (workspaceId: string, projectId: string) => `/workspaces/${workspaceId}/projects/${projectId}/networks`,
  WORKSPACE_NETWORK: (workspaceId: string, projectId: string, networkId: string) => `/workspaces/${workspaceId}/projects/${projectId}/networks/${networkId}`,
  WORKSPACE_AGENTS: (workspaceId: string, projectId: string) => `/workspaces/${workspaceId}/projects/${projectId}/agents`,
  WORKSPACE_CREATE_AGENT: (workspaceId: string, projectId: string) => `/workspaces/${workspaceId}/projects/${projectId}/agents/new`,
  WORKSPACE_AGENT_DETAIL: (workspaceId: string, projectId: string, agentId: string) => `/workspaces/${workspaceId}/projects/${projectId}/agents/${agentId}`,
  WORKSPACE_EDIT_AGENT: (workspaceId: string, projectId: string, agentId: string) => `/workspaces/${workspaceId}/projects/${projectId}/agents/${agentId}/edit`,
  WORKSPACE_AGENT_PLAYGROUND: (workspaceId: string, projectId: string, agentId: string) => `/workspaces/${workspaceId}/projects/${projectId}/agents/${agentId}/playground`,
  WORKSPACE_KNOWLEDGE: (workspaceId: string, projectId: string) => `/workspaces/${workspaceId}/projects/${projectId}/knowledge`,
  WORKSPACE_TOOLS: (workspaceId: string, projectId: string) => `/workspaces/${workspaceId}/projects/${projectId}/tools`,
  WORKSPACE_SKILLS: (workspaceId: string, projectId: string) => `/workspaces/${workspaceId}/projects/${projectId}/skills`,
  WORKSPACE_MODELS: (workspaceId: string, projectId: string) => `/workspaces/${workspaceId}/projects/${projectId}/models`,
  WORKSPACE_API_KEYS: (workspaceId: string, projectId: string) => `/workspaces/${workspaceId}/projects/${projectId}/api-keys`,
  WORKSPACE_USAGE: (workspaceId: string, projectId: string) => `/workspaces/${workspaceId}/projects/${projectId}/usage`,
  WORKSPACE_TRACES: (workspaceId: string, projectId: string) => `/workspaces/${workspaceId}/projects/${projectId}/traces`,

  PROJECTS: '/projects',
  PROJECT_DETAIL: (id: string) => `/projects/${id}`,
  NETWORKS: (id: string) => `/projects/${id}/networks`,
  NETWORK: (projectId: string, networkId: string) => `/projects/${projectId}/networks/${networkId}`,
  API_KEYS: (id: string) => `/projects/${id}/api-keys`,
  AGENTS: (id: string) => `/projects/${id}/agents`,
  CREATE_AGENT: (id: string) => `/projects/${id}/agents/new`,
  AGENT_DETAIL: (projectId: string, agentId: string) => `/projects/${projectId}/agents/${agentId}`,
  EDIT_AGENT: (projectId: string, agentId: string) => `/projects/${projectId}/agents/${agentId}/edit`,
  AGENT_PLAYGROUND: (projectId: string, agentId: string) => `/projects/${projectId}/agents/${agentId}/playground`,
  KNOWLEDGE: (id: string) => `/projects/${id}/knowledge`,
  TOOLS: (id: string) => `/projects/${id}/tools`,
  SKILLS: (id: string) => `/projects/${id}/skills`,
  MODELS: (id: string) => `/projects/${id}/models`,
  USAGE: (id: string) => `/projects/${id}/usage`,
  TRACES: (id: string) => `/projects/${id}/traces`,
  BILLING: '/billing',
  SETTINGS: '/settings',
} as const

export function workspaceProjectPath(workspaceId: string | undefined, projectId: string, ...segments: string[]): string {
  const normalizedSegments = segments.length === 1 && segments[0] === 'network' ? ['networks'] : segments
  if (workspaceId) {
    return `/workspaces/${workspaceId}/projects/${projectId}${normalizedSegments.length ? '/' + normalizedSegments.join('/') : ''}`
  }
  return `/projects/${projectId}${normalizedSegments.length ? '/' + normalizedSegments.join('/') : ''}`
}
