import { useMemo, useState } from 'react'
import { History, RotateCcw, X } from 'lucide-react'

import { dialogTypographyClass } from '@/components/ui/Dialog'
import type { NetworkVersion } from '../types'
import { cn } from '@/lib/utils'

export function NetworkRollbackDialog({
  versions,
  currentVersionId,
  pending,
  onClose,
  onConfirm,
}: {
  versions: NetworkVersion[]
  currentVersionId: string | null
  pending: boolean
  onClose: () => void
  onConfirm: (versionId: string) => void
}) {
  const candidates = useMemo(
    () => versions.filter((version) => version.kind === 'release' && version.id !== currentVersionId),
    [currentVersionId, versions],
  )
  const [selectedId, setSelectedId] = useState(candidates[0]?.id ?? '')

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 p-4 backdrop-blur-sm">
      <div role="dialog" aria-modal="true" aria-label="Select a historical Network release" className={`${dialogTypographyClass} flex max-h-[86vh] w-full max-w-xl flex-col overflow-hidden rounded-2xl border border-border bg-surface shadow-2xl`}>
        <header className="flex items-start gap-3 border-b border-border p-5">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl border border-amber-500/25 bg-amber-500/10 text-amber-300"><History className="h-4 w-4" /></div>
          <div className="min-w-0 flex-1">
            <p className="text-[9px] font-semibold uppercase tracking-widest text-amber-300">Production rollback</p>
            <h2 className="mt-1 text-base font-semibold text-white">Select a historical Network release</h2>
            <p className="mt-1 text-[10px] leading-4 text-muted">Rollback creates a new immutable Production version using the exact Network definition and Agent release IDs stored in the selected release.</p>
          </div>
          <button type="button" onClick={onClose} className="rounded-lg border border-border p-2 text-muted hover:text-white"><X className="h-4 w-4" /></button>
        </header>
        <div className="min-h-0 flex-1 space-y-2 overflow-y-auto p-5">
          {candidates.map((version) => (
            <button
              key={version.id}
              type="button"
              onClick={() => setSelectedId(version.id)}
              className={cn(
                'w-full rounded-xl border p-3 text-left',
                selectedId === version.id
                  ? 'border-primary/45 bg-primary/10'
                  : 'border-border bg-background/35 hover:border-primary/25',
              )}
            >
              <div className="flex items-center gap-3">
                <div className="min-w-0 flex-1">
                  <p className="text-[11px] font-medium text-white">{version.version}</p>
                  <p className="mt-1 font-mono text-[9px] text-muted">{version.composition_hash}</p>
                </div>
                <span className="text-[9px] text-muted">{new Date(version.created_at).toLocaleString()}</span>
              </div>
            </button>
          ))}
          {!candidates.length ? <div className="rounded-xl border border-border bg-background/35 p-6 text-center text-[10px] text-muted">No previous Production release is available.</div> : null}
        </div>
        <footer className="flex justify-end gap-2 border-t border-border p-4">
          <button type="button" onClick={onClose} className="rounded-lg border border-border px-3 py-2 text-[10px] text-muted hover:text-white">Cancel</button>
          <button type="button" disabled={!selectedId || pending} onClick={() => onConfirm(selectedId)} className="inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-[10px] font-semibold text-white disabled:cursor-not-allowed disabled:opacity-45"><RotateCcw className="h-3.5 w-3.5" />{pending ? 'Rolling back…' : 'Create rollback release'}</button>
        </footer>
      </div>
    </div>
  )
}
