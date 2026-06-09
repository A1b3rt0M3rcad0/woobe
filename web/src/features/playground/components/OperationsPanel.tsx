import type { LeftPanelTab } from './OperationsRail'
import { DebugView } from './DebugView'
import { TraceList } from './TraceList'
import { TraceDetails } from './TraceDetails'
import { SessionsPanel } from './SessionsPanel'
import type { AskResponse, SessionListItem, TraceItem } from '@/features/playground/types'

interface OperationsPanelProps {
  activeTab: LeftPanelTab | null
  lastResponse: AskResponse | null
  traces: TraceItem[]
  selectedTraceId: string | null
  sessions: SessionListItem[]
  sessionId: string | null
  onSelectTrace: (id: string | null) => void
  onNewSession: () => void
  onSelectSession: (id: string) => void
  tracesLoading?: boolean
  tracesError?: boolean
  tracesErrorMessage?: string
  onTracesRetry?: () => void
}

export function OperationsPanel({
  activeTab,
  lastResponse,
  traces,
  selectedTraceId,
  sessions,
  sessionId,
  onSelectTrace,
  onNewSession,
  onSelectSession,
  tracesLoading,
  tracesError,
  tracesErrorMessage,
  onTracesRetry,
}: OperationsPanelProps) {
  if (!activeTab) return null

  const panelContent = () => {
    switch (activeTab) {
      case 'debug':
        return <DebugView lastResponse={lastResponse} />
      case 'traces':
        return selectedTraceId && traces.find(t => t.id === selectedTraceId) ? (
          <TraceDetails
            trace={traces.find(t => t.id === selectedTraceId)!}
            onBack={() => onSelectTrace(null)}
          />
        ) : (
          <TraceList
            traces={traces}
            selectedTraceId={selectedTraceId}
            onSelectTrace={onSelectTrace}
            isLoading={tracesLoading}
            isError={tracesError}
            errorMessage={tracesErrorMessage}
            onRetry={onTracesRetry}
            hasSessionId={!!sessionId}
          />
        )
      case 'sessions':
        return (
          <SessionsPanel
            sessions={sessions}
            currentSessionId={sessionId}
            onNewSession={onNewSession}
            onSelectSession={onSelectSession}
          />
        )
      default:
        return null
    }
  }

  if (activeTab === 'traces') {
    const selectedTrace = selectedTraceId ? traces.find(t => t.id === selectedTraceId) : null
    return (
      <div className="w-[380px] shrink-0 h-full min-h-0 overflow-hidden border-r border-border bg-surface flex flex-col">
        <div className="flex-shrink-0 max-h-[260px] overflow-y-auto border-b border-border">
          <TraceList
            traces={traces}
            selectedTraceId={selectedTraceId}
            onSelectTrace={onSelectTrace}
            isLoading={tracesLoading}
            isError={tracesError}
            errorMessage={tracesErrorMessage}
            onRetry={onTracesRetry}
            hasSessionId={!!sessionId}
          />
        </div>
        <div className="flex-1 min-h-0 overflow-y-auto">
          {selectedTrace ? (
            <TraceDetails
              trace={selectedTrace}
              onBack={() => onSelectTrace(null)}
            />
          ) : (
            <div className="p-4 text-center">
              <p className="text-sm text-muted">Select a trace to view details.</p>
            </div>
          )}
        </div>
      </div>
    )
  }

  return (
    <div className="w-[380px] shrink-0 h-full min-h-0 overflow-hidden border-r border-border bg-surface">
      <div className="h-full min-h-0 overflow-y-auto overflow-x-hidden">
        {panelContent()}
      </div>
    </div>
  )
}
