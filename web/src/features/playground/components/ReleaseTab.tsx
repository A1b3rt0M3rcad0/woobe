import { useMemo, useState, type ReactNode } from 'react'
import { getRelease } from '@/features/agents/api'
import { useCreateRelease, useDeleteRelease, usePromoteRelease, useReleases, useRollbackRelease } from '@/features/agents/hooks'
import { Button } from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'
import { Skeleton } from '@/components/ui/Skeleton'
import { cn } from '@/lib/utils'
import { toast } from 'sonner'
import { CalendarDays, ChevronRight, Eye, FileText, Info, MoreHorizontal, Package, Rocket, Save, Trash2, Undo2, Upload } from 'lucide-react'
import { useAgentEditor, type AgentEditorState } from '../AgentEditorContext'
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

const statusLabel: Record<ReleaseStatus, string> = {
  production: 'Production',
  staging: 'Staging',
  draft: 'Draft',
  archived: 'Archived',
  rolled_back: 'Rolled back',
}

type SnapshotModalState = {
  open: boolean
  title: string
  description?: string
  release: AgentRelease | null
}

type MenuAction = {
  label: string
  icon: ReactNode
  onClick: () => void
  destructive?: boolean
  disabled?: boolean
}

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

function modelLabel(release: AgentRelease) {
  return `${release.provider ?? '—'}/${release.model ?? '—'}`
}

function releaseToEditorState(release: AgentRelease, current: AgentEditorState): AgentEditorState {
  const rf = release.response_format as Record<string, unknown> | undefined
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
      repair_attempts: rf?.repair_attempts as number | undefined,
    },
    outputSchema: release.output_schema ?? current.outputSchema,
  }
}

function ReleaseMetadata({ release, compact = false }: { release: AgentRelease; compact?: boolean }) {
  return (
    <div className={cn('flex flex-wrap items-center gap-x-3 gap-y-1 text-muted', compact ? 'text-[11px]' : 'text-xs')}>
      <span className="inline-flex items-center gap-1.5">
        <CalendarDays className="h-3.5 w-3.5" />
        {formatDate(release.created_at)}
      </span>
      <span className="text-border">|</span>
      <span className="inline-flex min-w-0 items-center gap-1.5">
        <Package className="h-3.5 w-3.5 shrink-0" />
        <span className="truncate">{modelLabel(release)}</span>
      </span>
    </div>
  )
}

function PipelineHint() {
  return (
    <div className="inline-flex items-center gap-2 rounded-lg border border-border/80 bg-surface/40 px-3 py-2 text-xs font-medium shadow-sm">
      <span className="text-muted">Draft</span>
      <span className="text-muted">→</span>
      <span className="text-yellow-400">Staging</span>
      <span className="text-muted">→</span>
      <span className="text-emerald-400">Production</span>
    </div>
  )
}

function ReleaseActionsMenu({ actions, label = 'Release actions' }: { actions: MenuAction[]; label?: string }) {
  const [open, setOpen] = useState(false)
  const enabledActions = actions.filter(Boolean)

  if (enabledActions.length === 0) return null

  return (
    <div className="relative shrink-0">
      <button
        type="button"
        aria-label={label}
        aria-expanded={open}
        className="flex h-9 w-9 items-center justify-center rounded-lg text-muted transition-colors hover:bg-accent hover:text-white focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-primary"
        onClick={() => setOpen((value) => !value)}
      >
        <MoreHorizontal className="h-4 w-4" />
      </button>

      {open && (
        <div className="absolute right-0 top-10 z-30 w-44 rounded-xl border border-border bg-surface p-1 shadow-2xl">
          {enabledActions.map((action) => (
            <button
              key={action.label}
              type="button"
              disabled={action.disabled}
              className={cn(
                'flex w-full items-center gap-2 rounded-lg px-3 py-2 text-left text-xs transition-colors disabled:pointer-events-none disabled:opacity-50',
                action.destructive ? 'text-red-400 hover:bg-red-500/10 hover:text-red-300' : 'text-slate-200 hover:bg-accent hover:text-white',
              )}
              onClick={() => {
                setOpen(false)
                action.onClick()
              }}
            >
              {action.icon}
              <span>{action.label}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  )
}

function EmptyStageCard({ message, tone = 'neutral' }: { message: string; tone?: 'neutral' | 'staging' | 'production' }) {
  return (
    <div
      className={cn(
        'rounded-2xl border bg-surface/40 p-4 text-sm text-muted',
        tone === 'staging' && 'border-yellow-500/25 bg-yellow-500/[0.03]',
        tone === 'production' && 'border-emerald-500/25 bg-emerald-500/[0.03]',
        tone === 'neutral' && 'border-border',
      )}
    >
      {message}
    </div>
  )
}

export function ReleaseTab({ agentId, projectId }: { agentId: string; projectId: string }) {
  const { data: releases, isLoading } = useReleases(agentId)
  const createRelease = useCreateRelease(agentId)
  const promoteRelease = usePromoteRelease(agentId)
  const rollbackRelease = useRollbackRelease(agentId)
  const deleteRelease = useDeleteRelease(agentId)
  const { state, setState, toSnapshot, setLoadedRelease } = useAgentEditor()
  const [deleteTarget, setDeleteTarget] = useState<AgentRelease | null>(null)
  const [createReleaseOpen, setCreateReleaseOpen] = useState(false)
  const [stagingSnapshot, setStagingSnapshot] = useState<AgentRelease | null>(null)
  const [isLoadingSnapshot, setIsLoadingSnapshot] = useState(false)
  const [loadingReleaseId, setLoadingReleaseId] = useState<string | null>(null)
  const [releaseDescription, setReleaseDescription] = useState('')
  const [snapshotModal, setSnapshotModal] = useState<SnapshotModalState>({ open: false, title: 'Release snapshot', release: null })

  const staging = useMemo(() => releases?.find((item) => item.status === 'staging'), [releases])
  const production = useMemo(() => releases?.find((item) => item.status === 'production'), [releases])
  const history = useMemo(() => {
    return [...(releases ?? [])]
      .filter((item) => item.status !== 'draft' && item.status !== 'staging' && item.status !== 'production')
      .sort((a, b) => new Date(b.created_at ?? 0).getTime() - new Date(a.created_at ?? 0).getTime())
  }, [releases])
  const rollbackTarget = useMemo(() => history.find((item) => item.status === 'archived' || item.status === 'rolled_back'), [history])

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
    if (!details) return
    setSnapshotModal({
      open: true,
      title: 'Current staging',
      description: 'This is the single staging snapshot used by API/runtime when execution_context=staging.',
      release: details,
    })
  }

  async function openReleaseSnapshot(release: AgentRelease, title = 'Release snapshot') {
    setLoadingReleaseId(release.id)
    try {
      const details = await getRelease(agentId, release.id)
      setSnapshotModal({ open: true, title, description: 'Review the immutable snapshot stored for this version.', release: details })
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Failed to load release snapshot')
    } finally {
      setLoadingReleaseId(null)
    }
  }

  async function openCreateRelease() {
    const details = await fetchStagingSnapshot()
    if (details) {
      setReleaseDescription('')
      setCreateReleaseOpen(true)
    }
  }

  async function createReleaseFromStaging() {
    const currentStaging = stagingSnapshot ?? staging
    if (!currentStaging) return
    try {
      const notes = releaseDescription.trim()
      await promoteRelease.mutateAsync({
        releaseId: currentStaging.id,
        targetStatus: 'production',
        copySnapshot: true,
        releaseNotes: notes || undefined,
      })
      setCreateReleaseOpen(false)
      setReleaseDescription('')
      setStagingSnapshot(null)
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

  async function loadForEditing(release: AgentRelease) {
    setLoadingReleaseId(release.id)
    try {
      const details = await getRelease(agentId, release.id)
      setState(releaseToEditorState(details, state))
      setLoadedRelease(details.id, details.version)
      toast.success(`${details.version} loaded for editing`)
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Failed to load release for editing')
    } finally {
      setLoadingReleaseId(null)
    }
  }

  async function confirmDelete() {
    if (!deleteTarget) return
    try {
      await deleteRelease.mutateAsync({ releaseId: deleteTarget.id })
      toast.success(`${deleteTarget.version} deleted`)
      setDeleteTarget(null)
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Failed to delete release')
    }
  }

  function productionActions(release: AgentRelease): MenuAction[] {
    return [
      { label: 'View snapshot', icon: <Eye className="h-3.5 w-3.5" />, onClick: () => openReleaseSnapshot(release, 'Production release') },
      { label: 'Load for editing', icon: <Save className="h-3.5 w-3.5" />, onClick: () => loadForEditing(release), disabled: loadingReleaseId === release.id },
      { label: 'Delete', icon: <Trash2 className="h-3.5 w-3.5" />, onClick: () => setDeleteTarget(release), destructive: true },
    ]
  }

  function historyActions(release: AgentRelease): MenuAction[] {
    return [
      { label: 'View snapshot', icon: <Eye className="h-3.5 w-3.5" />, onClick: () => openReleaseSnapshot(release, `Release ${release.version}`) },
      { label: 'Promote to production', icon: <Rocket className="h-3.5 w-3.5" />, onClick: () => deployRelease(release), disabled: promoteRelease.isPending },
      { label: 'Rollback to this version', icon: <Undo2 className="h-3.5 w-3.5" />, onClick: () => rollbackToRelease(release), disabled: rollbackRelease.isPending },
      { label: 'Load for editing', icon: <Save className="h-3.5 w-3.5" />, onClick: () => loadForEditing(release), disabled: loadingReleaseId === release.id },
      { label: 'Delete', icon: <Trash2 className="h-3.5 w-3.5" />, onClick: () => setDeleteTarget(release), destructive: true },
    ]
  }

  if (isLoading) {
    return (
      <div className="space-y-3 p-4">
        <Skeleton className="h-5 w-32" />
        <Skeleton className="h-20 w-full rounded-xl" />
        <Skeleton className="h-28 w-full rounded-xl" />
      </div>
    )
  }

  const currentStaging = stagingSnapshot ?? staging ?? null
  const hasStaging = Boolean(currentStaging)

  return (
    <div className="space-y-4 p-4">
      <section className="space-y-3">
        <div className="flex flex-col gap-3 min-[420px]:flex-row min-[420px]:items-start min-[420px]:justify-between">
          <div className="space-y-1">
            <h2 className="text-sm font-medium tracking-tight text-white">Versions</h2>
            <p className="max-w-[18rem] text-xs leading-5 text-muted">
              Promote snapshots from draft to staging, then publish one production release.
            </p>
          </div>
          <PipelineHint />
        </div>

        <div className="flex flex-col gap-2 min-[420px]:flex-row">
          <Button className="h-8 min-w-32 text-[11px]" onClick={promoteDraftToStaging} loading={createRelease.isPending || promoteRelease.isPending}>
            <Upload className="mr-1.5 h-3 w-3" />
            Stage draft
          </Button>
          <Button className="h-8 min-w-36 text-[11px]" variant="outline" onClick={openViewStaging} disabled={!hasStaging} loading={isLoadingSnapshot}>
            <Eye className="mr-1.5 h-3 w-3" />
            View staging
          </Button>
        </div>
      </section>

      <div className="h-px bg-border/70" />

      <section className="space-y-3">
        <h3 className="text-sm font-semibold text-muted">A) Current draft</h3>
        <div className="flex min-h-24 items-center justify-between gap-4 rounded-2xl border border-border bg-surface/45 p-4">
          <div className="flex min-w-0 items-center gap-4">
            <div className="flex h-16 w-16 shrink-0 items-center justify-center rounded-xl border border-border bg-background/30 text-primary">
              <FileText className="h-7 w-7" />
            </div>
            <div className="min-w-0 space-y-1">
              <p className="text-base font-semibold text-white">Editor snapshot</p>
              <p className="text-sm text-muted">Unstaged changes from the editor</p>
            </div>
          </div>
          <ChevronRight className="h-5 w-5 shrink-0 text-muted" />
        </div>
      </section>

      <div className="h-px bg-border/70" />

      <section className="space-y-3">
        <h3 className="text-sm font-semibold text-muted">B) Staging</h3>
        {currentStaging ? (
          <article className="rounded-2xl border border-yellow-500/45 bg-yellow-500/[0.035] p-4 shadow-sm">
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0 space-y-3">
                <h4 className="truncate font-mono text-xl font-semibold tracking-tight text-white">{currentStaging.version}</h4>
                <ReleaseMetadata release={currentStaging} />
                <div className="flex flex-wrap gap-2 pt-1">
                  <Button size="sm" variant="outline" className="min-w-24" onClick={openViewStaging} loading={isLoadingSnapshot}>
                    <Eye className="mr-2 h-3.5 w-3.5" />
                    View
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    className="min-w-28 border-yellow-500/60 text-yellow-400 hover:bg-yellow-500/10 hover:text-yellow-300"
                    onClick={openCreateRelease}
                    loading={promoteRelease.isPending || isLoadingSnapshot}
                  >
                    <Upload className="mr-2 h-3.5 w-3.5" />
                    Publish
                  </Button>
                </div>
              </div>
              <Badge variant="warning" className="shrink-0 px-3 py-1 text-sm">Staging</Badge>
            </div>
          </article>
        ) : (
          <EmptyStageCard tone="staging" message="No staging snapshot yet. Stage the current draft before publishing." />
        )}
      </section>

      <div className="h-px bg-border/70" />

      <section className="space-y-3">
        <h3 className="text-sm font-semibold text-muted">C) Production</h3>
        {production ? (
          <article className="rounded-2xl border border-emerald-500/45 bg-emerald-500/[0.035] p-4 shadow-sm">
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0 space-y-3">
                <h4 className="truncate font-mono text-xl font-semibold tracking-tight text-white">{production.version}</h4>
                <ReleaseMetadata release={production} />
                <div className="flex flex-wrap gap-2 pt-1">
                  <Button size="sm" variant="outline" className="min-w-24" onClick={() => openReleaseSnapshot(production, 'Production release')} loading={loadingReleaseId === production.id}>
                    <Eye className="mr-2 h-3.5 w-3.5" />
                    View
                  </Button>
                  {rollbackTarget && (
                    <Button
                      size="sm"
                      variant="outline"
                      className="min-w-28 border-emerald-500/60 text-emerald-400 hover:bg-emerald-500/10 hover:text-emerald-300"
                      onClick={() => rollbackToRelease(rollbackTarget)}
                      loading={rollbackRelease.isPending}
                    >
                      <Undo2 className="mr-2 h-3.5 w-3.5" />
                      Rollback
                    </Button>
                  )}
                </div>
              </div>
              <div className="flex shrink-0 items-start gap-2">
                <Badge variant="success" className="px-3 py-1 text-sm">Production</Badge>
                <ReleaseActionsMenu actions={productionActions(production)} />
              </div>
            </div>
          </article>
        ) : (
          <EmptyStageCard tone="production" message="No production release is active yet. Publish staging to create the first production version." />
        )}
      </section>

      <section className="space-y-3">
        <h3 className="text-sm font-semibold text-muted">D) History</h3>
        {history.length === 0 ? (
          <EmptyStageCard message="No archived releases yet." />
        ) : (
          <div className="rounded-2xl border border-border bg-surface/35">
            {history.map((release, index) => (
              <div key={release.id} className={cn('relative flex min-h-[82px] items-center justify-between gap-3 px-4 py-3', index !== history.length - 1 && 'border-b border-border/70')}>
                <div className="min-w-0 space-y-1">
                  <div className="flex min-w-0 flex-wrap items-center gap-2">
                    <p className="truncate font-mono text-base font-semibold text-white">{release.version}</p>
                    <Badge variant={statusVariant[release.status]}>{statusLabel[release.status]}</Badge>
                  </div>
                  <ReleaseMetadata release={release} compact />
                </div>
                <div className="flex shrink-0 items-center gap-2">
                  <ReleaseActionsMenu actions={historyActions(release)} />
                </div>
              </div>
            ))}
          </div>
        )}
      </section>

      <p className="flex items-center gap-2 text-[11px] text-muted">
        <Info className="h-3.5 w-3.5" />
        All times shown in your local timezone.
      </p>

      <ReleaseSnapshotModal
        open={snapshotModal.open}
        title={snapshotModal.title}
        description={snapshotModal.description}
        release={snapshotModal.release}
        onClose={() => setSnapshotModal((current) => ({ ...current, open: false }))}
      />
      <ReleaseSnapshotModal
        open={createReleaseOpen}
        title="Create release from staging"
        description="Review the current staging snapshot before creating a production release."
        release={currentStaging}
        confirmLabel="Create Release"
        isConfirming={promoteRelease.isPending}
        onConfirm={createReleaseFromStaging}
        onClose={() => setCreateReleaseOpen(false)}
        releaseDescription={releaseDescription}
        onReleaseDescriptionChange={setReleaseDescription}
      />
      <ConfirmDeleteModal open={deleteTarget !== null} onClose={() => setDeleteTarget(null)} onConfirm={confirmDelete} versionName={deleteTarget?.version ?? ''} isPending={deleteRelease.isPending} />
    </div>
  )
}
