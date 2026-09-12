import { useEffect, useState } from 'react'
import { Activity, SquareTerminal, X } from 'lucide-react'
import { EmptyStatePanel, SegmentedControl } from '@woobe/ui'
import type { LeftPanelTab } from './OperationsRail'
import { AgentRunEvidencePanel } from './AgentRunEvidencePanel'
import { AgentRunOperationalView } from './AgentRunOperationalView'
import { TraceList } from './TraceList'
import { SessionsPanel } from './SessionsPanel'
import { ScrollArea } from '@/components/ui/ScrollArea'
import { cn } from '@/lib/utils'
import { useAgentStreamStopState } from '@/features/playground/stream-stop-state'
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
  sessionMode?: 'stateful' | 'stateless'
  onSelectTrace: (id: string | null) => void
  onSelectSession: (id: string) => void
  onLoadMoreSessions?: () => void
  hasMoreSessions?: boolean
  sessionsLoading?: boolean
  sessionsLoadingMore?: boolean
  sessionsError?: boolean
  sessionsErrorMessage?: string
  onSessionsRetry?: () => void
  tracesLoading?: boolean
  tracesError?: boolean
  tracesErrorMessage?: string
  onTracesRetry?: () => void
}

type RunDetailView = 'run' | 'evidence'

export function OperationsPanel(props: OperationsPanelProps) {
  const {
    activeTab,
    traces,
    selectedTraceId,
    sessions,
    sessionId,
    sessionMode = 'stateful',
    onSelectTrace,
    onSelectSession,
    onLoadMoreSessions,
    hasMoreSessions,
    sessionsLoading,
    sessionsLoadingMore,
    sessionsError,
    sessionsErrorMessage,
    onSessionsRetry,
    tracesLoading,
    tracesError,
    tracesErrorMessage,
    onTracesRetry,
  } = props
  const [runDetailView, setRunDetailView] = useState<RunDetailView>('run')
  const streamState = useAgentStreamStopState()
  const sessionInteractionBlocked = streamState !== 'idle'

  useEffect(() => setRunDetailView('run'), [selectedTraceId])

  if (!activeTab) return null

  if (activeTab === 'traces' || activeTab === 'debug') {
    const selectedRun = selectedTraceId ? traces.find(run => run.id === selectedTraceId) ?? null : null
    const traceIdentity = selectedRun ? selectedRun.trace_id || selectedRun.id : null
    const runIdentity = selectedRun?.run_id ?? null
    const runFinalizing = selectedRun?.status === 'running' || selectedRun?.status === 'pending'

    return (
      <div className="flex h-full min-h-0 w-operations-panel shrink-0 flex-col overflow-hidden border-r border-border bg-surface/[0.74]">
        <ScrollArea className="max-h-[238px] flex-shrink-0 border-b border-border bg-background/15">
          <TraceList traces={traces} selectedTraceId={selectedTraceId} onSelectTrace={onSelectTrace} isLoading={tracesLoading} isError={tracesError} errorMessage={tracesErrorMessage} onRetry={onTracesRetry} hasSessionId={Boolean(sessionId)} />
        </ScrollArea>
        <ScrollArea className="min-h-0 flex-1">
          {selectedRun ? (
            <>
              <div className="flex min-h-panel-header items-center justify-between border-b border-border bg-background/20 px-ui-md py-ui-sm">
                <div className="min-w-0">
                  <h3 className="font-mono text-system-label font-bold text-slate-50">Agent Run detail</h3>
                  <p className="mt-ui-xs truncate font-sans text-product-caption text-muted-foreground">Execution first; raw evidence remains separate.</p>
                </div>
                <button type="button" onClick={() => onSelectTrace(null)} className="flex h-control-segment w-control-segment items-center justify-center rounded-control border border-transparent text-muted-foreground transition-colors hover:border-border hover:bg-control hover:text-slate-50" aria-label="Close Agent Run details"><X className="h-3.5 w-3.5" /></button>
              </div>

              <div className="border-b border-border bg-background/15 p-[3px]">
                <SegmentedControl
                  ariaLabel="Agent Run detail views"
                  value={runDetailView}
                  onValueChange={(value) => setRunDetailView(value as RunDetailView)}
                  stretch
                  items={[
                    { value: 'run', label: 'Run', icon: <Activity className="h-3 w-3" /> },
                    { value: 'evidence', label: 'Evidence', icon: <SquareTerminal className="h-3 w-3" /> },
                  ]}
                  className="w-full border-0 bg-transparent p-0"
                />
              </div>

              {runDetailView === 'run' ? <AgentRunOperationalView runId={runIdentity} traceId={traceIdentity} finalizing={runFinalizing} /> : null}
              {runDetailView === 'evidence' ? <div className="p-ui-md"><AgentRunEvidencePanel runId={runIdentity} traceId={traceIdentity} /></div> : null}
            </>
          ) : (
            <div className="p-ui-md"><EmptyStatePanel compact title="Select an Agent Run" description="Inspect execution, result, Context and evidence from one place." /></div>
          )}
        </ScrollArea>
      </div>
    )
  }

  return (
    <div className="flex h-full min-h-0 w-operations-panel shrink-0 flex-col overflow-hidden border-r border-border bg-surface/[0.74]">
      {sessionInteractionBlocked ? <div className="shrink-0 border-b border-border bg-background/25 px-ui-md py-ui-sm font-sans text-product-caption text-muted-foreground">{streamState === 'stopping' ? 'Stopping the active Agent Run. Session changes unlock after terminal finalization.' : 'An Agent Run is active. Session changes unlock after the Run reaches a terminal state.'}</div> : null}
      <ScrollArea className={cn('min-h-0 flex-1', sessionInteractionBlocked && 'pointer-events-none opacity-60')}>
        <SessionsPanel sessions={sessions} currentSessionId={sessionId} sessionMode={sessionMode} onSelectSession={onSelectSession} onLoadMoreSessions={onLoadMoreSessions} hasMoreSessions={hasMoreSessions} isInitialLoading={sessionsLoading} isLoadingMore={sessionsLoadingMore} isError={sessionsError} errorMessage={sessionsErrorMessage} onRetry={onSessionsRetry} />
      </ScrollArea>
    </div>
  )
}
