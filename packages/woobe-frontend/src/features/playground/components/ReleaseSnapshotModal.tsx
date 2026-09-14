import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { Dialog } from '@/components/ui/Dialog'
import { Textarea } from '@/components/ui/Textarea'
import type { AgentRelease } from '@/features/agents/types'
import { ReleaseDetailsView } from './ReleaseDetailsView'

type ReleaseSnapshotModalProps = {
  open: boolean
  title: string
  description?: string
  release: AgentRelease | null
  confirmLabel?: string
  isConfirming?: boolean
  onConfirm?: () => void
  onClose: () => void
  releaseDescription?: string
  onReleaseDescriptionChange?: (value: string) => void
  requireReleaseDescription?: boolean
}

export function ReleaseSnapshotModal({ open, title, description, release, confirmLabel, isConfirming, onConfirm, onClose, releaseDescription, onReleaseDescriptionChange, requireReleaseDescription = false }: ReleaseSnapshotModalProps) {
  if (!release) return null
  const canEditDescription = Boolean(onConfirm && onReleaseDescriptionChange)
  const descriptionValid = !requireReleaseDescription || (releaseDescription?.trim().length ?? 0) >= 3

  return <Dialog open={open} onClose={onClose} title={title} className="flex h-[min(760px,calc(100svh-2rem))] max-w-4xl flex-col overflow-hidden" contentClassName="min-h-0 flex-1 p-0">
    <div className="flex h-full min-h-0 flex-col">
      <div className="flex min-h-[42px] shrink-0 items-center gap-2 border-b border-border bg-background/20 px-4 py-2.5"><Badge variant="secondary">{release.version}</Badge>{description ? <p className="font-sans text-[9px] leading-4 text-muted-foreground">{description}</p> : null}</div>
      <div className="scrollbar-thin min-h-0 flex-1 space-y-4 overflow-y-auto p-4">
        {canEditDescription ? <section className="rounded-container border border-border bg-background/25 p-3"><p className="font-mono text-[8px] font-semibold uppercase tracking-[0.1em] text-slate-300">Release description</p><p className="mt-1 font-sans text-[9px] leading-4 text-muted-foreground">Describe the operational change this immutable Release introduces.</p><Textarea value={releaseDescription ?? ''} onChange={(event) => onReleaseDescriptionChange?.(event.target.value)} placeholder="Describe what changed in this Release." className="mt-3 min-h-24 font-sans text-[10px]" />{requireReleaseDescription && !descriptionValid ? <p className="mt-2 font-sans text-[8px] text-amber-300">A release description with at least 3 characters is required.</p> : null}</section> : null}
        <ReleaseDetailsView release={release} />
      </div>
      <div className="flex min-h-[56px] shrink-0 items-center justify-end gap-2 border-t border-border bg-surface/[0.98] px-4 py-3"><Button size="sm" variant="outline" onClick={onClose}>Close</Button>{onConfirm && confirmLabel ? <Button size="sm" onClick={onConfirm} loading={isConfirming} disabled={!descriptionValid}>{confirmLabel}</Button> : null}</div>
    </div>
  </Dialog>
}
