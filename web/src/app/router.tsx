import { useEffect } from 'react'
import { BrowserRouter, Routes, Route, Navigate, Outlet, useLocation, useParams } from 'react-router-dom'
import { AuthLayout } from '@/layouts/AuthLayout'
import { DashboardLayout } from '@/layouts/DashboardLayout'
import { ProtectedRoute, PublicRoute } from '@/features/auth/ProtectedRoute'
import { useAuth } from '@/features/auth/AuthProvider'
import { useAgents } from '@/features/agents/hooks'
import { useNetworks } from '@/features/network/hooks'
import { useWorkspace } from '@/features/workspace/WorkspaceProvider'
import { LoadingState } from '@/components/common/LoadingState'

import LoginPage from '@/pages/LoginPage'
import RegisterPage from '@/pages/RegisterPage'
import DashboardPage from '@/pages/DashboardPage'
import OrganizationsPage from '@/pages/OrganizationsPage'
import OrganizationDetailPage from '@/pages/OrganizationDetailPage'
import OrgProjectsPage from '@/pages/OrgProjectsPage'
import OrgProjectDetailPage from '@/pages/OrgProjectDetailPage'
import FirstRunSetupPage from '@/pages/FirstRunSetupPage'
import ApiKeysPage from '@/pages/ApiKeysPage'
import AgentsPage from '@/pages/AgentsPage'
import AgentPlaygroundPage from '@/pages/AgentPlaygroundPage'
import NetworksPage from '@/pages/NetworksPage'
import NetworkWorkspaceRoute from '@/pages/NetworkWorkspaceRoute'
import KnowledgePage from '@/pages/KnowledgePage'
import ToolsPage from '@/pages/ToolsPage'
import ModelsPage from '@/pages/ModelsPage'
import CredentialsPage from '@/pages/CredentialsPage'
import McpConnectCallbackPage from '@/pages/McpConnectCallbackPage'
import UsagePage from '@/pages/UsagePage'
import TracesRoute from '@/pages/TracesRoute'
import TraceDetailPage from '@/pages/TraceDetailPage'
import EvaluationsPage from '@/pages/EvaluationsPage'
import BillingPage from '@/pages/BillingPage'
import SettingsPage from '@/pages/SettingsPage'
import NotFoundPage from '@/pages/NotFoundPage'

function RootRedirect() {
  const { isAuthenticated } = useAuth()
  return <Navigate to={isAuthenticated ? '/dashboard' : '/login'} replace />
}

function LegacyProjectRedirect() {
  const { currentOrganization } = useWorkspace()
  const location = useLocation()
  if (currentOrganization) {
    const newPath = location.pathname.replace(/^\/projects/, `/organizations/${currentOrganization.id}/projects`)
    return <Navigate to={newPath + location.search} replace />
  }
  return <Navigate to="/organizations" replace />
}

function DashboardRedirect() {
  const {
    organizations,
    projects,
    currentOrganization,
    currentProject,
    selectOrganization,
    selectProject,
    isLoadingOrganizations,
    isLoadingProjects,
  } = useWorkspace()
  const agentsQuery = useAgents(currentProject?.id)

  useEffect(() => {
    if (!currentOrganization && !isLoadingOrganizations && organizations.length === 1) {
      selectOrganization(organizations[0])
    }
  }, [currentOrganization, isLoadingOrganizations, organizations, selectOrganization])

  useEffect(() => {
    if (currentOrganization && !currentProject && !isLoadingProjects && projects.length === 1) {
      selectProject(projects[0])
    }
  }, [currentOrganization, currentProject, isLoadingProjects, projects, selectProject])

  if (isLoadingOrganizations) return <LoadingState message="Opening workspace" />

  if (!currentOrganization) {
    if (organizations.length === 1) return <LoadingState message="Opening Organization" />
    return <Navigate to="/organizations" replace />
  }

  if (isLoadingProjects) return <LoadingState message="Opening Projects" />

  if (!currentProject) {
    if (projects.length === 1) return <LoadingState message="Opening Project" />
    return <Navigate to={`/organizations/${currentOrganization.id}/projects`} replace />
  }

  if (agentsQuery.isLoading) return <LoadingState message="Opening Project" />

  if (agentsQuery.isSuccess && (agentsQuery.data?.length ?? 0) === 0) {
    return <Navigate to={`/organizations/${currentOrganization.id}/projects/${currentProject.id}/agents`} replace />
  }

  return <Navigate to={`/organizations/${currentOrganization.id}/projects/${currentProject.id}`} replace />
}

function ProjectWorkspaceGuard() {
  const { organizationId, projectId } = useParams<{ organizationId: string; projectId: string }>()
  const {
    organizations,
    projects,
    currentOrganization,
    currentProject,
    selectOrganization,
    selectProject,
    clearCurrentProject,
    isLoadingOrganizations,
    isLoadingProjects,
    isFetchingProjects,
  } = useWorkspace()

  const routeOrganization = organizations.find((organization) => organization.id === organizationId)
  const routeProject = projects.find((project) => (
    project.id === projectId && project.organization_id === organizationId
  ))

  useEffect(() => {
    if (
      routeOrganization
      && currentOrganization?.id !== routeOrganization.id
      && !isLoadingOrganizations
    ) {
      selectOrganization(routeOrganization)
    }
  }, [currentOrganization, isLoadingOrganizations, routeOrganization, selectOrganization])

  useEffect(() => {
    if (
      routeProject
      && currentOrganization?.id === organizationId
      && currentProject?.id !== routeProject.id
      && !isLoadingProjects
    ) {
      selectProject(routeProject)
    }
  }, [currentOrganization, currentProject, isLoadingProjects, organizationId, routeProject, selectProject])

  useEffect(() => {
    if (
      currentOrganization?.id === organizationId
      && !isLoadingProjects
      && !isFetchingProjects
      && !routeProject
    ) {
      clearCurrentProject()
    }
  }, [clearCurrentProject, currentOrganization, isFetchingProjects, isLoadingProjects, organizationId, routeProject])

  if (!organizationId || !projectId) {
    return <Navigate to="/organizations" replace />
  }

  if (isLoadingOrganizations) {
    return <LoadingState message="Opening workspace" />
  }

  if (!routeOrganization) {
    return <Navigate to="/organizations" replace />
  }

  if (currentOrganization?.id !== routeOrganization.id) {
    return <LoadingState message="Opening Organization" />
  }

  if (isLoadingProjects || (!routeProject && isFetchingProjects)) {
    return <LoadingState message="Opening Project" />
  }

  if (!routeProject) {
    return <Navigate to={`/organizations/${organizationId}/projects`} replace />
  }

  if (currentProject?.id !== routeProject.id) {
    return <LoadingState message="Opening Project" />
  }

  return <Outlet />
}

function AgentListRedirect() {
  const { organizationId, projectId } = useParams<{ organizationId: string; projectId: string }>()
  return <Navigate to={`/organizations/${organizationId}/projects/${projectId}/agents`} replace />
}

function AgentPlaygroundRedirect() {
  const { organizationId, projectId, agentId } = useParams<{ organizationId: string; projectId: string; agentId: string }>()
  return <Navigate to={`/organizations/${organizationId}/projects/${projectId}/agents/${agentId}/playground`} replace />
}

function LegacyNetworkRedirect() {
  const { organizationId, projectId } = useParams<{ organizationId: string; projectId: string }>()
  const networksQuery = useNetworks(projectId)
  if (!organizationId || !projectId) return <Navigate to="/organizations" replace />
  if (networksQuery.isLoading) return <LoadingState message="Opening Networks" />
  const networks = networksQuery.data ?? []
  if (networks.length === 1) {
    return <Navigate to={`/organizations/${organizationId}/projects/${projectId}/networks/${networks[0].id}`} replace />
  }
  return <Navigate to={`/organizations/${organizationId}/projects/${projectId}/networks`} replace />
}

export function AppRouter() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<RootRedirect />} />

        <Route element={<PublicRoute><AuthLayout /></PublicRoute>}>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/register" element={<RegisterPage />} />
        </Route>

        <Route element={<ProtectedRoute><DashboardLayout /></ProtectedRoute>}>
          <Route path="/dashboard" element={<DashboardRedirect />} />
          <Route path="/organizations" element={<OrganizationsPage />} />
          <Route path="/organizations/:organizationId" element={<Navigate to="./settings" replace />} />
          <Route path="/organizations/:organizationId/settings" element={<OrganizationDetailPage />} />
          <Route path="/organizations/:organizationId/projects" element={<OrgProjectsPage />} />
          <Route path="/organizations/:organizationId/setup" element={<FirstRunSetupPage />} />

          <Route element={<ProjectWorkspaceGuard />}>
            <Route path="/organizations/:organizationId/projects/:projectId" element={<DashboardPage />} />
            <Route path="/organizations/:organizationId/projects/:projectId/setup" element={<FirstRunSetupPage />} />
            <Route path="/organizations/:organizationId/projects/:projectId/settings" element={<OrgProjectDetailPage />} />
            <Route path="/organizations/:organizationId/projects/:projectId/network" element={<LegacyNetworkRedirect />} />
            <Route path="/organizations/:organizationId/projects/:projectId/networks" element={<NetworksPage />} />
            <Route path="/organizations/:organizationId/projects/:projectId/networks/:networkId" element={<NetworkWorkspaceRoute />} />
            <Route path="/organizations/:organizationId/projects/:projectId/agents" element={<AgentsPage />} />
            <Route path="/organizations/:organizationId/projects/:projectId/agents/new" element={<AgentListRedirect />} />
            <Route path="/organizations/:organizationId/projects/:projectId/agents/:agentId" element={<AgentPlaygroundRedirect />} />
            <Route path="/organizations/:organizationId/projects/:projectId/agents/:agentId/edit" element={<AgentPlaygroundRedirect />} />
            <Route path="/organizations/:organizationId/projects/:projectId/agents/:agentId/playground" element={<AgentPlaygroundPage />} />
            <Route path="/organizations/:organizationId/projects/:projectId/knowledge" element={<KnowledgePage />} />
            <Route path="/organizations/:organizationId/projects/:projectId/tools" element={<ToolsPage />} />
            <Route path="/organizations/:organizationId/projects/:projectId/models" element={<ModelsPage />} />
            <Route path="/organizations/:organizationId/projects/:projectId/credentials" element={<CredentialsPage />} />
            <Route path="/organizations/:organizationId/projects/:projectId/api-keys" element={<ApiKeysPage />} />
            <Route path="/organizations/:organizationId/projects/:projectId/usage" element={<UsagePage />} />
            <Route path="/organizations/:organizationId/projects/:projectId/traces/:traceId" element={<TraceDetailPage />} />
            <Route path="/organizations/:organizationId/projects/:projectId/traces" element={<TracesRoute />} />
            <Route path="/organizations/:organizationId/projects/:projectId/evaluations" element={<EvaluationsPage />} />
          </Route>

          <Route path="/mcp/oauth/callback" element={<McpConnectCallbackPage />} />

          <Route path="/projects" element={<LegacyProjectRedirect />} />
          <Route path="/projects/:projectId" element={<LegacyProjectRedirect />} />
          <Route path="/projects/:projectId/network" element={<LegacyProjectRedirect />} />
          <Route path="/projects/:projectId/networks" element={<LegacyProjectRedirect />} />
          <Route path="/projects/:projectId/networks/:networkId" element={<LegacyProjectRedirect />} />
          <Route path="/projects/:projectId/agents" element={<LegacyProjectRedirect />} />
          <Route path="/projects/:projectId/agents/new" element={<LegacyProjectRedirect />} />
          <Route path="/projects/:projectId/agents/:agentId" element={<LegacyProjectRedirect />} />
          <Route path="/projects/:projectId/agents/:agentId/edit" element={<LegacyProjectRedirect />} />
          <Route path="/projects/:projectId/agents/:agentId/playground" element={<LegacyProjectRedirect />} />
          <Route path="/projects/:projectId/knowledge" element={<LegacyProjectRedirect />} />
          <Route path="/projects/:projectId/tools" element={<LegacyProjectRedirect />} />
          <Route path="/projects/:projectId/models" element={<LegacyProjectRedirect />} />
          <Route path="/projects/:projectId/credentials" element={<LegacyProjectRedirect />} />
          <Route path="/projects/:projectId/api-keys" element={<LegacyProjectRedirect />} />
          <Route path="/projects/:projectId/usage" element={<LegacyProjectRedirect />} />
          <Route path="/projects/:projectId/traces" element={<LegacyProjectRedirect />} />
          <Route path="/projects/:projectId/evaluations" element={<LegacyProjectRedirect />} />

          <Route path="/billing" element={<BillingPage />} />
          <Route path="/settings" element={<SettingsPage />} />
        </Route>

        <Route path="*" element={<NotFoundPage />} />
      </Routes>
    </BrowserRouter>
  )
}
