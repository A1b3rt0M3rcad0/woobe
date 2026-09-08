import { Circle, Clock, MessageSquare } from 'lucide-react'

import { ScrollArea } from '@/components/ui/ScrollArea'
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
  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="shrink-0 border-b border-border/80 px-4 py-3">
        <h3 className="text-sm font-semibold text-white">Sessions</h3>
        <p className="mt-0.5 text-[10px] text-muted">Conversation continuity for the active Network environment.</p>
      </div>

      <ScrollArea className="min-h-0 flex-1">
        <div className="space-y-1.5 p-4">
          {loading && sessions.length === 0 ? (
            Array.from({ length: 5 }).map((_, index) => (
              <div key={index} className="rounded-xl border border-border/70 bg-background/35 p-3">
                <div className="h-3 w-32 animate-pulse rounded-full bg-white/[0.07]" />
                <div className="mt-3 h-2.5 w-24 animate-pulse rounded-full bg-white/[0.07]" />
                <div className="mt-2 h-2.5 w-40 animate-pulse rounded-full bg-white/[0.07]" />
              </div>
            ))
          ) : null}

          {!loading && sessions.length === 0 ? (
            <div className="flex flex-col items-center justify-center rounded-xl border border-border/80 bg-background/45 px-4 py-8 text-center">
              <MessageSquare className="mb-2 h-8 w-8 text-muted" />
              <p className="text-sm text-muted">No sessions yet</p>
              <p className="mt-1 text-xs text-muted">Use New Session in the left rail to start a Network conversation.</p>
            </div>
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
                  'w-full rounded-xl border p-3 text-left shadow-sm shadow-black/5 transition-colors',
                  selected
                    ? 'border-primary/35 bg-primary/10'
                    : 'border-border/80 bg-background/45 hover:border-primary/25 hover:bg-background/70',
                )}
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="flex min-w-0 items-center gap-2">
                    <Circle className={cn('h-2 w-2 shrink-0 fill-current', selected ? 'text-primary-light' : 'text-muted')} />
                    <span className={cn('truncate text-xs', selected ? 'font-medium text-white' : 'text-slate-200')}>{session.title}</span>
                  </div>
                  {selected ? <span className="shrink-0 text-[9px] font-medium uppercase text-primary-light">Selected</span> : null}
                </div>

                <div className="mt-1.5 flex flex-wrap items-center gap-2 text-[10px] text-muted">
                  <span className="font-mono text-indigo-300">{session.versionLabel}</span>
                  {earlierSnapshot ? <span className="rounded border border-amber-400/25 bg-amber-400/5 px-1.5 py-0.5 text-amber-300">Earlier snapshot</span> : null}
                </div>

                <div className="mt-2 flex flex-wrap items-center gap-3 text-[10px] text-muted">
                  <span className="flex items-center gap-1"><Clock className="h-3 w-3" />{formatDate(session.lastMessageAt || session.createdAt)}</span>
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
