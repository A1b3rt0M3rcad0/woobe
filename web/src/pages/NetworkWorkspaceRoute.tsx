import type { CSSProperties } from 'react'
import { ChevronLeft } from 'lucide-react'
import { Navigate, useNavigate, useParams } from 'react-router-dom'

import { NetworkIdentityProvider } from '@/features/network/NetworkIdentityContext'
import { NetworkRuntimeControlsPopover } from '@/features/network/components/NetworkRuntimeControlsPopover'
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
  const shellStyle = {
    '--network-workspace-name': JSON.stringify(networkName || 'Network'),
  } as CSSProperties

  return (
    <NetworkIdentityProvider value={networkName || 'Network'}>
      <div
        className="network-workspace-shell relative h-screen overflow-hidden"
        style={shellStyle}
      >
        <style>{`
          .network-workspace-shell > div > header {
            padding-right: 7.5rem;
          }
          .network-workspace-shell > div > header > div > h1 {
            font-size: 0;
          }
          .network-workspace-shell > div > header > div > h1::after {
            content: var(--network-workspace-name);
            font-size: 0.875rem;
            line-height: 1.25rem;
          }
          .network-workspace-shell > div > header > div > p {
            font-size: 0;
          }
          .network-workspace-shell > div > header > div > p::after {
            content: 'Network workspace · isolated within this Project';
            font-size: 0.625rem;
            line-height: 0.875rem;
          }
        `}</style>

        <button
          type="button"
          aria-label="Back to Networks"
          title="Back to Networks"
          onClick={() => navigate(networksPath)}
          className="absolute left-3 top-3 z-[70] flex h-8 w-8 items-center justify-center rounded-lg border border-border bg-surface/95 text-muted transition-colors hover:border-primary/30 hover:text-white"
        >
          <ChevronLeft className="h-4 w-4" />
        </button>

        <div className="absolute right-3 top-3 z-[220]">
          <NetworkRuntimeControlsPopover networkId={networkId} projectId={projectId} />
        </div>

        <WorkspaceContext.Provider value={{ ...workspace, currentProject: displayProject }}>
          <NetworkPage key={networkId} />
        </WorkspaceContext.Provider>
      </div>
    </NetworkIdentityProvider>
  )
}
