import { useEffect, useRef, useState } from 'react'

import { cn } from '@/lib/utils'
import type { AgentNodeId } from './networkWorkspaceTypes'
import type { NetworkTraceRecord } from './networkObservabilityTypes'
import type { NetworkSession } from './networkSessionTypes'
import { NetworkSessionsPanel } from './NetworkSessionsPanel'
import { NetworkTracePanel } from './NetworkTracePanel'

export { Badge, NetworkOperationsRail } from './NetworkOperationsRail'
export type { PanelTab } from './NetworkOperationsRail'

export type NetworkOperationsPresentation = 'auto' | 'overlay' | 'docked'

export function NetworkOperationsPanel({
  activeTab,
  traces,
  sessions,
  session,
  selectedTraceId,
  currentVersionId,
  sessionsLoading = false,
  presentation = 'auto',
  onSelectTrace,
  onSelectSession,
  onViewCanvas,
  onOpenAgent,
}: {
  activeTab: 'traces' | 'sessions'
  traces: NetworkTraceRecord[]
  sessions: NetworkSession[]
  session: NetworkSession | null
  selectedTraceId: string | null
  currentVersionId: string | null
  sessionsLoading?: boolean
  presentation?: NetworkOperationsPresentation
  onSelectTrace: (trace: NetworkTraceRecord) => void
  onSelectSession: (sessionId: string) => void
  onViewCanvas: (trace: NetworkTraceRecord) => void
  onOpenAgent: (nodeId: AgentNodeId) => void
}) {
  const panelRef = useRef<HTMLElement | null>(null)
  const [autoDocked, setAutoDocked] = useState(false)

  useEffect(() => {
    if (presentation !== 'auto') return
    const panel = panelRef.current
    const centerWorkspace = panel?.nextElementSibling as HTMLElement | null
    if (!centerWorkspace) return
    const media = window.matchMedia('(min-width: 1280px)')
    const updatePresentation = () => {
      const chatLayer = centerWorkspace.children.item(1) as HTMLElement | null
      setAutoDocked(media.matches && chatLayer?.getAttribute('aria-hidden') === 'false')
    }
    const observer = new MutationObserver(updatePresentation)
    observer.observe(centerWorkspace, {
      attributes: true,
      subtree: true,
      attributeFilter: ['aria-hidden'],
    })
    media.addEventListener('change', updatePresentation)
    updatePresentation()
    return () => {
      observer.disconnect()
      media.removeEventListener('change', updatePresentation)
    }
  }, [presentation])

  const resolvedPresentation = presentation === 'auto'
    ? autoDocked ? 'docked' : 'overlay'
    : presentation

  return (
    <aside
      ref={panelRef}
      data-network-operations-panel
      data-presentation={resolvedPresentation}
      className={cn(
        'flex min-h-0 w-operations-panel max-w-[calc(100vw-5rem)] flex-col overflow-hidden border-r border-border bg-surface/95',
        resolvedPresentation === 'overlay'
          ? 'absolute inset-y-0 left-playground-rail z-workspace shadow-popup'
          : 'relative z-base shrink-0',
      )}
    >
      {activeTab === 'sessions' ? (
        <NetworkSessionsPanel
          sessions={sessions}
          activeSessionId={session?.id ?? null}
          currentVersionId={currentVersionId}
          loading={sessionsLoading}
          onSelectSession={onSelectSession}
        />
      ) : (
        <NetworkTracePanel
          traces={traces}
          session={session}
          selectedTraceId={selectedTraceId}
          onSelectTrace={onSelectTrace}
          onViewCanvas={onViewCanvas}
          onOpenAgent={onOpenAgent}
        />
      )}
    </aside>
  )
}
