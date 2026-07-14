import type { AgentNodeId } from './networkWorkspaceTypes'
import type { NetworkTraceRecord } from './networkObservabilityTypes'
import type { NetworkSession } from './networkSessionTypes'
import { NetworkDebugPanel } from './NetworkDebugPanel'
import { NetworkTracePanel } from './NetworkTracePanel'

export { Badge, NetworkOperationsRail } from './NetworkOperationsRail'
export type { PanelTab } from './NetworkOperationsRail'

export function NetworkOperationsPanel({
  activeTab,
  traces,
  session,
  selectedTraceId,
  onSelectTrace,
  onViewCanvas,
  onOpenAgent,
}: {
  activeTab: 'traces' | 'debug'
  traces: NetworkTraceRecord[]
  session: NetworkSession | null
  selectedTraceId: string | null
  onSelectTrace: (trace: NetworkTraceRecord) => void
  onViewCanvas: (trace: NetworkTraceRecord) => void
  onOpenAgent: (nodeId: AgentNodeId) => void
}) {
  const selectedTrace = selectedTraceId
    ? traces.find((trace) => trace.id === selectedTraceId) ?? null
    : null
  return (
    <aside className="flex h-full min-h-0 w-[400px] shrink-0 flex-col overflow-hidden border-r border-border bg-surface/65 shadow-sm shadow-black/10">
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
