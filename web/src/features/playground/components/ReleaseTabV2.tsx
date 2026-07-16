import { useMemo, useState } from 'react'
import { Copy, Eye, FileText, Package, Rocket, Upload } from 'lucide-react'
import { toast } from 'sonner'

import { Button } from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'
import { Skeleton } from '@/components/ui/Skeleton'
import { getRelease } from '@/features/agents/api'
import { useCreateRelease, usePromoteRelease, useReleases } from '@/features/agents/hooks'
import type { AgentRelease } from '@/features/agents/types'
import { releaseToEditorState, useAgentEditor } from '../AgentEditorContext'
import { ReleaseSnapshotModal } from './ReleaseSnapshotModal'
import { StageDraftSnapshotModal } from './StageDraftSnapshotModal'

function formatDate(value?: string) {
  if (!value) return '—'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '—'
  return new Intl.DateTimeFormat('pt-BR', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  }).format(date).replace(',', '')
}

function SnapshotMeta({ release }: { release: AgentRelease }) {
  return <p className="mt-1 text-[10px] text-muted">{release.provider ?? '—'}/{release.model ?? '—'} · {formatDate(release.created_at)}</p>
}

export function ReleaseTab({ agentId, projectId }: { agentId: string; projectId: string }) {
  const { data: releases = [], isLoading } = useReleases(agentId)
  const createRelease = useCreateRelease(agentId)
  const promoteRelease = usePromoteRelease(agentId)
  const { state, setState, toSnapshot, setLoadedRelease } = useAgentEditor()
  const [stageOpen, setStageOpen] = useState(false)
  const [publishOpen, setPublishOpen] = useState(false)
  const [releaseDescription, setReleaseDescription] = useState('')
  const [activationTarget, setActivationTarget] = useState<AgentRelease | null>(null)
  const [snapshot, setSnapshot] = useState<AgentRelease | null>(null)
  const [loadingId, setLoadingId] = useState<string | null>(null)

  const staging = useMemo(
    () => releases.find((item) => item.status === 'staging') ?? null,
    [releases],
  )
  const production = useMemo(
    () => releases.find((item) => item.status === 'production') ?? null,
    [releases],
  )
  const available = useMemo(
    () => releases
      .filter((item) => item.snapshot_kind === 'release' && item.status !== 'production')
      .sort((a, b) => new Date(b.created_at ?? 0).getTime() - new Date(a.created_at ?? 0).getTime()),
    [releases],
  )

  const stageDraft = async () => {
    try {
      const draft = await createRelease.mutateAsync({
        project_id: projectId,
        agent_id: agentId,
        version: 'draft',
        ...toSnapshot(),
      } as any)
      await promoteRelease.mutateAsync({
        releaseId: draft.id,
        targetStatus: 'staging',
        copySnapshot: true,
      })
      setStageOpen(false)
      toast.success('Current Draft promoted to Staging')
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Failed to promote Draft to Staging')
    }
  }

  const publishAndActivate = async () => {
    if (!staging) return
    try {
      await promoteRelease.mutateAsync({
        releaseId: staging.id,
        targetStatus: 'production',
        copySnapshot: true,
        releaseNotes: releaseDescription.trim() || undefined,
      })
      setPublishOpen(false)
      setReleaseDescription('')
      toast.success('Agent Release created and activated in Playground Production')
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Failed to publish Agent Release')
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

  const copyToDraft = async (release: AgentRelease) => {
    setLoadingId(release.id)
    try {
      const details = await getRelease(agentId, release.id)
      setState(releaseToEditorState(details, state))
      setLoadedRelease(details.id, details.version)
      toast.success(`${details.version} copied to the Draft editor`)
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Failed to copy Agent Release to Draft')
    } finally {
      setLoadingId(null)
    }
  }

  if (isLoading) {
    return <div className="space-y-3 p-4"><Skeleton className="h-5 w-32" /><Skeleton className="h-20 w-full rounded-lg" /><Skeleton className="h-24 w-full rounded-lg" /></div>
  }

  return (
    <div className="space-y-4 p-4">
      <div>
        <h2 className="text-sm font-medium text-white">Versions</h2>
        <p className="mt-1 text-[11px] leading-5 text-muted">Draft → Staging → Release. Production is an explicit activation of an existing Release.</p>
      </div>

      <section className="rounded-xl border border-border bg-surface/45 p-3">
        <div className="flex items-start gap-3">
          <div className="flex h-9 w-9 items-center justify-center rounded-lg border border-border bg-background/40"><FileText className="h-4 w-4 text-primary-light" /></div>
          <div className="min-w-0 flex-1"><p className="text-xs font-medium text-white">Current Draft</p><p className="mt-1 text-[10px] text-muted">Mutable configuration · {state.provider || '—'}/{state.model || '—'}</p></div>
          <Button size="sm" className="h-8 text-[10px]" onClick={() => setStageOpen(true)}><Upload className="mr-1 h-3.5 w-3.5" />Stage</Button>
        </div>
      </section>

      <section>
        <h3 className="mb-2 text-[10px] font-semibold uppercase tracking-wide text-muted">Staging</h3>
        {staging ? <div className="rounded-xl border border-indigo-500/30 bg-indigo-500/[0.04] p-3">
          <div className="flex items-start gap-3"><div className="min-w-0 flex-1"><p className="font-mono text-xs text-white">{staging.version}</p><SnapshotMeta release={staging} /><p className="mt-2 text-[10px] leading-4 text-muted">Immutable validation snapshot.</p></div><Badge variant="secondary" className="border-indigo-500/30 text-indigo-300">Staging</Badge></div>
          <div className="mt-3 flex gap-2"><Button size="sm" variant="outline" onClick={() => void viewSnapshot(staging)} loading={loadingId === staging.id}><Eye className="mr-1 h-3.5 w-3.5" />View</Button><Button size="sm" onClick={() => setPublishOpen(true)}><Rocket className="mr-1 h-3.5 w-3.5" />Create Release and activate</Button></div>
        </div> : <div className="rounded-xl border border-dashed border-border p-3 text-[10px] text-muted">No Agent Staging snapshot.</div>}
      </section>

      <section>
        <div className="mb-2 flex items-center gap-2"><h3 className="text-[10px] font-semibold uppercase tracking-wide text-muted">Available Releases</h3><span className="rounded border border-border px-1.5 py-0.5 text-[9px] text-muted">{available.length}</span></div>
        <p className="mb-2 text-[10px] leading-4 text-muted">Releases created by a Network appear here, but do not change Agent Playground Production.</p>
        {available.length ? <div className="space-y-2">{available.map((release) => <article key={release.id} className="rounded-xl border border-border bg-background/35 p-3"><div className="flex items-start gap-3"><Package className="mt-0.5 h-4 w-4 text-primary-light" /><div className="min-w-0 flex-1"><p className="font-mono text-xs text-white">{release.version}</p><SnapshotMeta release={release} /><p className="mt-1 text-[9px] text-slate-300">Available · not active in Playground</p></div><Button size="sm" onClick={() => setActivationTarget(release)}>Set as Production</Button></div><div className="mt-2 flex gap-2"><Button size="sm" variant="outline" onClick={() => void viewSnapshot(release)} loading={loadingId === release.id}><Eye className="mr-1 h-3 w-3" />View</Button><Button size="sm" variant="outline" onClick={() => void copyToDraft(release)} loading={loadingId === release.id}><Copy className="mr-1 h-3 w-3" />Copy to Draft</Button></div></article>)}</div> : <div className="rounded-xl border border-dashed border-border p-3 text-[10px] text-muted">No available Releases.</div>}
      </section>

      <section>
        <h3 className="mb-2 text-[10px] font-semibold uppercase tracking-wide text-muted">Production</h3>
        {production ? <article className="rounded-xl border border-emerald-500/30 bg-emerald-500/[0.04] p-3"><div className="flex items-start gap-3"><div className="min-w-0 flex-1"><p className="font-mono text-xs text-white">{production.version}</p><SnapshotMeta release={production} /><p className="mt-1 text-[9px] text-emerald-300">Active in Agent Playground runtime</p></div><Badge variant="success">Production</Badge></div><div className="mt-2"><Button size="sm" variant="outline" onClick={() => void viewSnapshot(production)} loading={loadingId === production.id}><Eye className="mr-1 h-3 w-3" />View snapshot</Button></div></article> : <div className="rounded-xl border border-dashed border-border p-3 text-[10px] text-muted">No Agent Playground Production is active.</div>}
      </section>

      <StageDraftSnapshotModal open={stageOpen} state={state} snapshot={toSnapshot()} currentStaging={staging} isConfirming={createRelease.isPending || promoteRelease.isPending} onClose={() => setStageOpen(false)} onConfirm={() => void stageDraft()} />
      <ReleaseSnapshotModal open={publishOpen} title="Create and activate Agent Release?" description="A new immutable Release will be created from Staging and explicitly activated in Agent Playground Production." release={staging} confirmLabel="Create Release and activate" isConfirming={promoteRelease.isPending} onConfirm={() => void publishAndActivate()} onClose={() => setPublishOpen(false)} releaseDescription={releaseDescription} onReleaseDescriptionChange={setReleaseDescription} />
      <ReleaseSnapshotModal open={Boolean(activationTarget)} title="Set Release as Agent Production?" description="This changes only the standalone Agent Playground runtime. Existing Network Releases remain pinned to their stored Agent Release IDs." release={activationTarget} confirmLabel="Set as Production" isConfirming={promoteRelease.isPending} onConfirm={() => void activateRelease()} onClose={() => setActivationTarget(null)} />
      <ReleaseSnapshotModal open={Boolean(snapshot)} title="Agent Release snapshot" description="Immutable configuration stored for this version." release={snapshot} onClose={() => setSnapshot(null)} />
    </div>
  )
}
