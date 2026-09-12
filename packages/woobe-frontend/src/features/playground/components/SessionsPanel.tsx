import { useEffect, useRef } from 'react'
import { EmptyStatePanel, TechnicalListItem } from '@woobe/ui'
import { CopyButton } from '@/components/common/CopyButton'
import { Activity, AlertTriangle, Circle, Clock, Loader2, MessageSquare, RefreshCw } from 'lucide-react'
import { cn } from '@/lib/utils'
import { useAgentStreamStopState } from '@/features/playground/stream-stop-state'
import type { SessionListItem } from '@/features/playground/types'

interface SessionsPanelProps {
  sessions: SessionListItem[]
  currentSessionId: string | null
  sessionMode: 'stateful' | 'stateless'
  onSelectSession: (id: string) => void
  onLoadMoreSessions?: () => void
  hasMoreSessions?: boolean
  isInitialLoading?: boolean
  isLoadingMore?: boolean
  isError?: boolean
  errorMessage?: string
  onRetry?: () => void
}

function formatDate(dateStr: string | null): string {
  if (!dateStr) return '—'
  const d = new Date(dateStr)
  return d.toLocaleDateString(undefined, {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

function formatSource(session: SessionListItem): string | null {
  const source = session.data?.source
  if (typeof source !== 'string' || !source.trim()) return null
  if (source === 'playground') return 'Playground'
  if (source === 'public_runtime') return 'API'
  if (source === 'chat_surface') return 'ChatSurface'
  return source
}

function SessionSkeleton() {
  return (
    <div className="rounded-container border border-border/70 bg-background/20 px-3 py-2.5">
      <div className="flex items-center justify-between gap-2">
        <div className="h-2.5 w-24 animate-pulse rounded-technical bg-white/[0.06]" />
        <div className="h-2 w-9 animate-pulse rounded-technical bg-white/[0.06]" />
      </div>
      <div className="mt-2 h-2 w-32 animate-pulse rounded-technical bg-white/[0.06]" />
    </div>
  )
}

export function SessionsPanel({
  sessions,
  currentSessionId,
  sessionMode,
  onSelectSession,
  onLoadMoreSessions,
  hasMoreSessions = false,
  isInitialLoading = false,
  isLoadingMore = false,
  isError = false,
  errorMessage,
  onRetry,
}: SessionsPanelProps) {
  const sentinelRef = useRef<HTMLDivElement | null>(null)
  const runtimeState = useAgentStreamStopState()
  const runtimeBusy = runtimeState !== 'idle'
  const disabledReason = runtimeBusy
    ? runtimeState === 'stopping'
      ? 'Wait for the active Agent Run cancellation to finish before changing Sessions'
      : 'Wait for the active Agent Run to finish or stop it before changing Sessions'
    : undefined
  const selectedSessionMissing = Boolean(currentSessionId) && !sessions.some((session) => session.id === currentSessionId)

  useEffect(() => {
    const node = sentinelRef.current
    if (!node || !hasMoreSessions || isInitialLoading || isLoadingMore || !onLoadMoreSessions) return

    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting && hasMoreSessions && !isLoadingMore) onLoadMoreSessions()
      },
      { root: null, rootMargin: '160px 0px', threshold: 0 },
    )

    observer.observe(node)
    return () => observer.disconnect()
  }, [hasMoreSessions, isInitialLoading, isLoadingMore, onLoadMoreSessions])

  return (
    <div className="space-y-3 p-3">
      <div className="flex items-center justify-between gap-3 border-b border-border/70 pb-2.5">
        <div>
          <h3 className="font-mono text-[10px] font-semibold text-slate-50">Sessions</h3>
          <p className="mt-0.5 font-sans text-[9px] leading-4 text-muted-foreground">Conversation continuity for this Agent runtime.</p>
        </div>
        <span className="font-mono text-[8px] text-muted-foreground">{sessions.length} loaded</span>
      </div>

      {disabledReason ? (
        <div className="flex gap-2 rounded-container border border-border bg-background/25 px-3 py-2 font-sans text-[9px] leading-4 text-muted-foreground">
          <Activity className="mt-0.5 h-3 w-3 shrink-0 text-primary-light" />
          <p>{disabledReason}. Historical Sessions remain available for inspection.</p>
        </div>
      ) : null}

      {currentSessionId ? (
        <div className="rounded-container border border-border bg-background/25 px-3 py-2">
          <div className="mb-1 flex items-center justify-between gap-2">
            <span className="font-mono text-[8px] uppercase tracking-[0.08em] text-muted-foreground">Selected session</span>
            <CopyButton text={currentSessionId} />
          </div>
          <code className="block truncate font-mono text-[9px] text-slate-200" title={currentSessionId}>{currentSessionId}</code>
        </div>
      ) : null}

      {isInitialLoading && sessions.length === 0 ? (
        <div className="space-y-1.5">{Array.from({ length: 6 }).map((_, index) => <SessionSkeleton key={index} />)}</div>
      ) : null}

      {!isInitialLoading && isError ? (
        <EmptyStatePanel
          icon={<AlertTriangle className="h-4 w-4 text-red-300" />}
          title="Couldn’t load Sessions"
          description={errorMessage || 'The Sessions list could not be loaded from the runtime.'}
          action={onRetry ? <button type="button" onClick={onRetry} className="inline-flex h-[27px] items-center gap-1.5 rounded-control border border-border bg-control/35 px-2.5 font-mono text-[8px] text-slate-200 hover:bg-control"><RefreshCw className="h-3 w-3" />Retry</button> : undefined}
        />
      ) : null}

      {!isInitialLoading && !isError && selectedSessionMissing && sessions.length === 0 ? (
        <EmptyStatePanel
          icon={<AlertTriangle className="h-4 w-4 text-amber-300" />}
          title="Session list is out of sync"
          description="The runtime returned a selected Session that is not present in the loaded environment list."
          action={onRetry ? <button type="button" onClick={onRetry} className="inline-flex h-[27px] items-center gap-1.5 rounded-control border border-border bg-control/35 px-2.5 font-mono text-[8px] text-slate-200 hover:bg-control"><RefreshCw className="h-3 w-3" />Refresh Sessions</button> : undefined}
        />
      ) : null}

      {!isInitialLoading && !isError && !currentSessionId && sessions.length === 0 ? (
        <EmptyStatePanel
          icon={<MessageSquare className="h-4 w-4" />}
          title="No Sessions yet"
          description={sessionMode === 'stateless' ? 'This Agent runtime is stateless and does not create persistent Sessions.' : 'Use New Session in the operations rail to start a conversation.'}
        />
      ) : null}

      {sessions.length > 0 ? (
        <div className="space-y-1.5">
          {selectedSessionMissing && !isError ? (
            <div className="flex items-start gap-2 rounded-container border border-amber-400/20 bg-background/25 px-3 py-2 font-sans text-[9px] leading-4 text-muted-foreground">
              <AlertTriangle className="mt-0.5 h-3 w-3 shrink-0 text-amber-300" />
              <p>The selected Session is not present in the loaded page. Refresh before continuing it.</p>
            </div>
          ) : null}

          {sessions.map((session) => {
            const isCurrent = session.id === currentSessionId
            const openedVersion = session.opened_release_version
            const source = formatSource(session)
            return (
              <TechnicalListItem
                key={session.id}
                selected={isCurrent}
                onClick={() => onSelectSession(session.id)}
                disabled={runtimeBusy}
                title={session.id.slice(0, 8) + '…'}
                description={openedVersion ? `Opened · ${openedVersion}` : undefined}
                leading={<Circle className={cn('h-2 w-2 fill-current', isCurrent ? 'text-primary-light' : 'text-muted-foreground')} />}
                trailing={isCurrent ? <span className="font-mono text-[8px] uppercase text-primary-light">Selected</span> : undefined}
                meta={
                  <>
                    <span className="inline-flex items-center gap-1"><Clock className="h-3 w-3" />{formatDate(session.last_message_at || session.created_at)}</span>
                    <span>{session.message_count ?? 0} msgs</span>
                    {source ? <span>{source}</span> : null}
                  </>
                }
                title={runtimeBusy ? disabledReason : undefined}
              />
            )
          })}

          <div ref={sentinelRef} className="h-1" />
          {isLoadingMore ? <div className="flex items-center justify-center gap-2 py-3 font-mono text-[8px] text-muted-foreground"><Loader2 className="h-3 w-3 animate-spin" />Loading more Sessions…</div> : null}
        </div>
      ) : null}
    </div>
  )
}
