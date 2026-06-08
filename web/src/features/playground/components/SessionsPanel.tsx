import { CopyButton } from '@/components/common/CopyButton'
import { Button } from '@/components/ui/Button'
import { Separator } from '@/components/ui/Separator'
import { Plus, Clock, MessageSquare, Circle } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { SessionListItem } from '@/features/playground/types'

interface SessionsPanelProps {
  sessions: SessionListItem[]
  currentSessionId: string | null
  onNewSession: () => void
  onSelectSession: (id: string) => void
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

export function SessionsPanel({ sessions, currentSessionId, onNewSession, onSelectSession }: SessionsPanelProps) {
  return (
    <div className="p-4 space-y-3">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-medium text-white">Sessions</h3>
        <Button size="sm" variant="outline" onClick={onNewSession}>
          <Plus className="mr-1 h-3.5 w-3.5" />
          New
        </Button>
      </div>

      {sessions.length === 0 && (
        <div className="flex flex-col items-center justify-center py-8 text-center">
          <MessageSquare className="h-8 w-8 text-muted mb-2" />
          <p className="text-sm text-muted">No sessions yet</p>
          <p className="text-xs text-muted mt-1">Send a message to start a new session.</p>
        </div>
      )}

      <div className="space-y-1">
        {sessions.map((s) => {
          const isCurrent = s.id === currentSessionId
          return (
            <button
              key={s.id}
              onClick={() => onSelectSession(s.id)}
              className={cn(
                'w-full text-left rounded-lg border p-3 transition-colors',
                isCurrent
                  ? 'border-primary/30 bg-primary/5'
                  : 'border-border bg-background hover:border-primary/20',
              )}
            >
              <div className="flex items-center justify-between gap-2">
                <div className="flex items-center gap-2 min-w-0">
                  <Circle
                    className={cn(
                      'h-2 w-2 shrink-0 fill-current',
                      isCurrent ? 'text-primary' : 'text-muted',
                    )}
                  />
                  <span className={cn('text-xs truncate', isCurrent ? 'text-white font-medium' : 'text-muted')}>
                    {s.id.slice(0, 8)}...
                  </span>
                </div>
                {isCurrent && (
                  <span className="text-[10px] font-medium text-primary uppercase">Active</span>
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
      </div>

      {currentSessionId && (
        <>
          <Separator />
          <div>
            <p className="text-xs font-medium text-muted mb-1">Current Session ID</p>
            <div className="flex items-center gap-2 rounded-lg border border-border bg-background p-2">
              <code className="text-xs flex-1 break-all">{currentSessionId}</code>
              <CopyButton text={currentSessionId} />
            </div>
          </div>
        </>
      )}
    </div>
  )
}
