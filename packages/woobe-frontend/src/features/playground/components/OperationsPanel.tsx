import { useEffect, useState } from 'react'
import { Activity, SquareTerminal, X } from 'lucide-react'
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
    const selectedRun = selectedTraceId
      ? traces.find(run => run.id === selectedTraceId) ?? null
      : null
    const traceIdentity = selectedRun ? selectedRun.trace_id || selectedRun.id : null
    const runIdentity = selectedRun?.run_id ?? null
    const runFinalizing = selectedRun?.status === 'running' || selectedRun?.status === 'pending'

    return (
      <div className="flex h-full min-h-0 w-[372px] shrink-0 flex-col overflow-hidden border-r border-border bg-surface/[0.74]">
        <ScrollArea className="max-h-[238px] flex-shrink-0 border-b border-border bg-background/15">
          <TraceList traces={traces} selectedTraceId={selectedTraceId} onSelectTrace={onSelectTrace} isLoading={tracesLoading} isError={tracesError} errorMessage={tracesErrorMessage} onRetry={onTracesRetry} hasSessionId={Boolean(sessionId)} />
        </ScrollArea>
        <ScrollArea className="min-h-0 flex-1">
          {selectedRun ? (
            <>
              <div className="flex min-h-[44px] items-center justify-between border-b border-border bg-background/20 px-3 py-2.5">
                <div className="min-w-0">
                  <h3 className="font-mono text-[9px] font-bold text-slate-50">Agent Run detail</h3>
                  <p className="mt-0.5 truncate font-sans text-[9px] text-muted-foreground">Execution first; raw evidence remains separate.</p>
                </div>
                <button type="button" onClick={() => onSelectTrace(null)} className="flex h-7 w-7 items-center justify-center rounded-control border border-transparent text-muted-foreground transition-colors hover:border-border hover:bg-control hover:text-slate-50" aria-label="Close Agent Run details"><X className="h-3.5 w-3.5" /></button>
              </div>

              <nav className="flex border-b border-border bg-background/15 p-[3px]" aria-label="Agent Run detail views">
                {([
                  ['run', Activity, 'Run'],
                  ['evidence', SquareTerminal, 'Evidence'],
                ] as const).map(([target, Icon, label]) => (
                  <button key={target} type="button" onClick={() => setRunDetailView(target)} className={cn('flex h-[27px] flex-1 items-center justify-center gap-1.5 rounded-technical border font-mono text-[8px] transition-colors', runDetailView === target ? 'border-primary/35 bg-primary/[0.10] text-primary-light' : 'border-transparent text-muted-foreground hover:bg-control/45 hover:text-slate-50')}>
                    <Icon className="h-3 w-3" />{label}
                  </button>
                ))}
              </nav>

              {runDetailView === 'run' ? <AgentRunOperationalView runId={runIdentity} traceId={traceIdentity} finalizing={runFinalizing} /> : null}
              {runDetailView === 'evidence' ? <div className="p-3"><AgentRunEvidencePanel runId={runIdentity} traceId={traceIdentity} /></div> : null}
            </>
          ) : (
            <div className="p-3"><div className="rounded-container border border-dashed border-border bg-background/20 px-4 py-8 text-center"><p className="font-sans text-[10px] leading-4 text-muted-foreground">Select an Agent Run to inspect execution, result, context and evidence.</p></div></div>
          )}
        </ScrollArea>
      </div>
    )
  }

  return (
    <div className="flex h-full min-h-0 w-[372px] shrink-0 flex-col overflow-hidden border-r border-border bg-surface/[0.74]">
      {sessionInteractionBlocked ? (
        <div className="shrink-0 border-b border-border bg-background/25 px-3 py-2 font-sans text-[9px] leading-4 text-muted-foreground">
          {streamState === 'stopping'
            ? 'Stopping the active Agent Run. Session changes unlock after terminal finalization.'
            : 'An Agent Run is active. Session changes unlock after the Run reaches a terminal state.'}
        </div>
      ) : null}
      <ScrollArea className={cn('min-h-0 flex-1', sessionInteractionBlocked && 'pointer-events-none opacity-60')}>
        <SessionsPanel sessions={sessions} currentSessionId={sessionId} sessionMode={sessionMode} onSelectSession={onSelectSession} onLoadMoreSessions={onLoadMoreSessions} hasMoreSessions={hasMoreSessions} isInitialLoading={sessionsLoading} isLoadingMore={sessionsLoadingMore} isError={sessionsError} errorMessage={sessionsErrorMessage} onRetry={onSessionsRetry} />
      </ScrollArea>
    </div>
  )
}
