import { useEffect, useRef, useState } from 'react'

import { cn } from '@/lib/utils'
import type { AgentNodeId } from './networkWorkspaceTypes'
import type { NetworkTraceRecord } from './networkObservabilityTypes'
import type { NetworkSession } from './networkSessionTypes'
import { NetworkDebugPanel } from './NetworkDebugPanel'
import { NetworkTracePanel } from './NetworkTracePanel'

export { Badge, NetworkOperationsRail } from './NetworkOperationsRail'
export type { PanelTab } from './NetworkOperationsRail'

export type NetworkOperationsPresentation = 'auto' | 'overlay' | 'docked'

export function NetworkOperationsPanel({
  activeTab,
  traces,
  session,
  selectedTraceId,
  presentation = 'auto',
  onSelectTrace,
  onViewCanvas,
  onOpenAgent,
}: {
  activeTab: 'traces' | 'debug'
  traces: NetworkTraceRecord[]
  session: NetworkSession | null
  selectedTraceId: string | null
  presentation?: NetworkOperationsPresentation
  onSelectTrace: (trace: NetworkTraceRecord) => void
  onViewCanvas: (trace: NetworkTraceRecord) => void
  onOpenAgent: (nodeId: AgentNodeId) => void
}) {
  const panelRef = useRef<HTMLElement | null>(null)
  const [autoDocked, setAutoDocked] = useState(false)
  const selectedTrace = selectedTraceId
    ? traces.find((trace) => trace.id === selectedTraceId) ?? null
    : null

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
        'flex min-h-0 w-[min(400px,calc(100vw-7rem))] flex-col overflow-hidden border-r border-border bg-surface/95',
        resolvedPresentation === 'overlay'
          ? 'absolute inset-y-0 left-14 z-30 shadow-2xl shadow-black/30'
          : 'relative z-0 shrink-0 shadow-xl shadow-black/20',
      )}
    >
      {activeTab === 'traces' ? (
        <NetworkTracePanel
          traces={traces}
          session={session}
          selectedTraceId={selectedTraceId}
          onSelectTrace={onSelectTrace}
          onViewCanvas={onViewCanvas}
          onOpenAgent={onOpenAgent}
        />
      ) : (
        <NetworkDebugPanel trace={selectedTrace} />
      )}
    </aside>
  )
}
