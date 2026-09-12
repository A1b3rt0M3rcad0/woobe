import { useCallback, useEffect, useMemo, useState } from 'react'
import { ArrowLeft, ArrowRight, History } from 'lucide-react'
import { toast } from 'sonner'

import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { Dialog } from '@/components/ui/Dialog'
import { getRelease } from '@/features/agents/api'
import type { AgentRelease, AgentReleaseActivation } from '@/features/agents/types'
import { activationLabel, describeReleaseChanges, formatReleaseDate, sessionModeLabel } from './releasePresentation'

type ActivationWithDescription = AgentReleaseActivation & { change_description?: string | null }
type ProductionChangesModalProps = { open: boolean; agentId: string; activations: AgentReleaseActivation[]; releases: AgentRelease[]; initialActivation?: AgentReleaseActivation | null; onClose: () => void }

function badgeVariant(action: AgentReleaseActivation['action']) {
  if (action === 'rollback') return 'warning' as const
  if (action === 'deploy') return 'success' as const
  return 'secondary' as const
}

function DetailSection({ title, children }: { title: string; children: React.ReactNode }) {
  return <section className="rounded-container border border-border bg-background/25 p-3"><p className="font-mono text-[8px] font-semibold uppercase tracking-[0.1em] text-slate-300">{title}</p><div className="mt-2">{children}</div></section>
}

export function ProductionChangesModal({ open, agentId, activations: rawActivations, releases, initialActivation = null, onClose }: ProductionChangesModalProps) {
  const activations = rawActivations as ActivationWithDescription[]
  const releasesById = useMemo(() => new Map(releases.map((release) => [release.id, release])), [releases])
  const [selected, setSelected] = useState<ActivationWithDescription | null>(null)
  const [currentRelease, setCurrentRelease] = useState<AgentRelease | null>(null)
  const [previousRelease, setPreviousRelease] = useState<AgentRelease | null>(null)
  const [loadingId, setLoadingId] = useState<string | null>(null)
  const [initialApplied, setInitialApplied] = useState(false)

  const view = useCallback(async (activation: ActivationWithDescription) => {
    setLoadingId(activation.id)
    try {
      const [current, previous] = await Promise.all([getRelease(agentId, activation.release_id), activation.previous_release_id ? getRelease(agentId, activation.previous_release_id) : Promise.resolve(null)])
      setSelected(activation); setCurrentRelease(current); setPreviousRelease(previous)
    } catch (error) { toast.error(error instanceof Error ? error.message : 'Failed to load Production change') } finally { setLoadingId(null) }
  }, [agentId])

  useEffect(() => {
    if (!open) { setInitialApplied(false); return }
    if (initialActivation && !initialApplied) { setInitialApplied(true); void view(initialActivation as ActivationWithDescription) }
  }, [initialActivation, initialApplied, open, view])

  const close = () => { setSelected(null); setCurrentRelease(null); setPreviousRelease(null); setLoadingId(null); setInitialApplied(false); onClose() }
  const back = () => { setSelected(null); setCurrentRelease(null); setPreviousRelease(null) }
  const changes = describeReleaseChanges(previousRelease, currentRelease)

  return <Dialog open={open} onClose={close} title={selected ? 'Production change details' : 'Latest Production Changes'} className="flex h-[min(760px,calc(100svh-2rem))] max-w-4xl flex-col overflow-hidden" contentClassName="min-h-0 flex-1 p-0">
    <div className="flex h-full min-h-0 flex-col">
      <div className="flex min-h-[42px] shrink-0 items-center gap-2 border-b border-border bg-background/20 px-4 py-2.5">{selected ? <button className="flex h-7 w-7 items-center justify-center rounded-control border border-border text-muted-foreground hover:bg-control hover:text-slate-50" onClick={back} aria-label="Back to Production changes"><ArrowLeft className="h-3.5 w-3.5" /></button> : null}<p className="font-sans text-[9px] text-muted-foreground">{selected ? 'Operational history for the selected Production activation.' : 'Deployments, reactivations and rollbacks from newest to oldest.'}</p></div>

      <div className="scrollbar-thin min-h-0 flex-1 overflow-y-auto p-4">
        {selected && currentRelease ? <div className="space-y-3">
          <DetailSection title="Production transition"><div className="flex flex-wrap items-center gap-2"><Badge variant={badgeVariant(selected.action)}>{activationLabel(selected.action)}</Badge><span className="font-mono text-[9px] text-slate-300">{previousRelease?.version ?? 'No Production'}</span><ArrowRight className="h-3.5 w-3.5 text-muted-foreground" /><span className="font-mono text-[9px] font-semibold text-slate-50">{currentRelease.version}</span></div><p className="mt-2 font-mono text-[8px] text-muted-foreground">{formatReleaseDate(selected.created_at)}</p></DetailSection>
          <DetailSection title="Audit note"><p className="whitespace-pre-wrap font-sans text-[9px] leading-4 text-slate-200">{selected.change_description || 'No audit note was recorded for this historical activation.'}</p></DetailSection>
          <DetailSection title="What changed"><ul className="space-y-2">{changes.map((change) => <li key={change} className="flex gap-2 font-sans text-[9px] leading-4 text-slate-200"><span className="mt-1.5 h-1 w-1 shrink-0 bg-primary-light" /><span>{change}</span></li>)}</ul></DetailSection>
          {currentRelease.release_notes ? <DetailSection title="Release description"><p className="whitespace-pre-wrap font-sans text-[9px] leading-4 text-slate-200">{currentRelease.release_notes}</p></DetailSection> : null}
          <DetailSection title="Resulting Production"><div className="grid gap-3 sm:grid-cols-2">{[['Release', currentRelease.version], ['Session Mode', sessionModeLabel(currentRelease.session_mode)], ['Provider', currentRelease.provider ?? '—'], ['Model', currentRelease.model ?? '—']].map(([label, value]) => <div key={label}><p className="font-mono text-[8px] uppercase tracking-[0.1em] text-muted-foreground">{label}</p><p className="mt-1 font-mono text-[9px] text-slate-100">{value}</p></div>)}</div></DetailSection>
        </div> : activations.length ? <div className="divide-y divide-border/60 rounded-container border border-border bg-background/20">{activations.map((activation) => {
          const release = releasesById.get(activation.release_id) ?? null
          const previous = activation.previous_release_id ? releasesById.get(activation.previous_release_id) ?? null : null
          const summary = activation.change_description || describeReleaseChanges(previous, release)[0]
          return <article key={activation.id} role="button" tabIndex={0} className="cursor-pointer px-3 py-3 transition-colors hover:bg-control/30" onClick={() => void view(activation)} onKeyDown={(event) => { if (event.key === 'Enter' || event.key === ' ') void view(activation) }}><div className="flex items-start gap-2.5"><History className="mt-0.5 h-3.5 w-3.5 shrink-0 text-muted-foreground" /><div className="min-w-0 flex-1"><div className="flex flex-wrap items-center gap-2"><Badge variant={badgeVariant(activation.action)}>{activationLabel(activation.action)}</Badge><span className="font-mono text-[8px] text-slate-300">{previous?.version ?? 'No Production'}</span><ArrowRight className="h-3 w-3 text-muted-foreground" /><span className="font-mono text-[8px] text-slate-50">{release?.version ?? activation.release_id.slice(0, 8)}</span></div><p className="mt-1.5 font-sans text-[9px] leading-4 text-slate-300">{summary}</p><p className="mt-1 font-mono text-[8px] text-muted-foreground">{formatReleaseDate(activation.created_at)}</p></div><Button size="sm" variant="outline" loading={loadingId === activation.id} onClick={(event) => { event.stopPropagation(); void view(activation) }}>View</Button></div></article>
        })}</div> : <div className="rounded-container border border-dashed border-border bg-background/20 p-6 text-center font-sans text-[9px] text-muted-foreground">No Production changes recorded.</div>}
      </div>
      <div className="flex min-h-[56px] shrink-0 items-center justify-end border-t border-border bg-surface/[0.98] px-4 py-3"><Button size="sm" variant="outline" onClick={close}>Close</Button></div>
    </div>
  </Dialog>
}
