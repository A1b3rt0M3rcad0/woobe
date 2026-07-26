import { useEffect, useMemo, useState } from 'react'
import { Activity, ArrowRight, FilePenLine, History, Layers3, Rocket, ShieldCheck } from 'lucide-react'
import { useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'

import { Badge } from '@/components/ui/Badge'
import { Dialog } from '@/components/ui/Dialog'
import { ScrollArea } from '@/components/ui/ScrollArea'
import { Textarea } from '@/components/ui/Textarea'
import { rollbackRelease } from '@/features/agents/api'
import { useCreateRelease, usePromoteRelease, useReleaseActivations, useReleases } from '@/features/agents/hooks'
import type { AgentRelease, AgentReleaseActivation, RuntimeEnvironment } from '@/features/agents/types'
import { cn } from '@/lib/utils'
import { useAgentEditor } from '../AgentEditorContext'
import { ReleaseDetailsView } from './ReleaseDetailsView'
import { activationLabel, formatReleaseDate, sessionModeLabel } from './releasePresentation'

export type AgentManagerSection = 'draft' | 'staging' | 'production' | 'releases' | 'activity'
export type AgentManagerMode = 'browse' | 'stage' | 'publish' | 'activate' | 'rollback'

type ActivationWithDescription = AgentReleaseActivation & { change_description?: string | null }

type AgentManagerModalProps = {
  open: boolean
  agentId: string
  agentName: string
  projectId: string
  environment: RuntimeEnvironment
  initialSection?: AgentManagerSection
  initialMode?: AgentManagerMode
  onClose: () => void
  onEnvironmentChange: (environment: RuntimeEnvironment) => void
}

function releaseTime(release: AgentRelease) {
  const value = release.created_at ?? release.promoted_at
  const parsed = value ? new Date(value).getTime() : 0
  return Number.isNaN(parsed) ? 0 : parsed
}

function SectionButton({ active, icon: Icon, label, detail, onClick }: { active: boolean; icon: typeof History; label: string; detail: string; onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        'rounded-xl border px-3 py-2.5 text-left transition-colors',
        active ? 'border-primary/35 bg-primary/10' : 'border-transparent hover:border-border hover:bg-background/45',
      )}
    >
      <span className="flex items-center gap-2 text-[10px] font-semibold text-white"><Icon className="h-3.5 w-3.5" />{label}</span>
      <span className="mt-1 block truncate text-[9px] text-muted">{detail}</span>
    </button>
  )
}

function ReleaseList({ releases, selectedId, productionId, onSelect }: { releases: AgentRelease[]; selectedId: string | null; productionId?: string; onSelect: (release: AgentRelease) => void }) {
  if (!releases.length) return <div className="p-4 text-[10px] text-muted">No immutable Agent Releases are available.</div>
  return (
    <div className="space-y-2 p-3">
      {releases.map((release) => (
        <button
          key={release.id}
          type="button"
          onClick={() => onSelect(release)}
          className={cn('w-full rounded-xl border p-3 text-left transition-colors', selectedId === release.id ? 'border-primary/35 bg-primary/10' : 'border-border/70 bg-background/35 hover:border-primary/25')}
        >
          <div className="flex items-center justify-between gap-2">
            <span className="font-mono text-[10px] text-white">{release.version}</span>
            {release.id === productionId ? <Badge variant="success" className="text-[8px]">Production</Badge> : null}
          </div>
          <p className="mt-1 truncate text-[9px] text-muted">{release.provider ?? '—'}/{release.model ?? '—'}</p>
          <p className="mt-1 text-[8px] text-muted">{sessionModeLabel(release.session_mode)} · {formatReleaseDate(release.created_at)}</p>
        </button>
      ))}
    </div>
  )
}

function ActivityList({ activations, releasesById, selectedId, onSelect }: { activations: ActivationWithDescription[]; releasesById: Map<string, AgentRelease>; selectedId: string | null; onSelect: (activation: ActivationWithDescription) => void }) {
  if (!activations.length) return <div className="p-4 text-[10px] text-muted">No Production activity recorded.</div>
  return (
    <div className="space-y-2 p-3">
      {activations.map((activation) => {
        const current = releasesById.get(activation.release_id)
        const previous = activation.previous_release_id ? releasesById.get(activation.previous_release_id) : null
        return (
          <button key={activation.id} type="button" onClick={() => onSelect(activation)} className={cn('w-full rounded-xl border p-3 text-left', selectedId === activation.id ? 'border-primary/35 bg-primary/10' : 'border-border/70 bg-background/35 hover:border-primary/25')}>
            <div className="flex items-center gap-2"><Badge variant={activation.action === 'rollback' ? 'warning' : activation.action === 'deploy' ? 'success' : 'secondary'} className="text-[8px]">{activationLabel(activation.action)}</Badge><span className="text-[8px] text-muted">{formatReleaseDate(activation.created_at)}</span></div>
            <div className="mt-2 flex items-center gap-1 font-mono text-[9px] text-slate-300"><span>{previous?.version ?? 'None'}</span><ArrowRight className="h-3 w-3 text-muted" /><span className="text-white">{current?.version ?? activation.release_id.slice(0, 8)}</span></div>
          </button>
        )
      })}
    </div>
  )
}

export function AgentManagerModal({ open, agentId, agentName, projectId, environment, initialSection, initialMode = 'browse', onClose, onEnvironmentChange }: AgentManagerModalProps) {
  const { data: releases = [] } = useReleases(agentId)
  const { data: rawActivations = [] } = useReleaseActivations(agentId)
  const activations = rawActivations as ActivationWithDescription[]
  const createRelease = useCreateRelease(agentId)
  const promoteRelease = usePromoteRelease(agentId)
  const queryClient = useQueryClient()
  const { state, toSnapshot, isDirty } = useAgentEditor()

  const draft = useMemo(() => releases.find((release) => release.status === 'draft') ?? null, [releases])
  const staging = useMemo(() => releases.find((release) => release.status === 'staging') ?? null, [releases])
  const production = useMemo(() => releases.find((release) => release.status === 'production') ?? null, [releases])
  const immutableReleases = useMemo(() => releases.filter((release) => release.snapshot_kind === 'release').sort((a, b) => releaseTime(b) - releaseTime(a)), [releases])
  const rollbackCandidates = useMemo(() => immutableReleases.filter((release) => release.id !== production?.id), [immutableReleases, production?.id])
  const releasesById = useMemo(() => new Map(releases.map((release) => [release.id, release])), [releases])

  const [section, setSection] = useState<AgentManagerSection>('draft')
  const [mode, setMode] = useState<AgentManagerMode>('browse')
  const [selectedReleaseId, setSelectedReleaseId] = useState<string | null>(null)
  const [selectedActivationId, setSelectedActivationId] = useState<string | null>(null)
  const [releaseDescription, setReleaseDescription] = useState('')
  const [actionReason, setActionReason] = useState('')
  const [rollbackPending, setRollbackPending] = useState(false)

  useEffect(() => {
    if (!open) return
    const nextSection = initialSection ?? (environment === 'draft' ? 'draft' : environment === 'staging' ? 'staging' : 'production')
    setSection(initialMode === 'rollback' || initialMode === 'activate' ? 'releases' : nextSection)
    setMode(initialMode)
    setReleaseDescription('')
    setActionReason('')
    setSelectedActivationId(null)
    if (initialMode !== 'rollback' && initialMode !== 'activate') setSelectedReleaseId(null)
  }, [environment, initialMode, initialSection, open])

  useEffect(() => {
    if (!open || mode !== 'rollback' || selectedReleaseId || !rollbackCandidates.length) return
    const latestActivation = activations[0]
    const preferred = latestActivation?.previous_release_id ? releasesById.get(latestActivation.previous_release_id) : null
    const target = preferred && preferred.id !== production?.id ? preferred : rollbackCandidates[0]
    setSelectedReleaseId(target?.id ?? null)
    if (target) setActionReason(`Rollback Agent Production from ${production?.version ?? 'current Production'} to ${target.version}.`)
  }, [activations, mode, open, production?.id, production?.version, releasesById, rollbackCandidates, selectedReleaseId])

  const selectedRelease = selectedReleaseId ? releasesById.get(selectedReleaseId) ?? null : null
  const selectedActivation = selectedActivationId ? activations.find((item) => item.id === selectedActivationId) ?? null : null
  const pending = createRelease.isPending || promoteRelease.isPending || rollbackPending

  const selectSection = (next: AgentManagerSection) => {
    setSection(next)
    setMode('browse')
    setSelectedReleaseId(null)
    setSelectedActivationId(null)
    setReleaseDescription('')
    setActionReason('')
  }

  const stageDraft = async () => {
    if (isDirty) {
      toast.info('Save the Agent Draft before creating Staging')
      return
    }
    try {
      const savedDraft = await createRelease.mutateAsync({ project_id: projectId, agent_id: agentId, version: 'draft', ...toSnapshot() } as any)
      const result = await promoteRelease.mutateAsync({ releaseId: savedDraft.id, targetStatus: 'staging', copySnapshot: true })
      setSection('staging')
      setMode('browse')
      onEnvironmentChange('staging')
      toast.success(`${result.version} created as current Staging`)
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Failed to stage Agent Draft')
    }
  }

  const publishRelease = async () => {
    if (!staging || releaseDescription.trim().length < 3) return
    try {
      const description = releaseDescription.trim()
      const result = await promoteRelease.mutateAsync({ releaseId: staging.id, targetStatus: 'production', copySnapshot: true, releaseNotes: description, changeDescription: description })
      setReleaseDescription('')
      setSection('production')
      setMode('browse')
      onEnvironmentChange('production')
      toast.success(`${result.version} published to Agent Production`)
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Failed to publish Agent Release')
    }
  }

  const reactivateRelease = async () => {
    if (!selectedRelease || actionReason.trim().length < 3) return
    try {
      await promoteRelease.mutateAsync({ releaseId: selectedRelease.id, targetStatus: 'production', copySnapshot: false, restoreExistingVersion: true, changeDescription: actionReason.trim() })
      setActionReason('')
      setSection('production')
      setMode('browse')
      onEnvironmentChange('production')
      toast.success(`${selectedRelease.version} activated in Agent Production`)
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Failed to activate Agent Release')
    }
  }

  const rollbackProduction = async () => {
    if (!selectedRelease || actionReason.trim().length < 3) return
    setRollbackPending(true)
    try {
      await rollbackRelease(agentId, selectedRelease.id, { changeDescription: actionReason.trim() })
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ['releases', agentId] }),
        queryClient.invalidateQueries({ queryKey: ['release-activations', agentId] }),
        queryClient.invalidateQueries({ queryKey: ['agent', agentId] }),
      ])
      setActionReason('')
      setSection('production')
      setMode('browse')
      onEnvironmentChange('production')
      toast.success(`${selectedRelease.version} restored by rollback`)
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Failed to rollback Agent Production')
    } finally {
      setRollbackPending(false)
    }
  }

  const openActivation = (release: AgentRelease, nextMode: 'activate' | 'rollback') => {
    setSelectedReleaseId(release.id)
    setMode(nextMode)
    setActionReason(nextMode === 'rollback'
      ? `Rollback Agent Production from ${production?.version ?? 'current Production'} to ${release.version}.`
      : `Activate ${release.version} in Agent Production.`)
  }

  const selectedEnvironmentRelease = section === 'draft' ? draft : section === 'staging' ? staging : section === 'production' ? production : null

  return (
    <Dialog open={open} onClose={onClose} title="Manage Agent" className="max-h-[90svh] max-w-[1120px] overflow-hidden" contentClassName="p-0">
      <div className="grid h-[calc(90svh-5rem)] max-h-[760px] grid-rows-[auto_minmax(0,1fr)_auto] overflow-hidden">
        <header className="flex items-center gap-3 border-b border-border bg-background/25 px-4 py-3">
          <div className="flex h-9 w-9 items-center justify-center rounded-xl border border-primary/25 bg-primary/10 text-primary-light"><History className="h-4 w-4" /></div>
          <div className="min-w-0"><p className="truncate text-[12px] font-semibold text-white">{agentName}</p><p className="mt-0.5 text-[9px] text-muted">Draft, Staging, immutable Releases, Production and activation history.</p></div>
          <span className="ml-auto rounded-lg border border-emerald-500/25 bg-emerald-500/10 px-2.5 py-1 font-mono text-[9px] text-emerald-300">{production ? `Production · ${production.version}` : 'No Production'}</span>
        </header>

        <div className="grid min-h-0 overflow-hidden lg:grid-cols-[210px_270px_minmax(0,1fr)]">
          <ScrollArea orientation="both" className="border-b border-border bg-surface/30 lg:border-b-0 lg:border-r">
            <nav className="flex min-w-max gap-2 p-3 lg:min-w-0 lg:flex-col">
              <SectionButton active={section === 'draft'} icon={FilePenLine} label="Draft" detail={isDirty ? 'Unsaved changes' : draft ? 'Saved · editable' : 'Editable'} onClick={() => selectSection('draft')} />
              <SectionButton active={section === 'staging'} icon={ShieldCheck} label="Staging" detail={staging?.version ?? 'Not created'} onClick={() => selectSection('staging')} />
              <SectionButton active={section === 'production'} icon={Rocket} label="Production" detail={production?.version ?? 'Not published'} onClick={() => selectSection('production')} />
              <SectionButton active={section === 'releases'} icon={Layers3} label="Releases" detail={`${immutableReleases.length} immutable`} onClick={() => selectSection('releases')} />
              <SectionButton active={section === 'activity'} icon={Activity} label="Activity" detail={`${activations.length} events`} onClick={() => selectSection('activity')} />
            </nav>
          </ScrollArea>

          <ScrollArea className="border-b border-border bg-background/20 lg:border-b-0 lg:border-r">
            {section === 'releases' ? (
              <ReleaseList releases={mode === 'rollback' ? rollbackCandidates : immutableReleases} selectedId={selectedReleaseId} productionId={production?.id} onSelect={(release) => { setSelectedReleaseId(release.id); if (mode === 'rollback') openActivation(release, 'rollback') }} />
            ) : section === 'activity' ? (
              <ActivityList activations={activations} releasesById={releasesById} selectedId={selectedActivationId} onSelect={(activation) => setSelectedActivationId(activation.id)} />
            ) : selectedEnvironmentRelease ? (
              <div className="p-3"><button type="button" className="w-full rounded-xl border border-primary/25 bg-primary/5 p-3 text-left"><p className="font-mono text-[10px] text-white">{selectedEnvironmentRelease.version}</p><p className="mt-1 text-[9px] text-muted">{selectedEnvironmentRelease.provider ?? '—'}/{selectedEnvironmentRelease.model ?? '—'} · {sessionModeLabel(selectedEnvironmentRelease.session_mode)}</p></button></div>
            ) : (
              <div className="p-4 text-[9px] text-muted">{section === 'draft' ? 'Save the Draft to materialize its lifecycle snapshot.' : `No ${section} snapshot is available.`}</div>
            )}
          </ScrollArea>

          <ScrollArea className="bg-surface/10">
            <div className="p-4">
              {mode === 'publish' && staging ? (
                <div className="space-y-4"><div><p className="text-[8px] uppercase tracking-wide text-primary-light">Publish immutable Release</p><h3 className="mt-1 font-mono text-sm text-white">{staging.version}</h3></div><ReleaseDetailsView release={staging} /><label className="block text-[9px] text-muted">Release description<textarea value={releaseDescription} onChange={(event) => setReleaseDescription(event.target.value)} className="mt-2 min-h-24 w-full rounded-xl border border-border bg-background/50 p-3 text-[10px] text-white outline-none focus:border-primary/40" placeholder="Describe what changed in this Release." /></label><p className="text-[8px] text-muted">Required. This description is stored with the immutable Release and its Production deployment event.</p></div>
              ) : (mode === 'activate' || mode === 'rollback') && selectedRelease ? (
                <div className="space-y-4"><div><p className="text-[8px] uppercase tracking-wide text-amber-300">{mode === 'rollback' ? 'Rollback target' : 'Production activation'}</p><h3 className="mt-1 font-mono text-sm text-white">{selectedRelease.version}</h3><p className="mt-1 text-[9px] text-muted">Current Production: {production?.version ?? 'none'}</p></div><ReleaseDetailsView release={selectedRelease} /><label className="block text-[9px] text-muted">Reason / audit note<Textarea value={actionReason} onChange={(event) => setActionReason(event.target.value)} className="mt-2 min-h-24 text-[10px]" /></label><p className="text-[8px] text-muted">Required for Production audit. Existing Sessions remain pinned to the Release they started with.</p></div>
              ) : section === 'activity' ? (
                selectedActivation ? (() => { const current = releasesById.get(selectedActivation.release_id) ?? null; const previous = selectedActivation.previous_release_id ? releasesById.get(selectedActivation.previous_release_id) ?? null : null; return <div className="space-y-4"><div className="rounded-xl border border-border bg-background/35 p-4"><div className="flex items-center gap-2"><Badge variant={selectedActivation.action === 'rollback' ? 'warning' : selectedActivation.action === 'deploy' ? 'success' : 'secondary'}>{activationLabel(selectedActivation.action)}</Badge><span className="font-mono text-[10px] text-slate-300">{previous?.version ?? 'None'}</span><ArrowRight className="h-3.5 w-3.5 text-muted" /><span className="font-mono text-[10px] text-white">{current?.version ?? selectedActivation.release_id.slice(0, 8)}</span></div><p className="mt-2 text-[9px] text-muted">{formatReleaseDate(selectedActivation.created_at)}</p></div><section className="rounded-xl border border-border bg-background/35 p-4"><p className="text-[9px] font-semibold uppercase tracking-wide text-slate-300">Audit note</p><p className="mt-2 whitespace-pre-wrap text-[10px] leading-5 text-slate-200">{selectedActivation.change_description || 'No audit note recorded for this historical event.'}</p></section>{current ? <ReleaseDetailsView release={current} /> : null}</div> })()
                : <div className="flex min-h-56 items-center justify-center text-[10px] text-muted">Select an activation event.</div>
              ) : section === 'draft' ? (
                draft ? <ReleaseDetailsView release={draft} /> : <div className="rounded-xl border border-border bg-background/35 p-4"><p className="text-sm font-medium text-white">{state.name || agentName}</p><p className="mt-2 text-[10px] text-muted">{state.provider || '—'}/{state.model || '—'} · {sessionModeLabel(state.sessionMode)}</p><p className="mt-3 text-[10px] leading-5 text-muted">The editor is the source of truth for Draft. Save it before creating Staging.</p></div>
              ) : section === 'releases' ? (
                selectedRelease ? <ReleaseDetailsView release={selectedRelease} /> : <div className="flex min-h-56 items-center justify-center text-[10px] text-muted">Select an immutable Release.</div>
              ) : selectedEnvironmentRelease ? <ReleaseDetailsView release={selectedEnvironmentRelease} /> : <div className="flex min-h-56 items-center justify-center text-[10px] text-muted">No snapshot available.</div>}
            </div>
          </ScrollArea>
        </div>

        <footer className="flex flex-wrap items-center gap-3 border-t border-border bg-background/30 px-4 py-3">
          <p className="min-w-0 flex-1 truncate text-[9px] text-muted">{mode === 'rollback' ? 'Rollback records a rollback event; manual activation records a reactivation event.' : 'Standalone Agent lifecycle is independent from Network Release pointers.'}</p>
          {mode === 'stage' ? <><button type="button" onClick={() => setMode('browse')} className="rounded-lg border border-border px-3 py-2 text-[10px] text-muted">Cancel</button><button type="button" disabled={pending || isDirty} onClick={() => void stageDraft()} className="rounded-lg bg-primary px-3 py-2 text-[10px] font-semibold text-white disabled:opacity-45">{pending ? 'Staging…' : 'Stage Agent'}</button></> : null}
          {mode === 'publish' ? <><button type="button" onClick={() => { setMode('browse'); setReleaseDescription('') }} className="rounded-lg border border-border px-3 py-2 text-[10px] text-muted">Cancel</button><button type="button" disabled={pending || releaseDescription.trim().length < 3} onClick={() => void publishRelease()} className="rounded-lg bg-primary px-3 py-2 text-[10px] font-semibold text-white disabled:opacity-45">{pending ? 'Publishing…' : 'Publish Release'}</button></> : null}
          {mode === 'activate' ? <><button type="button" onClick={() => { setMode('browse'); setActionReason('') }} className="rounded-lg border border-border px-3 py-2 text-[10px] text-muted">Cancel</button><button type="button" disabled={pending || actionReason.trim().length < 3} onClick={() => void reactivateRelease()} className="rounded-lg border border-emerald-500/40 bg-emerald-500/10 px-3 py-2 text-[10px] font-semibold text-emerald-300 disabled:opacity-45">{pending ? 'Activating…' : `Set ${selectedRelease?.version ?? 'Release'} as Production`}</button></> : null}
          {mode === 'rollback' ? <><button type="button" onClick={() => { setMode('browse'); setActionReason('') }} className="rounded-lg border border-border px-3 py-2 text-[10px] text-muted">Cancel</button><button type="button" disabled={pending || !selectedRelease || actionReason.trim().length < 3} onClick={() => void rollbackProduction()} className="rounded-lg bg-amber-600 px-3 py-2 text-[10px] font-semibold text-white disabled:opacity-45">{pending ? 'Applying…' : `Rollback to ${selectedRelease?.version ?? 'Release'}`}</button></> : null}
          {mode === 'browse' ? <><button type="button" onClick={onClose} className="rounded-lg border border-border px-3 py-2 text-[10px] text-muted hover:text-white">Close</button>{section === 'draft' ? <button type="button" disabled={pending || isDirty} onClick={() => setMode('stage')} className="rounded-lg bg-primary px-3 py-2 text-[10px] font-semibold text-white disabled:opacity-45">Stage Agent</button> : null}{section === 'staging' && staging ? <button type="button" disabled={pending} onClick={() => setMode('publish')} className="rounded-lg bg-primary px-3 py-2 text-[10px] font-semibold text-white disabled:opacity-45">Publish Release</button> : null}{section === 'production' && rollbackCandidates.length ? <button type="button" disabled={pending} onClick={() => { setSection('releases'); setMode('rollback'); setSelectedReleaseId(null) }} className="rounded-lg bg-primary px-3 py-2 text-[10px] font-semibold text-white disabled:opacity-45">Rollback</button> : null}{section === 'releases' && selectedRelease && selectedRelease.id !== production?.id ? <button type="button" disabled={pending} onClick={() => openActivation(selectedRelease, 'activate')} className="rounded-lg border border-emerald-500/40 bg-emerald-500/10 px-3 py-2 text-[10px] text-emerald-300">Set as Production</button> : null}</> : null}
        </footer>
      </div>
    </Dialog>
  )
}
