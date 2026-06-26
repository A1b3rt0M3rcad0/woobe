import { BrowserRouter, Routes, Route, Navigate, useLocation, useParams } from 'react-router-dom'
import { AppProviders } from './providers'
import { PublicLayout } from '@/layouts/PublicLayout'
import { AuthLayout } from '@/layouts/AuthLayout'
import { DashboardLayout } from '@/layouts/DashboardLayout'
import { ProtectedRoute, PublicRoute } from '@/features/auth/ProtectedRoute'
import { useWorkspace } from '@/features/workspace/WorkspaceProvider'

import LandingPage from '@/pages/LandingPage'
import LoginPage from '@/pages/LoginPage'
import RegisterPage from '@/pages/RegisterPage'
import DashboardPage from '@/pages/DashboardPage'
import OrganizationsPage from '@/pages/OrganizationsPage'
import OrganizationDetailPage from '@/pages/OrganizationDetailPage'
import OrgProjectsPage from '@/pages/OrgProjectsPage'
import OrgProjectDetailPage from '@/pages/OrgProjectDetailPage'
import ProjectsPage from '@/pages/ProjectsPage'
import ProjectDetailPage from '@/pages/ProjectDetailPage'
import ApiKeysPage from '@/pages/ApiKeysPage'
import AgentsPage from '@/pages/AgentsPage'
import AgentPlaygroundPage from '@/pages/AgentPlaygroundPage'
import KnowledgePage from '@/pages/KnowledgePage'
import ToolsPage from '@/pages/ToolsPage'
import McpConnectCallbackPage from '@/pages/McpConnectCallbackPage'
import UsagePage from '@/pages/UsagePage'
import TracesPage from '@/pages/TracesPage'
import BillingPage from '@/pages/BillingPage'
import SettingsPage from '@/pages/SettingsPage'
import NotFoundPage from '@/pages/NotFoundPage'

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
  const { currentOrganization, currentProject } = useWorkspace()
  if (!currentOrganization) return <Navigate to="/organizations" replace />
  if (!currentProject) return <Navigate to={`/organizations/${currentOrganization.id}/projects`} replace />
  return <Navigate to={`/organizations/${currentOrganization.id}/projects/${currentProject.id}`} replace />
}

function AgentListRedirect() {
  const { organizationId, projectId } = useParams<{ organizationId: string; projectId: string }>()
  return <Navigate to={`/organizations/${organizationId}/projects/${projectId}/agents`} replace />
}

function AgentPlaygroundRedirect() {
  const { organizationId, projectId, agentId } = useParams<{ organizationId: string; projectId: string; agentId: string }>()
  return <Navigate to={`/organizations/${organizationId}/projects/${projectId}/agents/${agentId}/playground`} replace />
}

export function AppRouter() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<PublicLayout />}>
          <Route path="/" element={<LandingPage />} />
        </Route>

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
          <Route path="/organizations/:organizationId/projects/:projectId" element={<DashboardPage />} />
          <Route path="/organizations/:organizationId/projects/:projectId/settings" element={<OrgProjectDetailPage />} />
          <Route path="/organizations/:organizationId/projects/:projectId/agents" element={<AgentsPage />} />
          <Route path="/organizations/:organizationId/projects/:projectId/agents/new" element={<AgentListRedirect />} />
          <Route path="/organizations/:organizationId/projects/:projectId/agents/:agentId" element={<AgentPlaygroundRedirect />} />
          <Route path="/organizations/:organizationId/projects/:projectId/agents/:agentId/edit" element={<AgentPlaygroundRedirect />} />
          <Route path="/organizations/:organizationId/projects/:projectId/agents/:agentId/playground" element={<AgentPlaygroundPage />} />
          <Route path="/organizations/:organizationId/projects/:projectId/knowledge" element={<KnowledgePage />} />
          <Route path="/organizations/:organizationId/projects/:projectId/tools" element={<ToolsPage />} />
          <Route path="/organizations/:organizationId/projects/:projectId/api-keys" element={<ApiKeysPage />} />
          <Route path="/organizations/:organizationId/projects/:projectId/usage" element={<UsagePage />} />
          <Route path="/organizations/:organizationId/projects/:projectId/traces" element={<TracesPage />} />

          <Route path="/mcp/oauth/callback" element={<McpConnectCallbackPage />} />

          <Route path="/projects" element={<LegacyProjectRedirect />} />
          <Route path="/projects/:projectId" element={<LegacyProjectRedirect />} />
          <Route path="/projects/:projectId/agents" element={<LegacyProjectRedirect />} />
          <Route path="/projects/:projectId/agents/new" element={<LegacyProjectRedirect />} />
          <Route path="/projects/:projectId/agents/:agentId" element={<LegacyProjectRedirect />} />
          <Route path="/projects/:projectId/agents/:agentId/edit" element={<LegacyProjectRedirect />} />
          <Route path="/projects/:projectId/agents/:agentId/playground" element={<LegacyProjectRedirect />} />
          <Route path="/projects/:projectId/knowledge" element={<LegacyProjectRedirect />} />
          <Route path="/projects/:projectId/tools" element={<LegacyProjectRedirect />} />
          <Route path="/projects/:projectId/api-keys" element={<LegacyProjectRedirect />} />
          <Route path="/projects/:projectId/usage" element={<LegacyProjectRedirect />} />
          <Route path="/projects/:projectId/traces" element={<LegacyProjectRedirect />} />

          <Route path="/billing" element={<BillingPage />} />
          <Route path="/settings" element={<SettingsPage />} />
        </Route>

        <Route path="*" element={<NotFoundPage />} />
      </Routes>
    </BrowserRouter>
  )
}
