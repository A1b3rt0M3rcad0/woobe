import { ChevronLeft } from 'lucide-react'
import { Navigate, useNavigate, useParams } from 'react-router-dom'

import { useNetwork } from '@/features/network/hooks'
import { WorkspaceContext, useWorkspace } from '@/features/workspace/WorkspaceProvider'
import NetworkPage from '@/pages/NetworkPage'

export default function NetworkWorkspaceRoute() {
  const { organizationId, projectId, networkId } = useParams<{
    organizationId: string
    projectId: string
    networkId: string
  }>()
  const navigate = useNavigate()
  const workspace = useWorkspace()
  const networkQuery = useNetwork(projectId)

  if (!organizationId || !projectId || !networkId) {
    return <Navigate to="/organizations" replace />
  }

  const networkName = networkQuery.data?.name.trim()
  const displayProject = workspace.currentProject && networkName
    ? {
        ...workspace.currentProject,
        name: networkName.replace(/\s+Network$/i, ''),
      }
    : workspace.currentProject
  const networksPath = `/organizations/${organizationId}/projects/${projectId}/networks`

  return (
    <div className="relative h-screen overflow-hidden">
      <button
        type="button"
        aria-label="Back to Networks"
        title="Back to Networks"
        onClick={() => navigate(networksPath)}
        className="absolute left-3 top-3 z-[70] flex h-8 w-8 items-center justify-center rounded-lg border border-border bg-surface/95 text-muted transition-colors hover:border-primary/30 hover:text-white"
      >
        <ChevronLeft className="h-4 w-4" />
      </button>

      <WorkspaceContext.Provider value={{ ...workspace, currentProject: displayProject }}>
        <NetworkPage key={networkId} />
      </WorkspaceContext.Provider>
    </div>
  )
}
