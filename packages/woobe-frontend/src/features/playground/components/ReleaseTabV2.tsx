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
    return <div className="space-y-3 p-4"><Skeleton className="h-5 w-32" /><Skeleton className="h-16 w-full" /><Skeleton className="h-20 w-full" /></div>
  }

  return (
    <div className="p-4">
      <div className="pb-4">
        <h2 className="text-xs font-semibold text-white">Version history</h2>
        <p className="mt-1 text-[11px] leading-4 text-muted">Inspect mutable Draft state, immutable environments, Releases and Production changes.</p>
      </div>

      <section aria-label="Environment versions" className="border-t border-border/80">
        <div className="flex items-start gap-3 py-3">
          <FileText className="mt-0.5 h-4 w-4 shrink-0 text-primary-light" />
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2">
              <p className="text-xs font-medium text-white">Current Draft</p>
              <Badge variant="outline" className="text-[9px]">Mutable</Badge>
            </div>
            <div className="mt-1 flex flex-wrap items-center gap-1.5">
              <span className="text-[10px] text-muted">{state.provider || '—'}/{state.model || '—'}</span>
              <SessionModeBadge mode={state.sessionMode} />
            </div>
          </div>
        </div>

        <div className="border-t border-border/80">
          {staging ? (
            <button type="button" onClick={() => void viewSnapshot(staging)} className="group flex w-full items-start gap-3 py-3 text-left">
              <span className="mt-1 h-2 w-2 shrink-0 rounded-full bg-indigo-400" />
              <div className="min-w-0 flex-1">
                <div className="flex items-center justify-between gap-2">
                  <div>
                    <p className="text-[10px] font-semibold uppercase tracking-wide text-muted">Staging</p>
                    <p className="mt-0.5 font-mono text-xs text-white">{staging.version}</p>
                  </div>
                  <Eye className={loadingId === staging.id ? 'h-4 w-4 animate-pulse text-primary-light' : 'h-4 w-4 text-muted transition-colors group-hover:text-primary-light'} />
                </div>
                <SnapshotMeta release={staging} />
                <p className="mt-1 text-[10px] text-muted">Immutable validation snapshot.</p>
              </div>
            </button>
          ) : (
            <div className="py-3 text-[10px] text-muted"><span className="font-semibold uppercase tracking-wide">Staging</span><span className="ml-2">No snapshot created.</span></div>
          )}
        </div>

        <div className="border-t border-border/80">
          {production ? (
            <button type="button" onClick={() => void viewSnapshot(production)} className="group flex w-full items-start gap-3 py-3 text-left">
              <span className="mt-1 h-2 w-2 shrink-0 rounded-full bg-emerald-400" />
              <div className="min-w-0 flex-1">
                <div className="flex items-center justify-between gap-2">
                  <div>
                    <p className="text-[10px] font-semibold uppercase tracking-wide text-muted">Production</p>
                    <p className="mt-0.5 font-mono text-xs text-white">{production.version}</p>
                  </div>
                  <Eye className={loadingId === production.id ? 'h-4 w-4 animate-pulse text-primary-light' : 'h-4 w-4 text-muted transition-colors group-hover:text-primary-light'} />
                </div>
                <SnapshotMeta release={production} />
                <p className="mt-1 text-[10px] text-emerald-300">Active standalone Agent Production release.</p>
              </div>
            </button>
          ) : (
            <div className="py-3 text-[10px] text-muted"><span className="font-semibold uppercase tracking-wide">Production</span><span className="ml-2">No active release.</span></div>
          )}
        </div>
      </section>

      <section aria-label="Agent Releases" className="border-t border-border/80 py-4">
        <div className="mb-2 flex items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <Package className="h-3.5 w-3.5 text-primary-light" />
            <h3 className="text-[10px] font-semibold uppercase tracking-wide text-muted">Releases</h3>
            <span className="font-mono text-[9px] text-muted">{availableReleases.length}</span>
          </div>
          {availableReleases.length ? <Button size="sm" variant="ghost" className="h-7 px-2 text-[10px]" onClick={() => setReleaseLibraryOpen(true)}>View all</Button> : null}
        </div>
        {visibleAvailableReleases.length ? (
          <div className="divide-y divide-border/70 border-y border-border/70">
            {visibleAvailableReleases.map((release) => (
              <button
                type="button"
                key={release.id}
                className="group flex w-full items-start gap-3 py-3 text-left"
                onClick={() => void viewSnapshot(release)}
              >
                <Package className="mt-0.5 h-4 w-4 shrink-0 text-primary-light" />
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <p className="font-mono text-xs text-white">{release.version}</p>
                    <SessionModeBadge mode={release.session_mode} />
                  </div>
                  <p className="mt-1 text-[10px] text-muted">{release.provider ?? '—'}/{release.model ?? '—'} · {formatReleaseDate(release.created_at)}</p>
                  {release.release_notes ? <p className="mt-1 line-clamp-2 text-[10px] leading-4 text-slate-300">{release.release_notes}</p> : null}
                </div>
                <Eye className={loadingId === release.id ? 'h-4 w-4 animate-pulse text-primary-light' : 'h-4 w-4 text-muted transition-colors group-hover:text-primary-light'} />
              </button>
            ))}
          </div>
        ) : <p className="py-2 text-[10px] text-muted">No immutable Releases are currently available.</p>}
      </section>

      <section aria-label="Production history" className="border-t border-border/80 pt-4">
        <div className="mb-2 flex items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <History className="h-3.5 w-3.5 text-muted" />
            <h3 className="text-[10px] font-semibold uppercase tracking-wide text-muted">Production history</h3>
            <span className="font-mono text-[9px] text-muted">{latestProductionChanges.length}</span>
          </div>
          {latestProductionChanges.length ? <Button size="sm" variant="ghost" className="h-7 px-2 text-[10px]" onClick={() => openProductionChange()}>View all</Button> : null}
        </div>
        {activationsLoading ? <Skeleton className="h-16 w-full" /> : visibleProductionChanges.length ? (
          <div className="divide-y divide-border/70 border-y border-border/70">
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
                  className="flex w-full items-start gap-3 py-3 text-left"
                  onClick={() => openProductionChange(activation)}
                >
                  <History className="mt-0.5 h-4 w-4 shrink-0 text-muted" />
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2 text-[10px]">
                      <Badge variant={activationVariant(activation.action)} className="text-[9px]">{activationLabel(activation.action)}</Badge>
                      <span className="font-mono text-slate-300">{previous?.version ?? 'No Production'}</span>
                      <ArrowRight className="h-3 w-3 text-muted" />
                      <span className="font-mono text-white">{release?.version ?? activation.release_id.slice(0, 8)}</span>
                    </div>
                    <p className="mt-1.5 text-[10px] text-slate-300">{summary}</p>
                    <p className="mt-1 text-[9px] text-muted">{formatReleaseDate(activation.created_at)}</p>
                  </div>
                </button>
              )
            })}
          </div>
        ) : <p className="py-2 text-[10px] text-muted">No Production changes recorded.</p>}
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