import { AlertTriangle, Network, RotateCcw } from 'lucide-react'

import type { ChatTarget, NetworkBinding } from './networkWorkspaceTypes'
import { networkLabel } from './networkChatExecution'

interface NetworkChatHeaderProps {
  target: ChatTarget
  counts: Record<NetworkBinding['source'], number>
  changed: boolean
  pinned: boolean
  onTarget: (target: ChatTarget) => void
  onNew: () => void
  onPin: () => void
}

export function NetworkChatHeader({ target, counts, changed, pinned, onTarget, onNew, onPin }: NetworkChatHeaderProps) {
  return (
    <div className="shrink-0 border-b border-border bg-surface/45 px-4 py-3">
      <div className="flex flex-wrap items-center gap-3">
        <div className="flex min-w-0 flex-1 items-center gap-2.5">
          <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-xl border border-primary/25 bg-primary/10">
            <Network className="h-4 w-4 text-primary-light" />
          </div>
          <div className="min-w-0">
            <p className="truncate text-[11px] font-semibold text-white">Network Chat · {networkLabel(target)}</p>
            <p className="mt-0.5 text-[9px] text-muted">{counts.draft} Draft · {counts.staging} Staging · {counts.release} Release</p>
          </div>
        </div>
        <button type="button" onClick={onNew} className="flex h-8 items-center gap-1.5 rounded-lg border border-border bg-background/45 px-2.5 text-[9px] text-muted hover:text-white">
          <RotateCcw className="h-3.5 w-3.5" />
          New
        </button>
        <select value={target} onChange={(event) => onTarget(event.target.value as ChatTarget)} className="h-8 rounded-lg border border-border bg-background/70 px-2.5 text-[9px] text-white outline-none focus:border-primary/40">
          <option value="draft">Draft · working composition</option>
          <option value="staging">Staging · v0.12</option>
          <option value="production">Production · v0.10</option>
          <option value="history">Historical Release · v0.8</option>
        </select>
      </div>

      {target === 'draft' && counts.draft > 0 ? (
        <div className="mt-2 rounded-lg border border-blue-500/20 bg-blue-500/5 px-3 py-2 text-[9px] text-blue-100/80">
          Draft Chat can include unsaved Agent overrides and is unavailable through Runtime Keys.
        </div>
      ) : null}
      {changed && !pinned ? (
        <div className="mt-2 flex flex-wrap items-center gap-2 rounded-lg border border-amber-500/25 bg-amber-500/5 px-3 py-2">
          <AlertTriangle className="h-3.5 w-3.5 shrink-0 text-amber-400" />
          <div className="min-w-0 flex-1">
            <p className="text-[9px] font-medium text-amber-100">Composition changed during this session</p>
            <p className="text-[8px] text-amber-100/65">Keep the pinned snapshot or start a clean session.</p>
          </div>
          <button type="button" onClick={onPin} className="text-[9px] text-amber-200 hover:text-white">Keep previous</button>
          <button type="button" onClick={onNew} className="rounded-md bg-primary px-2 py-1 text-[9px] font-medium text-white">Start new</button>
        </div>
      ) : null}
      {pinned ? <p className="mt-2 text-[8px] text-muted">This session remains pinned to its previous composition.</p> : null}
    </div>
  )
}
