import { useEffect, useRef } from 'react'
import { Button, EmptyStatePanel, TechnicalListItem } from '@woobe/ui'
import { CopyButton } from '@/components/common/CopyButton'
import { Activity, AlertTriangle, Braces, Circle, Clock, Loader2, MessageSquare, RefreshCw } from 'lucide-react'
import { cn } from '@/lib/utils'
import { useAgentStreamStopState } from '@/features/playground/stream-stop-state'
import type { SessionListItem } from '@/features/playground/types'
import { ContractValueForm } from '@/features/contracts/ContractValueForm'
import { contractFields } from '@/features/contracts/contractFields'

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
  sessionContextContract?: unknown
  sessionContextValues?: Record<string, unknown>
  onSessionContextValuesChange?: (values: Record<string, unknown>) => void
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
    <div className="rounded-container border border-border/70 bg-background/20 px-ui-md py-ui-sm">
      <div className="flex items-center justify-between gap-ui-sm">
        <div className="h-2.5 w-24 animate-pulse rounded-technical bg-white/[0.06]" />
        <div className="h-2 w-9 animate-pulse rounded-technical bg-white/[0.06]" />
      </div>
      <div className="mt-ui-sm h-2 w-32 animate-pulse rounded-technical bg-white/[0.06]" />
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
  sessionContextContract,
  sessionContextValues = {},
  onSessionContextValuesChange,
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
  const sessionContextFieldCount = Object.keys(contractFields(sessionContextContract)).length

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

  const retryAction = onRetry ? (
    <Button type="button" size="sm" variant="outline" onClick={onRetry}>
      <RefreshCw className="h-icon-sm w-icon-sm" />
      Retry
    </Button>
  ) : undefined

  return (
    <div className="space-y-ui-md p-ui-md">
      <div className="flex items-center justify-between gap-ui-md border-b border-border/70 pb-ui-sm">
        <div>
          <h3 className="font-mono text-system-control font-semibold text-slate-50">Sessions</h3>
          <p className="mt-ui-xs font-sans text-product-caption text-muted-foreground">Conversation continuity for this Agent runtime.</p>
        </div>
        <span className="font-mono text-system-meta text-muted-foreground">{sessions.length} loaded</span>
      </div>

      {disabledReason ? (
        <div className="flex gap-ui-sm rounded-container border border-border bg-background/25 px-ui-md py-ui-sm font-sans text-product-caption text-muted-foreground">
          <Activity className="mt-ui-hairline h-icon-sm w-icon-sm shrink-0 text-primary-light" />
          <p>{disabledReason}. Historical Sessions remain available for inspection.</p>
        </div>
      ) : null}

      {currentSessionId ? (
        <div className="rounded-container border border-border bg-background/25 px-ui-md py-ui-sm">
          <div className="mb-ui-xs flex items-center justify-between gap-ui-sm">
            <span className="font-mono text-system-meta uppercase tracking-[0.08em] text-muted-foreground">Selected session</span>
            <CopyButton text={currentSessionId} />
          </div>
          <code className="block truncate font-mono text-system-label text-slate-200" title={currentSessionId}>{currentSessionId}</code>

          {sessionContextFieldCount > 0 ? (
            <div className="mt-ui-sm border-t border-border/70 pt-ui-sm">
              <div className="mb-ui-sm flex items-start gap-ui-xs">
                <Braces className="mt-ui-hairline h-icon-sm w-icon-sm shrink-0 text-primary-light" />
                <div className="min-w-0">
                  <p className="font-mono text-system-control font-medium text-slate-100">Session Context</p>
                  <p className="mt-ui-hairline font-sans text-product-caption leading-4 text-muted-foreground">
                    Values apply to the selected Session. The next Run binds changes and the runtime reuses them across later Runs.
                  </p>
                </div>
              </div>
              <ContractValueForm
                contract={sessionContextContract}
                values={sessionContextValues}
                disabled={runtimeBusy}
                density="compact"
                onChange={onSessionContextValuesChange ?? (() => undefined)}
              />
            </div>
          ) : null}
        </div>
      ) : null}

      {isInitialLoading && sessions.length === 0 ? (
        <div className="space-y-ui-sm">{Array.from({ length: 6 }).map((_, index) => <SessionSkeleton key={index} />)}</div>
      ) : null}

      {!isInitialLoading && isError ? (
        <EmptyStatePanel
          icon={<AlertTriangle className="h-icon-lg w-icon-lg text-red-300" />}
          title="Couldn’t load Sessions"
          description={errorMessage || 'The Sessions list could not be loaded from the runtime.'}
          action={retryAction}
        />
      ) : null}

      {!isInitialLoading && !isError && selectedSessionMissing && sessions.length === 0 ? (
        <EmptyStatePanel
          icon={<AlertTriangle className="h-icon-lg w-icon-lg text-amber-300" />}
          title="Session list is out of sync"
          description="The runtime returned a selected Session that is not present in the loaded environment list."
          action={onRetry ? (
            <Button type="button" size="sm" variant="outline" onClick={onRetry}>
              <RefreshCw className="h-icon-sm w-icon-sm" />
              Refresh Sessions
            </Button>
          ) : undefined}
        />
      ) : null}

      {!isInitialLoading && !isError && !currentSessionId && sessions.length === 0 ? (
        <EmptyStatePanel
          icon={<MessageSquare className="h-icon-lg w-icon-lg" />}
          title="No Sessions yet"
          description={sessionMode === 'stateless' ? 'This Agent runtime is stateless and does not create persistent Sessions.' : 'Use New Session in the operations rail to start a conversation.'}
        />
      ) : null}

      {sessions.length > 0 ? (
        <div className="space-y-ui-sm">
          {selectedSessionMissing && !isError ? (
            <div className="flex items-start gap-ui-sm rounded-container border border-amber-400/20 bg-background/25 px-ui-md py-ui-sm font-sans text-product-caption text-muted-foreground">
              <AlertTriangle className="mt-ui-hairline h-icon-sm w-icon-sm shrink-0 text-amber-300" />
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
                label={session.id.slice(0, 8) + '…'}
                description={openedVersion ? `Opened · ${openedVersion}` : undefined}
                leading={<Circle className={cn('h-2 w-2 fill-current', isCurrent ? 'text-primary-light' : 'text-muted-foreground')} />}
                trailing={isCurrent ? <span className="font-mono text-system-meta uppercase text-primary-light">Selected</span> : undefined}
                meta={
                  <>
                    <span className="inline-flex items-center gap-ui-xs"><Clock className="h-icon-sm w-icon-sm" />{formatDate(session.last_message_at || session.created_at)}</span>
                    <span>{session.message_count ?? 0} msgs</span>
                    {source ? <span>{source}</span> : null}
                  </>
                }
                title={runtimeBusy ? disabledReason : undefined}
              />
            )
          })}

          <div ref={sentinelRef} className="h-ui-xs" />
          {isLoadingMore ? <div className="flex items-center justify-center gap-ui-sm py-ui-md font-mono text-system-meta text-muted-foreground"><Loader2 className="h-icon-sm w-icon-sm animate-spin" />Loading more Sessions…</div> : null}
        </div>
      ) : null}
    </div>
  )
}
