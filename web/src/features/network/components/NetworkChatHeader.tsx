import { AlertTriangle, Lock, Network, PencilLine } from 'lucide-react'

import type { Environment, NetworkBinding } from './networkWorkspaceTypes'
import { networkLabel } from './networkChatExecution'
import type { NetworkSession } from './networkSessionTypes'
import { NetworkSessionSelector } from './NetworkSessionSelector'

interface NetworkChatHeaderProps {
  environment: Environment
  counts: Record<NetworkBinding['source'], number>
  sessions: NetworkSession[]
  activeSessionId: string | null
  changed: boolean
  pinned: boolean
  onSelectSession: (sessionId: string) => void
  onNew: () => void
  onPin: () => void
}

export function NetworkChatHeader({
  environment,
  counts,
  sessions,
  activeSessionId,
  changed,
  pinned,
  onSelectSession,
  onNew,
  onPin,
}: NetworkChatHeaderProps) {
  const readOnly = environment !== 'draft'
  return (
    <div className="shrink-0 border-b border-border bg-surface/45 px-4 py-3">
      <div className="flex flex-wrap items-center gap-3">
        <div className="flex min-w-0 flex-1 items-center gap-2.5">
          <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl border border-primary/25 bg-primary/10">
            <Network className="h-4 w-4 text-primary-light" />
          </div>
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <p className="truncate text-[12px] font-semibold text-white">Network Chat</p>
              <span className="inline-flex items-center gap-1 rounded-md border border-border bg-background/55 px-1.5 py-0.5 text-[10px] text-muted">
                {readOnly ? <Lock className="h-3 w-3" /> : <PencilLine className="h-3 w-3" />}
                {readOnly ? 'Read-only composition' : 'Editable Draft'}
              </span>
            </div>
            <p className="mt-0.5 text-[10px] text-muted">{networkLabel(environment)} · {counts.draft} Draft · {counts.staging} Staging · {counts.release} Release</p>
          </div>
        </div>
        <NetworkSessionSelector sessions={sessions} activeSessionId={activeSessionId} onSelect={onSelectSession} onNew={onNew} />
      </div>

      {environment === 'draft' && counts.draft > 0 ? (
        <div className="mt-2 rounded-lg border border-blue-500/20 bg-blue-500/5 px-3 py-2 text-[10px] text-blue-100/80">
          Draft sessions can include Agent Draft contexts. Runtime Keys cannot execute this mutable composition.
        </div>
      ) : null}
      {changed && !pinned ? (
        <div className="mt-2 flex flex-wrap items-center gap-2 rounded-lg border border-amber-500/25 bg-amber-500/5 px-3 py-2">
          <AlertTriangle className="h-3.5 w-3.5 shrink-0 text-amber-400" />
          <div className="min-w-0 flex-1">
            <p className="text-[10px] font-medium text-amber-100">Draft changed after this session started</p>
            <p className="text-[9px] text-amber-100/65">Continue with the pinned snapshot or start a session with the current Draft.</p>
          </div>
          <button type="button" onClick={onPin} className="text-[10px] text-amber-200 hover:text-white">Continue pinned</button>
          <button type="button" onClick={onNew} className="rounded-md bg-primary px-2.5 py-1.5 text-[10px] font-medium text-white">Start new session</button>
        </div>
      ) : null}
      {pinned ? <p className="mt-2 text-[9px] text-muted">This Network Session remains pinned to its original composition and Agent contexts.</p> : null}
    </div>
  )
}
