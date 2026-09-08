import { AlertTriangle, Lock, Network, PencilLine, RotateCcw } from 'lucide-react'

import type { Environment, NetworkBinding } from './networkWorkspaceTypes'
import { networkLabel } from './networkChatExecution'

interface NetworkChatHeaderProps {
  environment: Environment
  counts: Record<NetworkBinding['source'], number>
  activeSessionId: string | null
  versionLabel: string
  changed: boolean
  onNew: () => void
  onResetContext: () => void
}

export function NetworkChatHeader({ environment, counts, activeSessionId, versionLabel, changed, onNew, onResetContext }: NetworkChatHeaderProps) {
  const readOnly = environment !== 'draft'
  const immutableSnapshotChanged = environment !== 'draft' && changed
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
            <p className="mt-0.5 text-[10px] text-muted">{networkLabel(environment, versionLabel)} · {counts.draft} Draft · {counts.staging} Staging · {counts.release} Release</p>
          </div>
        </div>
        <button type="button" disabled={!activeSessionId} onClick={onResetContext} className="inline-flex items-center gap-1.5 rounded-lg border border-border px-2.5 py-1.5 text-[9px] text-muted hover:border-primary/30 hover:text-white disabled:cursor-not-allowed disabled:opacity-40" title={activeSessionId ? 'Start fresh Agent contexts in this Network Session' : 'Send the first message before resetting session context'}><RotateCcw className="h-3 w-3" />Reset context</button>
      </div>

      {immutableSnapshotChanged ? (
        <div className="mt-2 flex flex-wrap items-center gap-2 rounded-lg border border-amber-500/25 bg-amber-500/5 px-3 py-2">
          <AlertTriangle className="h-3.5 w-3.5 shrink-0 text-amber-400" />
          <div className="min-w-0 flex-1">
            <p className="text-[10px] font-medium text-amber-100">This session belongs to an earlier {environment} snapshot</p>
            <p className="text-[9px] text-amber-100/65">Its messages and traces remain available, but new messages require a session for {networkLabel(environment, versionLabel)}.</p>
          </div>
          <button type="button" onClick={onNew} className="rounded-md bg-primary px-2.5 py-1.5 text-[10px] font-medium text-white">Start current snapshot conversation</button>
        </div>
      ) : null}
      {environment === 'draft' && activeSessionId ? <p className="mt-2 text-[9px] text-muted">This session follows the saved Draft. Every execution records the exact Draft revision it used.</p> : null}
    </div>
  )
}
