export const ROUTES = {
  HOME: '/',
  LOGIN: '/login',
  REGISTER: '/register',
  DASHBOARD: '/dashboard',
  ORGANIZATIONS: '/organizations',
  ORGANIZATION_DETAIL: (id: string) => `/organizations/${id}`,
  ORG_PROJECTS: (orgId: string) => `/organizations/${orgId}/projects`,
  ORG_OVERVIEW: (orgId: string, projectId: string) => `/organizations/${orgId}/projects/${projectId}`,
  ORG_PROJECT_DETAIL: (orgId: string, projectId: string) => `/organizations/${orgId}/projects/${projectId}`,
  ORG_AGENTS: (orgId: string, projectId: string) => `/organizations/${orgId}/projects/${projectId}/agents`,
  ORG_CREATE_AGENT: (orgId: string, projectId: string) => `/organizations/${orgId}/projects/${projectId}/agents/new`,
  ORG_AGENT_DETAIL: (orgId: string, projectId: string, agentId: string) => `/organizations/${orgId}/projects/${projectId}/agents/${agentId}`,
  ORG_EDIT_AGENT: (orgId: string, projectId: string, agentId: string) => `/organizations/${orgId}/projects/${projectId}/agents/${agentId}/edit`,
  ORG_AGENT_PLAYGROUND: (orgId: string, projectId: string, agentId: string) => `/organizations/${orgId}/projects/${projectId}/agents/${agentId}/playground`,
  ORG_KNOWLEDGE: (orgId: string, projectId: string) => `/organizations/${orgId}/projects/${projectId}/knowledge`,
  ORG_TOOLS: (orgId: string, projectId: string) => `/organizations/${orgId}/projects/${projectId}/tools`,
  ORG_API_KEYS: (orgId: string, projectId: string) => `/organizations/${orgId}/projects/${projectId}/api-keys`,
  ORG_USAGE: (orgId: string, projectId: string) => `/organizations/${orgId}/projects/${projectId}/usage`,
  ORG_TRACES: (orgId: string, projectId: string) => `/organizations/${orgId}/projects/${projectId}/traces`,

  PROJECTS: '/projects',
  PROJECT_DETAIL: (id: string) => `/projects/${id}`,
  API_KEYS: (id: string) => `/projects/${id}/api-keys`,
  AGENTS: (id: string) => `/projects/${id}/agents`,
  CREATE_AGENT: (id: string) => `/projects/${id}/agents/new`,
  AGENT_DETAIL: (projectId: string, agentId: string) => `/projects/${projectId}/agents/${agentId}`,
  EDIT_AGENT: (projectId: string, agentId: string) => `/projects/${projectId}/agents/${agentId}/edit`,
  AGENT_PLAYGROUND: (projectId: string, agentId: string) => `/projects/${projectId}/agents/${agentId}/playground`,
  KNOWLEDGE: (id: string) => `/projects/${id}/knowledge`,
  TOOLS: (id: string) => `/projects/${id}/tools`,
  USAGE: (id: string) => `/projects/${id}/usage`,
  TRACES: (id: string) => `/projects/${id}/traces`,
  BILLING: '/billing',
  SETTINGS: '/settings',
} as const

export function orgProjectPath(orgId: string | undefined, projectId: string, ...segments: string[]): string {
  if (orgId) {
    return `/organizations/${orgId}/projects/${projectId}${segments.length ? '/' + segments.join('/') : ''}`
  }
  return `/projects/${projectId}${segments.length ? '/' + segments.join('/') : ''}`
}
