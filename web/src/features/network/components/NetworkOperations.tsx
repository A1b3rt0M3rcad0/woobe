import { cn } from '@/lib/utils'
import type { AgentNodeId } from './networkWorkspaceTypes'
import type { NetworkTraceRecord } from './networkObservabilityTypes'
import type { NetworkSession } from './networkSessionTypes'
import { NetworkDebugPanel } from './NetworkDebugPanel'
import { NetworkTracePanel } from './NetworkTracePanel'

export { Badge, NetworkOperationsRail } from './NetworkOperationsRail'
export type { PanelTab } from './NetworkOperationsRail'

export type NetworkOperationsPresentation = 'overlay' | 'docked'

export function NetworkOperationsPanel({
  activeTab,
  traces,
  session,
  selectedTraceId,
  presentation = 'overlay',
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
  const selectedTrace = selectedTraceId
    ? traces.find((trace) => trace.id === selectedTraceId) ?? null
    : null
  return (
    <aside
      data-network-operations-panel
      data-presentation={presentation}
      className={cn(
        'flex min-h-0 flex-col overflow-hidden border-r border-border bg-surface/95',
        presentation === 'overlay'
          ? 'absolute inset-y-0 left-14 z-30 w-[400px] shadow-2xl shadow-black/30'
          : 'absolute inset-y-0 left-14 z-30 w-[min(360px,calc(100vw-7rem))] shadow-2xl shadow-black/30 xl:relative xl:inset-auto xl:left-auto xl:z-0 xl:w-[360px] xl:shrink-0 xl:shadow-xl xl:shadow-black/20',
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
