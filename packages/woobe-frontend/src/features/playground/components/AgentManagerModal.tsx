import { useEffect, useMemo, useState } from 'react'
import { Activity, ArrowRight, FilePenLine, History, Layers3, Rocket, ShieldCheck } from 'lucide-react'
import { useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import {
  Badge,
  Button,
  Dialog,
  EmptyStatePanel,
  Field,
  FieldDescription,
  FieldLabel,
  ScrollArea,
  SectionBlock,
  TechnicalListItem,
  Textarea,
} from '@woobe/ui'

import { rollbackRelease } from '@/features/agents/api'
import { useCreateRelease, usePromoteRelease, useReleaseActivations, useReleases } from '@/features/agents/hooks'
import type { AgentRelease, AgentReleaseActivation, RuntimeEnvironment } from '@/features/agents/types'
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

function ReleaseList({
  releases,
  selectedId,
  productionId,
  onSelect,
}: {
  releases: AgentRelease[]
  selectedId: string | null
  productionId?: string
  onSelect: (release: AgentRelease) => void
}) {
  if (!releases.length) {
    return (
      <div className="p-ui-sm">
        <EmptyStatePanel compact title="No immutable Releases" description="Publish a Staging snapshot to materialize an immutable Agent Release." />
      </div>
    )
  }

  return (
    <div className="grid gap-ui-xs p-ui-sm">
      {releases.map((release) => (
        <TechnicalListItem
          key={release.id}
          selected={selectedId === release.id}
          onClick={() => onSelect(release)}
          label={release.version}
          description={`${release.provider ?? '—'}/${release.model ?? '—'}`}
          meta={<><span>{sessionModeLabel(release.session_mode)}</span><span>{formatReleaseDate(release.created_at)}</span></>}
          trailing={release.id === productionId ? <Badge variant="success" size="compact">Production</Badge> : undefined}
        />
      ))}
    </div>
  )
}

function ActivityList({
  activations,
  releasesById,
  selectedId,
  onSelect,
}: {
  activations: ActivationWithDescription[]
  releasesById: Map<string, AgentRelease>
  selectedId: string | null
  onSelect: (activation: ActivationWithDescription) => void
}) {
  if (!activations.length) {
    return (
      <div className="p-ui-sm">
        <EmptyStatePanel compact title="No Production activity" description="Deploy, activation and rollback events will appear here." />
      </div>
    )
  }

  return (
    <div className="grid gap-ui-xs p-ui-sm">
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
            meta={(
              <span className="inline-flex items-center gap-ui-xs">
                <span>{previous?.version ?? 'None'}</span>
                <ArrowRight className="h-icon-sm w-icon-sm" />
                <span className="text-accent-foreground">{current?.version ?? activation.release_id.slice(0, 8)}</span>
              </span>
            )}
            trailing={(
              <Badge variant={activation.action === 'rollback' ? 'warning' : activation.action === 'deploy' ? 'success' : 'secondary'} size="compact">
                {activationLabel(activation.action)}
              </Badge>
            )}
          />
        )
      })}
    </div>
  )
}

export function AgentManagerModal({
  open,
  agentId,
  agentName,
  projectId,
  environment,
  initialSection,
  initialMode = 'browse',
  onClose,
  onEnvironmentChange,
}: AgentManagerModalProps) {
  const { data: releases = [] } = useReleases(agentId)
  const { data: rawActivations = [] } = useReleaseActivations(agentId)
  const activations = rawActivations as ActivationWithDescription[]
  const createRelease = useCreateRelease(agentId)
  const promoteRelease = usePromoteRelease(agentId)
  const queryClient = useQueryClient()
  const { state, baseRevision, updateBaseline, toSnapshot, isDirty } = useAgentEditor()

  const draft = useMemo(() => releases.find((release) => release.status === 'draft') ?? null, [releases])
  const staging = useMemo(() => releases.find((release) => release.status === 'staging') ?? null, [releases])
  const production = useMemo(() => releases.find((release) => release.status === 'production') ?? null, [releases])
  const immutableReleases = useMemo(
    () => releases.filter((release) => release.snapshot_kind === 'release').sort((a, b) => releaseTime(b) - releaseTime(a)),
    [releases],
  )
  const rollbackCandidates = useMemo(
    () => immutableReleases.filter((release) => release.id !== production?.id),
    [immutableReleases, production?.id],
  )
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
      const savedDraft = await createRelease.mutateAsync({ expected_revision: baseRevision, project_id: projectId, agent_id: agentId, version: 'draft', ...toSnapshot() } as any)
      updateBaseline(state, savedDraft.agent_revision)
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

  const selectedEnvironmentRelease = section === 'draft'
    ? draft
    : section === 'staging'
      ? staging
      : section === 'production'
        ? production
        : null

  const navigation = [
    { id: 'draft' as const, icon: FilePenLine, label: 'Draft', detail: isDirty ? 'Unsaved changes' : draft ? 'Saved · editable' : 'Editable' },
    { id: 'staging' as const, icon: ShieldCheck, label: 'Staging', detail: staging?.version ?? 'Not created' },
    { id: 'production' as const, icon: Rocket, label: 'Production', detail: production?.version ?? 'Not published' },
    { id: 'releases' as const, icon: Layers3, label: 'Releases', detail: `${immutableReleases.length} immutable` },
    { id: 'activity' as const, icon: Activity, label: 'Activity', detail: `${activations.length} events` },
  ]

  return (
    <Dialog
      open={open}
      onClose={onClose}
      title="Manage Agent"
      variant="workspace"
      height="workspace"
    >
      <div className="flex min-h-0 flex-1 flex-col overflow-hidden">
        <header className="flex shrink-0 items-center gap-ui-md border-b border-border bg-background/20 px-ui-lg py-ui-sm">
          <span className="flex h-control-nav w-control-nav items-center justify-center rounded-control border border-border bg-control text-primary-light">
            <History className="h-icon w-icon" />
          </span>
          <div className="min-w-0">
            <p className="truncate font-mono text-system-control font-semibold text-accent-foreground">{agentName}</p>
            <p className="mt-ui-xs font-sans text-product-caption text-muted-foreground">Draft → Staging → immutable Release → Production.</p>
          </div>
          <Badge variant={production ? 'success' : 'secondary'} size="compact" className="ml-auto">
            {production ? `Production · ${production.version}` : 'No Production'}
          </Badge>
        </header>

        <div className="grid min-h-0 flex-1 overflow-hidden lg:grid-cols-12">
          <ScrollArea orientation="both" className="border-b border-border bg-surface/20 lg:col-span-2 lg:border-b-0 lg:border-r">
            <nav className="flex min-w-max gap-ui-xs p-ui-sm lg:min-w-0 lg:flex-col">
              {navigation.map((item) => {
                const Icon = item.icon
                return (
                  <TechnicalListItem
                    key={item.id}
                    label={item.label}
                    description={item.detail}
                    leading={<Icon className="h-icon w-icon" />}
                    selected={section === item.id}
                    onClick={() => selectSection(item.id)}
                  />
                )
              })}
            </nav>
          </ScrollArea>

          <ScrollArea className="border-b border-border bg-background/15 lg:col-span-3 lg:border-b-0 lg:border-r">
            {section === 'releases' ? (
              <ReleaseList
                releases={mode === 'rollback' ? rollbackCandidates : immutableReleases}
                selectedId={selectedReleaseId}
                productionId={production?.id}
                onSelect={(release) => {
                  setSelectedReleaseId(release.id)
                  if (mode === 'rollback') openActivation(release, 'rollback')
                }}
              />
            ) : section === 'activity' ? (
              <ActivityList activations={activations} releasesById={releasesById} selectedId={selectedActivationId} onSelect={(activation) => setSelectedActivationId(activation.id)} />
            ) : selectedEnvironmentRelease ? (
              <div className="p-ui-sm">
                <TechnicalListItem
                  selected
                  label={selectedEnvironmentRelease.version}
                  description={`${selectedEnvironmentRelease.provider ?? '—'}/${selectedEnvironmentRelease.model ?? '—'}`}
                  meta={<span>{sessionModeLabel(selectedEnvironmentRelease.session_mode)}</span>}
                />
              </div>
            ) : (
              <div className="p-ui-sm">
                <EmptyStatePanel
                  compact
                  title={section === 'draft' ? 'Draft snapshot not materialized' : `No ${section} snapshot`}
                  description={section === 'draft' ? 'Save the Draft to materialize its lifecycle snapshot.' : undefined}
                />
              </div>
            )}
          </ScrollArea>

          <ScrollArea className="bg-surface/10 lg:col-span-7">
            <div className="p-ui-md">
              {mode === 'publish' && staging ? (
                <div className="grid gap-ui-md">
                  <SectionBlock density="compact" eyebrow="Publish" title={staging.version} description="Create an immutable Release from current Staging." />
                  <ReleaseDetailsView release={staging} />
                  <Field>
                    <FieldLabel>Release description</FieldLabel>
                    <Textarea value={releaseDescription} onChange={(event) => setReleaseDescription(event.target.value)} className="min-h-textarea-compact" placeholder="Describe what changed in this Release." />
                    <FieldDescription>Required. Stored with the immutable Release and its Production deployment event.</FieldDescription>
                  </Field>
                </div>
              ) : (mode === 'activate' || mode === 'rollback') && selectedRelease ? (
                <div className="grid gap-ui-md">
                  <SectionBlock density="compact" eyebrow={mode === 'rollback' ? 'Rollback target' : 'Production activation'} title={selectedRelease.version} description={`Current Production: ${production?.version ?? 'none'}`} />
                  <ReleaseDetailsView release={selectedRelease} />
                  <Field>
                    <FieldLabel>Reason / audit note</FieldLabel>
                    <Textarea value={actionReason} onChange={(event) => setActionReason(event.target.value)} className="min-h-textarea-compact" />
                    <FieldDescription>Required for Production audit. Existing Sessions remain pinned to the Release they started with.</FieldDescription>
                  </Field>
                </div>
              ) : section === 'activity' ? (
                selectedActivation ? (() => {
                  const current = releasesById.get(selectedActivation.release_id) ?? null
                  const previous = selectedActivation.previous_release_id ? releasesById.get(selectedActivation.previous_release_id) ?? null : null
                  return (
                    <div className="grid gap-ui-md">
                      <SectionBlock
                        density="compact"
                        eyebrow="Production event"
                        title={(
                          <span className="flex items-center gap-ui-sm">
                            <span>{previous?.version ?? 'None'}</span>
                            <ArrowRight className="h-icon-sm w-icon-sm" />
                            <span>{current?.version ?? selectedActivation.release_id.slice(0, 8)}</span>
                          </span>
                        )}
                        description={formatReleaseDate(selectedActivation.created_at)}
                        actions={(
                          <Badge variant={selectedActivation.action === 'rollback' ? 'warning' : selectedActivation.action === 'deploy' ? 'success' : 'secondary'} size="compact">
                            {activationLabel(selectedActivation.action)}
                          </Badge>
                        )}
                      >
                        <div className="border-t border-border pt-ui-sm">
                          <p className="font-mono text-system-label uppercase tracking-system-label text-muted-foreground">Audit note</p>
                          <p className="mt-ui-sm whitespace-pre-wrap font-sans text-product-small leading-5 text-accent-foreground/85">
                            {selectedActivation.change_description || 'No audit note recorded for this historical event.'}
                          </p>
                        </div>
                      </SectionBlock>
                      {current ? <ReleaseDetailsView release={current} /> : null}
                    </div>
                  )
                })() : (
                  <EmptyStatePanel compact title="Select an activation event" description="Choose an event from the lifecycle history to inspect its Release and audit note." />
                )
              ) : section === 'draft' ? (
                draft ? (
                  <ReleaseDetailsView release={draft} />
                ) : (
                  <SectionBlock density="compact" title={state.name || agentName} description={`${state.provider || '—'}/${state.model || '—'} · ${sessionModeLabel(state.sessionMode)}`}>
                    <p className="font-sans text-product-small leading-5 text-muted-foreground">The editor is the source of truth for Draft. Save it before creating Staging.</p>
                  </SectionBlock>
                )
              ) : section === 'releases' ? (
                selectedRelease ? <ReleaseDetailsView release={selectedRelease} /> : <EmptyStatePanel compact title="Select an immutable Release" description="Choose a Release to inspect its frozen configuration." />
              ) : selectedEnvironmentRelease ? (
                <ReleaseDetailsView release={selectedEnvironmentRelease} />
              ) : (
                <EmptyStatePanel compact title="No snapshot available" />
              )}
            </div>
          </ScrollArea>
        </div>

        <footer className="flex shrink-0 flex-wrap items-center gap-ui-sm border-t border-border bg-surface/95 px-ui-lg py-ui-md">
          <p className="min-w-0 flex-1 font-sans text-product-caption text-muted-foreground">
            {mode === 'rollback'
              ? 'Rollback records a rollback event; manual activation records a reactivation event.'
              : 'Standalone Agent lifecycle is independent from Network Release pointers.'}
          </p>

          {mode === 'stage' ? (
            <>
              <Button variant="outline" onClick={() => setMode('browse')}>Cancel</Button>
              <Button disabled={pending || isDirty} onClick={() => void stageDraft()}>{pending ? 'Staging…' : 'Stage Agent'}</Button>
            </>
          ) : null}
          {mode === 'publish' ? (
            <>
              <Button variant="outline" onClick={() => { setMode('browse'); setReleaseDescription('') }}>Cancel</Button>
              <Button disabled={pending || releaseDescription.trim().length < 3} onClick={() => void publishRelease()}>{pending ? 'Publishing…' : 'Publish Release'}</Button>
            </>
          ) : null}
          {mode === 'activate' ? (
            <>
              <Button variant="outline" onClick={() => { setMode('browse'); setActionReason('') }}>Cancel</Button>
              <Button disabled={pending || actionReason.trim().length < 3} onClick={() => void reactivateRelease()}>{pending ? 'Activating…' : `Set ${selectedRelease?.version ?? 'Release'} as Production`}</Button>
            </>
          ) : null}
          {mode === 'rollback' ? (
            <>
              <Button variant="outline" onClick={() => { setMode('browse'); setActionReason('') }}>Cancel</Button>
              <Button variant="destructive" disabled={pending || !selectedRelease || actionReason.trim().length < 3} onClick={() => void rollbackProduction()}>{pending ? 'Applying…' : `Rollback to ${selectedRelease?.version ?? 'Release'}`}</Button>
            </>
          ) : null}
          {mode === 'browse' ? (
            <>
              <Button variant="outline" onClick={onClose}>Close</Button>
              {section === 'draft' ? <Button disabled={pending || isDirty} onClick={() => setMode('stage')}>Stage Agent</Button> : null}
              {section === 'staging' && staging ? <Button disabled={pending} onClick={() => setMode('publish')}>Publish Release</Button> : null}
              {section === 'production' && rollbackCandidates.length ? <Button disabled={pending} onClick={() => { setSection('releases'); setMode('rollback'); setSelectedReleaseId(null) }}>Rollback</Button> : null}
              {section === 'releases' && selectedRelease && selectedRelease.id !== production?.id ? <Button disabled={pending} onClick={() => openActivation(selectedRelease, 'activate')}>Set as Production</Button> : null}
            </>
          ) : null}
        </footer>
      </div>
    </Dialog>
  )
}
