import { AlertTriangle, Save } from 'lucide-react'

import type { Environment } from './networkWorkspaceTypes'

export function NetworkUnsavedChangesDialog({
  target,
  networkDirty,
  agentNames,
  pending,
  onClose,
  onConfirm,
}: {
  target: Environment
  networkDirty: boolean
  agentNames: string[]
  pending: boolean
  onClose: () => void
  onConfirm: () => void
}) {
  return (
    <div className="fixed inset-0 z-[65] flex items-center justify-center bg-black/75 p-4 backdrop-blur-sm">
      <div className="w-full max-w-lg overflow-hidden rounded-2xl border border-border/90 bg-surface shadow-2xl shadow-black/40">
        <div className="border-b border-border/90 p-5">
          <div className="flex items-start gap-3">
            <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0 text-amber-400" />
            <div>
              <h2 className="text-base font-semibold text-white">Save Draft changes?</h2>
              <p className="mt-1 text-xs leading-5 text-muted">Draft changes must be saved before opening {target}. The environment will only change after every required save succeeds.</p>
            </div>
          </div>
        </div>
        <div className="space-y-2 p-5">
          {networkDirty ? <div className="rounded-lg border border-border bg-background/35 px-3 py-2.5 text-[10px] text-slate-200">Network composition and settings</div> : null}
          {agentNames.map((name) => <div key={name} className="rounded-lg border border-border bg-background/35 px-3 py-2.5 text-[10px] text-slate-200">Agent Draft · {name}</div>)}
        </div>
        <div className="flex justify-end gap-2 border-t border-border/90 p-4">
          <button type="button" disabled={pending} onClick={onClose} className="rounded-lg border border-border px-3 py-2 text-[10px] font-medium text-muted hover:text-white disabled:opacity-45">Stay in Draft</button>
          <button type="button" disabled={pending} onClick={onConfirm} className="inline-flex items-center gap-2 rounded-lg bg-primary px-3 py-2 text-[10px] font-semibold text-white disabled:opacity-45"><Save className="h-3.5 w-3.5" />{pending ? 'Saving…' : `Save and open ${target}`}</button>
        </div>
      </div>
    </div>
  )
}
