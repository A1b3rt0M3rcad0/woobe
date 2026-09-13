import { useMemo, useState } from 'react'
import { Circle, Clock, Loader2, MessageSquare, RotateCcw } from 'lucide-react'
import { toast } from 'sonner'
import { Button, EmptyStatePanel } from '@woobe/ui'

import { ScrollArea } from '@/components/ui/ScrollArea'
import { resetNetworkSessionContext } from '@/features/network/api'
import { cn } from '@/lib/utils'

import type { NetworkSession } from './networkSessionTypes'

function formatDate(value: string | null) {
  if (!value) return 'No messages yet'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return 'Unknown time'
  return date.toLocaleDateString(undefined, {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

export function NetworkSessionsPanel({
  sessions,
  activeSessionId,
  currentVersionId,
  loading = false,
  onSelectSession,
}: {
  sessions: NetworkSession[]
  activeSessionId: string | null
  currentVersionId: string | null
  loading?: boolean
  onSelectSession: (sessionId: string) => void
}) {
  const [resettingContext, setResettingContext] = useState(false)
  const activeSession = useMemo(
    () => sessions.find((session) => session.id === activeSessionId) ?? null,
    [activeSessionId, sessions],
  )
  const activeSessionIsEarlierSnapshot = Boolean(
    activeSession
      && activeSession.environment !== 'draft'
      && currentVersionId
      && activeSession.networkVersion !== currentVersionId,
  )

  const resetContext = async () => {
    if (!activeSession || activeSessionIsEarlierSnapshot || resettingContext) return
    setResettingContext(true)
    try {
      await resetNetworkSessionContext(activeSession.networkId, activeSession.id, activeSession.projectId)
      toast.success('Agent contexts reset for this Network Session')
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Unable to reset Network context')
    } finally {
      setResettingContext(false)
    }
  }

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="shrink-0 border-b border-border/80 px-ui-md py-ui-md">
        <div className="flex items-start justify-between gap-ui-md">
          <div>
            <h3 className="font-mono text-system-heading font-semibold text-white">Sessions</h3>
            <p className="mt-ui-hairline font-sans text-product-caption text-muted-foreground">Conversation continuity for the active Network environment.</p>
          </div>
          {activeSession && !activeSessionIsEarlierSnapshot ? (
            <Button
              type="button"
              size="sm"
              variant="outline"
              onClick={() => { void resetContext() }}
              disabled={resettingContext}
              title="Start fresh Agent contexts in the selected Network Session"
            >
              {resettingContext ? <Loader2 className="h-icon-sm w-icon-sm animate-spin" /> : <RotateCcw className="h-icon-sm w-icon-sm" />}
              Reset context
            </Button>
          ) : null}
        </div>
      </div>

      <ScrollArea className="min-h-0 flex-1">
        <div className="space-y-ui-sm p-ui-md">
          {loading && sessions.length === 0 ? (
            Array.from({ length: 5 }).map((_, index) => (
              <div key={index} className="rounded-container border border-border/70 bg-background/35 p-ui-md">
                <div className="h-3 w-32 animate-pulse rounded-full bg-white/[0.07]" />
                <div className="mt-ui-md h-2.5 w-24 animate-pulse rounded-full bg-white/[0.07]" />
                <div className="mt-ui-sm h-2.5 w-40 animate-pulse rounded-full bg-white/[0.07]" />
              </div>
            ))
          ) : null}

          {!loading && sessions.length === 0 ? (
            <EmptyStatePanel
              compact
              icon={<MessageSquare className="h-icon-lg w-icon-lg" />}
              title="No sessions yet"
              description="Use New Session in the left rail to start a Network conversation."
            />
          ) : null}

          {sessions.map((session) => {
            const selected = session.id === activeSessionId
            const earlierSnapshot = session.environment !== 'draft'
              && Boolean(currentVersionId)
              && session.networkVersion !== currentVersionId

            return (
              <button
                key={session.id}
                type="button"
                onClick={() => onSelectSession(session.id)}
                className={cn(
                  'w-full rounded-container border p-ui-md text-left transition-colors',
                  selected
                    ? 'border-primary/35 bg-primary/10'
                    : 'border-border/80 bg-background/45 hover:border-primary/25 hover:bg-background/70',
                )}
              >
                <div className="flex items-start justify-between gap-ui-md">
                  <div className="flex min-w-0 items-center gap-ui-sm">
                    <Circle className={cn('h-2 w-2 shrink-0 fill-current', selected ? 'text-primary-light' : 'text-muted-foreground')} />
                    <span className={cn('truncate font-sans text-product-small', selected ? 'font-medium text-white' : 'text-slate-200')}>{session.title}</span>
                  </div>
                  {selected ? <span className="shrink-0 font-mono text-system-meta font-medium uppercase text-primary-light">Selected</span> : null}
                </div>

                <div className="mt-ui-sm flex flex-wrap items-center gap-ui-sm font-mono text-system-meta text-muted-foreground">
                  <span className="text-indigo-300">{session.versionLabel}</span>
                  {earlierSnapshot ? <span className="rounded-technical border border-amber-400/25 bg-amber-400/5 px-ui-xs py-ui-hairline text-amber-300">Earlier snapshot</span> : null}
                </div>

                <div className="mt-ui-sm flex flex-wrap items-center gap-ui-md font-mono text-system-meta text-muted-foreground">
                  <span className="flex items-center gap-ui-xs"><Clock className="h-3 w-3" />{formatDate(session.lastMessageAt || session.createdAt)}</span>
                  <span>{session.messageCount} msgs</span>
                  <span>{session.traceCount} Runs</span>
                </div>
              </button>
            )
          })}
        </div>
      </ScrollArea>
    </div>
  )
}
