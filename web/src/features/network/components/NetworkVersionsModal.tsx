import { useEffect, useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useParams } from 'react-router-dom'
import { Activity, ArrowLeft, Eye, History, Lock, Network, Rocket, X } from 'lucide-react'

import { ScrollArea } from '@/components/ui/ScrollArea'
import type { Agent } from '@/features/agents/types'
import { getNetwork, getNetworkProductionActivations } from '@/features/network/api'
import type {
  NetworkDefinition,
  NetworkProductionActivation,
  NetworkVersion,
} from '@/features/network/types'
import { cn } from '@/lib/utils'

interface NetworkVersionsModalProps {
  open: boolean
  networkName: string
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

type ModalView = 'overview' | 'releases' | 'staging' | 'activity' | 'details'

function formatDate(value?: string) {
  if (!value) return '—'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '—'
  return new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeStyle: 'short' }).format(date)
}

function changeLabel(version: NetworkVersion) {
  if (version.change_kind === 'compatibility') return 'Compatibility change'
  if (version.change_kind === 'feature') return 'Feature change'
  if (version.change_kind === 'change') return 'Internal change'
  return version.kind === 'staging' ? 'Validation snapshot' : 'Immutable Release'
}

function contractLabel(version: NetworkVersion) {
  const contract = version.public_output_contract
  if (!contract?.enabled) return 'Text response'
  const properties = contract.schema?.properties
  const count = properties && typeof properties === 'object' ? Object.keys(properties).length : 0
  return count ? `Structured JSON · ${count} fields` : 'Structured JSON'
}

function diffVersion(current: NetworkVersion | null, target: NetworkVersion) {
  if (!current) return ['This will become the first Production Release.']
  const changes: string[] = []
  if (current.public_output_contract_hash !== target.public_output_contract_hash) {
    changes.push('Public output contract differs from the active Production contract.')
  }
  const currentNodes = new Map(current.definition.nodes.map((node) => [node.id, node]))
  const targetNodes = new Map(target.definition.nodes.map((node) => [node.id, node]))
  const added = target.definition.nodes.filter((node) => !currentNodes.has(node.id)).length
  const removed = current.definition.nodes.filter((node) => !targetNodes.has(node.id)).length
  if (added || removed) changes.push(`Composition: ${added} Agent${added === 1 ? '' : 's'} added, ${removed} removed.`)
  const edgeDelta = target.definition.edges.length - current.definition.edges.length
  if (edgeDelta) changes.push(`Delegations: ${Math.abs(edgeDelta)} ${edgeDelta > 0 ? 'added' : 'removed'}.`)
  for (const item of target.agent_release_manifest ?? []) {
    const before = current.agent_release_manifest?.find((candidate) => candidate.node_id === item.node_id)
    if (before && before.release_id !== item.release_id) {
      changes.push(`${item.role === 'entry' ? 'Entry Agent' : 'Specialist'}: ${before.release_version} → ${item.release_version}.`)
    }
  }
  const before = current.definition.settings
  const after = target.definition.settings
  if (before.max_depth !== after.max_depth) changes.push(`Max depth: ${before.max_depth} → ${after.max_depth}.`)
  if (before.max_invocations !== after.max_invocations) changes.push(`Max invocations: ${before.max_invocations} → ${after.max_invocations}.`)
  if (before.timeout_seconds !== after.timeout_seconds) changes.push(`Timeout: ${before.timeout_seconds}s → ${after.timeout_seconds}s.`)
  if (before.session_mode !== after.session_mode) changes.push(`Session mode: ${before.session_mode} → ${after.session_mode}.`)
  return changes.length ? changes : ['No operational differences were detected in the stored snapshots.']
}

function Metric({ label, value }: { label: string; value: string }) {
  return <div className="rounded-lg border border-border/75 bg-background/40 p-3"><p className="text-[9px] uppercase tracking-wide text-muted">{label}</p><p className="mt-1 text-[12px] font-medium text-white">{value}</p></div>
}

function Info({ label, value, mono = false }: { label: string; value: string; mono?: boolean }) {
  return <div className="min-w-0"><p className="text-[9px] uppercase tracking-wide text-muted">{label}</p><p className={cn('mt-1 break-words text-[11px] text-slate-200', mono && 'font-mono')}>{value}</p></div>
}

function EnvironmentCard({
  eyebrow,
  title,
  detail,
  tone,
  metrics,
  primary,
  secondary,
}: {
  eyebrow: string
  title: string
  detail: string
  tone: 'draft' | 'staging' | 'production'
  metrics: Array<[string, string]>
  primary?: { label: string; onClick: () => void; disabled?: boolean }
  secondary?: { label: string; onClick: () => void }
}) {
  const toneClass = tone === 'production'
    ? 'border-emerald-500/25 bg-emerald-500/[0.04] text-emerald-300'
    : tone === 'staging'
      ? 'border-indigo-500/25 bg-indigo-500/[0.04] text-indigo-300'
      : 'border-primary/25 bg-primary/[0.04] text-primary-light'
  return (
    <article className={cn('flex min-h-[230px] flex-col rounded-2xl border p-4', toneClass)}>
      <p className="text-[9px] font-semibold uppercase tracking-widest">{eyebrow}</p>
      <h3 className="mt-2 font-mono text-base font-semibold text-white">{title}</h3>
      <p className="mt-1 min-h-8 text-[10px] leading-4 text-muted">{detail}</p>
      <div className="mt-4 grid grid-cols-2 gap-2">
        {metrics.map(([label, value]) => <Metric key={label} label={label} value={value} />)}
      </div>
      <div className="mt-auto flex flex-wrap gap-2 pt-4">
        {secondary ? <button type="button" onClick={secondary.onClick} className="rounded-lg border border-border bg-background/45 px-3 py-2 text-[10px] font-medium text-muted hover:text-white">{secondary.label}</button> : null}
        {primary ? <button type="button" disabled={primary.disabled} onClick={primary.onClick} className="rounded-lg bg-primary px-3 py-2 text-[10px] font-semibold text-white disabled:cursor-not-allowed disabled:opacity-45">{primary.label}</button> : null}
      </div>
    </article>
  )
}

function SnapshotSummary({ version, agents }: { version: NetworkVersion; agents: Agent[] }) {
  const agentsById = useMemo(() => new Map(agents.map((agent) => [agent.id, agent])), [agents])
  const root = version.definition.nodes.find((node) => node.id === version.definition.root_node_id)
  const manifest = version.agent_release_manifest ?? version.definition.nodes.map((node) => ({
    node_id: node.id,
    role: node.id === version.definition.root_node_id ? 'entry' as const : 'specialist' as const,
    agent_id: node.agent_id,
    release_id: version.resolved_bindings[node.id]?.release_id ?? '',
    release_version: version.resolved_bindings[node.id]?.release_version ?? 'Unavailable',
    snapshot_hash: version.resolved_bindings[node.id]?.snapshot_hash ?? '',
    output_contract_hash: '',
  }))
  return (
    <div className="space-y-4">
      <section className="grid grid-cols-2 gap-2 lg:grid-cols-4">
        <Metric label="Agents" value={String(version.definition.nodes.length)} />
        <Metric label="Delegations" value={String(version.definition.edges.length)} />
        <Metric label="Public output" value={contractLabel(version)} />
        <Metric label="Change" value={changeLabel(version)} />
      </section>
      <section className="rounded-xl border border-border/80 bg-background/35 p-4">
        <p className="text-[10px] font-semibold uppercase tracking-wide text-muted">Release identity</p>
        <div className="mt-3 grid gap-3 text-[11px] sm:grid-cols-2 lg:grid-cols-3">
          <Info label="Entry Agent" value={root?.label ?? 'Not configured'} />
          <Info label="Entry Agent Release" value={version.entry_agent_release_version ?? 'Legacy snapshot'} mono />
          <Info label="Created" value={formatDate(version.created_at)} />
          <Info label="Session mode" value={version.definition.settings.session_mode} />
          <Info label="Max depth" value={String(version.definition.settings.max_depth)} />
          <Info label="Timeout" value={`${version.definition.settings.timeout_seconds}s`} />
        </div>
      </section>
      <section className="rounded-xl border border-border/80 bg-background/35 p-4">
        <p className="text-[10px] font-semibold uppercase tracking-wide text-muted">Inherited public output contract</p>
        <p className="mt-2 text-[10px] leading-5 text-slate-300">Inherited and frozen from the entry Agent Release. This is the contract used to classify Network compatibility.</p>
        {version.public_output_contract ? <pre className="scrollbar-thin mt-3 max-h-56 overflow-auto rounded-lg border border-border/70 bg-black/20 p-3 text-[9px] leading-5 text-slate-300">{JSON.stringify(version.public_output_contract, null, 2)}</pre> : <div className="mt-3 rounded-lg border border-border/70 bg-surface/40 px-3 py-2 text-[10px] text-muted">Text response. No structured output contract is configured.</div>}
      </section>
      <section className="rounded-xl border border-border/80 bg-background/35 p-4">
        <p className="text-[10px] font-semibold uppercase tracking-wide text-muted">Agent Release manifest</p>
        <div className="mt-3 space-y-2">
          {manifest.map((item) => {
            const node = version.definition.nodes.find((candidate) => candidate.id === item.node_id)
            const agent = agentsById.get(item.agent_id)
            return <div key={item.node_id} className="grid gap-3 rounded-lg border border-border/70 bg-surface/40 px-3 py-2.5 text-[10px] sm:grid-cols-[minmax(0,1.2fr)_minmax(0,1fr)_minmax(0,1fr)]"><div className="min-w-0"><p className="truncate font-medium text-white">{node?.label ?? agent?.name ?? item.agent_id}</p><p className="mt-0.5 capitalize text-muted">{item.role === 'entry' ? 'Entry point' : 'Specialist'}</p></div><div className="min-w-0"><p className="truncate font-mono text-slate-200">{item.release_version}</p><p className="mt-0.5 truncate text-muted">{agent ? `${agent.provider}/${agent.model}` : 'Agent snapshot'}</p></div><div className="min-w-0"><p className="truncate font-mono text-[9px] text-slate-400">{item.snapshot_hash || 'Legacy hash unavailable'}</p><p className="mt-0.5 text-muted">Execution snapshot</p></div></div>
          })}
        </div>
      </section>
      <details className="rounded-xl border border-border/80 bg-background/35 p-4">
        <summary className="cursor-pointer text-[10px] font-semibold uppercase tracking-wide text-muted">Advanced technical details</summary>
        <div className="mt-3 space-y-3"><Info label="Network Version ID" value={version.id} mono /><Info label="Composition hash" value={version.composition_hash} mono /><Info label="Release fingerprint" value={version.release_fingerprint ?? 'Legacy fingerprint unavailable'} mono /><pre className="scrollbar-thin max-h-64 overflow-auto rounded-lg border border-border/70 bg-black/20 p-3 text-[9px] leading-5 text-slate-300">{JSON.stringify({ definition: version.definition, resolved_bindings: version.resolved_bindings }, null, 2)}</pre></div>
      </details>
    </div>
  )
}

function VersionList({ versions, activeId, onSelect }: { versions: NetworkVersion[]; activeId?: string | null; onSelect: (version: NetworkVersion) => void }) {
  if (!versions.length) return <div className="rounded-xl border border-dashed border-border p-5 text-center text-[10px] text-muted">No versions in this category.</div>
  return <div className="space-y-2">{versions.map((version) => <button key={version.id} type="button" onClick={() => onSelect(version)} className="flex w-full items-center gap-3 rounded-xl border border-border/75 bg-background/35 p-3 text-left hover:border-primary/30"><div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-border bg-surface/50 text-primary-light"><Network className="h-4 w-4" /></div><div className="min-w-0 flex-1"><div className="flex items-center gap-2"><p className="truncate font-mono text-[11px] text-white">{version.version}</p>{version.id === activeId ? <span className="rounded border border-emerald-500/30 bg-emerald-500/10 px-1.5 py-0.5 text-[8px] font-semibold uppercase text-emerald-300">Active</span> : null}</div><p className="mt-1 truncate text-[9px] text-muted">{changeLabel(version)} · {formatDate(version.created_at)}</p></div><span className="text-[9px] text-muted">View</span></button>)}</div>
}

function ActivityList({ activations, versions }: { activations: NetworkProductionActivation[]; versions: NetworkVersion[] }) {
  const versionById = new Map(versions.map((version) => [version.id, version]))
  if (!activations.length) return <div className="rounded-xl border border-dashed border-border p-5 text-center text-[10px] text-muted">No Production activity recorded yet.</div>
  return <div className="space-y-2">{activations.map((activation) => <article key={activation.id} className="rounded-xl border border-border/75 bg-background/35 p-4"><div className="flex items-start gap-3"><div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-border bg-surface/50 text-emerald-300"><Activity className="h-4 w-4" /></div><div className="min-w-0 flex-1"><p className="text-[10px] font-medium capitalize text-white">{activation.activation_kind} · <span className="font-mono">{versionById.get(activation.version_id)?.version ?? activation.version_id}</span></p><p className="mt-1 text-[9px] text-muted">{formatDate(activation.created_at)}</p><p className="mt-3 text-[10px] leading-5 text-slate-300">{activation.change_description}</p></div></div></article>)}</div>
}

export function NetworkVersionsModal({ open, networkName, draftDefinition, draftRevision, draftDirty, stagingVersion, productionVersion, versions, agents, pending, onClose, onStage, onPublish, onViewVersion, onActivate }: NetworkVersionsModalProps) {
  const { projectId } = useParams<{ projectId: string }>()
  const networkResource = useQuery({ queryKey: ['network-version-modal-resource', projectId], queryFn: () => getNetwork(projectId!), enabled: Boolean(open && projectId), staleTime: 30_000 })
  const activations = useQuery({ queryKey: ['network-production-activations', networkResource.data?.id, projectId], queryFn: () => getNetworkProductionActivations(networkResource.data!.id, projectId!), enabled: Boolean(open && projectId && networkResource.data?.id) })
  const releases = useMemo(() => versions.filter((version) => version.kind === 'release'), [versions])
  const stagingSnapshots = useMemo(() => versions.filter((version) => version.kind === 'staging'), [versions])
  const [view, setView] = useState<ModalView>('overview')
  const [selectedVersion, setSelectedVersion] = useState<NetworkVersion | null>(null)
  const [activateId, setActivateId] = useState<string | null>(null)
  const [description, setDescription] = useState('')

  useEffect(() => {
    if (!open) return
    setView('overview')
    setSelectedVersion(null)
    setActivateId(null)
    setDescription('')
  }, [open])

  if (!open) return null
  const activationTarget = activateId ? versions.find((version) => version.id === activateId) ?? null : null
  const changes = activationTarget ? diffVersion(productionVersion, activationTarget) : []
  const openDetails = (version: NetworkVersion) => { setSelectedVersion(version); setView('details') }
  const confirmActivation = async () => {
    if (!activationTarget || description.trim().length < 3) return
    await onActivate(activationTarget.id, description.trim())
    setActivateId(null)
    setDescription('')
    await activations.refetch()
  }

  const main = view === 'overview' ? (
    <div className="space-y-5">
      <div><p className="text-[9px] font-semibold uppercase tracking-widest text-primary-light">Release pipeline</p><h3 className="mt-1 text-lg font-semibold text-white">Current environments</h3><p className="mt-1 text-[10px] text-muted">Draft, immutable validation and active Production remain distinct and traceable.</p></div>
      <div className="grid gap-3 xl:grid-cols-3">
        <EnvironmentCard eyebrow="Current Draft" title={`Draft r${draftRevision}`} detail={draftDirty ? 'Editable workspace with unsaved changes.' : 'Editable workspace saved and ready for validation.'} tone="draft" metrics={[["Agents", String(draftDefinition.nodes.length)], ["Delegations", String(draftDefinition.edges.length)], ["Session", draftDefinition.settings.session_mode], ["Output", "Entry Agent"]]} primary={{ label: 'Stage Network', onClick: onStage, disabled: pending }} />
        <EnvironmentCard eyebrow="Current Staging" title={stagingVersion?.version ?? 'Not created'} detail={stagingVersion ? `Inherited output: ${contractLabel(stagingVersion)}` : 'Create an immutable validation snapshot from Draft.'} tone="staging" metrics={stagingVersion ? [["Agents", String(stagingVersion.definition.nodes.length)], ["Delegations", String(stagingVersion.definition.edges.length)], ["Entry Release", stagingVersion.entry_agent_release_version ?? 'Legacy'], ["Created", formatDate(stagingVersion.created_at)]] : [["Agents", '—'], ["Delegations", '—'], ["Entry Release", '—'], ["Created", '—']]} secondary={stagingVersion ? { label: 'View snapshot', onClick: () => openDetails(stagingVersion) } : undefined} primary={stagingVersion ? { label: 'Publish Release', onClick: onPublish, disabled: pending } : undefined} />
        <EnvironmentCard eyebrow="Active Production" title={productionVersion?.version ?? 'Not published'} detail={productionVersion ? `${changeLabel(productionVersion)} · ${contractLabel(productionVersion)}` : 'Publish the validated Staging snapshot to Production.'} tone="production" metrics={productionVersion ? [["Agents", String(productionVersion.definition.nodes.length)], ["Delegations", String(productionVersion.definition.edges.length)], ["Entry Release", productionVersion.entry_agent_release_version ?? 'Legacy'], ["Activated", formatDate((activations.data ?? [])[0]?.created_at ?? productionVersion.created_at)]] : [["Agents", '—'], ["Delegations", '—'], ["Entry Release", '—'], ["Activated", '—']]} secondary={productionVersion ? { label: 'View snapshot', onClick: () => openDetails(productionVersion) } : undefined} />
      </div>
      <section className="rounded-2xl border border-border/80 bg-background/25 p-4"><p className="text-[10px] font-semibold uppercase tracking-wide text-muted">History</p><div className="mt-3 grid gap-2 sm:grid-cols-3"><button type="button" onClick={() => setView('releases')} className="rounded-xl border border-border bg-background/40 p-4 text-left hover:border-primary/30"><p className="text-[12px] font-medium text-white">Releases</p><p className="mt-1 text-[10px] text-muted">{releases.length} immutable product versions</p></button><button type="button" onClick={() => setView('staging')} className="rounded-xl border border-border bg-background/40 p-4 text-left hover:border-primary/30"><p className="text-[12px] font-medium text-white">Staging snapshots</p><p className="mt-1 text-[10px] text-muted">{stagingSnapshots.length} validation snapshots</p></button><button type="button" onClick={() => setView('activity')} className="rounded-xl border border-border bg-background/40 p-4 text-left hover:border-primary/30"><p className="text-[12px] font-medium text-white">Production activity</p><p className="mt-1 text-[10px] text-muted">{activations.data?.length ?? 0} deployments and rollbacks</p></button></div></section>
    </div>
  ) : view === 'details' && selectedVersion ? (
    <div className="space-y-4"><button type="button" onClick={() => setView('overview')} className="inline-flex items-center gap-2 text-[10px] text-muted hover:text-white"><ArrowLeft className="h-3.5 w-3.5" />Back to overview</button><div className="flex items-start gap-3"><div className="flex h-10 w-10 items-center justify-center rounded-xl border border-border bg-background/45 text-primary-light"><Lock className="h-4 w-4" /></div><div className="min-w-0 flex-1"><p className="text-[9px] font-semibold uppercase tracking-widest text-muted">{selectedVersion.kind === 'staging' ? 'Staging snapshot' : selectedVersion.id === productionVersion?.id ? 'Active Production' : 'Network Release'}</p><h3 className="mt-1 font-mono text-lg font-semibold text-white">{selectedVersion.version}</h3><p className="mt-1 text-[10px] text-muted">{selectedVersion.change_description || 'Immutable Network snapshot.'}</p></div></div><SnapshotSummary version={selectedVersion} agents={agents} /><div className="flex flex-wrap gap-2 border-t border-border/80 pt-4"><button type="button" onClick={() => onViewVersion(selectedVersion)} className="inline-flex items-center gap-2 rounded-lg border border-border bg-background/45 px-3 py-2 text-[10px] font-medium text-primary-light hover:border-primary/30 hover:text-white"><Eye className="h-3.5 w-3.5" />View on Canvas</button>{selectedVersion.id === stagingVersion?.id ? <button type="button" onClick={onPublish} className="inline-flex items-center gap-2 rounded-lg bg-primary px-3 py-2 text-[10px] font-semibold text-white"><Rocket className="h-3.5 w-3.5" />Publish Release</button> : null}{selectedVersion.kind === 'release' && selectedVersion.id !== productionVersion?.id ? <button type="button" onClick={() => setActivateId(selectedVersion.id)} className="inline-flex items-center gap-2 rounded-lg border border-emerald-500/40 bg-emerald-500/10 px-3 py-2 text-[10px] font-medium text-emerald-300">Set as Production</button> : null}</div></div>
  ) : (
    <div className="space-y-4"><button type="button" onClick={() => setView('overview')} className="inline-flex items-center gap-2 text-[10px] text-muted hover:text-white"><ArrowLeft className="h-3.5 w-3.5" />Back to overview</button><div><p className="text-[9px] font-semibold uppercase tracking-widest text-primary-light">History</p><h3 className="mt-1 text-lg font-semibold text-white">{view === 'releases' ? 'Network Releases' : view === 'staging' ? 'Staging snapshots' : 'Production activity'}</h3></div>{view === 'releases' ? <VersionList versions={releases} activeId={productionVersion?.id} onSelect={openDetails} /> : view === 'staging' ? <VersionList versions={stagingSnapshots} activeId={stagingVersion?.id} onSelect={openDetails} /> : <ActivityList activations={activations.data ?? []} versions={versions} />}</div>
  )

  return <div className="fixed inset-0 z-[80] flex items-center justify-center bg-black/75 p-4 backdrop-blur-md"><div className="flex max-h-[92vh] w-full max-w-7xl flex-col overflow-hidden rounded-2xl border border-border/90 bg-surface shadow-2xl shadow-black/45"><header className="flex items-start gap-3 border-b border-border/90 bg-background/25 p-5"><div className="flex h-10 w-10 items-center justify-center rounded-xl border border-primary/25 bg-primary/10 text-primary-light"><History className="h-4 w-4" /></div><div className="min-w-0 flex-1"><p className="text-[9px] font-semibold uppercase tracking-widest text-primary-light">Network versions</p><h2 className="mt-1 truncate text-base font-semibold text-white">{networkName}</h2><p className="mt-1 text-[10px] text-muted">Draft, Staging, Releases and Production activity in one operational view.</p></div><button type="button" onClick={onClose} className="rounded-lg border border-border p-2 text-muted hover:text-white"><X className="h-4 w-4" /></button></header><ScrollArea className="min-h-0 flex-1"><main className="p-5">{main}</main></ScrollArea>{activationTarget ? <div className="absolute inset-0 z-10 flex items-center justify-center bg-black/70 p-4 backdrop-blur-sm"><section className="w-full max-w-xl rounded-2xl border border-border bg-surface p-5 shadow-2xl"><p className="text-[9px] font-semibold uppercase tracking-widest text-emerald-300">Production activation</p><h3 className="mt-1 text-base font-semibold text-white">Set {activationTarget.version} as Production?</h3><div className="mt-4 grid grid-cols-2 gap-2"><Metric label="Current" value={productionVersion?.version ?? 'None'} /><Metric label="Selected" value={activationTarget.version} /></div><div className="mt-4 rounded-xl border border-border/80 bg-background/35 p-4"><p className="text-[10px] font-medium text-white">Changes from current Production</p><ul className="mt-2 space-y-1">{changes.map((change) => <li key={change} className="text-[9px] leading-4 text-muted">• {change}</li>)}</ul></div><label className="mt-4 block"><span className="text-[9px] font-semibold uppercase tracking-wide text-muted">Reason for change</span><textarea value={description} onChange={(event) => setDescription(event.target.value)} rows={4} className="mt-2 w-full resize-none rounded-xl border border-border bg-background/50 p-3 text-[11px] text-white outline-none focus:border-primary/40" placeholder="Explain why this immutable Release should become Production." /></label><p className="mt-3 text-[9px] leading-4 text-muted">Existing Sessions and Runs remain pinned to their original Network versions. This action records a deployment; it does not create a duplicate Release.</p><div className="mt-5 flex justify-end gap-2"><button type="button" onClick={() => { setActivateId(null); setDescription('') }} className="rounded-lg border border-border px-3 py-2 text-[10px] text-muted hover:text-white">Cancel</button><button type="button" disabled={pending || description.trim().length < 3} onClick={() => void confirmActivation()} className="rounded-lg bg-emerald-600 px-3 py-2 text-[10px] font-semibold text-white disabled:cursor-not-allowed disabled:opacity-45">{pending ? 'Activating…' : 'Activate Release'}</button></div></section></div> : null}</div></div>
}
