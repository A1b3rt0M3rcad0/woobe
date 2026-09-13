import { useEffect, useMemo, useRef, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Activity, Eye, FilePenLine, History, Layers3, Network, Rocket, ShieldCheck } from 'lucide-react'
import { useParams } from 'react-router-dom'
import { Button, Textarea } from '@woobe/ui'

import { Dialog } from '@/components/ui/Dialog'
import { ScrollArea } from '@/components/ui/ScrollArea'
import type { Agent } from '@/features/agents/types'
import { getNetworkProductionActivations } from '@/features/network/api'
import type { NetworkDefinition, NetworkProductionActivation, NetworkVersion } from '@/features/network/types'
import { cn } from '@/lib/utils'
import { NetworkBindingBadge } from './NetworkBindingBadge'

export type NetworkManagerSection = 'draft' | 'staging' | 'production'
export type NetworkManagerMode = 'browse' | 'rollback'
type Section = NetworkManagerSection | 'releases' | 'activity'

interface NetworkVersionsModalProps {
  open: boolean
  networkName: string
  initialSection: NetworkManagerSection
  initialMode?: NetworkManagerMode
  draftDefinition: NetworkDefinition
  draftRevision: number
  draftDirty: boolean
  stagingVersion: NetworkVersion | null
  productionVersion: NetworkVersion | null
  versions: NetworkVersion[]
  agents: Agent[]
  pending: boolean
  onClose: () => void
  onStage: () => void
  onPublish: () => void
  onViewVersion: (version: NetworkVersion) => void
  onActivate: (versionId: string, description: string) => Promise<void>
}

function formatDate(value?: string | null) {
  if (!value) return '—'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '—'
  return new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeStyle: 'short' }).format(date)
}

function SectionButton({ active, icon: Icon, label, detail, onClick }: { active: boolean; icon: typeof Network; label: string; detail: string; onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        'flex min-w-[170px] items-center gap-ui-sm rounded-control border px-ui-md py-ui-sm text-left transition-colors lg:min-w-0',
        active ? 'border-primary/35 bg-primary/10 text-white' : 'border-transparent text-muted-foreground hover:border-border hover:text-white',
      )}
    >
      <Icon className="h-3.5 w-3.5 shrink-0" />
      <span className="min-w-0">
        <span className="block font-mono text-system-label font-semibold">{label}</span>
        <span className="block truncate font-mono text-system-meta text-muted-foreground">{detail}</span>
      </span>
    </button>
  )
}

function VersionList({ versions, selectedId, activeId, onSelect }: { versions: NetworkVersion[]; selectedId: string | null; activeId?: string | null; onSelect: (version: NetworkVersion) => void }) {
  if (!versions.length) return <p className="p-ui-md font-sans text-product-caption text-muted-foreground">No versions available.</p>

  return (
    <div className="space-y-ui-xs p-ui-sm">
      {versions.map((version) => (
        <button
          key={version.id}
          type="button"
          onClick={() => onSelect(version)}
          className={cn(
            'w-full rounded-container border p-ui-md text-left transition-colors',
            selectedId === version.id ? 'border-primary/35 bg-primary/10' : 'border-border/70 bg-background/25 hover:border-border',
          )}
        >
          <div className="flex items-center gap-ui-sm">
            <span className="truncate font-mono text-system-control text-white">{version.version}</span>
            {version.id === activeId ? <span className="ml-auto rounded-technical border border-emerald-500/30 bg-emerald-500/10 px-ui-xs py-ui-hairline font-mono text-system-meta text-emerald-300">Active</span> : null}
          </div>
          <p className="mt-ui-xs font-mono text-system-meta text-muted-foreground">{formatDate(version.created_at)} · {version.definition.nodes.length} Agents</p>
        </button>
      ))}
    </div>
  )
}

function SnapshotDetails({ version, agents }: { version: NetworkVersion; agents: Agent[] }) {
  const agentsById = new Map(agents.map((agent) => [agent.id, agent]))
  return (
    <div className="space-y-ui-md p-ui-md">
      <div>
        <p className="font-mono text-system-meta uppercase tracking-ui-label text-primary-light">{version.kind === 'release' ? 'Network Release' : 'Network Staging'}</p>
        <h3 className="mt-ui-xs font-mono text-heading-sm font-semibold text-white">{version.version}</h3>
        <p className="mt-ui-xs font-mono text-system-meta text-muted-foreground">Immutable snapshot · {formatDate(version.created_at)}</p>
      </div>
      <section className="rounded-container border border-border bg-background/30 p-ui-md">
        <div className="grid grid-cols-3 gap-ui-md">
          <div><p className="font-mono text-system-meta text-muted-foreground">Agents</p><p className="mt-ui-xs font-mono text-system-control text-white">{version.definition.nodes.length}</p></div>
          <div><p className="font-mono text-system-meta text-muted-foreground">Delegations</p><p className="mt-ui-xs font-mono text-system-control text-white">{version.definition.edges.length}</p></div>
          <div><p className="font-mono text-system-meta text-muted-foreground">Mode</p><p className="mt-ui-xs font-mono text-system-control capitalize text-white">{version.definition.settings.session_mode}</p></div>
        </div>
      </section>
      <section>
        <p className="mb-ui-sm font-mono text-system-label font-semibold uppercase tracking-ui-label text-muted-foreground">Agent bindings</p>
        <div className="space-y-ui-sm">
          {version.definition.nodes.map((node) => {
            const resolved = version.resolved_bindings[node.id]
            const source = resolved?.binding_source === 'release' || resolved?.snapshot_kind === 'release' ? 'release' : 'staging'
            const label = agentsById.get(node.agent_id)?.name ?? node.label
            return (
              <div key={node.id} className="flex items-center gap-ui-md rounded-container border border-border bg-background/30 p-ui-md">
                <div className="min-w-0 flex-1">
                  <p className="truncate font-sans text-product-small text-white">{label}</p>
                  <p className="mt-ui-xs font-mono text-system-meta text-muted-foreground">{node.id === version.definition.root_node_id ? 'Entry Agent' : 'Specialist'}</p>
                </div>
                <div className="w-44"><NetworkBindingBadge source={source} version={resolved?.release_version ?? 'pinned'} /></div>
              </div>
            )
          })}
        </div>
      </section>
      {version.kind === 'release' ? <p className="rounded-container border border-emerald-500/20 bg-emerald-500/[0.04] p-ui-md font-sans text-product-caption leading-4 text-emerald-200">This Network Release uses exact Agent Release IDs. It does not depend on Agent Playground Production.</p> : null}
    </div>
  )
}

function DraftDetails({ definition, revision, dirty, agents }: { definition: NetworkDefinition; revision: number; dirty: boolean; agents: Agent[] }) {
  const agentsById = new Map(agents.map((agent) => [agent.id, agent]))
  return (
    <div className="space-y-ui-md p-ui-md">
      <div>
        <p className="font-mono text-system-meta uppercase tracking-ui-label text-primary-light">Editable Network Draft</p>
        <h3 className="mt-ui-xs font-sans text-heading-sm font-semibold text-white">Revision {revision}</h3>
        <p className="mt-ui-xs font-sans text-product-caption text-muted-foreground">{dirty ? 'Unsaved changes' : 'Saved'} · Draft bindings remain unchanged after promotion.</p>
      </div>
      <div className="space-y-ui-sm">
        {definition.nodes.map((node) => (
          <div key={node.id} className="flex items-center gap-ui-md rounded-container border border-border bg-background/30 p-ui-md">
            <div className="min-w-0 flex-1">
              <p className="truncate font-sans text-product-small text-white">{agentsById.get(node.agent_id)?.name ?? node.label}</p>
              <p className="mt-ui-xs font-mono text-system-meta text-muted-foreground">{node.id === definition.root_node_id ? 'Entry Agent' : 'Specialist'}</p>
            </div>
            <div className="w-44"><NetworkBindingBadge source={node.binding.source} version={node.binding.source === 'draft' ? 'current' : 'pinned'} /></div>
          </div>
        ))}
      </div>
    </div>
  )
}

function ActivityList({ activations, versions }: { activations: NetworkProductionActivation[]; versions: NetworkVersion[] }) {
  if (!activations.length) return <p className="p-ui-md font-sans text-product-caption text-muted-foreground">No Production activity.</p>
  return (
    <div className="space-y-ui-sm p-ui-md">
      {activations.map((activation) => {
        const version = versions.find((item) => item.id === activation.version_id)
        return (
          <article key={activation.id} className="rounded-container border border-border bg-background/30 p-ui-md">
            <div className="flex items-center gap-ui-sm">
              <span className="font-mono text-system-control text-white">{version?.version ?? activation.version_id.slice(0, 8)}</span>
              <span className="ml-auto rounded-technical border border-border px-ui-xs py-ui-hairline font-mono text-system-meta capitalize text-muted-foreground">{activation.activation_kind}</span>
            </div>
            <p className="mt-ui-sm font-sans text-product-caption leading-4 text-slate-300">{activation.change_description}</p>
            <p className="mt-ui-xs font-mono text-system-meta text-muted-foreground">{formatDate(activation.created_at)}</p>
          </article>
        )
      })}
    </div>
  )
}

export function NetworkVersionsModal({ open, networkName, initialSection, initialMode = 'browse', draftDefinition, draftRevision, draftDirty, stagingVersion, productionVersion, versions, agents, pending, onClose, onStage, onPublish, onViewVersion, onActivate }: NetworkVersionsModalProps) {
  const { projectId, networkId } = useParams<{ projectId: string; networkId: string }>()
  const activationsQuery = useQuery({ queryKey: ['network-production-activations', projectId, networkId], queryFn: () => getNetworkProductionActivations(networkId!, projectId!), enabled: Boolean(open && projectId && networkId) })
  const releases = useMemo(() => versions.filter((version) => version.kind === 'release').sort((a, b) => new Date(b.created_at ?? 0).getTime() - new Date(a.created_at ?? 0).getTime()), [versions])
  const rollbackCandidates = useMemo(() => releases.filter((version) => version.id !== productionVersion?.id), [productionVersion?.id, releases])
  const [section, setSection] = useState<Section>(initialMode === 'rollback' ? 'releases' : initialSection)
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [activationTargetId, setActivationTargetId] = useState<string | null>(null)
  const [description, setDescription] = useState('')
  const initialized = useRef(false)

  useEffect(() => {
    if (!open) { initialized.current = false; return }
    if (initialized.current) return
    initialized.current = true
    const nextSection: Section = initialMode === 'rollback' ? 'releases' : initialSection
    setSection(nextSection)
    setSelectedId(nextSection === 'staging' ? stagingVersion?.id ?? null : nextSection === 'production' ? productionVersion?.id ?? null : null)
    setActivationTargetId(null)
    setDescription('')
  }, [initialMode, initialSection, open, productionVersion?.id, stagingVersion?.id])

  useEffect(() => {
    if (!open || initialMode !== 'rollback' || activationsQuery.isLoading || activationTargetId) return
    const previousId = activationsQuery.data?.[0]?.previous_version_id
    const target = rollbackCandidates.find((item) => item.id === previousId) ?? rollbackCandidates[0]
    if (!target) return
    setSection('releases')
    setSelectedId(target.id)
    setActivationTargetId(target.id)
    setDescription(`Rollback from ${productionVersion?.version ?? 'current Production'} to ${target.version}.`)
  }, [activationTargetId, activationsQuery.data, activationsQuery.isLoading, initialMode, open, productionVersion?.version, rollbackCandidates])

  const selectedVersion = section === 'staging' ? stagingVersion : section === 'production' ? productionVersion : section === 'releases' ? releases.find((item) => item.id === selectedId) ?? releases[0] ?? null : null
  const activationTarget = activationTargetId ? releases.find((item) => item.id === activationTargetId) ?? null : null
  const confirmActivation = async () => { if (!activationTarget || description.trim().length < 3) return; await onActivate(activationTarget.id, description.trim()); await activationsQuery.refetch(); setActivationTargetId(null); setDescription('') }
  const selectRelease = (version: NetworkVersion) => { setSelectedId(version.id); if (initialMode === 'rollback') { setActivationTargetId(version.id); setDescription(`Rollback from ${productionVersion?.version ?? 'current Production'} to ${version.version}.`) } }

  return (
    <Dialog open={open} onClose={onClose} title="Manage Network" className="max-h-[90svh] max-w-[1120px] overflow-hidden">
      <div className="-m-6 grid h-[calc(90svh-6rem)] max-h-[740px] grid-rows-[auto_minmax(0,1fr)_auto] overflow-hidden">
        <header className="flex items-center gap-ui-md border-b border-border bg-background/25 px-ui-md py-ui-md">
          <div className="flex h-control w-control items-center justify-center rounded-control border border-primary/25 bg-primary/10 text-primary-light"><History className="h-icon w-icon" /></div>
          <div className="min-w-0">
            <p className="truncate font-sans text-product-small font-semibold text-white">{networkName}</p>
            <p className="mt-ui-hairline font-sans text-product-caption text-muted-foreground">Draft, Staging, immutable Releases and Production activations.</p>
          </div>
          <span className="ml-auto rounded-technical border border-emerald-500/25 bg-emerald-500/10 px-ui-sm py-ui-xs font-mono text-system-label text-emerald-300">{productionVersion ? `Production · ${productionVersion.version}` : 'No Production'}</span>
        </header>

        <div className="grid min-h-0 overflow-hidden lg:grid-cols-[210px_260px_minmax(0,1fr)]">
          <ScrollArea orientation="both" className="border-b border-border bg-surface/30 lg:border-b-0 lg:border-r">
            <nav className="flex min-w-max gap-ui-sm p-ui-md lg:min-w-0 lg:flex-col">
              <SectionButton active={section === 'draft'} icon={FilePenLine} label="Draft" detail={`r${draftRevision} · editable`} onClick={() => { setSection('draft'); setActivationTargetId(null) }} />
              <SectionButton active={section === 'staging'} icon={ShieldCheck} label="Staging" detail={stagingVersion?.version ?? 'Not created'} onClick={() => { setSection('staging'); setActivationTargetId(null) }} />
              <SectionButton active={section === 'production'} icon={Rocket} label="Production" detail={productionVersion?.version ?? 'Not published'} onClick={() => { setSection('production'); setActivationTargetId(null) }} />
              <SectionButton active={section === 'releases'} icon={Layers3} label="Releases" detail={`${releases.length} immutable`} onClick={() => { setSection('releases'); setActivationTargetId(null) }} />
              <SectionButton active={section === 'activity'} icon={Activity} label="Activity" detail={`${activationsQuery.data?.length ?? 0} events`} onClick={() => { setSection('activity'); setActivationTargetId(null) }} />
            </nav>
          </ScrollArea>

          <ScrollArea className="border-b border-border bg-background/20 lg:border-b-0 lg:border-r">
            {section === 'releases'
              ? <VersionList versions={initialMode === 'rollback' ? rollbackCandidates : releases} selectedId={selectedVersion?.id ?? null} activeId={productionVersion?.id} onSelect={selectRelease} />
              : section === 'activity'
                ? <ActivityList activations={activationsQuery.data ?? []} versions={versions} />
                : <div className="p-ui-md font-sans text-product-caption text-muted-foreground">Select the current environment details.</div>}
          </ScrollArea>

          <ScrollArea className="bg-surface/10">
            {activationTarget ? (
              <div className="space-y-ui-md p-ui-md">
                <div>
                  <p className="font-mono text-system-meta uppercase tracking-ui-label text-amber-300">{initialMode === 'rollback' ? 'Rollback target' : 'Production activation'}</p>
                  <h3 className="mt-ui-xs font-mono text-heading-sm text-white">{activationTarget.version}</h3>
                  <p className="mt-ui-xs font-mono text-system-meta text-muted-foreground">Current: {productionVersion?.version ?? 'none'}</p>
                </div>
                <label className="block font-mono text-system-label text-muted-foreground">
                  Reason / audit note
                  <Textarea value={description} onChange={(event) => setDescription(event.target.value)} className="mt-ui-sm min-h-24" />
                </label>
                <p className="font-sans text-system-meta text-muted-foreground">Required for Production audit. The Network pointer changes; Agent Playground Productions do not.</p>
              </div>
            ) : section === 'draft' ? (
              <DraftDetails definition={draftDefinition} revision={draftRevision} dirty={draftDirty} agents={agents} />
            ) : selectedVersion ? (
              <SnapshotDetails version={selectedVersion} agents={agents} />
            ) : (
              <div className="flex h-full items-center justify-center p-ui-xl font-sans text-product-caption text-muted-foreground">No version available.</div>
            )}
          </ScrollArea>
        </div>

        <footer className="flex flex-wrap items-center gap-ui-sm border-t border-border bg-background/30 px-ui-md py-ui-md">
          <p className="min-w-0 flex-1 truncate font-sans text-product-caption text-muted-foreground">{activationTarget ? `${initialMode === 'rollback' ? 'Rollback' : 'Activation'} changes only Network Production.` : 'Network and Agent Playground Production remain independent.'}</p>
          {activationTarget ? (
            <>
              <Button type="button" size="sm" variant="outline" onClick={initialMode === 'rollback' ? onClose : () => setActivationTargetId(null)}>Cancel</Button>
              <Button type="button" size="sm" variant="outline" className="border-amber-500/40 bg-amber-500/10 text-amber-200 hover:border-amber-400/55 hover:bg-amber-500/15 hover:text-amber-100" disabled={pending || description.trim().length < 3} onClick={() => void confirmActivation()}>{pending ? 'Applying…' : initialMode === 'rollback' ? `Rollback to ${activationTarget.version}` : `Activate ${activationTarget.version}`}</Button>
            </>
          ) : (
            <>
              <Button type="button" size="sm" variant="outline" onClick={onClose}>Close</Button>
              {selectedVersion ? <Button type="button" size="sm" variant="outline" onClick={() => onViewVersion(selectedVersion)}><Eye className="h-icon-sm w-icon-sm" />View on Canvas</Button> : null}
              {section === 'draft' ? <Button type="button" size="sm" disabled={pending} onClick={onStage}>Stage Network</Button> : null}
              {selectedVersion?.id === stagingVersion?.id ? <Button type="button" size="sm" disabled={pending} onClick={onPublish}>Publish Network Release</Button> : null}
              {selectedVersion?.kind === 'release' && selectedVersion.id !== productionVersion?.id ? <Button type="button" size="sm" variant="outline" className="border-emerald-500/40 bg-emerald-500/10 text-emerald-300 hover:border-emerald-400/55 hover:bg-emerald-500/15 hover:text-emerald-200" disabled={pending} onClick={() => { setActivationTargetId(selectedVersion.id); setDescription(`Activate ${selectedVersion.version} in Network Production.`) }}>Set as Production</Button> : null}
            </>
          )}
        </footer>
      </div>
    </Dialog>
  )
}
