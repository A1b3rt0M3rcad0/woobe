import { useState } from 'react'
import { ArrowLeft, Eye, Package, Rocket } from 'lucide-react'
import { toast } from 'sonner'

import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { Dialog } from '@/components/ui/Dialog'
import { getRelease } from '@/features/agents/api'
import type { AgentRelease } from '@/features/agents/types'
import { ReleaseDetailsView } from './ReleaseDetailsView'
import { formatReleaseDate, sessionModeLabel } from './releasePresentation'

type ReleaseLibraryModalProps = {
  open: boolean
  agentId: string
  releases: AgentRelease[]
  onClose: () => void
  onDeploy: (release: AgentRelease) => void
  readOnly?: boolean
  title?: string
  description?: string
  actionLabel?: string
}

export function ReleaseLibraryModal({
  open,
  agentId,
  releases,
  onClose,
  onDeploy,
  readOnly = false,
  title = 'Available Releases',
  description = 'Immutable Agent Releases available for inspection.',
  actionLabel = 'Deploy',
}: ReleaseLibraryModalProps) {
  const [selected, setSelected] = useState<AgentRelease | null>(null)
  const [loadingId, setLoadingId] = useState<string | null>(null)

  const close = () => {
    setSelected(null)
    setLoadingId(null)
    onClose()
  }

  const view = async (release: AgentRelease) => {
    setLoadingId(release.id)
    try {
      setSelected(await getRelease(agentId, release.id))
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Failed to load Agent Release')
    } finally {
      setLoadingId(null)
    }
  }

  const deploy = (release: AgentRelease) => {
    close()
    onDeploy(release)
  }

  return (
    <Dialog
      open={open}
      onClose={close}
      title={selected ? selected.version : title}
      className="max-w-4xl"
      contentClassName="p-0"
      scrollMode="content"
    >
      <div className="flex min-h-0 flex-1 flex-col">
        <div className="flex shrink-0 items-center gap-3 border-b border-border/90 bg-background/20 px-5 py-3">
          {selected ? (
            <button className="rounded-lg border border-border/70 p-1.5 text-muted hover:bg-background/60 hover:text-white" onClick={() => setSelected(null)} aria-label="Back to releases">
              <ArrowLeft className="h-4 w-4" />
            </button>
          ) : null}
          <p className="text-xs text-muted">{selected ? 'Immutable Agent Release snapshot.' : description}</p>
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto p-5">
          {selected ? (
            <ReleaseDetailsView release={selected} />
          ) : releases.length ? (
            <div className="space-y-2">
              {releases.map((release) => (
                <article
                  key={release.id}
                  role="button"
                  tabIndex={0}
                  className="cursor-pointer rounded-xl border border-border bg-background/35 p-3 transition-colors hover:border-primary/30 hover:bg-background/55"
                  onClick={() => void view(release)}
                  onKeyDown={(event) => {
                    if (event.key === 'Enter' || event.key === ' ') void view(release)
                  }}
                >
                  <div className="flex items-start gap-3">
                    <Package className="mt-0.5 h-4 w-4 shrink-0 text-primary-light" />
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <p className="font-mono text-xs text-white">{release.version}</p>
                        <Badge variant="outline" className="text-[9px]">{sessionModeLabel(release.session_mode)}</Badge>
                      </div>
                      <p className="mt-1 text-[10px] text-muted">{release.provider ?? '—'}/{release.model ?? '—'} · {formatReleaseDate(release.created_at)}</p>
                      {release.release_notes ? <p className="mt-2 line-clamp-2 text-[11px] leading-5 text-slate-300">{release.release_notes}</p> : null}
                    </div>
                    <div className="flex shrink-0 gap-2">
                      <Button size="sm" variant="outline" loading={loadingId === release.id} onClick={(event) => { event.stopPropagation(); void view(release) }}>
                        <Eye className="mr-1 h-3.5 w-3.5" />View
                      </Button>
                      {!readOnly ? (
                        <Button size="sm" onClick={(event) => { event.stopPropagation(); deploy(release) }}>
                          <Rocket className="mr-1 h-3.5 w-3.5" />{actionLabel}
                        </Button>
                      ) : null}
                    </div>
                  </div>
                </article>
              ))}
            </div>
          ) : (
            <div className="rounded-xl border border-dashed border-border p-6 text-center text-xs text-muted">No immutable Agent Releases are available.</div>
          )}
        </div>

        <div className="flex shrink-0 items-center justify-end gap-2 border-t border-border/90 bg-background/20 p-4">
          {selected && !readOnly ? <Button size="sm" onClick={() => deploy(selected)}><Rocket className="mr-1 h-3.5 w-3.5" />{actionLabel}</Button> : null}
          <Button size="sm" variant="outline" onClick={close}>Close</Button>
        </div>
      </div>
    </Dialog>
  )
}
