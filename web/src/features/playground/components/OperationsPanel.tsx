import type { LeftPanelTab } from './OperationsRail'
import { DebugView } from './DebugView'
import { TraceList } from './TraceList'
import { TraceDetails } from './TraceDetails'
import { TraceDiagnosticsPanel } from './TraceDiagnosticsPanel'
import { SessionsPanel } from './SessionsPanel'
import { ScrollArea } from '@/components/ui/ScrollArea'
import type { AskResponse, RawStreamEvent, SessionListItem, TraceItem } from '@/features/playground/types'

interface OperationsPanelProps {
  activeTab: LeftPanelTab | null
  lastResponse: AskResponse | null
  lastRequestPayload: Record<string, unknown> | null
  rawEvents: RawStreamEvent[]
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

export function OperationsPanel(props: OperationsPanelProps) {
  const {
    activeTab,
    lastResponse,
    lastRequestPayload,
    rawEvents,
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
  } = props

  if (!activeTab) return null

  if (activeTab === 'traces') {
    const selectedTrace = selectedTraceId
      ? traces.find(trace => trace.id === selectedTraceId) ?? null
      : null

    return (
      <div className="w-[380px] shrink-0 h-full min-h-0 overflow-hidden border-r border-border bg-surface flex flex-col">
        <ScrollArea className="flex-shrink-0 max-h-[260px] border-b border-border">
          <TraceList
            traces={traces}
            selectedTraceId={selectedTraceId}
            onSelectTrace={onSelectTrace}
            isLoading={tracesLoading}
            isError={tracesError}
            errorMessage={tracesErrorMessage}
            onRetry={onTracesRetry}
            hasSessionId={Boolean(sessionId)}
          />
        </ScrollArea>
        <ScrollArea className="flex-1 min-h-0">
          {selectedTrace ? (
            <>
              <TraceDiagnosticsPanel traceId={selectedTrace.id} />
              <TraceDetails
                trace={selectedTrace}
                onBack={() => onSelectTrace(null)}
              />
            </>
          ) : (
            <div className="p-4 text-center">
              <p className="text-sm text-muted">Select a trace to view details.</p>
            </div>
          )}
        </ScrollArea>
      </div>
    )
  }

  const content = activeTab === 'debug'
    ? <DebugView lastResponse={lastResponse} lastRequestPayload={lastRequestPayload} rawEvents={rawEvents} />
    : (
        <SessionsPanel
          sessions={sessions}
          currentSessionId={sessionId}
          onNewSession={onNewSession}
          onSelectSession={onSelectSession}
        />
      )

  return (
    <div className="w-[380px] shrink-0 h-full min-h-0 overflow-hidden border-r border-border bg-surface">
      <ScrollArea className="h-full min-h-0">
        {content}
      </ScrollArea>
    </div>
  )
}
