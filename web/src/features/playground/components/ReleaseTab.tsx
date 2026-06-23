import { useMemo, useState, type ReactNode } from 'react'
import { getRelease } from '@/features/agents/api'
import { useCreateRelease, useDeleteRelease, usePromoteRelease, useReleases, useRollbackRelease } from '@/features/agents/hooks'
import { Button } from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'
import { Skeleton } from '@/components/ui/Skeleton'
import { cn } from '@/lib/utils'
import { toast } from 'sonner'
import { AlertTriangle, CalendarDays, Eye, FileText, Info, MoreHorizontal, Package, Rocket, Save, Trash2, Undo2, Upload } from 'lucide-react'
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

type ConfirmAction =
  | { type: 'deploy'; release: AgentRelease }
  | { type: 'rollback'; release: AgentRelease }
  | { type: 'load'; release: AgentRelease }
  | null

type ConfirmationDetail = {
  label: string
  value: ReactNode
}

type ConfirmReleaseActionModalProps = {
  open: boolean
  title: string
  description: string
  details: ConfirmationDetail[]
  warning?: string
  confirmLabel: string
  confirmVariant?: 'default' | 'destructive'
  isPending?: boolean
  onClose: () => void
  onConfirm: () => void
}

type DraftSnapshotModalProps = {
  open: boolean
  state: AgentEditorState
  snapshot: Record<string, unknown>
  currentStaging: AgentRelease | null
  isConfirming?: boolean
  onClose: () => void
  onConfirm: () => void
}

type ConfirmModalModel = Omit<ConfirmReleaseActionModalProps, 'open' | 'onClose' | 'onConfirm'>

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

function formatJson(value: unknown) {
  if (!value) return '—'
  try {
    return JSON.stringify(value, null, 2)
  } catch {
    return String(value)
  }
}

function formatValue(value: unknown): string {
  if (value === null || value === undefined || value === '') return '—'
  if (typeof value === 'string') return value
  if (typeof value === 'number' || typeof value === 'boolean') return String(value)
  return formatJson(value)
}

function modelLabel(release: AgentRelease) {
  return `${release.provider ?? '—'}/${release.model ?? '—'}`
}

function editorModelLabel(state: AgentEditorState) {
  return `${state.provider || '—'}/${state.model || '—'}`
}

function responseFormatLabel(state: AgentEditorState) {
  if (!state.responseFormat?.enabled) return 'Text'
  return state.responseFormat.type === 'json' ? `JSON${state.responseFormat.strict ? ' strict' : ''}` : 'Text'
}

function modalRow(label: string, value: unknown) {
  return (
    <div className="grid grid-cols-[96px_1fr] gap-3 text-xs">
      <span className="text-muted">{label}</span>
      <span className="min-w-0 break-words text-slate-200">{formatValue(value)}</span>
    </div>
  )
}

function draftDetails(state: AgentEditorState): ConfirmationDetail[] {
  return [
    { label: 'Agent', value: state.name || 'Untitled agent' },
    { label: 'Model', value: editorModelLabel(state) },
    { label: 'Mode', value: state.sessionMode || '—' },
    { label: 'Temperature', value: state.temperature ?? '—' },
    { label: 'Max tokens', value: state.maxOutputTokens ?? '—' },
    { label: 'Collections', value: state.collectionIds?.length ?? 0 },
    { label: 'Response', value: responseFormatLabel(state) },
  ]
}

function releaseDetails(release: AgentRelease): ConfirmationDetail[] {
  return [
    { label: 'Version', value: release.version },
    { label: 'Model', value: modelLabel(release) },
    { label: 'Created', value: formatDate(release.created_at) },
    { label: 'Collections', value: release.collection_ids?.length ?? 0 },
  ]
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

function ReleaseMetadata({ release }: { release: AgentRelease; compact?: boolean }) {
  return (
    <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-[11px] text-muted">
      <span className="inline-flex items-center gap-1">
        <CalendarDays className="h-3 w-3" />
        {formatDate(release.created_at)}
      </span>
      <span className="text-border">·</span>
      <span className="inline-flex min-w-0 items-center gap-1">
        <Package className="h-3 w-3 shrink-0" />
        <span className="truncate">{modelLabel(release)}</span>
      </span>
    </div>
  )
}

function PipelineHint() {
  return (
    <div className="inline-flex items-center gap-1.5 rounded-md border border-border/80 bg-surface/40 px-2 py-1 text-[10px] font-medium shadow-sm">
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
        className="flex h-7 w-7 items-center justify-center rounded-md text-muted transition-colors hover:bg-accent hover:text-white focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-primary"
        onClick={() => setOpen((value) => !value)}
      >
        <MoreHorizontal className="h-3.5 w-3.5" />
      </button>

      {open && (
        <div className="absolute right-0 top-8 z-30 w-40 rounded-lg border border-border bg-surface p-1 shadow-2xl">
          {enabledActions.map((action) => (
            <button
              key={action.label}
              type="button"
              disabled={action.disabled}
              className={cn(
                'flex w-full items-center gap-2 rounded-md px-2.5 py-2 text-left text-[11px] transition-colors disabled:pointer-events-none disabled:opacity-50',
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
        'rounded-lg border bg-surface/40 p-3 text-xs leading-5 text-muted',
        tone === 'staging' && 'border-yellow-500/25 bg-yellow-500/[0.03]',
        tone === 'production' && 'border-emerald-500/25 bg-emerald-500/[0.03]',
        tone === 'neutral' && 'border-border',
      )}
    >
      {message}
    </div>
  )
}

function ConfirmReleaseActionModal({ open, title, description, details, warning, confirmLabel, confirmVariant = 'default', isPending, onClose, onConfirm }: ConfirmReleaseActionModalProps) {
  if (!open) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
      <div className="w-full max-w-lg overflow-hidden rounded-2xl border border-border bg-surface shadow-2xl">
        <div className="space-y-1 border-b border-border p-5">
          <h2 className="text-base font-semibold text-white">{title}</h2>
          <p className="text-xs leading-5 text-muted">{description}</p>
        </div>

        <div className="space-y-4 p-5">
          {warning && (
            <div className="flex gap-2 rounded-xl border border-yellow-500/30 bg-yellow-500/[0.06] p-3 text-xs leading-5 text-yellow-100">
              <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0 text-yellow-400" />
              <p>{warning}</p>
            </div>
          )}

          <section className="space-y-2 rounded-xl border border-border bg-background/40 p-4">
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-300">What will be applied</p>
            <div className="space-y-2">
              {details.map((detail) => (
                <div key={detail.label} className="grid grid-cols-[96px_1fr] gap-3 text-xs">
                  <span className="text-muted">{detail.label}</span>
                  <span className="min-w-0 break-words text-slate-200">{detail.value}</span>
                </div>
              ))}
            </div>
          </section>
        </div>

        <div className="flex items-center justify-end gap-2 border-t border-border p-4">
          <Button size="sm" variant="outline" onClick={onClose} disabled={isPending}>Cancel</Button>
          <Button size="sm" variant={confirmVariant === 'destructive' ? 'destructive' : 'default'} onClick={onConfirm} loading={isPending}>{confirmLabel}</Button>
        </div>
      </div>
    </div>
  )
}

function DraftSnapshotModal({ open, state, snapshot, currentStaging, isConfirming, onClose, onConfirm }: DraftSnapshotModalProps) {
  if (!open) return null
  const outputSchema = snapshot.output_schema ?? state.outputSchema ?? state.responseFormat?.schema

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
      <div className="max-h-[86vh] w-full max-w-2xl overflow-hidden rounded-2xl border border-border bg-surface shadow-2xl">
        <div className="flex items-start justify-between gap-4 border-b border-border p-5">
          <div className="space-y-1">
            <div className="flex flex-wrap items-center gap-2">
              <h2 className="text-base font-semibold text-white">Stage current draft?</h2>
              <Badge variant="secondary">Current draft</Badge>
            </div>
            <p className="text-xs leading-5 text-muted">Review the editor configuration that will be copied into staging.</p>
          </div>
        </div>

        <div className="max-h-[60vh] space-y-5 overflow-y-auto p-5">
          {currentStaging && (
            <div className="flex gap-2 rounded-xl border border-yellow-500/30 bg-yellow-500/[0.06] p-3 text-xs leading-5 text-yellow-100">
              <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0 text-yellow-400" />
              <p>This will replace the current staging snapshot: {currentStaging.version}.</p>
            </div>
          )}

          <section className="space-y-2 rounded-xl border border-border bg-background/40 p-4">
            <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-slate-300"><FileText className="h-3.5 w-3.5" />Agent snapshot</div>
            {modalRow('Name', state.name || 'Untitled agent')}
            {modalRow('Model', editorModelLabel(state))}
            {modalRow('Status', state.status)}
            {modalRow('Mode', state.sessionMode)}
            {modalRow('Temp', state.temperature)}
            {modalRow('Max tokens', state.maxOutputTokens)}
            {modalRow('Response', responseFormatLabel(state))}
          </section>

          <section className="space-y-2 rounded-xl border border-border bg-background/40 p-4">
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-300">System prompt</p>
            <pre className="max-h-44 overflow-auto whitespace-pre-wrap rounded-lg bg-black/20 p-3 text-xs text-slate-200">{state.systemPrompt || '—'}</pre>
          </section>

          <section className="space-y-2 rounded-xl border border-border bg-background/40 p-4">
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-300">Output / schema</p>
            <pre className="max-h-44 overflow-auto whitespace-pre-wrap rounded-lg bg-black/20 p-3 text-xs text-slate-200">{formatJson(outputSchema ?? snapshot.response_format)}</pre>
          </section>

          <section className="space-y-2 rounded-xl border border-border bg-background/40 p-4">
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-300">Runtime / knowledge</p>
            {modalRow('Collections', state.collectionIds?.length ? `${state.collectionIds.length}` : '—')}
            <pre className="max-h-40 overflow-auto whitespace-pre-wrap rounded-lg bg-black/20 p-3 text-xs text-slate-200">{formatJson(snapshot.runtime_config ?? state.runtimeConfig)}</pre>
          </section>
        </div>

        <div className="flex items-center justify-end gap-2 border-t border-border p-4">
          <Button size="sm" variant="outline" onClick={onClose} disabled={isConfirming}>Cancel</Button>
          <Button size="sm" onClick={onConfirm} loading={isConfirming}>Stage draft</Button>
        </div>
      </div>
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
  const [stageDraftOpen, setStageDraftOpen] = useState(false)
  const [confirmAction, setConfirmAction] = useState<ConfirmAction>(null)
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
  const currentStaging = stagingSnapshot ?? staging ?? null
  const draftSnapshot = toSnapshot()

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
      return true
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Failed to promote draft to staging')
      return false
    }
  }

  async function confirmStageDraft() {
    const succeeded = await promoteDraftToStaging()
    if (succeeded) setStageDraftOpen(false)
  }

  async function fetchStagingSnapshot() {
    const activeStaging = stagingSnapshot ?? staging
    if (!activeStaging) return null
    setIsLoadingSnapshot(true)
    try {
      const details = await getRelease(agentId, activeStaging.id)
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
    const activeStaging = stagingSnapshot ?? staging
    if (!activeStaging) return
    try {
      const notes = releaseDescription.trim()
      await promoteRelease.mutateAsync({
        releaseId: activeStaging.id,
        targetStatus: 'production',
        copySnapshot: true,
        releaseNotes: notes || undefined,
      })
      setCreateReleaseOpen(false)
      setReleaseDescription('')
      setStagingSnapshot(null)
      toast.success('Release published to production')
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Failed to publish release')
    }
  }

  async function deployRelease(release: AgentRelease) {
    if (release.status === 'production') {
      toast.info(`${release.version} is already in production`)
      return false
    }
    try {
      await promoteRelease.mutateAsync({ releaseId: release.id, targetStatus: 'production', copySnapshot: false, restoreExistingVersion: true })
      toast.success(`${release.version} deployed`)
      return true
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Failed to deploy release')
      return false
    }
  }

  async function rollbackToRelease(release: AgentRelease) {
    if (release.status === 'production') {
      toast.info(`${release.version} is already in production`)
      return false
    }
    try {
      await rollbackRelease.mutateAsync({ releaseId: release.id })
      toast.success(`Rolled back to ${release.version}`)
      return true
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Failed to rollback')
      return false
    }
  }

  async function loadForEditing(release: AgentRelease) {
    setLoadingReleaseId(release.id)
    try {
      const details = await getRelease(agentId, release.id)
      setState(releaseToEditorState(details, state))
      setLoadedRelease(details.id, details.version)
      toast.success(`${details.version} loaded for editing`)
      return true
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Failed to load release for editing')
      return false
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

  async function confirmSelectedAction() {
    const action = confirmAction
    if (!action) return

    let succeeded = false
    if (action.type === 'deploy') succeeded = await deployRelease(action.release)
    if (action.type === 'rollback') succeeded = await rollbackToRelease(action.release)
    if (action.type === 'load') succeeded = await loadForEditing(action.release)

    if (succeeded) setConfirmAction(null)
  }

  function productionActions(release: AgentRelease): MenuAction[] {
    return [
      { label: 'View snapshot', icon: <Eye className="h-3.5 w-3.5" />, onClick: () => openReleaseSnapshot(release, 'Production release') },
      { label: 'Load for editing', icon: <Save className="h-3.5 w-3.5" />, onClick: () => setConfirmAction({ type: 'load', release }), disabled: loadingReleaseId === release.id },
      { label: 'Delete', icon: <Trash2 className="h-3.5 w-3.5" />, onClick: () => setDeleteTarget(release), destructive: true },
    ]
  }

  function historyActions(release: AgentRelease): MenuAction[] {
    return [
      { label: 'View snapshot', icon: <Eye className="h-3.5 w-3.5" />, onClick: () => openReleaseSnapshot(release, `Release ${release.version}`) },
      { label: 'Promote to production', icon: <Rocket className="h-3.5 w-3.5" />, onClick: () => setConfirmAction({ type: 'deploy', release }), disabled: promoteRelease.isPending },
      { label: 'Rollback to this version', icon: <Undo2 className="h-3.5 w-3.5" />, onClick: () => setConfirmAction({ type: 'rollback', release }), disabled: rollbackRelease.isPending },
      { label: 'Load for editing', icon: <Save className="h-3.5 w-3.5" />, onClick: () => setConfirmAction({ type: 'load', release }), disabled: loadingReleaseId === release.id },
      { label: 'Delete', icon: <Trash2 className="h-3.5 w-3.5" />, onClick: () => setDeleteTarget(release), destructive: true },
    ]
  }

  function confirmModalProps(): ConfirmModalModel | null {
    if (!confirmAction) return null

    if (confirmAction.type === 'deploy') {
      return {
        title: 'Promote this release to production?',
        description: 'This will make the selected archived release the active production release.',
        warning: production ? `Current production ${production.version} will be replaced.` : undefined,
        details: releaseDetails(confirmAction.release),
        confirmLabel: 'Promote to production',
        isPending: promoteRelease.isPending,
      }
    }

    if (confirmAction.type === 'rollback') {
      return {
        title: 'Rollback production?',
        description: 'This will replace the active production release with the selected historical version.',
        warning: production ? `Current production ${production.version} will be replaced by ${confirmAction.release.version}.` : undefined,
        details: releaseDetails(confirmAction.release),
        confirmLabel: 'Rollback production',
        confirmVariant: 'destructive' as const,
        isPending: rollbackRelease.isPending,
      }
    }

    return {
      title: 'Load this release into the editor?',
      description: 'This will replace the current editor draft with the selected release snapshot.',
      warning: 'Any unsaved editor changes may be overwritten.',
      details: releaseDetails(confirmAction.release),
      confirmLabel: 'Load for editing',
      isPending: loadingReleaseId === confirmAction.release.id,
    }
  }

  if (isLoading) {
    return (
      <div className="space-y-3 p-4">
        <Skeleton className="h-5 w-32" />
        <Skeleton className="h-20 w-full rounded-lg" />
        <Skeleton className="h-24 w-full rounded-lg" />
      </div>
    )
  }

  const confirmModal = confirmModalProps()

  return (
    <div className="space-y-4 p-4">
      <section className="space-y-3">
        <div className="flex flex-col gap-3 min-[420px]:flex-row min-[420px]:items-start min-[420px]:justify-between">
          <div className="space-y-1">
            <h2 className="text-sm font-medium tracking-tight text-white">Versions</h2>
            <p className="max-w-[18rem] text-xs leading-5 text-muted">
              Move the current draft through staging into production.
            </p>
          </div>
          <PipelineHint />
        </div>
      </section>

      <div className="h-px bg-border/50" />

      <section className="space-y-3">
        <h3 className="text-[11px] font-medium text-muted">Current draft</h3>
        <div className="rounded-lg border border-border bg-surface/45 p-3">
          <div className="flex items-start justify-between gap-3">
            <div className="flex min-w-0 gap-3">
              <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg border border-border bg-background/30 text-primary">
                <FileText className="h-4 w-4" />
              </div>
              <div className="min-w-0 space-y-1.5">
                <p className="truncate text-xs font-medium text-white">{state.name || 'Untitled agent'}</p>
                <p className="text-[11px] leading-4 text-muted">Current editor configuration. This has not been staged yet.</p>
                <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-[10px] text-muted">
                  <span>{editorModelLabel(state)}</span>
                  <span className="text-border">·</span>
                  <span>{state.sessionMode || '—'}</span>
                  <span className="text-border">·</span>
                  <span>{state.collectionIds?.length ?? 0} collections</span>
                  <span className="text-border">·</span>
                  <span>{responseFormatLabel(state)}</span>
                </div>
              </div>
            </div>
            <Button
              size="sm"
              className="h-7 shrink-0 px-2 text-[11px]"
              onClick={() => setStageDraftOpen(true)}
              loading={createRelease.isPending || promoteRelease.isPending}
            >
              <Upload className="mr-1 h-3 w-3" />
              Stage draft
            </Button>
          </div>
        </div>
      </section>

      <div className="h-px bg-border/50" />

      <section className="space-y-3">
        <h3 className="text-[11px] font-medium text-muted">Staging</h3>
        {currentStaging ? (
          <article className="rounded-lg border border-yellow-500/35 bg-yellow-500/[0.03] p-3 shadow-sm">
            <div className="flex items-start justify-between gap-2.5">
              <div className="min-w-0 space-y-2">
                <h4 className="truncate font-mono text-xs font-medium tracking-tight text-white">{currentStaging.version}</h4>
                <ReleaseMetadata release={currentStaging} />
                <p className="max-w-md text-[11px] leading-4 text-muted">This is the candidate snapshot. View the model and configuration before publishing.</p>
                <div className="flex flex-wrap gap-2 pt-1">
                  <Button size="sm" variant="outline" className="h-7 min-w-[96px] px-2 text-[11px]" onClick={openViewStaging} loading={isLoadingSnapshot}>
                    <Eye className="mr-1 h-3 w-3" />
                    View snapshot
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    className="h-7 min-w-[112px] border-yellow-500/60 px-2 text-[11px] text-yellow-400 hover:bg-yellow-500/10 hover:text-yellow-300"
                    onClick={openCreateRelease}
                    loading={promoteRelease.isPending || isLoadingSnapshot}
                  >
                    <Rocket className="mr-1 h-3 w-3" />
                    Publish release
                  </Button>
                </div>
              </div>
              <Badge variant="warning" className="shrink-0 px-1.5 py-0 text-[10px]">Staging</Badge>
            </div>
          </article>
        ) : (
          <EmptyStageCard tone="staging" message="No staging snapshot yet. Review the current draft and stage it before publishing." />
        )}
      </section>

      <div className="h-px bg-border/50" />

      <section className="space-y-3">
        <h3 className="text-[11px] font-medium text-muted">Production</h3>
        {production ? (
          <article className="rounded-lg border border-emerald-500/35 bg-emerald-500/[0.03] p-3 shadow-sm">
            <div className="flex items-start justify-between gap-2.5">
              <div className="min-w-0 space-y-2">
                <h4 className="truncate font-mono text-xs font-medium tracking-tight text-white">{production.version}</h4>
                <ReleaseMetadata release={production} />
                <p className="max-w-md text-[11px] leading-4 text-muted">This is the active runtime release used in production context.</p>
                <div className="flex flex-wrap gap-2 pt-1">
                  <Button size="sm" variant="outline" className="h-7 min-w-[96px] px-2 text-[11px]" onClick={() => openReleaseSnapshot(production, 'Production release')} loading={loadingReleaseId === production.id}>
                    <Eye className="mr-1 h-3 w-3" />
                    View snapshot
                  </Button>
                  {rollbackTarget && (
                    <Button
                      size="sm"
                      variant="outline"
                      className="h-7 min-w-[118px] border-emerald-500/60 px-2 text-[11px] text-emerald-400 hover:bg-emerald-500/10 hover:text-emerald-300"
                      onClick={() => setConfirmAction({ type: 'rollback', release: rollbackTarget })}
                      loading={rollbackRelease.isPending}
                    >
                      <Undo2 className="mr-1 h-3 w-3" />
                      Rollback production
                    </Button>
                  )}
                </div>
              </div>
              <div className="flex shrink-0 items-start gap-2">
                <Badge variant="success" className="px-1.5 py-0 text-[10px]">Production</Badge>
                <ReleaseActionsMenu actions={productionActions(production)} />
              </div>
            </div>
          </article>
        ) : (
          <EmptyStageCard tone="production" message="No production release is active yet. Publish staging to create the first production version." />
        )}
      </section>

      <section className="space-y-3">
        <h3 className="text-[11px] font-medium text-muted">History</h3>
        {history.length === 0 ? (
          <EmptyStageCard message="No archived releases yet." />
        ) : (
          <div className="space-y-1">
            {history.map((release) => (
              <div key={release.id} className="relative flex min-h-[60px] items-center justify-between gap-2 rounded-lg border border-border bg-background px-3 py-2.5">
                <div className="min-w-0 space-y-1">
                  <div className="flex min-w-0 flex-wrap items-center gap-2">
                    <p className="truncate font-mono text-xs font-medium text-white">{release.version}</p>
                    <Badge variant={statusVariant[release.status]} className="px-1.5 py-0 text-[10px]">{statusLabel[release.status]}</Badge>
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
        title="Publish staging release?"
        description={production ? `Review the model and snapshot that will be published. Current production ${production.version} will be archived.` : 'Review the model and snapshot that will become the first production release.'}
        release={currentStaging}
        confirmLabel="Publish release"
        isConfirming={promoteRelease.isPending}
        onConfirm={createReleaseFromStaging}
        onClose={() => setCreateReleaseOpen(false)}
        releaseDescription={releaseDescription}
        onReleaseDescriptionChange={setReleaseDescription}
      />
      <DraftSnapshotModal
        open={stageDraftOpen}
        state={state}
        snapshot={draftSnapshot}
        currentStaging={currentStaging}
        isConfirming={createRelease.isPending || promoteRelease.isPending}
        onClose={() => setStageDraftOpen(false)}
        onConfirm={confirmStageDraft}
      />
      {confirmModal && (
        <ConfirmReleaseActionModal
          open={confirmAction !== null}
          title={confirmModal.title}
          description={confirmModal.description}
          details={confirmModal.details}
          warning={confirmModal.warning}
          confirmLabel={confirmModal.confirmLabel}
          confirmVariant={confirmModal.confirmVariant}
          isPending={confirmModal.isPending}
          onClose={() => setConfirmAction(null)}
          onConfirm={confirmSelectedAction}
        />
      )}
      <ConfirmDeleteModal open={deleteTarget !== null} onClose={() => setDeleteTarget(null)} onConfirm={confirmDelete} versionName={deleteTarget?.version ?? ''} isPending={deleteRelease.isPending} />
    </div>
  )
}
