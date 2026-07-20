import { useMemo, useState } from 'react'
import { ArrowRight, Eye, FileText, History, Package, Rocket, Upload } from 'lucide-react'
import { toast } from 'sonner'

import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { Skeleton } from '@/components/ui/Skeleton'
import { getRelease } from '@/features/agents/api'
import {
  useCreateRelease,
  usePromoteRelease,
  useReleaseActivations,
  useReleases,
} from '@/features/agents/hooks'
import type { AgentRelease, AgentReleaseActivation } from '@/features/agents/types'
import { useAgentEditor } from '../AgentEditorContext'
import { ProductionChangesModal } from './ProductionChangesModal'
import { ReleaseLibraryModal } from './ReleaseLibraryModal'
import { ReleaseSnapshotModal } from './ReleaseSnapshotModal'
import { StageDraftSnapshotModal } from './StageDraftSnapshotModal'
import {
  activationLabel,
  describeReleaseChanges,
  formatReleaseDate,
  newestProductionChanges,
  promotableReleases,
  sessionModeLabel,
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

type PublishAction = 'release' | 'deploy' | null

export function ReleaseTab({ agentId, projectId }: { agentId: string; projectId: string }) {
  const { data: releases = [], isLoading } = useReleases(agentId)
  const { data: activations = [], isLoading: activationsLoading } = useReleaseActivations(agentId)
  const createRelease = useCreateRelease(agentId)
  const promoteRelease = usePromoteRelease(agentId)
  const { state, toSnapshot } = useAgentEditor()
  const [stageOpen, setStageOpen] = useState(false)
  const [publishAction, setPublishAction] = useState<PublishAction>(null)
  const [releaseDescription, setReleaseDescription] = useState('')
  const [activationTarget, setActivationTarget] = useState<AgentRelease | null>(null)
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
  const sessionModeChange = Boolean(
    staging
    && production
    && staging.session_mode
    && production.session_mode
    && staging.session_mode !== production.session_mode,
  )

  const stageDraft = async () => {
    try {
      const draft = await createRelease.mutateAsync({
        project_id: projectId,
        agent_id: agentId,
        version: 'draft',
        ...toSnapshot(),
      } as any)
      const staged = await promoteRelease.mutateAsync({
        releaseId: draft.id,
        targetStatus: 'staging',
        copySnapshot: true,
      })
      setStageOpen(false)
      toast.success(`${staged.version} created as current Staging`)
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Failed to promote Draft to Staging')
    }
  }

  const createFromStaging = async () => {
    if (!staging || !publishAction) return
    const deploy = publishAction === 'deploy'
    const existingIds = new Set(releases.map((release) => release.id))
    try {
      const result = await promoteRelease.mutateAsync({
        releaseId: staging.id,
        targetStatus: deploy ? 'production' : 'released',
        copySnapshot: true,
        releaseNotes: releaseDescription.trim() || undefined,
      })
      const reused = existingIds.has(result.id)
      setPublishAction(null)
      setReleaseDescription('')

      if (deploy) {
        toast.success(
          reused
            ? `${result.version} reused and deployed to Production`
            : `${result.version} created and deployed to Production`,
        )
      } else if (result.status === 'production') {
        toast.info(`Equivalent Release already exists as ${result.version} and is active in Production`)
      } else {
        toast.success(reused ? `Equivalent Release already exists as ${result.version}` : `${result.version} created without deployment`)
      }
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Failed to create Agent Release')
    }
  }

  const activateRelease = async () => {
    if (!activationTarget) return
    try {
      await promoteRelease.mutateAsync({
        releaseId: activationTarget.id,
        targetStatus: 'production',
        copySnapshot: false,
        restoreExistingVersion: true,
      })
      toast.success(`${activationTarget.version} is now active in Agent Playground Production`)
      setActivationTarget(null)
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Failed to activate Agent Release')
    }
  }

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
        <p className="mt-1 text-[11px] leading-5 text-muted">Draft → Staging → Release → Production.</p>
      </div>

      <section className="rounded-xl border border-border bg-surface/45 p-3">
        <div className="flex items-start gap-3">
          <div className="flex h-9 w-9 items-center justify-center rounded-lg border border-border bg-background/40"><FileText className="h-4 w-4 text-primary-light" /></div>
          <div className="min-w-0 flex-1">
            <p className="text-xs font-medium text-white">Current Draft</p>
            <div className="mt-1 flex flex-wrap items-center gap-1.5">
              <span className="text-[10px] text-muted">Mutable configuration · {state.provider || '—'}/{state.model || '—'}</span>
              <SessionModeBadge mode={state.sessionMode} />
            </div>
          </div>
          <Button size="sm" className="h-8 text-[10px]" onClick={() => setStageOpen(true)}><Upload className="mr-1 h-3.5 w-3.5" />Stage</Button>
        </div>
      </section>

      <section>
        <h3 className="mb-2 text-[10px] font-semibold uppercase tracking-wide text-muted">Current Staging</h3>
        {staging ? (
          <div className="rounded-xl border border-indigo-500/30 bg-indigo-500/[0.04] p-3">
            <div className="flex items-start gap-3">
              <div className="min-w-0 flex-1">
                <p className="font-mono text-xs text-white">{staging.version}</p>
                <SnapshotMeta release={staging} />
                <p className="mt-2 text-[10px] leading-4 text-muted">Immutable validation snapshot. Create a Release or create and deploy it.</p>
              </div>
              <Badge variant="secondary" className="border-indigo-500/30 text-indigo-300">Staging</Badge>
            </div>
            <div className="mt-3 flex flex-wrap gap-2">
              <Button size="sm" variant="outline" onClick={() => void viewSnapshot(staging)} loading={loadingId === staging.id}><Eye className="mr-1 h-3.5 w-3.5" />View</Button>
              <Button size="sm" variant="outline" onClick={() => setPublishAction('release')}><Package className="mr-1 h-3.5 w-3.5" />Create Release</Button>
              <Button size="sm" onClick={() => setPublishAction('deploy')}><Rocket className="mr-1 h-3.5 w-3.5" />Create & Deploy</Button>
            </div>
          </div>
        ) : <div className="rounded-xl border border-dashed border-border p-3 text-[10px] text-muted">No Agent Staging snapshot.</div>}
      </section>

      <section>
        <h3 className="mb-2 text-[10px] font-semibold uppercase tracking-wide text-muted">Production</h3>
        {production ? (
          <article className="rounded-xl border border-emerald-500/30 bg-emerald-500/[0.04] p-3">
            <div className="flex items-start gap-3">
              <div className="min-w-0 flex-1">
                <p className="font-mono text-xs text-white">{production.version}</p>
                <SnapshotMeta release={production} />
                <p className="mt-1 text-[9px] text-emerald-300">Active in Agent Playground runtime</p>
              </div>
              <Badge variant="success">Production</Badge>
            </div>
            <div className="mt-2"><Button size="sm" variant="outline" onClick={() => void viewSnapshot(production)} loading={loadingId === production.id}><Eye className="mr-1 h-3 w-3" />View details</Button></div>
          </article>
        ) : <div className="rounded-xl border border-dashed border-border p-3 text-[10px] text-muted">No Agent Playground Production is active.</div>}
      </section>

      <section>
        <div className="mb-2 flex items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <Package className="h-3.5 w-3.5 text-primary-light" />
            <h3 className="text-[10px] font-semibold uppercase tracking-wide text-muted">Available Releases</h3>
            <span className="rounded border border-border px-1.5 py-0.5 text-[9px] text-muted">{availableReleases.length}</span>
          </div>
          {availableReleases.length ? <Button size="sm" variant="outline" onClick={() => setReleaseLibraryOpen(true)}>View all</Button> : null}
        </div>
        {visibleAvailableReleases.length ? (
          <div className="space-y-2">
            {visibleAvailableReleases.map((release) => (
              <article
                key={release.id}
                role="button"
                tabIndex={0}
                className="cursor-pointer rounded-xl border border-border bg-background/35 p-3 transition-colors hover:border-primary/30 hover:bg-background/55"
                onClick={() => void viewSnapshot(release)}
                onKeyDown={(event) => {
                  if (event.key === 'Enter' || event.key === ' ') void viewSnapshot(release)
                }}
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
                  <div className="flex shrink-0 flex-wrap gap-2">
                    <Button size="sm" variant="outline" loading={loadingId === release.id} onClick={(event) => { event.stopPropagation(); void viewSnapshot(release) }}><Eye className="mr-1 h-3 w-3" />View</Button>
                    <Button size="sm" onClick={(event) => { event.stopPropagation(); setActivationTarget(release) }}><Rocket className="mr-1 h-3 w-3" />Deploy</Button>
                  </div>
                </div>
              </article>
            ))}
          </div>
        ) : <div className="rounded-xl border border-dashed border-border p-3 text-[10px] text-muted">No Releases are currently available for Production.</div>}
      </section>

      <section>
        <div className="mb-2 flex items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <History className="h-3.5 w-3.5 text-muted" />
            <h3 className="text-[10px] font-semibold uppercase tracking-wide text-muted">Latest Production Changes</h3>
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
                <article
                  key={activation.id}
                  role="button"
                  tabIndex={0}
                  className="cursor-pointer rounded-xl border border-border bg-background/30 p-3 transition-colors hover:border-primary/30 hover:bg-background/50"
                  onClick={() => openProductionChange(activation)}
                  onKeyDown={(event) => {
                    if (event.key === 'Enter' || event.key === ' ') openProductionChange(activation)
                  }}
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
                    <Button size="sm" variant="outline" onClick={(event) => { event.stopPropagation(); openProductionChange(activation) }}>View</Button>
                  </div>
                </article>
              )
            })}
          </div>
        ) : <div className="rounded-xl border border-dashed border-border p-3 text-[10px] text-muted">No Production changes recorded.</div>}
      </section>

      <StageDraftSnapshotModal open={stageOpen} state={state} snapshot={toSnapshot()} currentStaging={staging} isConfirming={createRelease.isPending || promoteRelease.isPending} onClose={() => setStageOpen(false)} onConfirm={() => void stageDraft()} />
      <ReleaseSnapshotModal
        open={Boolean(publishAction)}
        title={publishAction === 'deploy' ? 'Create Release and deploy?' : 'Create immutable Release?'}
        description={publishAction === 'deploy'
          ? sessionModeChange
            ? `Compatibility change: Session Mode will change from ${sessionModeLabel(production?.session_mode)} to ${sessionModeLabel(staging?.session_mode)}. A new major Release will be created and deployed.`
            : 'Create an immutable Release from current Staging and activate it in Agent Playground Production.'
          : 'Create an immutable Release from current Staging without changing the active Production deployment.'}
        release={staging}
        confirmLabel={publishAction === 'deploy' ? 'Create Release & Deploy' : 'Create Release'}
        isConfirming={promoteRelease.isPending}
        onConfirm={() => void createFromStaging()}
        onClose={() => { setPublishAction(null); setReleaseDescription('') }}
        releaseDescription={releaseDescription}
        onReleaseDescriptionChange={setReleaseDescription}
      />
      <ReleaseSnapshotModal open={Boolean(activationTarget)} title="Deploy Release to Agent Production?" description="This changes only the standalone Agent Playground runtime. Existing Network Releases remain pinned to their stored Agent Release IDs." release={activationTarget} confirmLabel="Deploy Release" isConfirming={promoteRelease.isPending} onConfirm={() => void activateRelease()} onClose={() => setActivationTarget(null)} />
      <ReleaseSnapshotModal open={Boolean(snapshot)} title="Agent Release details" description="Operational configuration stored for this immutable version." release={snapshot} onClose={() => setSnapshot(null)} />
      <ReleaseLibraryModal open={releaseLibraryOpen} agentId={agentId} releases={availableReleases} onClose={() => setReleaseLibraryOpen(false)} onDeploy={(release) => setActivationTarget(release)} />
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
