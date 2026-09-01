import { useEffect, useRef } from 'react'
import { CopyButton } from '@/components/common/CopyButton'
import { Separator } from '@/components/ui/Separator'
import { Activity, AlertTriangle, Circle, Clock, Loader2, MessageSquare, Plus, RefreshCw } from 'lucide-react'
import { cn } from '@/lib/utils'
import { useAgentStreamStopState } from '@/features/playground/stream-stop-state'
import type { SessionListItem } from '@/features/playground/types'

interface SessionsPanelProps {
  sessions: SessionListItem[]
  currentSessionId: string | null
  sessionMode: 'stateful' | 'stateless'
  creationDisabledReason?: string
  onNewSession: () => void | Promise<void>
  onSelectSession: (id: string) => void
  onLoadMoreSessions?: () => void
  hasMoreSessions?: boolean
  isInitialLoading?: boolean
  isLoadingMore?: boolean
  isCreatingSession?: boolean
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
    <div className="rounded-xl border border-border/80 bg-background/45 p-3 shadow-sm shadow-black/5">
      <div className="flex items-center justify-between gap-2">
        <div className="h-3 w-28 animate-pulse rounded-full bg-white/[0.07]" />
        <div className="h-2.5 w-10 animate-pulse rounded-full bg-white/[0.07]" />
      </div>
      <div className="mt-3 h-2.5 w-36 animate-pulse rounded-full bg-white/[0.07]" />
    </div>
  )
}

export function SessionsPanel({
  sessions,
  currentSessionId,
  sessionMode,
  creationDisabledReason,
  onNewSession,
  onSelectSession,
  onLoadMoreSessions,
  hasMoreSessions = false,
  isInitialLoading = false,
  isLoadingMore = false,
  isCreatingSession = false,
  isError = false,
  errorMessage,
  onRetry,
}: SessionsPanelProps) {
  const sentinelRef = useRef<HTMLDivElement | null>(null)
  const runtimeState = useAgentStreamStopState()
  const runtimeBusy = runtimeState !== 'idle'
  const newSessionsDisabled = runtimeBusy || sessionMode === 'stateless' || Boolean(creationDisabledReason)
  const disabledReason = runtimeBusy
    ? runtimeState === 'stopping'
      ? 'Wait for the active Agent Run cancellation to finish before changing Sessions'
      : 'Wait for the active Agent Run to finish or stop it before changing Sessions'
    : creationDisabledReason
      ?? (sessionMode === 'stateless' ? 'This Agent runtime is stateless and cannot create persistent Sessions' : undefined)
  const selectedSessionMissing = Boolean(currentSessionId) && !sessions.some((session) => session.id === currentSessionId)

  useEffect(() => {
    const node = sentinelRef.current
    if (!node || !hasMoreSessions || isInitialLoading || isLoadingMore || !onLoadMoreSessions) return

    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting && hasMoreSessions && !isLoadingMore) {
          onLoadMoreSessions()
        }
      },
      { root: null, rootMargin: '160px 0px', threshold: 0 },
    )

    observer.observe(node)
    return () => observer.disconnect()
  }, [hasMoreSessions, isInitialLoading, isLoadingMore, onLoadMoreSessions])

  return (
    <div className="p-4 space-y-3">
      <div className="flex items-center justify-between gap-3">
        <h3 className="text-sm font-semibold text-white">Sessions</h3>
        <button
          type="button"
          onClick={() => void onNewSession()}
          disabled={isCreatingSession || newSessionsDisabled}
          title={disabledReason}
          className="inline-flex h-7 items-center gap-1.5 rounded-lg border border-primary/30 bg-primary/10 px-2.5 text-[11px] font-medium text-primary-light transition-colors hover:border-primary/50 hover:bg-primary/15 disabled:cursor-not-allowed disabled:opacity-60"
        >
          {isCreatingSession ? <Loader2 className="h-3 w-3 animate-spin" /> : <Plus className="h-3 w-3" />}
          New
        </button>
      </div>

      {disabledReason && (
        <div className="flex gap-2 rounded-xl border border-border/80 bg-background/45 p-3 text-xs leading-5 text-muted">
          <Activity className="mt-0.5 h-3.5 w-3.5 shrink-0" />
          <p>{disabledReason} Historical Sessions remain available for inspection.</p>
        </div>
      )}

      {currentSessionId && (
        <>
          <div>
            <p className="mb-1 text-xs font-medium text-muted">Selected Session ID</p>
            <div className="flex items-center gap-2 rounded-xl border border-border/80 bg-background/45 p-2">
              <code className="min-w-0 flex-1 truncate text-xs" title={currentSessionId}>{currentSessionId}</code>
              <CopyButton text={currentSessionId} />
            </div>
          </div>
          <Separator />
        </>
      )}

      {isInitialLoading && sessions.length === 0 && (
        <div className="space-y-1.5">
          {Array.from({ length: 6 }).map((_, index) => <SessionSkeleton key={index} />)}
        </div>
      )}

      {!isInitialLoading && isError && (
        <div className="flex flex-col items-center justify-center rounded-xl border border-red-500/20 bg-red-500/[0.04] px-4 py-8 text-center">
          <AlertTriangle className="mb-2 h-8 w-8 text-red-300" />
          <p className="text-sm font-medium text-white">Couldn&apos;t load Sessions</p>
          <p className="mt-1 max-w-xs text-xs leading-5 text-muted">{errorMessage || 'The Sessions list could not be loaded from the runtime.'}</p>
          {onRetry ? (
            <button
              type="button"
              onClick={onRetry}
              className="mt-4 inline-flex h-8 items-center gap-1.5 rounded-lg border border-border/80 bg-background/55 px-3 text-xs font-medium text-white transition-colors hover:bg-background/80"
            >
              <RefreshCw className="h-3 w-3" />
              Retry
            </button>
          ) : null}
        </div>
      )}

      {!isInitialLoading && !isError && selectedSessionMissing && sessions.length === 0 && (
        <div className="flex flex-col items-center justify-center rounded-xl border border-amber-400/20 bg-amber-400/[0.04] px-4 py-8 text-center">
          <AlertTriangle className="mb-2 h-8 w-8 text-amber-300" />
          <p className="text-sm font-medium text-white">Session list is out of sync</p>
          <p className="mt-1 max-w-xs text-xs leading-5 text-muted">The runtime returned a selected Session, but it is not present in the current environment list.</p>
          {onRetry ? (
            <button
              type="button"
              onClick={onRetry}
              className="mt-4 inline-flex h-8 items-center gap-1.5 rounded-lg border border-border/80 bg-background/55 px-3 text-xs font-medium text-white transition-colors hover:bg-background/80"
            >
              <RefreshCw className="h-3 w-3" />
              Refresh Sessions
            </button>
          ) : null}
        </div>
      )}

      {!isInitialLoading && !isError && !currentSessionId && sessions.length === 0 && (
        <div className="flex flex-col items-center justify-center rounded-xl border border-border/80 bg-background/45 px-4 py-8 text-center">
          <MessageSquare className="mb-2 h-8 w-8 text-muted" />
          <p className="text-sm text-muted">No sessions yet</p>
          <p className="mt-1 text-xs text-muted">{newSessionsDisabled ? 'Persistent Sessions cannot be created in the current runtime state.' : 'Create a Session or execute this stateful Agent.'}</p>
          {!newSessionsDisabled ? (
            <button
              type="button"
              onClick={() => void onNewSession()}
              disabled={isCreatingSession}
              className="mt-4 inline-flex h-8 items-center gap-1.5 rounded-lg border border-primary/30 bg-primary/10 px-3 text-xs font-medium text-primary-light transition-colors hover:border-primary/50 hover:bg-primary/15 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {isCreatingSession ? <Loader2 className="h-3 w-3 animate-spin" /> : <Plus className="h-3 w-3" />}
              New Session
            </button>
          ) : null}
        </div>
      )}

      {sessions.length > 0 && (
        <div className="space-y-1.5">
          {selectedSessionMissing && !isError ? (
            <div className="mb-2 flex items-start gap-2 rounded-xl border border-amber-400/20 bg-amber-400/[0.04] p-3 text-xs leading-5 text-muted">
              <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0 text-amber-300" />
              <p>The selected Session is not present in the loaded Sessions page. Refresh the list before continuing it.</p>
            </div>
          ) : null}
          {sessions.map((session) => {
            const isCurrent = session.id === currentSessionId
            const openedVersion = session.opened_release_version
            const source = formatSource(session)
            return (
              <button
                type="button"
                key={session.id}
                onClick={() => onSelectSession(session.id)}
                disabled={runtimeBusy}
                title={runtimeBusy ? disabledReason : undefined}
                className={cn(
                  'w-full rounded-xl border p-3 text-left shadow-sm shadow-black/5 transition-colors disabled:cursor-not-allowed disabled:opacity-60',
                  isCurrent
                    ? 'border-primary/35 bg-primary/10'
                    : 'border-border/80 bg-background/45 hover:border-primary/25 hover:bg-background/70',
                )}
              >
                <div className="flex items-center justify-between gap-2">
                  <div className="flex min-w-0 items-center gap-2">
                    <Circle
                      className={cn(
                        'h-2 w-2 shrink-0 fill-current',
                        isCurrent ? 'text-primary-light' : 'text-muted',
                      )}
                    />
                    <span className={cn('truncate text-xs', isCurrent ? 'font-medium text-white' : 'text-muted')}>
                      {session.id.slice(0, 8)}...
                    </span>
                  </div>
                  {isCurrent ? <span className="text-[10px] font-medium uppercase text-primary-light">Selected</span> : null}
                </div>
                {openedVersion ? <p className="mt-1 font-mono text-[10px] text-indigo-300">Opened · {openedVersion}</p> : null}
                <div className="mt-1.5 flex items-center gap-3 text-[11px] text-muted">
                  <span className="flex items-center gap-1">
                    <Clock className="h-3 w-3" />
                    {formatDate(session.last_message_at || session.created_at)}
                  </span>
                  <span>{session.message_count ?? 0} msgs</span>
                  {source ? <span>{source}</span> : null}
                </div>
              </button>
            )
          })}

          <div ref={sentinelRef} className="h-1" />

          {isLoadingMore && (
            <div className="flex items-center justify-center gap-2 py-3 text-xs text-muted">
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
              Loading more sessions...
            </div>
          )}
        </div>
      )}
    </div>
  )
}