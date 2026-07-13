import type { AgentNodeId } from './networkWorkspaceTypes'
import type { NetworkTraceRecord } from './networkObservabilityTypes'
import { NetworkDebugPanel } from './NetworkDebugPanel'
import { NetworkTracePanel } from './NetworkTracePanel'

export { Badge, NetworkOperationsRail } from './NetworkOperationsRail'
export type { PanelTab } from './NetworkOperationsRail'

export function NetworkOperationsPanel({
  activeTab,
  traces,
  selectedTraceId,
  currentSessionId,
  onSelectTrace,
  onViewCanvas,
  onOpenAgent,
}: {
  activeTab: 'traces' | 'debug'
  traces: NetworkTraceRecord[]
  selectedTraceId: string | null
  currentSessionId: string
  onSelectTrace: (trace: NetworkTraceRecord) => void
  onViewCanvas: (trace: NetworkTraceRecord) => void
  onOpenAgent: (nodeId: AgentNodeId) => void
}) {
  const selectedTrace = traces.find((trace) => trace.id === selectedTraceId) ?? traces[0] ?? null
  return (
    <aside className="flex h-full min-h-0 w-[400px] shrink-0 flex-col overflow-hidden border-r border-border bg-surface/65 shadow-sm shadow-black/10">
      {activeTab === 'traces' ? (
        <NetworkTracePanel
          traces={traces}
          selectedTraceId={selectedTraceId}
          currentSessionId={currentSessionId}
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
