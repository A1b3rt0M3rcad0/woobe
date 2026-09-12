import { useEffect, useState, type CSSProperties } from 'react'
import { createPortal } from 'react-dom'
import { ChevronLeft } from 'lucide-react'
import { Navigate, useNavigate, useParams } from 'react-router-dom'

import { NetworkIdentityProvider } from '@/features/network/NetworkIdentityContext'
import { NetworkRuntimeControlsPopover } from '@/features/network/components/NetworkRuntimeControlsPopover'
import { useNetwork } from '@/features/network/hooks'
import { WorkspaceContext, useWorkspace } from '@/features/workspace/WorkspaceProvider'
import NetworkPage from '@/pages/NetworkPage'

function NetworkHeaderRuntimeControls({
  networkId,
  projectId,
}: {
  networkId: string
  projectId: string
}) {
  const [host, setHost] = useState<HTMLDivElement | null>(null)

  useEffect(() => {
    let currentHost: HTMLDivElement | null = null
    let frame = 0

    function attachToHeaderActions() {
      const header = document.querySelector<HTMLElement>('.network-workspace-shell > div > header')
      if (!header) return

      const actionGroup = Array.from(header.children).find(
        (element) => element instanceof HTMLElement && element.classList.contains('ml-auto'),
      )
      if (!(actionGroup instanceof HTMLElement)) return

      let nextHost = actionGroup.querySelector<HTMLDivElement>(':scope > [data-network-runtime-host]')
      const actionChildren = Array.from(actionGroup.children).filter((element) => element !== nextHost)
      const releaseAction = actionChildren.length > 0 ? actionChildren[actionChildren.length - 1] : null

      if (!nextHost) {
        nextHost = document.createElement('div')
        nextHost.dataset.networkRuntimeHost = 'true'
        nextHost.className = 'shrink-0'
      }

      if (releaseAction && nextHost.nextElementSibling !== releaseAction) {
        actionGroup.insertBefore(nextHost, releaseAction)
      } else if (!releaseAction && nextHost.parentElement !== actionGroup) {
        actionGroup.appendChild(nextHost)
      }

      currentHost = nextHost
      setHost(nextHost)
    }

    function scheduleAttach() {
      window.cancelAnimationFrame(frame)
      frame = window.requestAnimationFrame(attachToHeaderActions)
    }

    scheduleAttach()

    const shell = document.querySelector('.network-workspace-shell')
    const observer = new MutationObserver(scheduleAttach)
    if (shell) observer.observe(shell, { childList: true, subtree: true })

    return () => {
      observer.disconnect()
      window.cancelAnimationFrame(frame)
      currentHost?.remove()
    }
  }, [networkId])

  if (!host) return null

  return createPortal(
    <NetworkRuntimeControlsPopover networkId={networkId} projectId={projectId} />,
    host,
  )
}

export default function NetworkWorkspaceRoute() {
  const { workspaceId, projectId, networkId } = useParams<{
    workspaceId: string
    projectId: string
    networkId: string
  }>()
  const navigate = useNavigate()
  const workspace = useWorkspace()
  const networkQuery = useNetwork(projectId)

  if (!workspaceId || !projectId || !networkId) {
    return <Navigate to="/workspaces" replace />
  }

  const networkName = networkQuery.data?.name.trim()
  const displayProject = workspace.currentProject && networkName
    ? {
        ...workspace.currentProject,
        name: networkName.replace(/\s+Network$/i, ''),
      }
    : workspace.currentProject
  const networksPath = `/workspaces/${workspaceId}/projects/${projectId}/networks`
  const shellStyle = {
    '--network-workspace-name': JSON.stringify(networkName || 'Network'),
  } as CSSProperties

  return (
    <NetworkIdentityProvider value={networkName || 'Network'}>
      <div
        className="network-workspace-shell relative h-screen overflow-hidden bg-background"
        style={shellStyle}
      >
        <style>{`
          .network-workspace-shell > div > header {
            overflow-x: auto;
            overflow-y: hidden;
            border-color: #1e293b;
            background: rgba(15, 23, 41, 0.96);
          }
          .network-workspace-shell > div > header > div > h1 {
            font-size: 0;
          }
          .network-workspace-shell > div > header > div > h1::after {
            content: var(--network-workspace-name);
            font-family: 'JetBrains Mono', 'Fira Code', monospace;
            font-size: 0.75rem;
            line-height: 1rem;
            font-weight: 700;
            letter-spacing: 0.015em;
          }
          .network-workspace-shell > div > header > div > p {
            font-size: 0;
          }
          .network-workspace-shell > div > header > div > p::after {
            content: 'Network workspace · isolated within this Project';
            font-family: 'JetBrains Mono', 'Fira Code', monospace;
            font-size: 0.5rem;
            line-height: 0.75rem;
            color: #94a3b8;
          }
          .network-workspace-shell .rounded-xl { border-radius: 4px !important; }
          .network-workspace-shell .rounded-lg { border-radius: 3px !important; }
          .network-workspace-shell .rounded-md { border-radius: 2px !important; }
        `}</style>

        <button
          type="button"
          aria-label="Back to Networks"
          title="Back to Networks"
          onClick={() => navigate(networksPath)}
          className="absolute left-3 top-3 z-[70] flex h-[34px] w-[34px] items-center justify-center rounded-control border border-border bg-control text-muted-foreground transition-colors hover:border-slate-600 hover:text-slate-50 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-primary"
        >
          <ChevronLeft className="h-3.5 w-3.5" />
        </button>

        <WorkspaceContext.Provider value={{ ...workspace, currentProject: displayProject }}>
          <NetworkPage key={networkId} />
        </WorkspaceContext.Provider>

        <NetworkHeaderRuntimeControls networkId={networkId} projectId={projectId} />
      </div>
    </NetworkIdentityProvider>
  )
}
