import { useEffect, useState } from 'react'
import { Activity, SquareTerminal, X } from 'lucide-react'
import type { LeftPanelTab } from './OperationsRail'
import { AgentRunOperationalView } from './AgentRunOperationalView'
import { TraceList } from './TraceList'
import { TraceDetails } from './TraceDetails'
import { SessionsPanel } from './SessionsPanel'
import './trace-details-embedded.css'
import { ScrollArea } from '@/components/ui/ScrollArea'
import { cn } from '@/lib/utils'
import type { AskResponse, RawStreamEvent, SessionListItem, TraceItem } from '@/features/playground/types'

interface OperationsPanelProps {
  activeTab: LeftPanelTab | null
  // Kept temporarily for call-site compatibility while Current Run is removed from UX.
  lastResponse: AskResponse | null
  lastRequestPayload: Record<string, unknown> | null
  rawEvents: RawStreamEvent[]
  traces: TraceItem[]
  selectedTraceId: string | null
  sessions: SessionListItem[]
  sessionId: string | null
  sessionMode?: 'stateful' | 'stateless'
  sessionCreationDisabledReason?: string
  onSelectTrace: (id: string | null) => void
  onNewSession: () => void | Promise<void>
  onSelectSession: (id: string) => void
  onLoadMoreSessions?: () => void
  hasMoreSessions?: boolean
  sessionsLoading?: boolean
  sessionsLoadingMore?: boolean
  creatingSession?: boolean
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
    sessionCreationDisabledReason,
    onSelectTrace,
    onNewSession,
    onSelectSession,
    onLoadMoreSessions,
    hasMoreSessions,
    sessionsLoading,
    sessionsLoadingMore,
    creatingSession,
    sessionsError,
    sessionsErrorMessage,
    onSessionsRetry,
    tracesLoading,
    tracesError,
    tracesErrorMessage,
    onTracesRetry,
  } = props
  const [runDetailView, setRunDetailView] = useState<RunDetailView>('run')

  useEffect(() => {
    setRunDetailView('run')
  }, [selectedTraceId])

  if (!activeTab) return null

  // `debug` is treated as Runs only for compatibility with pre-existing local state.
  // The rail no longer exposes Current Run or Debug as separate destinations.
  if (activeTab === 'traces' || activeTab === 'debug') {
    const selectedRun = selectedTraceId
      ? traces.find(run => run.id === selectedTraceId) ?? null
      : null

    return (
      <div className="w-[400px] shrink-0 h-full min-h-0 overflow-hidden border-r border-border/90 bg-surface/70 shadow-sm shadow-black/5 flex flex-col">
        <ScrollArea className="flex-shrink-0 max-h-[260px] border-b border-border/90 bg-background/20">
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
          {selectedRun ? (
            <>
              <div className="flex items-center justify-between border-b border-border/90 bg-background/25 px-4 py-3">
                <div>
                  <h3 className="text-sm font-medium text-white">Agent Run Detail</h3>
                  <p className="mt-0.5 text-[10px] text-muted">Execution and Context together; technical evidence stays separate</p>
                </div>
                <button type="button" onClick={() => onSelectTrace(null)} className="rounded-lg border border-transparent p-1 text-muted transition-colors hover:border-border/80 hover:bg-background/60 hover:text-white" aria-label="Close Agent Run details"><X className="h-4 w-4" /></button>
              </div>

              <nav className="grid grid-cols-2 border-b border-border/90 bg-background/20 p-1.5" aria-label="Agent Run detail views">
                {([
                  ['run', Activity, 'Run'],
                  ['evidence', SquareTerminal, 'Evidence'],
                ] as const).map(([target, Icon, label]) => (
                  <button
                    key={target}
                    type="button"
                    onClick={() => setRunDetailView(target)}
                    className={cn(
                      'flex items-center justify-center gap-1.5 rounded-lg px-2 py-1.5 text-[9px] font-medium transition-colors',
                      runDetailView === target ? 'bg-primary/10 text-primary-light' : 'text-muted hover:text-white',
                    )}
                  >
                    <Icon className="h-3.5 w-3.5" />
                    {label}
                  </button>
                ))}
              </nav>

              {runDetailView === 'run' ? (
                <AgentRunOperationalView traceId={selectedRun.trace_id || selectedRun.id} />
              ) : null}

              {runDetailView === 'evidence' ? (
                <div className="trace-details-embedded"><TraceDetails trace={selectedRun} onBack={() => setRunDetailView('run')} /></div>
              ) : null}
            </>
          ) : (
            <div className="p-4 text-center"><div className="rounded-xl border border-border/80 bg-background/45 px-4 py-8"><p className="text-sm text-muted">Select an Agent Run to inspect its execution, Context, and evidence.</p></div></div>
          )}
        </ScrollArea>
      </div>
    )
  }

  return (
    <div className="w-[400px] shrink-0 h-full min-h-0 overflow-hidden border-r border-border/90 bg-surface/70 shadow-sm shadow-black/5">
      <ScrollArea className="h-full min-h-0">
        <SessionsPanel
          sessions={sessions}
          currentSessionId={sessionId}
          sessionMode={sessionMode}
          creationDisabledReason={sessionCreationDisabledReason}
          onNewSession={onNewSession}
          onSelectSession={onSelectSession}
          onLoadMoreSessions={onLoadMoreSessions}
          hasMoreSessions={hasMoreSessions}
          isInitialLoading={sessionsLoading}
          isLoadingMore={sessionsLoadingMore}
          isCreatingSession={creatingSession}
          isError={sessionsError}
          errorMessage={sessionsErrorMessage}
          onRetry={onSessionsRetry}
        />
      </ScrollArea>
    </div>
  )
}
