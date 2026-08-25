import { useEffect, useRef, useState } from 'react'
import { Check, ChevronDown } from 'lucide-react'

import { ScrollArea } from '@/components/ui/ScrollArea'
import { cn } from '@/lib/utils'

import type { NetworkSession } from './networkSessionTypes'

function relativeTime(value: string | null) {
  if (!value) return 'No messages yet'
  const minutes = Math.max(1, Math.round((Date.now() - new Date(value).getTime()) / 60_000))
  if (minutes < 60) return `${minutes}m ago`
  const hours = Math.round(minutes / 60)
  if (hours < 24) return `${hours}h ago`
  return `${Math.round(hours / 24)}d ago`
}

function environmentLabel(session: NetworkSession) {
  if (session.environment === 'draft') return session.versionLabel || 'Draft'
  if (session.environment === 'staging') return session.versionLabel || 'Staging'
  return session.versionLabel || 'Production'
}

export function NetworkSessionSelector({
  sessions,
  activeSessionId,
  onSelect,
}: {
  sessions: NetworkSession[]
  activeSessionId: string | null
  onSelect: (sessionId: string) => void
}) {
  const [open, setOpen] = useState(false)
  const containerRef = useRef<HTMLDivElement | null>(null)
  const active = sessions.find((session) => session.id === activeSessionId) ?? null

  useEffect(() => {
    if (!open) return
    const close = (event: PointerEvent) => {
      if (!containerRef.current?.contains(event.target as Node)) setOpen(false)
    }
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setOpen(false)
    }
    document.addEventListener('pointerdown', close)
    document.addEventListener('keydown', closeOnEscape)
    return () => {
      document.removeEventListener('pointerdown', close)
      document.removeEventListener('keydown', closeOnEscape)
    }
  }, [open])

  return (
    <div ref={containerRef} className="relative">
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        className="flex h-9 min-w-[220px] max-w-[340px] items-center gap-2 rounded-lg border border-border bg-background/55 px-3 text-left transition-colors hover:border-primary/30"
        aria-haspopup="listbox"
        aria-expanded={open}
      >
        <div className="min-w-0 flex-1">
          <p className="truncate text-[11px] font-medium text-white">{active?.title ?? 'New conversation'}</p>
          <p className="mt-0.5 truncate text-[9px] text-muted">
            {active ? `${environmentLabel(active)} · ${active.messageCount} messages · ${active.traceCount} Runs` : 'Session created on the first message'}
          </p>
        </div>
        <ChevronDown className={cn('h-3.5 w-3.5 shrink-0 text-muted transition-transform', open && 'rotate-180')} />
      </button>

      {open ? (
        <div className="absolute right-0 top-11 z-40 w-[360px] max-w-[min(90vw,360px)] overflow-hidden rounded-xl border border-border bg-surface shadow-2xl shadow-black/35">
          <div className="border-b border-border/80 px-3 py-2.5">
            <p className="text-[11px] font-semibold text-white">Network Sessions</p>
            <p className="mt-0.5 text-[9px] text-muted">Select a previous session from the active environment.</p>
          </div>
          <ScrollArea className="max-h-72 p-2">
            <div className="space-y-1">
              {sessions.length ? sessions.map((session) => {
                const selected = session.id === activeSessionId
                return (
                  <button
                    key={session.id}
                    type="button"
                    onClick={() => { onSelect(session.id); setOpen(false) }}
                    role="option"
                    aria-selected={selected}
                    className={cn(
                      'flex w-full items-start gap-2 rounded-lg border px-3 py-2.5 text-left transition-colors',
                      selected ? 'border-primary/30 bg-primary/10' : 'border-transparent hover:border-border hover:bg-background/55',
                    )}
                  >
                    <div className="min-w-0 flex-1">
                      <p className={cn('truncate text-[11px] font-medium', selected ? 'text-white' : 'text-slate-200')}>{session.title}</p>
                      <p className="mt-1 truncate text-[9px] text-muted">{environmentLabel(session)}</p>
                      <p className="mt-0.5 text-[9px] text-muted">{session.messageCount} messages · {session.traceCount} Runs · {relativeTime(session.lastMessageAt)}</p>
                    </div>
                    {selected ? <Check className="mt-0.5 h-3.5 w-3.5 shrink-0 text-primary-light" /> : null}
                  </button>
                )
              }) : (
                <div className="p-6 text-center">
                  <p className="text-[11px] text-muted">No previous sessions in this environment.</p>
                </div>
              )}
            </div>
          </ScrollArea>
        </div>
      ) : null}
    </div>
  )
}
