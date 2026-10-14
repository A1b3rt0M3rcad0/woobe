import { useEffect, useState } from 'react'
import { createPortal } from 'react-dom'
import { Navigate, useParams } from 'react-router-dom'

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

  return (
    <NetworkIdentityProvider value={networkName || 'Network'}>
      <div
        className="network-workspace-shell relative h-svh overflow-hidden bg-background"
      >
        <WorkspaceContext.Provider value={{ ...workspace, currentProject: displayProject }}>
          <NetworkPage key={networkId} />
        </WorkspaceContext.Provider>

        <NetworkHeaderRuntimeControls networkId={networkId} projectId={projectId} />
      </div>
    </NetworkIdentityProvider>
  )
}
