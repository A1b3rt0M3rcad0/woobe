import { useMemo, useState, type ReactNode } from 'react'
import { getRelease } from '@/features/agents/api'
import { useCreateRelease, usePromoteRelease, useReleases, useRollbackRelease } from '@/features/agents/hooks'
import { Button } from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'
import { Skeleton } from '@/components/ui/Skeleton'
import { toast } from 'sonner'
import { CalendarDays, Copy, Eye, FileText, Info, MoreHorizontal, Package, Rocket, Undo2, Upload } from 'lucide-react'
import { releaseToEditorState, useAgentEditor, type AgentEditorState } from '../AgentEditorContext'
import { ReleaseSnapshotModal } from './ReleaseSnapshotModal'
import { StageDraftSnapshotModal } from './StageDraftSnapshotModal'
import type { AgentRelease, ReleaseStatus } from '@/features/agents/types'

const statusVariant: Record<ReleaseStatus, 'success' | 'warning' | 'secondary' | 'default' | 'destructive'> = {
  production: 'success',
  staging: 'secondary',
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
  | { type: 'copy'; release: AgentRelease }
  | null

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

function editorModelLabel(state: AgentEditorState) {
  return `${state.provider || '—'}/${state.model || '—'}`
}

function responseFormatLabel(state: AgentEditorState) {
  if (!state.responseFormat?.enabled) return 'Text'
  return state.responseFormat.type === 'json' ? `JSON${state.responseFormat.strict ? ' strict' : ''}` : 'Text'
}

function ReleaseMetadata({ release }: { release: AgentRelease }) {
  return (
    <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-[11px] text-muted">
      <span className="inline-flex items-center gap-1"><CalendarDays className="h-3 w-3" />{formatDate(release.created_at)}</span>
      <span className="text-border">·</span>
      <span className="inline-flex min-w-0 items-center gap-1"><Package className="h-3 w-3 shrink-0" /><span className="truncate">{modelLabel(release)}</span></span>
    </div>
  )
}

function PipelineHint() {
  return (
    <div className="inline-flex items-center gap-1.5 rounded-md border border-border/80 bg-surface/40 px-2 py-1 text-[10px] font-medium shadow-sm">
      <span className="text-muted">Draft</span><span className="text-muted">→</span><span className="text-indigo-300">Staging</span><span className="text-muted">→</span><span className="text-emerald-400">Production</span>
    </div>
  )
}

function ReleaseActionsMenu({ actions, label = 'Release actions' }: { actions: MenuAction[]; label?: string }) {
  const [open, setOpen] = useState(false)
  if (actions.length === 0) return null
  return (
    <div className="relative shrink-0">
      <button type="button" aria-label={label} aria-expanded={open} className="flex h-7 w-7 items-center justify-center rounded-md border border-transparent text-muted transition-colors hover:border-border/80 hover:bg-background/60 hover:text-white focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-primary" onClick={() => setOpen((value) => !value)}>
        <MoreHorizontal className="h-3.5 w-3.5" />
      </button>
      {open && (
        <div className="absolute right-0 top-8 z-30 w-48 rounded-lg border border-border/90 bg-surface/95 p-1 shadow-2xl shadow-black/30">
          {actions.map((action) => (
            <button key={action.label} type="button" disabled={action.disabled} className={`flex w-full items-center gap-2 rounded-md px-2.5 py-2 text-left text-[11px] transition-colors disabled:pointer-events-none disabled:opacity-50 ${action.destructive ? 'text-red-400 hover:bg-red-500/10 hover:text-red-300' : 'text-slate-200 hover:bg-background/70 hover:text-white'}`} onClick={() => { setOpen(false); action.onClick() }}>
              {action.icon}<span>{action.label}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  )
}

function EmptyStageCard({ message, tone = 'neutral' }: { message: string; tone?: 'neutral' | 'staging' | 'production' }) {
  const toneClass = tone === 'staging' ? 'border-indigo-500/25 bg-indigo-500/[0.04]' : tone === 'production' ? 'border-emerald-500/25 bg-emerald-500/[0.03]' : 'border-border bg-surface/40'
  return <div className={`rounded-lg border p-3 text-xs leading-5 text-muted ${toneClass}`}>{message}</div>
}

function ConfirmReleaseActionModal({ open, title, description, warning, confirmLabel, confirmVariant = 'default', isPending, onClose, onConfirm }: { open: boolean; title: string; description: string; warning?: string; confirmLabel: string; confirmVariant?: 'default' | 'destructive'; isPending?: boolean; onClose: () => void; onConfirm: () => void }) {
  if (!open) return null
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4 backdrop-blur-md">
      <div className="w-full max-w-lg overflow-hidden rounded-2xl border border-border/90 bg-surface/95 shadow-2xl shadow-black/40">
        <div className="space-y-1 border-b border-border/90 bg-background/20 p-5"><h2 className="text-base font-semibold text-white">{title}</h2><p className="text-xs leading-5 text-muted">{description}</p></div>
        {warning && <div className="m-5 rounded-xl border border-yellow-500/30 bg-yellow-500/[0.06] p-3 text-xs leading-5 text-yellow-100">{warning}</div>}
        <div className="flex items-center justify-end gap-2 border-t border-border/90 bg-background/20 p-4"><Button size="sm" variant="outline" onClick={onClose} disabled={isPending}>Cancel</Button><Button size="sm" variant={confirmVariant === 'destructive' ? 'destructive' : 'default'} onClick={onConfirm} loading={isPending}>{confirmLabel}</Button></div>
      </div>
    </div>
  )
}

export function ReleaseTab({ agentId, projectId }: { agentId: string; projectId: string }) {
  const { data: releases, isLoading } = useReleases(agentId)
  const createRelease = useCreateRelease(agentId)
  const promoteRelease = usePromoteRelease(agentId)
  const rollbackRelease = useRollbackRelease(agentId)
  const { state, setState, toSnapshot, setLoadedRelease } = useAgentEditor()
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
  const history = useMemo(() => [...(releases ?? [])].filter((item) => item.status !== 'draft' && item.status !== 'staging' && item.status !== 'production').sort((a, b) => new Date(b.created_at ?? 0).getTime() - new Date(a.created_at ?? 0).getTime()), [releases])
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
      toast.success('Current Draft promoted to Staging')
      return true
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Failed to promote Draft to Staging')
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
      toast.error(error instanceof Error ? error.message : 'Failed to load Staging snapshot')
      return null
    } finally {
      setIsLoadingSnapshot(false)
    }
  }

  async function openViewStaging() {
    const details = await fetchStagingSnapshot()
    if (!details) return
    setSnapshotModal({ open: true, title: 'Current Staging', description: 'Read-only snapshot. It can only change when a new Draft is promoted.', release: details })
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
      await promoteRelease.mutateAsync({ releaseId: activeStaging.id, targetStatus: 'production', copySnapshot: true, releaseNotes: notes || undefined })
      setCreateReleaseOpen(false)
      setReleaseDescription('')
      setStagingSnapshot(null)
      toast.success('Release published to Production')
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Failed to publish release')
    }
  }

  async function deployRelease(release: AgentRelease) {
    if (release.status === 'production') return false
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
    if (release.status === 'production') return false
    try {
      await rollbackRelease.mutateAsync({ releaseId: release.id })
      toast.success(`Rolled back to ${release.version}`)
      return true
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Failed to rollback')
      return false
    }
  }

  async function copyToDraft(release: AgentRelease) {
    setLoadingReleaseId(release.id)
    try {
      const details = await getRelease(agentId, release.id)
      setState(releaseToEditorState(details, state))
      setLoadedRelease(details.id, details.version)
      toast.success(`${details.version} copied to the Draft editor`)
      return true
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Failed to copy release to Draft')
      return false
    } finally {
      setLoadingReleaseId(null)
    }
  }

  async function confirmSelectedAction() {
    const action = confirmAction
    if (!action) return
    let succeeded = false
    if (action.type === 'deploy') succeeded = await deployRelease(action.release)
    if (action.type === 'rollback') succeeded = await rollbackToRelease(action.release)
    if (action.type === 'copy') succeeded = await copyToDraft(action.release)
    if (succeeded) setConfirmAction(null)
  }

  function productionActions(release: AgentRelease): MenuAction[] {
    return [
      { label: 'View snapshot', icon: <Eye className="h-3.5 w-3.5" />, onClick: () => openReleaseSnapshot(release, 'Production release') },
      { label: 'Copy to Draft', icon: <Copy className="h-3.5 w-3.5" />, onClick: () => setConfirmAction({ type: 'copy', release }), disabled: loadingReleaseId === release.id },
    ]
  }

  function historyActions(release: AgentRelease): MenuAction[] {
    return [
      { label: 'View snapshot', icon: <Eye className="h-3.5 w-3.5" />, onClick: () => openReleaseSnapshot(release, `Release ${release.version}`) },
      { label: 'Promote to production', icon: <Rocket className="h-3.5 w-3.5" />, onClick: () => setConfirmAction({ type: 'deploy', release }), disabled: promoteRelease.isPending },
      { label: 'Rollback to this version', icon: <Undo2 className="h-3.5 w-3.5" />, onClick: () => setConfirmAction({ type: 'rollback', release }), disabled: rollbackRelease.isPending },
      { label: 'Copy to Draft', icon: <Copy className="h-3.5 w-3.5" />, onClick: () => setConfirmAction({ type: 'copy', release }), disabled: loadingReleaseId === release.id },
    ]
  }

  if (isLoading) return <div className="space-y-3 p-4"><Skeleton className="h-5 w-32" /><Skeleton className="h-20 w-full rounded-lg" /><Skeleton className="h-24 w-full rounded-lg" /></div>

  const confirmTitle = confirmAction?.type === 'deploy' ? 'Promote this release to production?' : confirmAction?.type === 'rollback' ? 'Rollback production?' : 'Copy this snapshot to Draft?'
  const confirmDescription = confirmAction?.type === 'deploy' ? 'This will make the selected archived release the active production release.' : confirmAction?.type === 'rollback' ? 'This will replace the active production release with the selected historical version.' : 'The source release remains immutable. Its snapshot will replace the current Draft editor state.'
  const confirmWarning = confirmAction?.type === 'deploy' && production ? `Current production ${production.version} will be replaced.` : confirmAction?.type === 'rollback' && production ? `Current production ${production.version} will be replaced.` : confirmAction?.type === 'copy' ? 'Any unsaved Draft changes may be overwritten. Save Draft explicitly after reviewing the copied snapshot.' : undefined
  const confirmLabel = confirmAction?.type === 'deploy' ? 'Promote to production' : confirmAction?.type === 'rollback' ? 'Rollback production' : 'Copy to Draft'
  const confirmPending = confirmAction?.type === 'deploy' ? promoteRelease.isPending : confirmAction?.type === 'rollback' ? rollbackRelease.isPending : confirmAction ? loadingReleaseId === confirmAction.release.id : false

  return (
    <div className="space-y-4 p-4">
      <section className="space-y-3"><div className="flex flex-col gap-3 min-[420px]:flex-row min-[420px]:items-start min-[420px]:justify-between"><div className="space-y-1"><h2 className="text-sm font-medium tracking-tight text-white">Versions</h2><p className="max-w-[18rem] text-xs leading-5 text-muted">Edit Draft, promote an exact snapshot to Staging, then publish Staging to Production.</p></div><PipelineHint /></div></section>
      <div className="h-px bg-border/50" />

      <section className="space-y-3">
        <h3 className="text-[11px] font-medium text-muted">Current draft</h3>
        <div className="rounded-lg border border-border bg-surface/45 p-3"><div className="flex items-start justify-between gap-3"><div className="flex min-w-0 gap-3"><div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg border border-border bg-background/30 text-primary"><FileText className="h-4 w-4" /></div><div className="min-w-0 space-y-1.5"><p className="truncate text-xs font-medium text-white">{state.name || 'Untitled agent'}</p><p className="text-[11px] leading-4 text-muted">The only directly editable environment.</p><div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-[10px] text-muted"><span>{editorModelLabel(state)}</span><span className="text-border">·</span><span>{state.collectionIds?.length ?? 0} collections</span><span className="text-border">·</span><span>{responseFormatLabel(state)}</span></div></div></div><Button size="sm" className="h-7 shrink-0 px-2 text-[11px]" onClick={() => setStageDraftOpen(true)} loading={createRelease.isPending || promoteRelease.isPending}><Upload className="mr-1 h-3 w-3" />Stage draft</Button></div></div>
      </section>

      <div className="h-px bg-border/50" />
      <section className="space-y-3">
        <h3 className="text-[11px] font-medium text-muted">Staging</h3>
        {currentStaging ? <article className="rounded-lg border border-indigo-500/35 bg-indigo-500/[0.04] p-3 shadow-sm"><div className="flex items-start justify-between gap-2.5"><div className="min-w-0 space-y-2"><h4 className="truncate font-mono text-xs font-medium tracking-tight text-white">{currentStaging.version}</h4><ReleaseMetadata release={currentStaging} /><p className="max-w-md text-[11px] leading-4 text-muted">Read-only snapshot. It changes only when a new Draft is promoted.</p><div className="flex flex-wrap gap-2 pt-1"><Button size="sm" variant="outline" className="h-7 min-w-[96px] px-2 text-[11px]" onClick={openViewStaging} loading={isLoadingSnapshot}><Eye className="mr-1 h-3 w-3" />View snapshot</Button><Button size="sm" className="h-7 min-w-[110px] px-2 text-[11px]" onClick={openCreateRelease} loading={promoteRelease.isPending || isLoadingSnapshot}><Rocket className="mr-1 h-3 w-3" />Publish release</Button></div></div><Badge variant="secondary" className="shrink-0 border-indigo-500/35 bg-indigo-500/10 px-1.5 py-0 text-[10px] text-indigo-300">Staging</Badge></div></article> : <EmptyStageCard tone="staging" message="No Staging snapshot yet. Promote the current Draft before publishing." />}
      </section>

      <div className="h-px bg-border/50" />
      <section className="space-y-3">
        <h3 className="text-[11px] font-medium text-muted">Production</h3>
        {production ? <article className="rounded-lg border border-emerald-500/35 bg-emerald-500/[0.03] p-3 shadow-sm"><div className="flex items-start justify-between gap-2.5"><div className="min-w-0 space-y-2"><h4 className="truncate font-mono text-xs font-medium tracking-tight text-white">{production.version}</h4><ReleaseMetadata release={production} /><p className="max-w-md text-[11px] leading-4 text-muted">Immutable active runtime release.</p><div className="flex flex-wrap gap-2 pt-1"><Button size="sm" variant="outline" className="h-7 min-w-[96px] px-2 text-[11px]" onClick={() => openReleaseSnapshot(production, 'Production release')} loading={loadingReleaseId === production.id}><Eye className="mr-1 h-3 w-3" />View snapshot</Button>{rollbackTarget && <Button size="sm" variant="outline" className="h-7 min-w-[118px] border-emerald-500/60 px-2 text-[11px] text-emerald-400 hover:bg-emerald-500/10 hover:text-emerald-300" onClick={() => setConfirmAction({ type: 'rollback', release: rollbackTarget })} loading={rollbackRelease.isPending}><Undo2 className="mr-1 h-3 w-3" />Rollback production</Button>}</div></div><div className="flex shrink-0 items-start gap-2"><Badge variant="success" className="px-1.5 py-0 text-[10px]">Production</Badge><ReleaseActionsMenu actions={productionActions(production)} /></div></div></article> : <EmptyStageCard tone="production" message="No Production release is active yet. Publish Staging to create the first release." />}
      </section>

      <section className="space-y-3"><h3 className="text-[11px] font-medium text-muted">History</h3>{history.length === 0 ? <EmptyStageCard message="No archived releases yet." /> : <div className="space-y-1">{history.map((release) => <div key={release.id} className="relative flex min-h-[60px] items-center justify-between gap-2 rounded-lg border border-border bg-background px-3 py-2.5"><div className="min-w-0 space-y-1"><div className="flex min-w-0 flex-wrap items-center gap-2"><p className="truncate font-mono text-xs font-medium text-white">{release.version}</p><Badge variant={statusVariant[release.status]} className="px-1.5 py-0 text-[10px]">{statusLabel[release.status]}</Badge></div><ReleaseMetadata release={release} /></div><ReleaseActionsMenu actions={historyActions(release)} /></div>)}</div>}</section>

      <p className="flex items-center gap-2 text-[11px] text-muted"><Info className="h-3.5 w-3.5" />All times shown in your local timezone.</p>
      <ReleaseSnapshotModal open={snapshotModal.open} title={snapshotModal.title} description={snapshotModal.description} release={snapshotModal.release} onClose={() => setSnapshotModal((current) => ({ ...current, open: false }))} />
      <ReleaseSnapshotModal open={createReleaseOpen} title="Publish staging release?" description={production ? `Review the exact Staging snapshot that will be published. Current production ${production.version} will be archived.` : 'Review the exact Staging snapshot that will become the first Production release.'} release={currentStaging} confirmLabel="Publish release" isConfirming={promoteRelease.isPending} onConfirm={createReleaseFromStaging} onClose={() => setCreateReleaseOpen(false)} releaseDescription={releaseDescription} onReleaseDescriptionChange={setReleaseDescription} />
      <StageDraftSnapshotModal open={stageDraftOpen} state={state} snapshot={draftSnapshot} currentStaging={currentStaging} isConfirming={createRelease.isPending || promoteRelease.isPending} onClose={() => setStageDraftOpen(false)} onConfirm={confirmStageDraft} />
      {confirmAction && <ConfirmReleaseActionModal open title={confirmTitle} description={confirmDescription} warning={confirmWarning} confirmLabel={confirmLabel} confirmVariant={confirmAction.type === 'rollback' ? 'destructive' : 'default'} isPending={confirmPending} onClose={() => setConfirmAction(null)} onConfirm={confirmSelectedAction} />}
    </div>
  )
}
