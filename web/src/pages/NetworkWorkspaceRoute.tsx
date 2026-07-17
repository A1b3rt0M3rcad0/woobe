import { Navigate, useParams } from 'react-router-dom'

import NetworkPage from '@/pages/NetworkPage'

export default function NetworkWorkspaceRoute() {
  const { organizationId, projectId, networkId } = useParams<{
    organizationId: string
    projectId: string
    networkId: string
  }>()

  if (!organizationId || !projectId || !networkId) {
    return <Navigate to="/organizations" replace />
  }

  return <NetworkPage key={networkId} />
}
