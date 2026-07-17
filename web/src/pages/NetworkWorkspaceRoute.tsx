import { Navigate, useParams } from 'react-router-dom'

import { useNetwork } from '@/features/network/hooks'
import { WorkspaceContext, useWorkspace } from '@/features/workspace/WorkspaceProvider'
import NetworkPage from '@/pages/NetworkPage'

export default function NetworkWorkspaceRoute() {
  const { organizationId, projectId, networkId } = useParams<{
    organizationId: string
    projectId: string
    networkId: string
  }>()
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

  return (
    <WorkspaceContext.Provider value={{ ...workspace, currentProject: displayProject }}>
      <NetworkPage key={networkId} />
    </WorkspaceContext.Provider>
  )
}
