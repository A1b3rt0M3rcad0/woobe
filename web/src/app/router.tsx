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
import WorkspaceDetailPage from '@/pages/WorkspaceDetailPage'
import WorkspaceProjectsPage from '@/pages/WorkspaceProjectsPage'
import WorkspaceProjectDetailPage from '@/pages/WorkspaceProjectDetailPage'
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

function LegacyProjectRedirect() {
  const { currentWorkspace } = useWorkspace()
  const location = useLocation()
  if (currentWorkspace) {
    const newPath = location.pathname.replace(/^\/projects/, `/workspaces/${currentWorkspace.id}/projects`)
    return <Navigate to={newPath + location.search} replace />
  }
  return <Navigate to="/workspaces" replace />
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
  }, [currentWorkspace, isLoadingWorkspaces, workspaces, selectWorkspace])

  useEffect(() => {
    if (currentWorkspace && !currentProject && !isLoadingProjects && projects.length === 1) selectProject(projects[0])
  }, [currentWorkspace, currentProject, isLoadingProjects, projects, selectProject])

  if (isLoadingWorkspaces) return <LoadingState message="Opening workspace" />
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

function WorkspaceGuard() {
  const { workspaceId } = useParams<{ workspaceId: string }>()
  const { workspaces, currentWorkspace, selectWorkspace, isLoadingWorkspaces } = useWorkspace()
  const routeWorkspace = workspaces.find((workspace) => workspace.id === workspaceId)

  useEffect(() => {
    if (routeWorkspace && currentWorkspace?.id !== routeWorkspace.id && !isLoadingWorkspaces) {
      selectWorkspace(routeWorkspace)
    }
  }, [currentWorkspace, isLoadingWorkspaces, routeWorkspace, selectWorkspace])

  if (!workspaceId) return <Navigate to="/workspaces" replace />
  if (isLoadingWorkspaces) return <LoadingState message="Opening Workspace" />
  if (!routeWorkspace) return <Navigate to="/workspaces" replace />
  if (currentWorkspace?.id !== routeWorkspace.id) return <LoadingState message="Opening Workspace" />
  return <Outlet />
}

function ProjectWorkspaceGuard() {
  const { workspaceId, projectId } = useParams<{ workspaceId: string; projectId: string }>()
  const {
    projects,
    currentWorkspace,
    currentProject,
    selectProject,
    clearCurrentProject,
    isLoadingProjects,
    isFetchingProjects,
  } = useWorkspace()

  const routeProject = projects.find((project) => project.id === projectId && project.workspace_id === workspaceId)

  useEffect(() => {
    if (routeProject && currentProject?.id !== routeProject.id && !isLoadingProjects) selectProject(routeProject)
  }, [currentProject, isLoadingProjects, routeProject, selectProject])

  useEffect(() => {
    if (currentWorkspace?.id === workspaceId && !isLoadingProjects && !isFetchingProjects && !routeProject) clearCurrentProject()
  }, [clearCurrentProject, currentWorkspace, isFetchingProjects, isLoadingProjects, workspaceId, routeProject])

  if (!workspaceId || !projectId) return <Navigate to="/workspaces" replace />
  if (isLoadingProjects || (!routeProject && isFetchingProjects)) return <LoadingState message="Opening Project" />
  if (!routeProject) return <Navigate to={`/workspaces/${workspaceId}/projects`} replace />
  if (currentProject?.id !== routeProject.id) return <LoadingState message="Opening Project" />
  return <Outlet />
}

function AgentListRedirect() {
  const { workspaceId, projectId } = useParams<{ workspaceId: string; projectId: string }>()
  return <Navigate to={`/workspaces/${workspaceId}/projects/${projectId}/agents`} replace />
}

function AgentPlaygroundRedirect() {
  const { workspaceId, projectId, agentId } = useParams<{ workspaceId: string; projectId: string; agentId: string }>()
  return <Navigate to={`/workspaces/${workspaceId}/projects/${projectId}/agents/${agentId}/playground`} replace />
}

function LegacyNetworkRedirect() {
  const { workspaceId, projectId } = useParams<{ workspaceId: string; projectId: string }>()
  const networksQuery = useNetworks(projectId)
  if (!workspaceId || !projectId) return <Navigate to="/workspaces" replace />
  if (networksQuery.isLoading) return <LoadingState message="Opening Networks" />
  const networks = networksQuery.data ?? []
  if (networks.length === 1) return <Navigate to={`/workspaces/${workspaceId}/projects/${projectId}/networks/${networks[0].id}`} replace />
  return <Navigate to={`/workspaces/${workspaceId}/projects/${projectId}/networks`} replace />
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

          <Route element={<WorkspaceGuard />}>
            <Route path="/workspaces/:workspaceId" element={<Navigate to="./settings" replace />} />
            <Route path="/workspaces/:workspaceId/settings" element={<WorkspaceDetailPage />} />
            <Route path="/workspaces/:workspaceId/projects" element={<WorkspaceProjectsPage />} />
            <Route path="/workspaces/:workspaceId/setup" element={<FirstRunSetupPage />} />

            <Route element={<ProjectWorkspaceGuard />}>
              <Route path="/workspaces/:workspaceId/projects/:projectId" element={<DashboardPage />} />
              <Route path="/workspaces/:workspaceId/projects/:projectId/setup" element={<FirstRunSetupPage />} />
              <Route path="/workspaces/:workspaceId/projects/:projectId/settings" element={<WorkspaceProjectDetailPage />} />
              <Route path="/workspaces/:workspaceId/projects/:projectId/network" element={<LegacyNetworkRedirect />} />
              <Route path="/workspaces/:workspaceId/projects/:projectId/networks" element={<NetworksPage />} />
              <Route path="/workspaces/:workspaceId/projects/:projectId/networks/:networkId" element={<NetworkWorkspaceRoute />} />
              <Route path="/workspaces/:workspaceId/projects/:projectId/agents" element={<AgentsPage />} />
              <Route path="/workspaces/:workspaceId/projects/:projectId/agents/new" element={<AgentListRedirect />} />
              <Route path="/workspaces/:workspaceId/projects/:projectId/agents/:agentId" element={<AgentPlaygroundRedirect />} />
              <Route path="/workspaces/:workspaceId/projects/:projectId/agents/:agentId/edit" element={<AgentPlaygroundRedirect />} />
              <Route path="/workspaces/:workspaceId/projects/:projectId/agents/:agentId/playground" element={<AgentPlaygroundPage />} />
              <Route path="/workspaces/:workspaceId/projects/:projectId/knowledge" element={<KnowledgePage />} />
              <Route path="/workspaces/:workspaceId/projects/:projectId/tools" element={<ToolsPage />} />
              <Route path="/workspaces/:workspaceId/projects/:projectId/models" element={<ModelsPage />} />
              <Route path="/workspaces/:workspaceId/projects/:projectId/credentials" element={<CredentialsPage />} />
              <Route path="/workspaces/:workspaceId/projects/:projectId/api-keys" element={<ApiKeysPage />} />
              <Route path="/workspaces/:workspaceId/projects/:projectId/chat-surfaces" element={<ChatSurfacesPage />} />
              <Route path="/workspaces/:workspaceId/projects/:projectId/usage" element={<UsagePage />} />
              <Route path="/workspaces/:workspaceId/projects/:projectId/traces" element={<TracesPage />} />
            </Route>
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
          <Route path="/projects/:projectId/chat-surfaces" element={<LegacyProjectRedirect />} />
          <Route path="/projects/:projectId/usage" element={<LegacyProjectRedirect />} />
          <Route path="/projects/:projectId/traces" element={<LegacyProjectRedirect />} />
          <Route path="/settings" element={<SettingsPage />} />
        </Route>

        <Route path="*" element={<NotFoundPage />} />
      </Routes>
    </BrowserRouter>
  )
}
