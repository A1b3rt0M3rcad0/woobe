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
import WorkspacesPage from '@/pages/WorkspacesPage'
import WorkspaceProjectsPage from '@/pages/WorkspaceProjectsPage'
import OrgProjectDetailPage from '@/pages/OrgProjectDetailPage'
import FirstRunSetupPage from '@/pages/FirstRunSetupPage'
import ApiKeysPage from '@/pages/ApiKeysPage'
import ChatSurfacesPage from '@/pages/ChatSurfacesPage'
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
import TracesPage from '@/pages/TracesPage'
import SettingsPage from '@/pages/SettingsPage'
import NotFoundPage from '@/pages/NotFoundPage'

function RootRedirect() {
  const { isAuthenticated } = useAuth()
  return <Navigate to={isAuthenticated ? '/dashboard' : '/login'} replace />
}

function DashboardRedirect() {
  const {
    workspaces,
    projects,
    currentWorkspace,
    currentProject,
    selectWorkspace,
    selectProject,
    isLoadingWorkspaces,
    isLoadingProjects,
  } = useWorkspace()
  const agentsQuery = useAgents(currentProject?.id)

  useEffect(() => {
    if (!currentWorkspace && !isLoadingWorkspaces && workspaces.length === 1) selectWorkspace(workspaces[0])
  }, [currentWorkspace, isLoadingWorkspaces, selectWorkspace, workspaces])

  useEffect(() => {
    if (currentWorkspace && !currentProject && !isLoadingProjects && projects.length === 1) selectProject(projects[0])
  }, [currentProject, currentWorkspace, isLoadingProjects, projects, selectProject])

  if (isLoadingWorkspaces) return <LoadingState message="Opening Workspaces" />
  if (!currentWorkspace) {
    if (workspaces.length === 1) return <LoadingState message="Opening Workspace" />
    return <Navigate to="/workspaces" replace />
  }
  if (isLoadingProjects) return <LoadingState message="Opening Projects" />
  if (!currentProject) {
    if (projects.length === 1) return <LoadingState message="Opening Project" />
    return <Navigate to={`/workspaces/${currentWorkspace.id}/projects`} replace />
  }
  if (agentsQuery.isLoading) return <LoadingState message="Opening Project" />
  if (agentsQuery.isSuccess && (agentsQuery.data?.length ?? 0) === 0) {
    return <Navigate to={`/workspaces/${currentWorkspace.id}/projects/${currentProject.id}/agents`} replace />
  }
  return <Navigate to={`/workspaces/${currentWorkspace.id}/projects/${currentProject.id}`} replace />
}

function ProjectWorkspaceGuard() {
  const { organizationId: workspaceId, projectId } = useParams<{ organizationId: string; projectId: string }>()
  const { projects, currentWorkspace, currentProject, selectProject, clearCurrentProject, isLoadingProjects, isFetchingProjects } = useWorkspace()
  const routeProject = projects.find((project) => project.id === projectId && project.workspace_id === workspaceId)

  useEffect(() => {
    if (routeProject && currentProject?.id !== routeProject.id && !isLoadingProjects) selectProject(routeProject)
  }, [currentProject?.id, isLoadingProjects, routeProject, selectProject])

  useEffect(() => {
    if (currentWorkspace?.id === workspaceId && !isLoadingProjects && !isFetchingProjects && !routeProject) clearCurrentProject()
  }, [clearCurrentProject, currentWorkspace?.id, isFetchingProjects, isLoadingProjects, routeProject, workspaceId])

  if (!workspaceId || !projectId) return <Navigate to="/workspaces" replace />
  if (isLoadingProjects || (!routeProject && isFetchingProjects)) return <LoadingState message="Opening Project" />
  if (!routeProject) return <Navigate to={`/workspaces/${workspaceId}/projects`} replace />
  if (currentProject?.id !== routeProject.id) return <LoadingState message="Opening Project" />
  return <Outlet />
}

function AgentListRedirect() {
  const { organizationId, projectId } = useParams<{ organizationId: string; projectId: string }>()
  return <Navigate to={`/workspaces/${organizationId}/projects/${projectId}/agents`} replace />
}

function AgentPlaygroundRedirect() {
  const { organizationId, projectId, agentId } = useParams<{ organizationId: string; projectId: string; agentId: string }>()
  return <Navigate to={`/workspaces/${organizationId}/projects/${projectId}/agents/${agentId}/playground`} replace />
}

function LegacyNetworkRedirect() {
  const { organizationId, projectId } = useParams<{ organizationId: string; projectId: string }>()
  const networksQuery = useNetworks(projectId)
  if (!organizationId || !projectId) return <Navigate to="/workspaces" replace />
  if (networksQuery.isLoading) return <LoadingState message="Opening Networks" />
  const networks = networksQuery.data ?? []
  if (networks.length === 1) return <Navigate to={`/workspaces/${organizationId}/projects/${projectId}/networks/${networks[0].id}`} replace />
  return <Navigate to={`/workspaces/${organizationId}/projects/${projectId}/networks`} replace />
}

function LegacyOrganizationRedirect() {
  const location = useLocation()
  return <Navigate to={location.pathname.replace(/^\/organizations/, '/workspaces') + location.search} replace />
}

function LegacyProjectRedirect() {
  const { currentWorkspace } = useWorkspace()
  const location = useLocation()
  if (!currentWorkspace) return <Navigate to="/workspaces" replace />
  return <Navigate to={location.pathname.replace(/^\/projects/, `/workspaces/${currentWorkspace.id}/projects`) + location.search} replace />
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
          <Route path="/workspaces" element={<WorkspacesPage />} />
          <Route path="/workspaces/:workspaceId/projects" element={<WorkspaceProjectsPage />} />
          <Route path="/workspaces/:workspaceId/settings" element={<WorkspacesPage />} />
          <Route path="/workspaces/:workspaceId/setup" element={<FirstRunSetupPage />} />
          <Route path="/workspaces/:workspaceId/projects/:projectId/setup" element={<FirstRunSetupPage />} />

          <Route element={<ProjectWorkspaceGuard />}>
            <Route path="/workspaces/:organizationId/projects/:projectId" element={<DashboardPage />} />
            <Route path="/workspaces/:organizationId/projects/:projectId/settings" element={<OrgProjectDetailPage />} />
            <Route path="/workspaces/:organizationId/projects/:projectId/network" element={<LegacyNetworkRedirect />} />
            <Route path="/workspaces/:organizationId/projects/:projectId/networks" element={<NetworksPage />} />
            <Route path="/workspaces/:organizationId/projects/:projectId/networks/:networkId" element={<NetworkWorkspaceRoute />} />
            <Route path="/workspaces/:organizationId/projects/:projectId/agents" element={<AgentsPage />} />
            <Route path="/workspaces/:organizationId/projects/:projectId/agents/new" element={<AgentListRedirect />} />
            <Route path="/workspaces/:organizationId/projects/:projectId/agents/:agentId" element={<AgentPlaygroundRedirect />} />
            <Route path="/workspaces/:organizationId/projects/:projectId/agents/:agentId/edit" element={<AgentPlaygroundRedirect />} />
            <Route path="/workspaces/:organizationId/projects/:projectId/agents/:agentId/playground" element={<AgentPlaygroundPage />} />
            <Route path="/workspaces/:organizationId/projects/:projectId/knowledge" element={<KnowledgePage />} />
            <Route path="/workspaces/:organizationId/projects/:projectId/tools" element={<ToolsPage />} />
            <Route path="/workspaces/:organizationId/projects/:projectId/models" element={<ModelsPage />} />
            <Route path="/workspaces/:organizationId/projects/:projectId/credentials" element={<CredentialsPage />} />
            <Route path="/workspaces/:organizationId/projects/:projectId/api-keys" element={<ApiKeysPage />} />
            <Route path="/workspaces/:organizationId/projects/:projectId/chat-surfaces" element={<ChatSurfacesPage />} />
            <Route path="/workspaces/:organizationId/projects/:projectId/usage" element={<UsagePage />} />
            <Route path="/workspaces/:organizationId/projects/:projectId/traces" element={<TracesPage />} />
          </Route>

          <Route path="/organizations/*" element={<LegacyOrganizationRedirect />} />
          <Route path="/projects/*" element={<LegacyProjectRedirect />} />
          <Route path="/mcp/oauth/callback" element={<McpConnectCallbackPage />} />
          <Route path="/settings" element={<SettingsPage />} />
        </Route>
        <Route path="*" element={<NotFoundPage />} />
      </Routes>
    </BrowserRouter>
  )
}
