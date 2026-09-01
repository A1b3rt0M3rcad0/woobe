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
  requireReleaseDescription = false,
}: ReleaseSnapshotModalProps) {
  if (!release) return null
  const canEditDescription = Boolean(onConfirm && onReleaseDescriptionChange)
  const descriptionValid = !requireReleaseDescription || (releaseDescription?.trim().length ?? 0) >= 3

  return (
    <Dialog
      open={open}
      onClose={onClose}
      title={title}
      className="max-w-4xl"
      contentClassName="p-0"
      scrollMode="content"
    >
      <div className="flex min-h-0 flex-1 flex-col">
        <div className="shrink-0 border-b border-border/90 bg-background/20 px-5 py-3">
          <div className="flex flex-wrap items-center gap-2">
            <Badge variant="secondary">{release.version}</Badge>
            {description ? <p className="text-xs leading-5 text-muted">{description}</p> : null}
          </div>
        </div>

        <div className="min-h-0 flex-1 space-y-5 overflow-y-auto p-5">
          {canEditDescription ? (
            <section className="space-y-2 rounded-xl border border-border/80 bg-background/35 p-4">
              <p className="text-xs font-semibold uppercase tracking-wide text-slate-300">Release description</p>
              <p className="text-[11px] leading-5 text-muted">Describe the operational change this immutable Release introduces.</p>
              <Textarea
                value={releaseDescription ?? ''}
                onChange={(event) => onReleaseDescriptionChange?.(event.target.value)}
                placeholder="Describe what changed in this Release."
                className="min-h-24 text-sm"
              />
              {requireReleaseDescription && !descriptionValid ? <p className="text-[10px] text-amber-300">A release description with at least 3 characters is required.</p> : null}
            </section>
          ) : null}
          <ReleaseDetailsView release={release} />
        </div>

        <div className="flex shrink-0 items-center justify-end gap-2 border-t border-border/90 bg-background/20 p-4">
          <Button size="sm" variant="outline" onClick={onClose}>Close</Button>
          {onConfirm && confirmLabel ? (
            <Button size="sm" onClick={onConfirm} loading={isConfirming} disabled={!descriptionValid}>{confirmLabel}</Button>
          ) : null}
        </div>
      </div>
    </Dialog>
  )
}
