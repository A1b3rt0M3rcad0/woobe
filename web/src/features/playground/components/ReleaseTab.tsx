import { useMemo, useState } from 'react'
import { getRelease } from '@/features/agents/api'
import { useCreateRelease, useDeleteRelease, usePromoteRelease, useReleases, useRollbackRelease } from '@/features/agents/hooks'
import { Button } from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'
import { Skeleton } from '@/components/ui/Skeleton'
import { toast } from 'sonner'
import { Archive, CheckCircle2, Circle, Eye, FileText, Rocket, Save, Undo2, Upload } from 'lucide-react'
import { useAgentEditor } from '../AgentEditorContext'
import { ConfirmDeleteModal } from './ConfirmDeleteModal'
import { ReleaseSnapshotModal } from './ReleaseSnapshotModal'
import type { AgentRelease, ReleaseStatus } from '@/features/agents/types'

const statusVariant: Record<ReleaseStatus, 'success' | 'warning' | 'secondary' | 'default' | 'destructive'> = {
  production: 'success',
  staging: 'warning',
  draft: 'secondary',
  archived: 'default',
  rolled_back: 'destructive',
}

function formatDate(value?: string) {
  return value ? new Date(value).toLocaleString() : '—'
}

function releaseToEditorState(release: AgentRelease, current: any) {
  const rf = release.response_format as any
  return {
    ...current,
    name: release.name ?? current.name,
    description: release.description ?? current.description,
    systemPrompt: release.system_prompt ?? current.systemPrompt,
    provider: release.provider ?? current.provider,
    model: release.model ?? current.model,
    providerCredentialId: release.provider_credential_id ?? current.providerCredentialId,
    fallbackProvider: release.fallback_provider ?? current.fallbackProvider,
    fallbackModel: release.fallback_model ?? current.fallbackModel,
    fallbackProviderCredentialId: release.fallback_credential_id ?? current.fallbackProviderCredentialId,
    baseUrl: release.base_url ?? current.baseUrl,
    temperature: release.temperature ?? current.temperature,
    maxOutputTokens: release.max_output_tokens ?? current.maxOutputTokens,
    sessionMode: (release.session_mode as 'stateful' | 'stateless') ?? current.sessionMode,
    status: (release.agent_status as 'active' | 'inactive') ?? current.status,
    collectionIds: release.collection_ids ?? current.collectionIds,
    runtimeConfig: release.runtime_config ?? current.runtimeConfig,
    responseFormat: {
      enabled: Boolean(rf?.enabled ?? release.output_schema),
      type: rf?.type === 'json' ? 'json' : 'text',
      strict: Boolean(rf?.strict),
      schema: rf?.schema ?? release.output_schema ?? null,
      repair_attempts: rf?.repair_attempts,
    },
    outputSchema: release.output_schema ?? current.outputSchema,
  }
}

export function ReleaseTab({ agentId, projectId }: { agentId: string; projectId: string }) {
  const { data: releases, isLoading } = useReleases(agentId)
  const createRelease = useCreateRelease(agentId)
  const promoteRelease = usePromoteRelease(agentId)
  const rollbackRelease = useRollbackRelease(agentId)
  const deleteRelease = useDeleteRelease(agentId)
  const { state, setState, toSnapshot, setLoadedRelease } = useAgentEditor()
  const [deleteTarget, setDeleteTarget] = useState<AgentRelease | null>(null)
  const [viewStagingOpen, setViewStagingOpen] = useState(false)
  const [createReleaseOpen, setCreateReleaseOpen] = useState(false)
  const [stagingSnapshot, setStagingSnapshot] = useState<AgentRelease | null>(null)
  const [isLoadingSnapshot, setIsLoadingSnapshot] = useState(false)

  const staging = useMemo(() => releases?.find((item) => item.status === 'staging'), [releases])
  const releaseHistory = useMemo(() => {
    return [...(releases ?? [])]
      .filter((item) => item.status !== 'draft' && item.status !== 'staging')
      .sort((a, b) => {
        if (a.status === 'production' && b.status !== 'production') return -1
        if (b.status === 'production' && a.status !== 'production') return 1
        return new Date(b.created_at ?? 0).getTime() - new Date(a.created_at ?? 0).getTime()
      })
  }, [releases])

  async function saveDraftFromEditor() {
    const snapshot = toSnapshot()
    return createRelease.mutateAsync({ project_id: projectId, agent_id: agentId, version: 'draft', ...snapshot } as any)
  }

  async function promoteDraftToStaging() {
    try {
      const currentDraft = await saveDraftFromEditor()
      const saved = await promoteRelease.mutateAsync({ releaseId: currentDraft.id, targetStatus: 'staging', copySnapshot: true })
      setStagingSnapshot(saved)
      toast.success('Current draft promoted to staging')
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Failed to promote draft to staging')
    }
  }

  async function fetchStagingSnapshot() {
    const currentStaging = stagingSnapshot ?? staging
    if (!currentStaging) return null
    setIsLoadingSnapshot(true)
    try {
      const details = await getRelease(agentId, currentStaging.id)
      setStagingSnapshot(details)
      return details
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Failed to load staging snapshot')
      return null
    } finally {
      setIsLoadingSnapshot(false)
    }
  }

  async function openViewStaging() {
    const details = await fetchStagingSnapshot()
    if (details) setViewStagingOpen(true)
  }

  async function openCreateRelease() {
    const details = await fetchStagingSnapshot()
    if (details) setCreateReleaseOpen(true)
  }

  async function createReleaseFromStaging() {
    const currentStaging = stagingSnapshot ?? staging
    if (!currentStaging) return
    try {
      await promoteRelease.mutateAsync({ releaseId: currentStaging.id, targetStatus: 'production', copySnapshot: true })
      setCreateReleaseOpen(false)
      toast.success('Release created from current staging')
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Failed to create release')
    }
  }

  async function deployRelease(release: AgentRelease) {
    if (release.status === 'production') {
      toast.info(`${release.version} is already in production`)
      return
    }
    try {
      await promoteRelease.mutateAsync({ releaseId: release.id, targetStatus: 'production', copySnapshot: false, restoreExistingVersion: true })
      toast.success(`${release.version} deployed`)
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Failed to deploy release')
    }
  }

  async function rollbackToRelease(release: AgentRelease) {
    if (release.status === 'production') {
      toast.info(`${release.version} is already in production`)
      return
    }
    try {
      await rollbackRelease.mutateAsync({ releaseId: release.id })
      toast.success(`Rolled back to ${release.version}`)
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Failed to rollback')
    }
  }

  function loadForEditing(release: AgentRelease) {
    setState(releaseToEditorState(release, state))
    setLoadedRelease(release.id, release.version)
    toast.success(`${release.version} loaded for editing`)
  }

  async function confirmDelete() {
    if (!deleteTarget) return
    await deleteRelease.mutateAsync({ releaseId: deleteTarget.id })
    toast.success(`${deleteTarget.version} deleted`)
    setDeleteTarget(null)
  }

  if (isLoading) {
    return <div className="p-4 space-y-4"><Skeleton className="h-5 w-48" /><Skeleton className="h-32 w-full" /></div>
  }

  const hasStaging = Boolean(stagingSnapshot ?? staging)

  return <div className="p-4 space-y-5">
    <section className="space-y-2">
      <h3 className="text-sm font-semibold text-white">Quick actions</h3>
      <p className="text-xs text-muted">Draft stays in the Editor. Promote the current editor snapshot to the single staging slot.</p>
      <div className="rounded-xl border border-border bg-surface p-3">
        <Button size="sm" className="w-full" onClick={promoteDraftToStaging} loading={createRelease.isPending || promoteRelease.isPending}>
          <Upload className="mr-1.5 h-4 w-4" />Promote current Draft to Staging
        </Button>
      </div>
    </section>

    <section className="space-y-2">
      <h3 className="text-sm font-semibold text-white">Current staging</h3>
      <div className="rounded-xl border border-yellow-500/30 bg-yellow-500/[0.04] p-3 space-y-2">
        <div className="flex items-center justify-between gap-2"><p className="truncate text-xs text-muted">{hasStaging ? 'Staging ready' : 'No staging available'}</p>{hasStaging && <Badge variant="warning">Staging</Badge>}</div>
        <Button size="sm" variant="outline" className="w-full" onClick={openViewStaging} disabled={!hasStaging} loading={isLoadingSnapshot}><Eye className="mr-1 h-3 w-3" />View Staging</Button>
      </div>
    </section>

    <section className="space-y-3">
      <div className="flex items-center justify-between gap-3">
        <div><h3 className="text-sm font-semibold text-white">Releases</h3><p className="text-xs text-muted">Only published releases are listed here. New Release opens a staging review first.</p></div>
        <Button size="sm" variant="outline" onClick={openCreateRelease} disabled={!hasStaging} loading={promoteRelease.isPending || isLoadingSnapshot}>
          <Rocket className="mr-1.5 h-4 w-4" />New Release
        </Button>
      </div>

      {releaseHistory.length === 0 ? <div className="rounded-xl border border-border bg-surface p-6 text-center text-sm text-muted">No releases yet.</div> : releaseHistory.map((release) => {
        const isProduction = release.status === 'production'
        return <article key={release.id} className={`rounded-xl border p-4 space-y-3 ${isProduction ? 'border-emerald-500/50 bg-emerald-500/[0.06]' : 'border-border bg-surface'}`}>
          {isProduction && <p className="text-[10px] font-semibold uppercase tracking-wide text-emerald-300">In use today</p>}
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0 space-y-1">
              <div className="flex items-center gap-2"><h4 className="truncate font-semibold text-white">{release.version}</h4><Badge variant={statusVariant[release.status]} className="capitalize">{release.status.replace('_', ' ')}</Badge></div>
              <p className="text-[10px] text-muted">{formatDate(release.created_at)}</p>
              <p className="text-[11px] text-muted"><FileText className="inline h-3 w-3 mr-1" />{release.name ?? 'Unnamed'}</p>
              <p className="text-[11px] text-muted">Model: {release.provider}/{release.model ?? '—'}</p>
            </div>
            {isProduction ? <CheckCircle2 className="h-4 w-4 text-emerald-400 shrink-0" /> : <Circle className="h-4 w-4 text-muted shrink-0" />}
          </div>
          <div className="grid grid-cols-2 gap-2">
            <Button size="sm" variant="outline" onClick={() => deployRelease(release)} disabled={isProduction} loading={promoteRelease.isPending}><Rocket className="mr-1 h-3 w-3" />{isProduction ? 'In use' : 'Deploy'}</Button>
            <Button size="sm" variant="outline" onClick={() => rollbackToRelease(release)} disabled={isProduction} loading={rollbackRelease.isPending}><Undo2 className="mr-1 h-3 w-3" />Rollback</Button>
            <Button size="sm" variant="outline" onClick={() => loadForEditing(release)}><Save className="mr-1 h-3 w-3" />Load for editing</Button>
            <Button size="sm" variant="ghost" className="text-red-400 hover:text-red-300" onClick={() => setDeleteTarget(release)}><Archive className="mr-1 h-3 w-3" />Delete</Button>
          </div>
        </article>
      })}
      <p className="text-[11px] text-muted">Releases are created from the current staging version.</p>
    </section>

    <ReleaseSnapshotModal open={viewStagingOpen} title="Current Staging" description="This is the single staging snapshot used by API/runtime when execution_context=staging." release={stagingSnapshot ?? staging ?? null} onClose={() => setViewStagingOpen(false)} />
    <ReleaseSnapshotModal open={createReleaseOpen} title="Create Release from Staging" description="Review the current staging snapshot before creating a production release." release={stagingSnapshot ?? staging ?? null} confirmLabel="Create Release" isConfirming={promoteRelease.isPending} onConfirm={createReleaseFromStaging} onClose={() => setCreateReleaseOpen(false)} />
    <ConfirmDeleteModal open={deleteTarget !== null} onClose={() => setDeleteTarget(null)} onConfirm={confirmDelete} versionName={deleteTarget?.version ?? ''} isPending={deleteRelease.isPending} />
  </div>
}
