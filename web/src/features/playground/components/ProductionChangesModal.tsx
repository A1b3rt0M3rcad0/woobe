import { useCallback, useEffect, useMemo, useState } from 'react'
import { ArrowLeft, ArrowRight, History, X } from 'lucide-react'
import { toast } from 'sonner'

import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { getRelease } from '@/features/agents/api'
import type { AgentRelease, AgentReleaseActivation } from '@/features/agents/types'
import {
  activationLabel,
  describeReleaseChanges,
  formatReleaseDate,
  sessionModeLabel,
} from './releasePresentation'

type ProductionChangesModalProps = {
  open: boolean
  agentId: string
  activations: AgentReleaseActivation[]
  releases: AgentRelease[]
  initialActivation?: AgentReleaseActivation | null
  onClose: () => void
}

function badgeVariant(action: AgentReleaseActivation['action']) {
  if (action === 'rollback') return 'warning' as const
  if (action === 'deploy') return 'success' as const
  return 'secondary' as const
}

export function ProductionChangesModal({
  open,
  agentId,
  activations,
  releases,
  initialActivation = null,
  onClose,
}: ProductionChangesModalProps) {
  const releasesById = useMemo(
    () => new Map(releases.map((release) => [release.id, release])),
    [releases],
  )
  const [selected, setSelected] = useState<AgentReleaseActivation | null>(null)
  const [currentRelease, setCurrentRelease] = useState<AgentRelease | null>(null)
  const [previousRelease, setPreviousRelease] = useState<AgentRelease | null>(null)
  const [loadingId, setLoadingId] = useState<string | null>(null)
  const [initialApplied, setInitialApplied] = useState(false)

  const view = useCallback(async (activation: AgentReleaseActivation) => {
    setLoadingId(activation.id)
    try {
      const [current, previous] = await Promise.all([
        getRelease(agentId, activation.release_id),
        activation.previous_release_id
          ? getRelease(agentId, activation.previous_release_id)
          : Promise.resolve(null),
      ])
      setSelected(activation)
      setCurrentRelease(current)
      setPreviousRelease(previous)
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Failed to load Production change')
    } finally {
      setLoadingId(null)
    }
  }, [agentId])

  useEffect(() => {
    if (!open) {
      setInitialApplied(false)
      return
    }
    if (initialActivation && !initialApplied) {
      setInitialApplied(true)
      void view(initialActivation)
    }
  }, [initialActivation, initialApplied, open, view])

  if (!open) return null

  const close = () => {
    setSelected(null)
    setCurrentRelease(null)
    setPreviousRelease(null)
    setLoadingId(null)
    setInitialApplied(false)
    onClose()
  }

  const back = () => {
    setSelected(null)
    setCurrentRelease(null)
    setPreviousRelease(null)
  }

  const changes = describeReleaseChanges(previousRelease, currentRelease)

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4 backdrop-blur-md">
      <div className="flex max-h-[88vh] w-full max-w-4xl flex-col overflow-hidden rounded-2xl border border-border/90 bg-surface/95 shadow-2xl shadow-black/40">
        <div className="flex items-start justify-between gap-4 border-b border-border/90 bg-background/20 p-5">
          <div className="flex items-start gap-3">
            {selected ? (
              <button className="mt-0.5 rounded-lg border border-border/70 p-1.5 text-muted hover:bg-background/60 hover:text-white" onClick={back} aria-label="Back to Production changes">
                <ArrowLeft className="h-4 w-4" />
              </button>
            ) : null}
            <div>
              <h2 className="text-base font-semibold text-white">{selected ? 'Production change details' : 'Latest Production Changes'}</h2>
              <p className="mt-1 text-xs text-muted">
                {selected ? 'Operational history for the selected Production activation.' : 'Deployments, reactivations and rollbacks from newest to oldest.'}
              </p>
            </div>
          </div>
          <button className="rounded-lg border border-transparent p-1 text-muted transition-colors hover:border-border/80 hover:bg-background/60 hover:text-white" onClick={close} aria-label="Close">
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto p-5">
          {selected && currentRelease ? (
            <div className="space-y-5">
              <section className="rounded-xl border border-border/80 bg-background/35 p-4">
                <div className="flex flex-wrap items-center gap-2">
                  <Badge variant={badgeVariant(selected.action)}>{activationLabel(selected.action)}</Badge>
                  <span className="font-mono text-sm text-slate-300">{previousRelease?.version ?? 'No Production'}</span>
                  <ArrowRight className="h-4 w-4 text-muted" />
                  <span className="font-mono text-sm text-white">{currentRelease.version}</span>
                </div>
                <p className="mt-2 text-[11px] text-muted">{formatReleaseDate(selected.created_at)}</p>
              </section>

              <section className="rounded-xl border border-border/80 bg-background/35 p-4">
                <p className="text-xs font-semibold uppercase tracking-wide text-slate-300">What changed</p>
                <ul className="mt-3 space-y-2">
                  {changes.map((change) => (
                    <li key={change} className="flex gap-2 text-sm leading-6 text-slate-200">
                      <span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-primary-light" />
                      <span>{change}</span>
                    </li>
                  ))}
                </ul>
              </section>

              {currentRelease.release_notes ? (
                <section className="rounded-xl border border-border/80 bg-background/35 p-4">
                  <p className="text-xs font-semibold uppercase tracking-wide text-slate-300">Release description</p>
                  <p className="mt-2 whitespace-pre-wrap text-sm leading-6 text-slate-200">{currentRelease.release_notes}</p>
                </section>
              ) : null}

              <section className="rounded-xl border border-border/80 bg-background/35 p-4">
                <p className="text-xs font-semibold uppercase tracking-wide text-slate-300">Resulting Production</p>
                <div className="mt-3 grid gap-3 sm:grid-cols-2">
                  <div><p className="text-[10px] uppercase tracking-wide text-muted">Release</p><p className="mt-1 font-mono text-sm text-white">{currentRelease.version}</p></div>
                  <div><p className="text-[10px] uppercase tracking-wide text-muted">Session Mode</p><p className="mt-1 text-sm text-slate-200">{sessionModeLabel(currentRelease.session_mode)}</p></div>
                  <div><p className="text-[10px] uppercase tracking-wide text-muted">Provider</p><p className="mt-1 text-sm text-slate-200">{currentRelease.provider ?? '—'}</p></div>
                  <div><p className="text-[10px] uppercase tracking-wide text-muted">Model</p><p className="mt-1 text-sm text-slate-200">{currentRelease.model ?? '—'}</p></div>
                </div>
              </section>
            </div>
          ) : activations.length ? (
            <div className="space-y-2">
              {activations.map((activation) => {
                const release = releasesById.get(activation.release_id) ?? null
                const previous = activation.previous_release_id
                  ? releasesById.get(activation.previous_release_id) ?? null
                  : null
                const summary = describeReleaseChanges(previous, release)[0]
                return (
                  <article
                    key={activation.id}
                    role="button"
                    tabIndex={0}
                    className="cursor-pointer rounded-xl border border-border bg-background/35 p-3 transition-colors hover:border-primary/30 hover:bg-background/55"
                    onClick={() => void view(activation)}
                    onKeyDown={(event) => {
                      if (event.key === 'Enter' || event.key === ' ') void view(activation)
                    }}
                  >
                    <div className="flex items-start gap-3">
                      <History className="mt-0.5 h-4 w-4 shrink-0 text-muted" />
                      <div className="min-w-0 flex-1">
                        <div className="flex flex-wrap items-center gap-2 text-[10px]">
                          <Badge variant={badgeVariant(activation.action)} className="text-[9px]">{activationLabel(activation.action)}</Badge>
                          <span className="font-mono text-slate-300">{previous?.version ?? 'No Production'}</span>
                          <ArrowRight className="h-3 w-3 text-muted" />
                          <span className="font-mono text-white">{release?.version ?? activation.release_id.slice(0, 8)}</span>
                        </div>
                        <p className="mt-2 text-[11px] text-slate-300">{summary}</p>
                        <p className="mt-1 text-[9px] text-muted">{formatReleaseDate(activation.created_at)}</p>
                      </div>
                      <Button size="sm" variant="outline" loading={loadingId === activation.id} onClick={(event) => { event.stopPropagation(); void view(activation) }}>View</Button>
                    </div>
                  </article>
                )
              })}
            </div>
          ) : (
            <div className="rounded-xl border border-dashed border-border p-6 text-center text-xs text-muted">No Production changes recorded.</div>
          )}
        </div>

        <div className="flex items-center justify-end border-t border-border/90 bg-background/20 p-4">
          <Button size="sm" variant="outline" onClick={close}>Close</Button>
        </div>
      </div>
    </div>
  )
}
