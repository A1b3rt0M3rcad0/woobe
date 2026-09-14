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

export function ReleaseLibraryModal({ open, agentId, releases, onClose, onDeploy, readOnly = false, title = 'Available Releases', description = 'Immutable Agent Releases available for inspection.', actionLabel = 'Deploy' }: ReleaseLibraryModalProps) {
  const [selected, setSelected] = useState<AgentRelease | null>(null)
  const [loadingId, setLoadingId] = useState<string | null>(null)
  const close = () => { setSelected(null); setLoadingId(null); onClose() }
  const view = async (release: AgentRelease) => {
    setLoadingId(release.id)
    try { setSelected(await getRelease(agentId, release.id)) } catch (error) { toast.error(error instanceof Error ? error.message : 'Failed to load Agent Release') } finally { setLoadingId(null) }
  }
  const deploy = (release: AgentRelease) => { close(); onDeploy(release) }

  return <Dialog open={open} onClose={close} title={selected ? selected.version : title} className="flex h-[min(760px,calc(100svh-2rem))] max-w-4xl flex-col overflow-hidden" contentClassName="min-h-0 flex-1 p-0">
    <div className="flex h-full min-h-0 flex-col">
      <div className="flex min-h-[42px] shrink-0 items-center gap-ui-sm border-b border-border bg-background/20 px-ui-md py-ui-sm">
        {selected ? <button className="flex h-control-sm w-control-sm items-center justify-center rounded-control border border-border text-muted-foreground transition-colors hover:bg-control hover:text-slate-50" onClick={() => setSelected(null)} aria-label="Back to releases"><ArrowLeft className="h-icon-sm w-icon-sm" /></button> : null}
        <p className="font-sans text-product-caption text-muted-foreground">{selected ? 'Immutable Agent Release snapshot.' : description}</p>
      </div>

      <div className="scrollbar-thin min-h-0 flex-1 overflow-y-auto p-ui-md">
        {selected ? <ReleaseDetailsView release={selected} /> : releases.length ? <div className="divide-y divide-border/60 rounded-container border border-border bg-background/20">{releases.map((release) => <article key={release.id} role="button" tabIndex={0} className="cursor-pointer px-ui-md py-ui-md transition-colors hover:bg-control/30" onClick={() => void view(release)} onKeyDown={(event) => { if (event.key === 'Enter' || event.key === ' ') void view(release) }}>
          <div className="flex items-start gap-ui-md"><Package className="mt-ui-hairline h-3.5 w-3.5 shrink-0 text-primary-light" /><div className="min-w-0 flex-1"><div className="flex flex-wrap items-center gap-ui-sm"><p className="font-mono text-system-label font-semibold text-slate-100">{release.version}</p><Badge variant="outline">{sessionModeLabel(release.session_mode)}</Badge></div><p className="mt-ui-xs font-mono text-system-meta text-muted-foreground">{release.provider ?? '—'}/{release.model ?? '—'} · {formatReleaseDate(release.created_at)}</p>{release.release_notes ? <p className="mt-ui-sm line-clamp-2 font-sans text-product-caption leading-4 text-slate-300">{release.release_notes}</p> : null}</div><div className="flex shrink-0 gap-ui-sm"><Button size="sm" variant="outline" loading={loadingId === release.id} onClick={(event) => { event.stopPropagation(); void view(release) }}><Eye className="h-icon-sm w-icon-sm" />View</Button>{!readOnly ? <Button size="sm" onClick={(event) => { event.stopPropagation(); deploy(release) }}><Rocket className="h-icon-sm w-icon-sm" />{actionLabel}</Button> : null}</div></div>
        </article>)}</div> : <div className="rounded-container border border-dashed border-border bg-background/20 p-ui-xl text-center font-sans text-product-caption text-muted-foreground">No immutable Agent Releases are available.</div>}
      </div>

      <div className="flex min-h-[56px] shrink-0 items-center justify-end gap-ui-sm border-t border-border bg-surface/[0.98] px-ui-md py-ui-md">{selected && !readOnly ? <Button size="sm" onClick={() => deploy(selected)}><Rocket className="h-icon-sm w-icon-sm" />{actionLabel}</Button> : null}<Button size="sm" variant="outline" onClick={close}>Close</Button></div>
    </div>
  </Dialog>
}
