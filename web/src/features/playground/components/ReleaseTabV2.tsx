import { useMemo, useState } from 'react'
import { ArrowRight, Eye, FileText, History, Package } from 'lucide-react'
import { toast } from 'sonner'

import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { Skeleton } from '@/components/ui/Skeleton'
import { getRelease } from '@/features/agents/api'
import { useReleaseActivations, useReleases } from '@/features/agents/hooks'
import type { AgentRelease, AgentReleaseActivation } from '@/features/agents/types'
import { useAgentEditor } from '../AgentEditorContext'
import { ProductionChangesModal } from './ProductionChangesModal'
import { ReleaseLibraryModal } from './ReleaseLibraryModal'
import { ReleaseSnapshotModal } from './ReleaseSnapshotModal'
import {
  activationLabel,
  describeReleaseChanges,
  formatReleaseDate,
  newestProductionChanges,
  promotableReleases,
} from './releasePresentation'

function SessionModeBadge({ mode }: { mode?: string }) {
  if (mode === 'stateful') {
    return <Badge variant="outline" className="border-indigo-400/25 bg-indigo-500/10 text-[9px] text-indigo-300">Stateful</Badge>
  }
  if (mode === 'stateless') {
    return <Badge variant="outline" className="border-cyan-400/25 bg-cyan-500/10 text-[9px] text-cyan-300">Stateless</Badge>
  }
  return <Badge variant="outline" className="text-[9px] text-muted">Mode unknown</Badge>
}

function SnapshotMeta({ release }: { release: AgentRelease }) {
  return (
    <div className="mt-1 flex flex-wrap items-center gap-1.5">
      <span className="text-[10px] text-muted">{release.provider ?? '—'}/{release.model ?? '—'} · {formatReleaseDate(release.created_at)}</span>
      <SessionModeBadge mode={release.session_mode} />
    </div>
  )
}

function activationVariant(action: AgentReleaseActivation['action']) {
  if (action === 'rollback') return 'warning' as const
  if (action === 'deploy') return 'success' as const
  return 'secondary' as const
}

export function ReleaseTab({ agentId, projectId: _projectId }: { agentId: string; projectId: string }) {
  const { data: releases = [], isLoading } = useReleases(agentId)
  const { data: activations = [], isLoading: activationsLoading } = useReleaseActivations(agentId)
  const { state } = useAgentEditor()
  const [snapshot, setSnapshot] = useState<AgentRelease | null>(null)
  const [loadingId, setLoadingId] = useState<string | null>(null)
  const [releaseLibraryOpen, setReleaseLibraryOpen] = useState(false)
  const [productionChangesOpen, setProductionChangesOpen] = useState(false)
  const [initialProductionChange, setInitialProductionChange] = useState<AgentReleaseActivation | null>(null)

  const staging = useMemo(
    () => releases.find((item) => item.status === 'staging') ?? null,
    [releases],
  )
  const production = useMemo(
    () => releases.find((item) => item.status === 'production') ?? null,
    [releases],
  )
  const availableReleases = useMemo(
    () => promotableReleases(releases),
    [releases],
  )
  const latestProductionChanges = useMemo(
    () => newestProductionChanges(activations),
    [activations],
  )
  const visibleAvailableReleases = availableReleases.slice(0, 3)
  const visibleProductionChanges = latestProductionChanges.slice(0, 3)
  const releasesById = useMemo(
    () => new Map(releases.map((release) => [release.id, release])),
    [releases],
  )

  const viewSnapshot = async (release: AgentRelease) => {
    setLoadingId(release.id)
    try {
      setSnapshot(await getRelease(agentId, release.id))
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Failed to load Agent Release')
    } finally {
      setLoadingId(null)
    }
  }

  const openProductionChange = (activation?: AgentReleaseActivation) => {
    setInitialProductionChange(activation ?? null)
    setProductionChangesOpen(true)
  }

  if (isLoading) {
    return <div className="space-y-3 p-4"><Skeleton className="h-5 w-32" /><Skeleton className="h-20 w-full rounded-lg" /><Skeleton className="h-24 w-full rounded-lg" /></div>
  }

  return (
    <div className="space-y-4 p-4">
      <div>
        <h2 className="text-sm font-medium text-white">Versions</h2>
        <p className="mt-1 text-[11px] leading-5 text-muted">Inspect Draft, immutable environments, Releases and Production history. Lifecycle actions live in the header.</p>
      </div>

      <section className="rounded-xl border border-border bg-surface/45 p-3">
        <div className="flex items-start gap-3">
          <div className="flex h-9 w-9 items-center justify-center rounded-lg border border-border bg-background/40"><FileText className="h-4 w-4 text-primary-light" /></div>
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2">
              <p className="text-xs font-medium text-white">Current Draft</p>
              <Badge variant="outline" className="text-[9px]">Mutable</Badge>
            </div>
            <div className="mt-1 flex flex-wrap items-center gap-1.5">
              <span className="text-[10px] text-muted">{state.provider || '—'}/{state.model || '—'}</span>
              <SessionModeBadge mode={state.sessionMode} />
            </div>
            <p className="mt-2 text-[10px] leading-4 text-muted">Editable working configuration. Save changes in the Editor before staging.</p>
          </div>
        </div>
      </section>

      <section>
        <h3 className="mb-2 text-[10px] font-semibold uppercase tracking-wide text-muted">Current Staging</h3>
        {staging ? (
          <button type="button" onClick={() => void viewSnapshot(staging)} className="w-full rounded-xl border border-indigo-500/30 bg-indigo-500/[0.04] p-3 text-left transition-colors hover:border-indigo-400/40 hover:bg-indigo-500/[0.07]">
            <div className="flex items-start gap-3">
              <div className="min-w-0 flex-1">
                <p className="font-mono text-xs text-white">{staging.version}</p>
                <SnapshotMeta release={staging} />
                <p className="mt-2 text-[10px] leading-4 text-muted">Immutable validation snapshot.</p>
              </div>
              <Badge variant="secondary" className="border-indigo-500/30 text-indigo-300">Staging</Badge>
            </div>
            <span className="mt-3 inline-flex items-center text-[10px] text-indigo-300"><Eye className="mr-1 h-3.5 w-3.5" />View snapshot</span>
          </button>
        ) : <div className="rounded-xl border border-dashed border-border p-3 text-[10px] text-muted">No Agent Staging snapshot.</div>}
      </section>

      <section>
        <h3 className="mb-2 text-[10px] font-semibold uppercase tracking-wide text-muted">Production</h3>
        {production ? (
          <button type="button" onClick={() => void viewSnapshot(production)} className="w-full rounded-xl border border-emerald-500/30 bg-emerald-500/[0.04] p-3 text-left transition-colors hover:border-emerald-400/40 hover:bg-emerald-500/[0.07]">
            <div className="flex items-start gap-3">
              <div className="min-w-0 flex-1">
                <p className="font-mono text-xs text-white">{production.version}</p>
                <SnapshotMeta release={production} />
                <p className="mt-1 text-[9px] text-emerald-300">Active in standalone Agent Production runtime</p>
              </div>
              <Badge variant="success">Production</Badge>
            </div>
            <span className="mt-3 inline-flex items-center text-[10px] text-emerald-300"><Eye className="mr-1 h-3.5 w-3.5" />View snapshot</span>
          </button>
        ) : <div className="rounded-xl border border-dashed border-border p-3 text-[10px] text-muted">No standalone Agent Production release is active.</div>}
      </section>

      <section>
        <div className="mb-2 flex items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <Package className="h-3.5 w-3.5 text-primary-light" />
            <h3 className="text-[10px] font-semibold uppercase tracking-wide text-muted">Releases</h3>
            <span className="rounded border border-border px-1.5 py-0.5 text-[9px] text-muted">{availableReleases.length}</span>
          </div>
          {availableReleases.length ? <Button size="sm" variant="outline" onClick={() => setReleaseLibraryOpen(true)}>View all</Button> : null}
        </div>
        {visibleAvailableReleases.length ? (
          <div className="space-y-2">
            {visibleAvailableReleases.map((release) => (
              <button
                type="button"
                key={release.id}
                className="w-full rounded-xl border border-border bg-background/35 p-3 text-left transition-colors hover:border-primary/30 hover:bg-background/55"
                onClick={() => void viewSnapshot(release)}
              >
                <div className="flex items-start gap-3">
                  <Package className="mt-0.5 h-4 w-4 shrink-0 text-primary-light" />
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <p className="font-mono text-xs text-white">{release.version}</p>
                      <SessionModeBadge mode={release.session_mode} />
                    </div>
                    <p className="mt-1 text-[10px] text-muted">{release.provider ?? '—'}/{release.model ?? '—'} · {formatReleaseDate(release.created_at)}</p>
                    {release.release_notes ? <p className="mt-2 line-clamp-2 text-[10px] leading-4 text-slate-300">{release.release_notes}</p> : null}
                  </div>
                  <Eye className={loadingId === release.id ? 'h-4 w-4 animate-pulse text-primary-light' : 'h-4 w-4 text-muted'} />
                </div>
              </button>
            ))}
          </div>
        ) : <div className="rounded-xl border border-dashed border-border p-3 text-[10px] text-muted">No immutable Releases are currently available.</div>}
      </section>

      <section>
        <div className="mb-2 flex items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <History className="h-3.5 w-3.5 text-muted" />
            <h3 className="text-[10px] font-semibold uppercase tracking-wide text-muted">Production history</h3>
            <span className="rounded border border-border px-1.5 py-0.5 text-[9px] text-muted">{latestProductionChanges.length}</span>
          </div>
          {latestProductionChanges.length ? <Button size="sm" variant="outline" onClick={() => openProductionChange()}>View all</Button> : null}
        </div>
        {activationsLoading ? <Skeleton className="h-16 w-full rounded-lg" /> : visibleProductionChanges.length ? (
          <div className="space-y-2">
            {visibleProductionChanges.map((activation) => {
              const release = releasesById.get(activation.release_id) ?? null
              const previous = activation.previous_release_id
                ? releasesById.get(activation.previous_release_id) ?? null
                : null
              const summary = describeReleaseChanges(previous, release)[0]
              return (
                <button
                  type="button"
                  key={activation.id}
                  className="w-full rounded-xl border border-border bg-background/30 p-3 text-left transition-colors hover:border-primary/30 hover:bg-background/50"
                  onClick={() => openProductionChange(activation)}
                >
                  <div className="flex items-start gap-3">
                    <History className="mt-0.5 h-4 w-4 shrink-0 text-muted" />
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-2 text-[10px]">
                        <Badge variant={activationVariant(activation.action)} className="text-[9px]">{activationLabel(activation.action)}</Badge>
                        <span className="font-mono text-slate-300">{previous?.version ?? 'No Production'}</span>
                        <ArrowRight className="h-3 w-3 text-muted" />
                        <span className="font-mono text-white">{release?.version ?? activation.release_id.slice(0, 8)}</span>
                      </div>
                      <p className="mt-2 text-[10px] text-slate-300">{summary}</p>
                      <p className="mt-1 text-[9px] text-muted">{formatReleaseDate(activation.created_at)}</p>
                    </div>
                  </div>
                </button>
              )
            })}
          </div>
        ) : <div className="rounded-xl border border-dashed border-border p-3 text-[10px] text-muted">No Production changes recorded.</div>}
      </section>

      <ReleaseSnapshotModal open={Boolean(snapshot)} title="Agent Release details" description="Operational configuration stored for this immutable version." release={snapshot} onClose={() => setSnapshot(null)} />
      <ReleaseLibraryModal open={releaseLibraryOpen} agentId={agentId} releases={availableReleases} readOnly onClose={() => setReleaseLibraryOpen(false)} onDeploy={() => undefined} />
      <ProductionChangesModal
        open={productionChangesOpen}
        agentId={agentId}
        activations={latestProductionChanges}
        releases={releases}
        initialActivation={initialProductionChange}
        onClose={() => {
          setProductionChangesOpen(false)
          setInitialProductionChange(null)
        }}
      />
    </div>
  )
}
