import { useEffect, useMemo, useState } from 'react'
import { Activity, ArrowRight, FilePenLine, History, Layers3, Rocket, ShieldCheck } from 'lucide-react'
import { EmptyStatePanel, SectionBlock, TechnicalListItem } from '@woobe/ui'
import { useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'

import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
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
    <button type="button" onClick={onClick} className={cn('min-h-[42px] rounded-control border px-2.5 py-2 text-left transition-colors', active ? 'border-primary/35 bg-primary/[0.09]' : 'border-transparent hover:border-border hover:bg-control/35')}>
      <span className="flex items-center gap-2 font-mono text-[8px] font-semibold text-slate-100"><Icon className="h-3 w-3" />{label}</span>
      <span className="mt-0.5 block truncate font-sans text-[8px] leading-3.5 text-muted-foreground">{detail}</span>
    </button>
  )
}

function ReleaseList({ releases, selectedId, productionId, onSelect }: { releases: AgentRelease[]; selectedId: string | null; productionId?: string; onSelect: (release: AgentRelease) => void }) {
  if (!releases.length) return <div className="p-3"><EmptyStatePanel compact title="No immutable Releases" description="Publish a Staging snapshot to materialize an immutable Agent Release." /></div>
  return (
    <div className="space-y-1.5 p-2.5">
      {releases.map((release) => (
        <TechnicalListItem
          key={release.id}
          selected={selectedId === release.id}
          onClick={() => onSelect(release)}
          label={release.version}
          description={`${release.provider ?? '—'}/${release.model ?? '—'}`}
          meta={<><span>{sessionModeLabel(release.session_mode)}</span><span>{formatReleaseDate(release.created_at)}</span></>}
          trailing={release.id === productionId ? <Badge variant="success">Production</Badge> : undefined}
        />
      ))}
    </div>
  )
}

function ActivityList({ activations, releasesById, selectedId, onSelect }: { activations: ActivationWithDescription[]; releasesById: Map<string, AgentRelease>; selectedId: string | null; onSelect: (activation: ActivationWithDescription) => void }) {
  if (!activations.length) return <div className="p-3"><EmptyStatePanel compact title="No Production activity" description="Deploy, activation and rollback events will appear here." /></div>
  return (
    <div className="space-y-1.5 p-2.5">
      {activations.map((activation) => {
        const current = releasesById.get(activation.release_id)
        const previous = activation.previous_release_id ? releasesById.get(activation.previous_release_id) : null
        return (
          <TechnicalListItem
            key={activation.id}
            selected={selectedId === activation.id}
            onClick={() => onSelect(activation)}
            label={activationLabel(activation.action)}
            description={formatReleaseDate(activation.created_at)}
            meta={<span className="inline-flex items-center gap-1"><span>{previous?.version ?? 'None'}</span><ArrowRight className="h-3 w-3" /><span className="text-slate-300">{current?.version ?? activation.release_id.slice(0, 8)}</span></span>}
            trailing={<Badge variant={activation.action === 'rollback' ? 'warning' : activation.action === 'deploy' ? 'success' : 'secondary'}>{activationLabel(activation.action)}</Badge>}
          />
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

  const selectSection = (next: AgentManagerSection) => { setSection(next); setMode('browse'); setSelectedReleaseId(null); setSelectedActivationId(null); setReleaseDescription(''); setActionReason('') }

  const stageDraft = async () => {
    if (isDirty) { toast.info('Save the Agent Draft before creating Staging'); return }
    try {
      const savedDraft = await createRelease.mutateAsync({ project_id: projectId, agent_id: agentId, version: 'draft', ...toSnapshot() } as any)
      const result = await promoteRelease.mutateAsync({ releaseId: savedDraft.id, targetStatus: 'staging', copySnapshot: true })
      setSection('staging'); setMode('browse'); onEnvironmentChange('staging'); toast.success(`${result.version} created as current Staging`)
    } catch (error) { toast.error(error instanceof Error ? error.message : 'Failed to stage Agent Draft') }
  }

  const publishRelease = async () => {
    if (!staging || releaseDescription.trim().length < 3) return
    try {
      const description = releaseDescription.trim()
      const result = await promoteRelease.mutateAsync({ releaseId: staging.id, targetStatus: 'production', copySnapshot: true, releaseNotes: description, changeDescription: description })
      setReleaseDescription(''); setSection('production'); setMode('browse'); onEnvironmentChange('production'); toast.success(`${result.version} published to Agent Production`)
    } catch (error) { toast.error(error instanceof Error ? error.message : 'Failed to publish Agent Release') }
  }

  const reactivateRelease = async () => {
    if (!selectedRelease || actionReason.trim().length < 3) return
    try {
      await promoteRelease.mutateAsync({ releaseId: selectedRelease.id, targetStatus: 'production', copySnapshot: false, restoreExistingVersion: true, changeDescription: actionReason.trim() })
      setActionReason(''); setSection('production'); setMode('browse'); onEnvironmentChange('production'); toast.success(`${selectedRelease.version} activated in Agent Production`)
    } catch (error) { toast.error(error instanceof Error ? error.message : 'Failed to activate Agent Release') }
  }

  const rollbackProduction = async () => {
    if (!selectedRelease || actionReason.trim().length < 3) return
    setRollbackPending(true)
    try {
      await rollbackRelease(agentId, selectedRelease.id, { changeDescription: actionReason.trim() })
      await Promise.all([queryClient.invalidateQueries({ queryKey: ['releases', agentId] }), queryClient.invalidateQueries({ queryKey: ['release-activations', agentId] }), queryClient.invalidateQueries({ queryKey: ['agent', agentId] })])
      setActionReason(''); setSection('production'); setMode('browse'); onEnvironmentChange('production'); toast.success(`${selectedRelease.version} restored by rollback`)
    } catch (error) { toast.error(error instanceof Error ? error.message : 'Failed to rollback Agent Production') } finally { setRollbackPending(false) }
  }

  const openActivation = (release: AgentRelease, nextMode: 'activate' | 'rollback') => {
    setSelectedReleaseId(release.id)
    setMode(nextMode)
    setActionReason(nextMode === 'rollback' ? `Rollback Agent Production from ${production?.version ?? 'current Production'} to ${release.version}.` : `Activate ${release.version} in Agent Production.`)
  }

  const selectedEnvironmentRelease = section === 'draft' ? draft : section === 'staging' ? staging : section === 'production' ? production : null

  return (
    <Dialog open={open} onClose={onClose} title="Manage Agent" className="flex h-[min(720px,calc(100svh-2rem))] max-w-[1040px] flex-col overflow-hidden" contentClassName="min-h-0 flex-1 p-0">
      <div className="grid h-full min-h-0 grid-rows-[44px_minmax(0,1fr)_52px] overflow-hidden">
        <header className="flex items-center gap-2.5 border-b border-border bg-background/20 px-3.5">
          <span className="flex h-7 w-7 items-center justify-center rounded-control border border-border bg-control text-primary-light"><History className="h-3.5 w-3.5" /></span>
          <div className="min-w-0"><p className="truncate font-mono text-[9px] font-semibold text-slate-50">{agentName}</p><p className="mt-0.5 font-sans text-[8px] text-muted-foreground">Draft → Staging → immutable Release → Production.</p></div>
          <Badge variant={production ? 'success' : 'secondary'} className="ml-auto">{production ? `Production · ${production.version}` : 'No Production'}</Badge>
        </header>

        <div className="grid min-h-0 overflow-hidden lg:grid-cols-[170px_220px_minmax(0,1fr)]">
          <ScrollArea orientation="both" className="border-b border-border bg-surface/20 lg:border-b-0 lg:border-r">
            <nav className="flex min-w-max gap-1 p-2 lg:min-w-0 lg:flex-col">
              <SectionButton active={section === 'draft'} icon={FilePenLine} label="Draft" detail={isDirty ? 'Unsaved changes' : draft ? 'Saved · editable' : 'Editable'} onClick={() => selectSection('draft')} />
              <SectionButton active={section === 'staging'} icon={ShieldCheck} label="Staging" detail={staging?.version ?? 'Not created'} onClick={() => selectSection('staging')} />
              <SectionButton active={section === 'production'} icon={Rocket} label="Production" detail={production?.version ?? 'Not published'} onClick={() => selectSection('production')} />
              <SectionButton active={section === 'releases'} icon={Layers3} label="Releases" detail={`${immutableReleases.length} immutable`} onClick={() => selectSection('releases')} />
              <SectionButton active={section === 'activity'} icon={Activity} label="Activity" detail={`${activations.length} events`} onClick={() => selectSection('activity')} />
            </nav>
          </ScrollArea>

          <ScrollArea className="border-b border-border bg-background/15 lg:border-b-0 lg:border-r">
            {section === 'releases' ? (
              <ReleaseList releases={mode === 'rollback' ? rollbackCandidates : immutableReleases} selectedId={selectedReleaseId} productionId={production?.id} onSelect={(release) => { setSelectedReleaseId(release.id); if (mode === 'rollback') openActivation(release, 'rollback') }} />
            ) : section === 'activity' ? (
              <ActivityList activations={activations} releasesById={releasesById} selectedId={selectedActivationId} onSelect={(activation) => setSelectedActivationId(activation.id)} />
            ) : selectedEnvironmentRelease ? (
              <div className="p-2.5"><TechnicalListItem selected label={selectedEnvironmentRelease.version} description={`${selectedEnvironmentRelease.provider ?? '—'}/${selectedEnvironmentRelease.model ?? '—'}`} meta={<span>{sessionModeLabel(selectedEnvironmentRelease.session_mode)}</span>} /></div>
            ) : (
              <div className="p-3"><EmptyStatePanel compact title={section === 'draft' ? 'Draft snapshot not materialized' : `No ${section} snapshot`} description={section === 'draft' ? 'Save the Draft to materialize its lifecycle snapshot.' : undefined} /></div>
            )}
          </ScrollArea>

          <ScrollArea className="bg-surface/10">
            <div className="p-3">
              {mode === 'publish' && staging ? (
                <div className="space-y-3">
                  <SectionBlock density="compact" eyebrow="Publish" title={staging.version} description="Create an immutable Release from current Staging." />
                  <ReleaseDetailsView release={staging} />
                  <label className="block font-mono text-[8px] text-muted-foreground">Release description<Textarea value={releaseDescription} onChange={(event) => setReleaseDescription(event.target.value)} className="mt-1.5 min-h-20 font-sans text-[10px]" placeholder="Describe what changed in this Release." /></label>
                  <p className="font-sans text-[8px] text-muted-foreground">Required. Stored with the immutable Release and its Production deployment event.</p>
                </div>
              ) : (mode === 'activate' || mode === 'rollback') && selectedRelease ? (
                <div className="space-y-3">
                  <SectionBlock density="compact" eyebrow={mode === 'rollback' ? 'Rollback target' : 'Production activation'} title={selectedRelease.version} description={`Current Production: ${production?.version ?? 'none'}`} />
                  <ReleaseDetailsView release={selectedRelease} />
                  <label className="block font-mono text-[8px] text-muted-foreground">Reason / audit note<Textarea value={actionReason} onChange={(event) => setActionReason(event.target.value)} className="mt-1.5 min-h-20 font-sans text-[10px]" /></label>
                  <p className="font-sans text-[8px] text-muted-foreground">Required for Production audit. Existing Sessions remain pinned to the Release they started with.</p>
                </div>
              ) : section === 'activity' ? (
                selectedActivation ? (() => {
                  const current = releasesById.get(selectedActivation.release_id) ?? null
                  const previous = selectedActivation.previous_release_id ? releasesById.get(selectedActivation.previous_release_id) ?? null : null
                  return <div className="space-y-3"><SectionBlock density="compact" eyebrow="Production event" title={<span className="flex items-center gap-2"><span>{previous?.version ?? 'None'}</span><ArrowRight className="h-3 w-3" /><span>{current?.version ?? selectedActivation.release_id.slice(0, 8)}</span></span>} description={formatReleaseDate(selectedActivation.created_at)} actions={<Badge variant={selectedActivation.action === 'rollback' ? 'warning' : selectedActivation.action === 'deploy' ? 'success' : 'secondary'}>{activationLabel(selectedActivation.action)}</Badge>}><div className="border-t border-border/60 pt-2.5"><p className="font-mono text-[8px] uppercase tracking-[0.08em] text-muted-foreground">Audit note</p><p className="mt-1.5 whitespace-pre-wrap font-sans text-[9px] leading-4 text-slate-200">{selectedActivation.change_description || 'No audit note recorded for this historical event.'}</p></div></SectionBlock>{current ? <ReleaseDetailsView release={current} /> : null}</div>
                })() : <EmptyStatePanel compact title="Select an activation event" description="Choose an event from the lifecycle history to inspect its Release and audit note." />
              ) : section === 'draft' ? (
                draft ? <ReleaseDetailsView release={draft} /> : <SectionBlock density="compact" title={state.name || agentName} description={`${state.provider || '—'}/${state.model || '—'} · ${sessionModeLabel(state.sessionMode)}`}><p className="font-sans text-[9px] leading-4 text-muted-foreground">The editor is the source of truth for Draft. Save it before creating Staging.</p></SectionBlock>
              ) : section === 'releases' ? (
                selectedRelease ? <ReleaseDetailsView release={selectedRelease} /> : <EmptyStatePanel compact title="Select an immutable Release" description="Choose a Release to inspect its frozen configuration." />
              ) : selectedEnvironmentRelease ? (
                <ReleaseDetailsView release={selectedEnvironmentRelease} />
              ) : <EmptyStatePanel compact title="No snapshot available" />}
            </div>
          </ScrollArea>
        </div>

        <footer className="flex flex-wrap items-center gap-2 border-t border-border bg-surface/[0.96] px-3.5 py-2.5">
          <p className="min-w-0 flex-1 truncate font-sans text-[8px] text-muted-foreground">{mode === 'rollback' ? 'Rollback records a rollback event; manual activation records a reactivation event.' : 'Standalone Agent lifecycle is independent from Network Release pointers.'}</p>
          {mode === 'stage' ? <><Button variant="outline" onClick={() => setMode('browse')}>Cancel</Button><Button disabled={pending || isDirty} onClick={() => void stageDraft()}>{pending ? 'Staging…' : 'Stage Agent'}</Button></> : null}
          {mode === 'publish' ? <><Button variant="outline" onClick={() => { setMode('browse'); setReleaseDescription('') }}>Cancel</Button><Button disabled={pending || releaseDescription.trim().length < 3} onClick={() => void publishRelease()}>{pending ? 'Publishing…' : 'Publish Release'}</Button></> : null}
          {mode === 'activate' ? <><Button variant="outline" onClick={() => { setMode('browse'); setActionReason('') }}>Cancel</Button><Button disabled={pending || actionReason.trim().length < 3} onClick={() => void reactivateRelease()}>{pending ? 'Activating…' : `Set ${selectedRelease?.version ?? 'Release'} as Production`}</Button></> : null}
          {mode === 'rollback' ? <><Button variant="outline" onClick={() => { setMode('browse'); setActionReason('') }}>Cancel</Button><Button variant="destructive" disabled={pending || !selectedRelease || actionReason.trim().length < 3} onClick={() => void rollbackProduction()}>{pending ? 'Applying…' : `Rollback to ${selectedRelease?.version ?? 'Release'}`}</Button></> : null}
          {mode === 'browse' ? <><Button variant="outline" onClick={onClose}>Close</Button>{section === 'draft' ? <Button disabled={pending || isDirty} onClick={() => setMode('stage')}>Stage Agent</Button> : null}{section === 'staging' && staging ? <Button disabled={pending} onClick={() => setMode('publish')}>Publish Release</Button> : null}{section === 'production' && rollbackCandidates.length ? <Button disabled={pending} onClick={() => { setSection('releases'); setMode('rollback'); setSelectedReleaseId(null) }}>Rollback</Button> : null}{section === 'releases' && selectedRelease && selectedRelease.id !== production?.id ? <Button disabled={pending} onClick={() => openActivation(selectedRelease, 'activate')}>Set as Production</Button> : null}</> : null}
        </footer>
      </div>
    </Dialog>
  )
}
