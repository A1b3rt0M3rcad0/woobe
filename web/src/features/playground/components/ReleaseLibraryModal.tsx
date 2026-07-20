import { useState } from 'react'
import { ArrowLeft, Eye, Package, Rocket, X } from 'lucide-react'
import { toast } from 'sonner'

import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
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
}

export function ReleaseLibraryModal({ open, agentId, releases, onClose, onDeploy }: ReleaseLibraryModalProps) {
  const [selected, setSelected] = useState<AgentRelease | null>(null)
  const [loadingId, setLoadingId] = useState<string | null>(null)

  if (!open) return null

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
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4 backdrop-blur-md">
      <div className="flex max-h-[88vh] w-full max-w-4xl flex-col overflow-hidden rounded-2xl border border-border/90 bg-surface/95 shadow-2xl shadow-black/40">
        <div className="flex items-start justify-between gap-4 border-b border-border/90 bg-background/20 p-5">
          <div className="flex items-start gap-3">
            {selected ? (
              <button className="mt-0.5 rounded-lg border border-border/70 p-1.5 text-muted hover:bg-background/60 hover:text-white" onClick={() => setSelected(null)} aria-label="Back to releases">
                <ArrowLeft className="h-4 w-4" />
              </button>
            ) : null}
            <div>
              <h2 className="text-base font-semibold text-white">{selected ? selected.version : 'Available Releases'}</h2>
              <p className="mt-1 text-xs text-muted">
                {selected ? 'Release ready to be activated in Production.' : 'Only immutable Releases that can be promoted to Production are shown.'}
              </p>
            </div>
          </div>
          <button className="rounded-lg border border-transparent p-1 text-muted transition-colors hover:border-border/80 hover:bg-background/60 hover:text-white" onClick={close} aria-label="Close">
            <X className="h-4 w-4" />
          </button>
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
                      <Button size="sm" onClick={(event) => { event.stopPropagation(); deploy(release) }}>
                        <Rocket className="mr-1 h-3.5 w-3.5" />Deploy
                      </Button>
                    </div>
                  </div>
                </article>
              ))}
            </div>
          ) : (
            <div className="rounded-xl border border-dashed border-border p-6 text-center text-xs text-muted">No Releases are currently available for Production.</div>
          )}
        </div>

        <div className="flex items-center justify-end gap-2 border-t border-border/90 bg-background/20 p-4">
          {selected ? <Button size="sm" onClick={() => deploy(selected)}><Rocket className="mr-1 h-3.5 w-3.5" />Deploy Release</Button> : null}
          <Button size="sm" variant="outline" onClick={close}>Close</Button>
        </div>
      </div>
    </div>
  )
}
