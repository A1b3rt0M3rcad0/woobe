import { useEffect, useRef } from 'react'
import { CopyButton } from '@/components/common/CopyButton'
import { Separator } from '@/components/ui/Separator'
import { Clock, MessageSquare, Circle, Plus, Loader2, Activity } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { SessionListItem } from '@/features/playground/types'

interface SessionsPanelProps {
  sessions: SessionListItem[]
  currentSessionId: string | null
  sessionMode: 'stateful' | 'stateless'
  onNewSession: () => void | Promise<void>
  onSelectSession: (id: string) => void
  onLoadMoreSessions?: () => void
  hasMoreSessions?: boolean
  isInitialLoading?: boolean
  isLoadingMore?: boolean
  isCreatingSession?: boolean
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
  onNewSession,
  onSelectSession,
  onLoadMoreSessions,
  hasMoreSessions = false,
  isInitialLoading = false,
  isLoadingMore = false,
  isCreatingSession = false,
}: SessionsPanelProps) {
  const sentinelRef = useRef<HTMLDivElement | null>(null)
  const isStateless = sessionMode === 'stateless'

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
          disabled={isCreatingSession || isStateless}
          title={isStateless ? 'Stateless agents do not create sessions' : undefined}
          className="inline-flex h-7 items-center gap-1.5 rounded-lg border border-primary/30 bg-primary/10 px-2.5 text-[11px] font-medium text-primary-light transition-colors hover:border-primary/50 hover:bg-primary/15 disabled:cursor-not-allowed disabled:opacity-60"
        >
          {isCreatingSession ? <Loader2 className="h-3 w-3 animate-spin" /> : <Plus className="h-3 w-3" />}
          New
        </button>
      </div>

      {isStateless && (
        <div className="flex gap-2 rounded-xl border border-border/80 bg-background/45 p-3 text-xs leading-5 text-muted">
          <Activity className="mt-0.5 h-3.5 w-3.5 shrink-0" />
          <p>This agent is stateless. New conversations are not persisted as sessions.</p>
        </div>
      )}

      {currentSessionId && !isStateless && (
        <>
          <div>
            <p className="mb-1 text-xs font-medium text-muted">Current Session ID</p>
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

      {!isInitialLoading && sessions.length === 0 && !isStateless && (
        <div className="flex flex-col items-center justify-center rounded-xl border border-border/80 bg-background/45 px-4 py-8 text-center">
          <MessageSquare className="mb-2 h-8 w-8 text-muted" />
          <p className="text-sm text-muted">No sessions yet</p>
          <p className="mt-1 text-xs text-muted">Create a session to test this agent.</p>
          <button
            type="button"
            onClick={() => void onNewSession()}
            disabled={isCreatingSession}
            className="mt-4 inline-flex h-8 items-center gap-1.5 rounded-lg border border-primary/30 bg-primary/10 px-3 text-xs font-medium text-primary-light transition-colors hover:border-primary/50 hover:bg-primary/15 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {isCreatingSession ? <Loader2 className="h-3 w-3 animate-spin" /> : <Plus className="h-3 w-3" />}
            New Session
          </button>
        </div>
      )}

      {sessions.length > 0 && (
        <div className="space-y-1.5">
          {sessions.map((s) => {
            const isCurrent = !isStateless && s.id === currentSessionId
            return (
              <button
                key={s.id}
                onClick={() => onSelectSession(s.id)}
                disabled={isStateless}
                className={cn(
                  'w-full rounded-xl border p-3 text-left shadow-sm shadow-black/5 transition-colors disabled:cursor-not-allowed disabled:opacity-70',
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
                      {s.id.slice(0, 8)}...
                    </span>
                  </div>
                  {isCurrent && (
                    <span className="text-[10px] font-medium uppercase text-primary-light">Active</span>
                  )}
                </div>
                <div className="mt-1.5 flex items-center gap-3 text-[11px] text-muted">
                  <span className="flex items-center gap-1">
                    <Clock className="h-3 w-3" />
                    {formatDate(s.last_message_at || s.created_at)}
                  </span>
                  <span>{s.message_count ?? 0} msgs</span>
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
