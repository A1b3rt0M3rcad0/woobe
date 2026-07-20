import { X } from 'lucide-react'

import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
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
}

export function ReleaseSnapshotModal({
  open,
  title,
  description,
  release,
  confirmLabel,
  isConfirming,
  onConfirm,
  onClose,
  releaseDescription,
  onReleaseDescriptionChange,
}: ReleaseSnapshotModalProps) {
  if (!open || !release) return null
  const canEditDescription = Boolean(onConfirm && onReleaseDescriptionChange)

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4 backdrop-blur-md">
      <div className="flex max-h-[88vh] w-full max-w-4xl flex-col overflow-hidden rounded-2xl border border-border/90 bg-surface/95 shadow-2xl shadow-black/40">
        <div className="flex items-start justify-between gap-4 border-b border-border/90 bg-background/20 p-5">
          <div className="space-y-1">
            <div className="flex flex-wrap items-center gap-2">
              <h2 className="text-base font-semibold text-white">{title}</h2>
              <Badge variant="secondary">{release.version}</Badge>
            </div>
            {description ? <p className="text-xs leading-5 text-muted">{description}</p> : null}
          </div>
          <button className="rounded-lg border border-transparent p-1 text-muted transition-colors hover:border-border/80 hover:bg-background/60 hover:text-white" onClick={onClose} aria-label="Close">
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="min-h-0 flex-1 space-y-5 overflow-y-auto p-5">
          {canEditDescription ? (
            <section className="space-y-2 rounded-xl border border-border/80 bg-background/35 p-4">
              <p className="text-xs font-semibold uppercase tracking-wide text-slate-300">Release description</p>
              <p className="text-[11px] leading-5 text-muted">Describe the operational change this Release introduces.</p>
              <Textarea
                value={releaseDescription ?? ''}
                onChange={(event) => onReleaseDescriptionChange?.(event.target.value)}
                placeholder="Describe what changed in this Release."
                className="min-h-24 text-sm"
              />
            </section>
          ) : null}
          <ReleaseDetailsView release={release} />
        </div>

        <div className="flex items-center justify-end gap-2 border-t border-border/90 bg-background/20 p-4">
          <Button size="sm" variant="outline" onClick={onClose}>Close</Button>
          {onConfirm && confirmLabel ? (
            <Button size="sm" onClick={onConfirm} loading={isConfirming}>{confirmLabel}</Button>
          ) : null}
        </div>
      </div>
    </div>
  )
}
