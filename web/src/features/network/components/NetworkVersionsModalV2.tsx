import { useEffect, useMemo, useRef, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Activity, Eye, FilePenLine, History, Layers3, Network, Rocket, ShieldCheck } from 'lucide-react'
import { useParams } from 'react-router-dom'

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
  return <button type="button" onClick={onClick} className={cn('flex min-w-[170px] items-center gap-2 rounded-xl border px-3 py-2 text-left lg:min-w-0', active ? 'border-primary/35 bg-primary/10 text-white' : 'border-transparent text-muted hover:border-border hover:text-white')}><Icon className="h-3.5 w-3.5" /><span className="min-w-0"><span className="block text-[10px] font-semibold">{label}</span><span className="block truncate text-[8px] text-muted">{detail}</span></span></button>
}

function VersionList({ versions, selectedId, activeId, onSelect }: { versions: NetworkVersion[]; selectedId: string | null; activeId?: string | null; onSelect: (version: NetworkVersion) => void }) {
  if (!versions.length) return <p className="p-4 text-[9px] text-muted">No versions available.</p>
  return <div className="space-y-1 p-2">{versions.map((version) => <button key={version.id} type="button" onClick={() => onSelect(version)} className={cn('w-full rounded-xl border p-3 text-left', selectedId === version.id ? 'border-primary/35 bg-primary/10' : 'border-border/70 bg-background/25 hover:border-border')}><div className="flex items-center gap-2"><span className="truncate font-mono text-[10px] text-white">{version.version}</span>{version.id === activeId ? <span className="ml-auto rounded border border-emerald-500/30 bg-emerald-500/10 px-1.5 py-0.5 text-[8px] text-emerald-300">Active</span> : null}</div><p className="mt-1 text-[8px] text-muted">{formatDate(version.created_at)} · {version.definition.nodes.length} Agents</p></button>)}</div>
}

function SnapshotDetails({ version, agents }: { version: NetworkVersion; agents: Agent[] }) {
  const agentsById = new Map(agents.map((agent) => [agent.id, agent]))
  return <div className="space-y-4 p-4"><div><p className="text-[8px] uppercase tracking-wider text-primary-light">{version.kind === 'release' ? 'Network Release' : 'Network Staging'}</p><h3 className="mt-1 font-mono text-sm font-semibold text-white">{version.version}</h3><p className="mt-1 text-[9px] text-muted">Immutable snapshot · {formatDate(version.created_at)}</p></div><section className="rounded-xl border border-border bg-background/30 p-3"><div className="grid grid-cols-3 gap-3 text-[9px]"><div><p className="text-muted">Agents</p><p className="mt-1 text-white">{version.definition.nodes.length}</p></div><div><p className="text-muted">Delegations</p><p className="mt-1 text-white">{version.definition.edges.length}</p></div><div><p className="text-muted">Mode</p><p className="mt-1 capitalize text-white">{version.definition.settings.session_mode}</p></div></div></section><section><p className="mb-2 text-[9px] font-semibold uppercase tracking-wide text-muted">Agent bindings</p><div className="space-y-2">{version.definition.nodes.map((node) => { const resolved = version.resolved_bindings[node.id]; const source = resolved?.binding_source === 'release' || resolved?.snapshot_kind === 'release' ? 'release' : 'staging'; const label = agentsById.get(node.agent_id)?.name ?? node.label; return <div key={node.id} className="flex items-center gap-3 rounded-xl border border-border bg-background/30 p-3"><div className="min-w-0 flex-1"><p className="truncate text-[10px] text-white">{label}</p><p className="mt-1 text-[8px] text-muted">{node.id === version.definition.root_node_id ? 'Entry Agent' : 'Specialist'}</p></div><div className="w-44"><NetworkBindingBadge source={source} version={resolved?.release_version ?? 'pinned'} /></div></div> })}</div></section>{version.kind === 'release' ? <p className="rounded-xl border border-emerald-500/20 bg-emerald-500/[0.04] p-3 text-[9px] leading-4 text-emerald-200">This Network Release uses exact Agent Release IDs. It does not depend on Agent Playground Production.</p> : null}</div>
}

function DraftDetails({ definition, revision, dirty, agents }: { definition: NetworkDefinition; revision: number; dirty: boolean; agents: Agent[] }) {
  const agentsById = new Map(agents.map((agent) => [agent.id, agent]))
  return <div className="space-y-4 p-4"><div><p className="text-[8px] uppercase tracking-wider text-primary-light">Editable Network Draft</p><h3 className="mt-1 text-sm font-semibold text-white">Revision {revision}</h3><p className="mt-1 text-[9px] text-muted">{dirty ? 'Unsaved changes' : 'Saved'} · Draft bindings remain unchanged after promotion.</p></div><div className="space-y-2">{definition.nodes.map((node) => <div key={node.id} className="flex items-center gap-3 rounded-xl border border-border bg-background/30 p-3"><div className="min-w-0 flex-1"><p className="truncate text-[10px] text-white">{agentsById.get(node.agent_id)?.name ?? node.label}</p><p className="mt-1 text-[8px] text-muted">{node.id === definition.root_node_id ? 'Entry Agent' : 'Specialist'}</p></div><div className="w-44"><NetworkBindingBadge source={node.binding.source} version={node.binding.source === 'draft' ? 'current' : 'pinned'} /></div></div>)}</div></div>
}

function ActivityList({ activations, versions }: { activations: NetworkProductionActivation[]; versions: NetworkVersion[] }) {
  if (!activations.length) return <p className="p-4 text-[9px] text-muted">No Production activity.</p>
  return <div className="space-y-2 p-3">{activations.map((activation) => { const version = versions.find((item) => item.id === activation.version_id); return <article key={activation.id} className="rounded-xl border border-border bg-background/30 p-3"><div className="flex items-center gap-2"><span className="font-mono text-[10px] text-white">{version?.version ?? activation.version_id.slice(0, 8)}</span><span className="ml-auto rounded border border-border px-1.5 py-0.5 text-[8px] capitalize text-muted">{activation.activation_kind}</span></div><p className="mt-2 text-[9px] leading-4 text-slate-300">{activation.change_description}</p><p className="mt-1 text-[8px] text-muted">{formatDate(activation.created_at)}</p></article> })}</div>
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

  return <Dialog open={open} onClose={onClose} title="Manage Network" className="max-h-[90svh] max-w-[1120px] overflow-hidden"><div className="-m-6 grid h-[calc(90svh-6rem)] max-h-[740px] grid-rows-[auto_minmax(0,1fr)_auto] overflow-hidden"><header className="flex items-center gap-3 border-b border-border bg-background/25 px-4 py-3"><div className="flex h-9 w-9 items-center justify-center rounded-xl border border-primary/25 bg-primary/10 text-primary-light"><History className="h-4 w-4" /></div><div className="min-w-0"><p className="truncate text-[12px] font-semibold text-white">{networkName}</p><p className="mt-0.5 text-[9px] text-muted">Draft, Staging, immutable Releases and Production activations.</p></div><span className="ml-auto rounded-lg border border-emerald-500/25 bg-emerald-500/10 px-2.5 py-1 font-mono text-[9px] text-emerald-300">{productionVersion ? `Production · ${productionVersion.version}` : 'No Production'}</span></header><div className="grid min-h-0 overflow-hidden lg:grid-cols-[210px_260px_minmax(0,1fr)]"><ScrollArea orientation="both" className="border-b border-border bg-surface/30 lg:border-b-0 lg:border-r"><nav className="flex min-w-max gap-2 p-3 lg:min-w-0 lg:flex-col"><SectionButton active={section === 'draft'} icon={FilePenLine} label="Draft" detail={`r${draftRevision} · editable`} onClick={() => { setSection('draft'); setActivationTargetId(null) }} /><SectionButton active={section === 'staging'} icon={ShieldCheck} label="Staging" detail={stagingVersion?.version ?? 'Not created'} onClick={() => { setSection('staging'); setActivationTargetId(null) }} /><SectionButton active={section === 'production'} icon={Rocket} label="Production" detail={productionVersion?.version ?? 'Not published'} onClick={() => { setSection('production'); setActivationTargetId(null) }} /><SectionButton active={section === 'releases'} icon={Layers3} label="Releases" detail={`${releases.length} immutable`} onClick={() => { setSection('releases'); setActivationTargetId(null) }} /><SectionButton active={section === 'activity'} icon={Activity} label="Activity" detail={`${activationsQuery.data?.length ?? 0} events`} onClick={() => { setSection('activity'); setActivationTargetId(null) }} /></nav></ScrollArea><ScrollArea className="border-b border-border bg-background/20 lg:border-b-0 lg:border-r">{section === 'releases' ? <VersionList versions={initialMode === 'rollback' ? rollbackCandidates : releases} selectedId={selectedVersion?.id ?? null} activeId={productionVersion?.id} onSelect={selectRelease} /> : section === 'activity' ? <ActivityList activations={activationsQuery.data ?? []} versions={versions} /> : <div className="p-4 text-[9px] text-muted">Select the current environment details.</div>}</ScrollArea><ScrollArea className="bg-surface/10">{activationTarget ? <div className="space-y-4 p-4"><div><p className="text-[8px] uppercase tracking-wide text-amber-300">{initialMode === 'rollback' ? 'Rollback target' : 'Production activation'}</p><h3 className="mt-1 font-mono text-sm text-white">{activationTarget.version}</h3><p className="mt-1 text-[9px] text-muted">Current: {productionVersion?.version ?? 'none'}</p></div><label className="block text-[9px] text-muted">Reason / audit note<textarea value={description} onChange={(event) => setDescription(event.target.value)} className="mt-2 min-h-24 w-full rounded-xl border border-border bg-background/50 p-3 text-[10px] text-white outline-none focus:border-primary/40" /></label><p className="text-[8px] text-muted">Required for Production audit. The Network pointer changes; Agent Playground Productions do not.</p></div> : section === 'draft' ? <DraftDetails definition={draftDefinition} revision={draftRevision} dirty={draftDirty} agents={agents} /> : selectedVersion ? <SnapshotDetails version={selectedVersion} agents={agents} /> : <div className="flex h-full items-center justify-center p-6 text-[10px] text-muted">No version available.</div>}</ScrollArea></div><footer className="flex flex-wrap items-center gap-3 border-t border-border bg-background/30 px-4 py-3"><p className="min-w-0 flex-1 truncate text-[9px] text-muted">{activationTarget ? `${initialMode === 'rollback' ? 'Rollback' : 'Activation'} changes only Network Production.` : 'Network and Agent Playground Production remain independent.'}</p>{activationTarget ? <><button type="button" onClick={initialMode === 'rollback' ? onClose : () => setActivationTargetId(null)} className="rounded-lg border border-border px-3 py-2 text-[10px] text-muted hover:text-white">Cancel</button><button type="button" disabled={pending || description.trim().length < 3} onClick={() => void confirmActivation()} className="rounded-lg bg-amber-600 px-3 py-2 text-[10px] font-semibold text-white disabled:opacity-45">{pending ? 'Applying…' : initialMode === 'rollback' ? `Rollback to ${activationTarget.version}` : `Activate ${activationTarget.version}`}</button></> : <><button type="button" onClick={onClose} className="rounded-lg border border-border px-3 py-2 text-[10px] text-muted hover:text-white">Close</button>{selectedVersion ? <button type="button" onClick={() => onViewVersion(selectedVersion)} className="inline-flex items-center gap-2 rounded-lg border border-border px-3 py-2 text-[10px] text-primary-light"><Eye className="h-3.5 w-3.5" />View on Canvas</button> : null}{section === 'draft' ? <button type="button" disabled={pending} onClick={onStage} className="rounded-lg bg-primary px-3 py-2 text-[10px] font-semibold text-white disabled:opacity-45">Stage Network</button> : null}{selectedVersion?.id === stagingVersion?.id ? <button type="button" disabled={pending} onClick={onPublish} className="rounded-lg bg-primary px-3 py-2 text-[10px] font-semibold text-white disabled:opacity-45">Publish Network Release</button> : null}{selectedVersion?.kind === 'release' && selectedVersion.id !== productionVersion?.id ? <button type="button" disabled={pending} onClick={() => { setActivationTargetId(selectedVersion.id); setDescription(`Activate ${selectedVersion.version} in Network Production.`) }} className="rounded-lg border border-emerald-500/40 bg-emerald-500/10 px-3 py-2 text-[10px] text-emerald-300">Set as Production</button> : null}</>}</footer></div></Dialog>
}
