import { useEffect, useMemo, useState } from 'react'
import { ArrowRight, Eye, GitCompare, History, Lock, Network, Rocket, X } from 'lucide-react'

import { ScrollArea } from '@/components/ui/ScrollArea'
import type { Agent } from '@/features/agents/types'
import type { NetworkDefinition, NetworkVersion } from '@/features/network/types'
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

function formatDate(value?: string) {
  if (!value) return '—'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '—'
  return new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeStyle: 'short' }).format(date)
}

function versionEnvironment(version: NetworkVersion, stagingId?: string | null, productionId?: string | null) {
  if (version.id === productionId) return 'Production'
  if (version.id === stagingId) return 'Staging'
  return version.kind === 'release' ? 'Release history' : 'Historical Staging'
}

function diffVersion(current: NetworkVersion | null, target: NetworkVersion) {
  if (!current) return ['This will become the first Production Release.']
  const changes: string[] = []
  const currentNodes = new Map(current.definition.nodes.map((node) => [node.id, node]))
  const targetNodes = new Map(target.definition.nodes.map((node) => [node.id, node]))
  const added = target.definition.nodes.filter((node) => !currentNodes.has(node.id)).length
  const removed = current.definition.nodes.filter((node) => !targetNodes.has(node.id)).length
  if (added || removed) changes.push(`Composition: ${added} Agent${added === 1 ? '' : 's'} added, ${removed} removed.`)
  const edgeDelta = target.definition.edges.length - current.definition.edges.length
  if (edgeDelta) changes.push(`Delegations: ${Math.abs(edgeDelta)} ${edgeDelta > 0 ? 'added' : 'removed'}.`)
  for (const node of target.definition.nodes) {
    const before = current.resolved_bindings[node.id]
    const after = target.resolved_bindings[node.id]
    if (before?.release_id && after?.release_id && before.release_id !== after.release_id) {
      changes.push(`${node.label}: ${before.release_version ?? 'previous Release'} → ${after.release_version ?? 'selected Release'}.`)
    }
  }
  const currentSettings = current.definition.settings
  const targetSettings = target.definition.settings
  if (currentSettings.max_depth !== targetSettings.max_depth) changes.push(`Max depth: ${currentSettings.max_depth} → ${targetSettings.max_depth}.`)
  if (currentSettings.max_invocations !== targetSettings.max_invocations) changes.push(`Max invocations: ${currentSettings.max_invocations} → ${targetSettings.max_invocations}.`)
  if (currentSettings.timeout_seconds !== targetSettings.timeout_seconds) changes.push(`Timeout: ${currentSettings.timeout_seconds}s → ${targetSettings.timeout_seconds}s.`)
  if (currentSettings.session_mode !== targetSettings.session_mode) changes.push(`Session mode: ${currentSettings.session_mode} → ${targetSettings.session_mode}.`)
  return changes.length ? changes : ['No operational differences were detected in the stored snapshots.']
}

function SnapshotSummary({ version, agents }: { version: NetworkVersion; agents: Agent[] }) {
  const agentsById = useMemo(() => new Map(agents.map((agent) => [agent.id, agent])), [agents])
  const root = version.definition.nodes.find((node) => node.id === version.definition.root_node_id)
  return (
    <div className="space-y-4">
      <section className="grid grid-cols-2 gap-2 lg:grid-cols-4">
        <Metric label="Agents" value={String(version.definition.nodes.length)} />
        <Metric label="Delegations" value={String(version.definition.edges.length)} />
        <Metric label="Session" value={version.definition.settings.session_mode} />
        <Metric label="Timeout" value={`${version.definition.settings.timeout_seconds}s`} />
      </section>
      <section className="rounded-xl border border-border/80 bg-background/35 p-4">
        <p className="text-[10px] font-semibold uppercase tracking-wide text-muted">Composition</p>
        <div className="mt-3 grid gap-2 text-[11px] sm:grid-cols-2">
          <Info label="Entry Agent" value={root?.label ?? 'Not configured'} />
          <Info label="Max depth" value={String(version.definition.settings.max_depth)} />
          <Info label="Max invocations" value={String(version.definition.settings.max_invocations)} />
          <Info label="Created" value={formatDate(version.created_at)} />
        </div>
      </section>
      <section className="rounded-xl border border-border/80 bg-background/35 p-4">
        <p className="text-[10px] font-semibold uppercase tracking-wide text-muted">Agent Releases</p>
        <div className="mt-3 space-y-2">
          {version.definition.nodes.map((node) => {
            const binding = version.resolved_bindings[node.id]
            const agent = agentsById.get(node.agent_id)
            return <div key={node.id} className="grid grid-cols-[minmax(0,1fr)_minmax(0,1fr)] gap-3 rounded-lg border border-border/70 bg-surface/40 px-3 py-2.5 text-[10px] sm:grid-cols-[minmax(0,1.2fr)_minmax(0,1fr)_minmax(0,1fr)]"><div className="min-w-0"><p className="truncate font-medium text-white">{node.label}</p><p className="mt-0.5 truncate text-muted">{agent?.name ?? node.agent_id}</p></div><div className="min-w-0"><p className="truncate font-mono text-slate-200">{binding?.release_version ?? 'Unavailable'}</p><p className="mt-0.5 capitalize text-muted">{binding?.binding_source ?? binding?.snapshot_kind ?? 'release'}</p></div><div className="hidden min-w-0 sm:block"><p className="truncate text-slate-200">{agent ? `${agent.provider}/${agent.model}` : 'Model unavailable'}</p><p className="mt-0.5 text-muted">{node.id === version.definition.root_node_id ? 'Entry point' : 'Network Agent'}</p></div></div>
          })}
        </div>
      </section>
      <details className="rounded-xl border border-border/80 bg-background/35 p-4">
        <summary className="cursor-pointer text-[10px] font-semibold uppercase tracking-wide text-muted">Advanced technical details</summary>
        <div className="mt-3 space-y-3"><Info label="Network Version ID" value={version.id} mono /><Info label="Composition hash" value={version.composition_hash} mono /><pre className="max-h-64 overflow-auto rounded-lg border border-border/70 bg-black/20 p-3 text-[9px] leading-5 text-slate-300">{JSON.stringify({ definition: version.definition, resolved_bindings: version.resolved_bindings }, null, 2)}</pre></div>
      </details>
    </div>
  )
}

function Metric({ label, value }: { label: string; value: string }) {
  return <div className="rounded-lg border border-border/75 bg-background/40 p-3"><p className="text-[9px] uppercase tracking-wide text-muted">{label}</p><p className="mt-1 text-[12px] font-medium capitalize text-white">{value}</p></div>
}

function Info({ label, value, mono = false }: { label: string; value: string; mono?: boolean }) {
  return <div className="min-w-0"><p className="text-[9px] uppercase tracking-wide text-muted">{label}</p><p className={cn('mt-1 break-words text-[11px] text-slate-200', mono && 'font-mono')}>{value}</p></div>
}

export function NetworkVersionsModal({ open, networkName, draftDefinition, draftRevision, draftDirty, stagingVersion, productionVersion, versions, agents, pending, onClose, onStage, onPublish, onViewVersion, onActivate }: NetworkVersionsModalProps) {
  const releases = useMemo(() => versions.filter((version) => version.kind === 'release'), [versions])
  const [selectedId, setSelectedId] = useState<string>('draft')
  const [activateId, setActivateId] = useState<string | null>(null)
  const [description, setDescription] = useState('')

  useEffect(() => {
    if (!open) return
    setSelectedId(productionVersion?.id ?? stagingVersion?.id ?? 'draft')
    setActivateId(null)
    setDescription('')
  }, [open, productionVersion?.id, stagingVersion?.id])

  if (!open) return null
  const selectedVersion = selectedId === 'draft' ? null : versions.find((version) => version.id === selectedId) ?? null
  const activationTarget = activateId ? versions.find((version) => version.id === activateId) ?? null : null
  const changes = activationTarget ? diffVersion(productionVersion, activationTarget) : []

  const confirmActivation = async () => {
    if (!activationTarget || description.trim().length < 3) return
    await onActivate(activationTarget.id, description.trim())
    setActivateId(null)
    setDescription('')
  }

  return <div className="fixed inset-0 z-[80] flex items-center justify-center bg-black/75 p-4 backdrop-blur-md"><div className="flex max-h-[90vh] w-full max-w-6xl flex-col overflow-hidden rounded-2xl border border-border/90 bg-surface shadow-2xl shadow-black/45"><header className="flex items-start gap-3 border-b border-border/90 bg-background/25 p-5"><div className="flex h-10 w-10 items-center justify-center rounded-xl border border-primary/25 bg-primary/10 text-primary-light"><History className="h-4 w-4" /></div><div className="min-w-0 flex-1"><p className="text-[9px] font-semibold uppercase tracking-widest text-primary-light">Network versions</p><h2 className="mt-1 truncate text-base font-semibold text-white">{networkName}</h2><p className="mt-1 text-[10px] text-muted">Draft, Staging, Production and immutable history in one place.</p></div><button type="button" onClick={onClose} className="rounded-lg border border-border p-2 text-muted hover:text-white"><X className="h-4 w-4" /></button></header><div className="grid min-h-0 flex-1 grid-cols-[280px_minmax(0,1fr)] overflow-hidden"><aside className="min-h-0 border-r border-border/90 bg-background/20"><ScrollArea className="h-full"><div className="space-y-4 p-3"><section><p className="px-2 text-[9px] font-semibold uppercase tracking-widest text-muted">Pipeline</p><div className="mt-2 space-y-1"><VersionButton selected={selectedId === 'draft'} label={`Draft r${draftRevision}`} detail={draftDirty ? 'Unsaved changes' : 'Current Draft'} tone="draft" onClick={() => setSelectedId('draft')} />{stagingVersion ? <VersionButton selected={selectedId === stagingVersion.id} label={stagingVersion.version} detail="Current Staging" tone="staging" onClick={() => setSelectedId(stagingVersion.id)} /> : <EmptyVersion label="No Staging snapshot" />}{productionVersion ? <VersionButton selected={selectedId === productionVersion.id} label={productionVersion.version} detail="Active Production" tone="production" onClick={() => setSelectedId(productionVersion.id)} /> : <EmptyVersion label="No Production Release" />}</div></section><section><p className="px-2 text-[9px] font-semibold uppercase tracking-widest text-muted">Release history</p><div className="mt-2 space-y-1">{releases.filter((version) => version.id !== productionVersion?.id).map((version) => <VersionButton key={version.id} selected={selectedId === version.id} label={version.version} detail={formatDate(version.created_at)} tone="history" onClick={() => setSelectedId(version.id)} />)}{releases.filter((version) => version.id !== productionVersion?.id).length === 0 ? <EmptyVersion label="No historical Releases" /> : null}</div></section></div></ScrollArea></aside><main className="min-h-0"><ScrollArea className="h-full"><div className="p-5">{selectedId === 'draft' ? <div className="space-y-4"><div><p className="text-[9px] font-semibold uppercase tracking-widest text-primary-light">Current Draft</p><h3 className="mt-1 text-lg font-semibold text-white">Draft r{draftRevision}</h3><p className="mt-1 text-[10px] text-muted">The only editable Network environment.</p></div><section className="grid grid-cols-2 gap-2 lg:grid-cols-4"><Metric label="Agents" value={String(draftDefinition.nodes.length)} /><Metric label="Delegations" value={String(draftDefinition.edges.length)} /><Metric label="Session" value={draftDefinition.settings.session_mode} /><Metric label="Timeout" value={`${draftDefinition.settings.timeout_seconds}s`} /></section><div className="rounded-xl border border-border/80 bg-background/35 p-4 text-[10px] text-muted">{draftDirty ? 'Save the Draft before creating a Staging snapshot.' : 'Draft is saved and ready for Staging validation.'}</div><button type="button" onClick={onStage} className="inline-flex items-center gap-2 rounded-lg bg-primary px-3 py-2 text-[10px] font-semibold text-white"><Rocket className="h-3.5 w-3.5" />Stage Network</button></div> : selectedVersion ? <div className="space-y-4"><div className="flex items-start gap-3"><div className="flex h-10 w-10 items-center justify-center rounded-xl border border-border bg-background/45 text-primary-light"><Lock className="h-4 w-4" /></div><div className="min-w-0 flex-1"><p className="text-[9px] font-semibold uppercase tracking-widest text-muted">{versionEnvironment(selectedVersion, stagingVersion?.id, productionVersion?.id)}</p><h3 className="mt-1 font-mono text-lg font-semibold text-white">{selectedVersion.version}</h3><p className="mt-1 text-[10px] text-muted">{selectedVersion.change_description || 'Immutable Network snapshot.'}</p></div></div><SnapshotSummary version={selectedVersion} agents={agents} /><div className="flex flex-wrap gap-2 border-t border-border/80 pt-4"><button type="button" onClick={() => onViewVersion(selectedVersion)} className="inline-flex items-center gap-2 rounded-lg border border-border bg-background/45 px-3 py-2 text-[10px] font-medium text-primary-light hover:border-primary/30 hover:text-white"><Eye className="h-3.5 w-3.5" />View on Canvas</button>{selectedVersion.id === stagingVersion?.id ? <button type="button" onClick={onPublish} className="inline-flex items-center gap-2 rounded-lg bg-primary px-3 py-2 text-[10px] font-semibold text-white"><Rocket className="h-3.5 w-3.5" />Publish Release</button> : null}{selectedVersion.kind === 'release' && selectedVersion.id !== productionVersion?.id ? <><button type="button" onClick={() => setActivateId(selectedVersion.id)} className="inline-flex items-center gap-2 rounded-lg border border-emerald-500/40 bg-emerald-500/10 px-3 py-2 text-[10px] font-medium text-emerald-300 hover:bg-emerald-500/15"><ArrowRight className="h-3.5 w-3.5" />Set as Production</button><span className="inline-flex items-center gap-1.5 text-[9px] text-muted"><GitCompare className="h-3.5 w-3.5" />Compare before activation</span></> : null}</div></div> : <div className="p-8 text-center text-sm text-muted">Select a Network version.</div>}</div></ScrollArea></main></div></div>{activationTarget ? <div className="fixed inset-0 z-[90] flex items-center justify-center bg-black/70 p-4 backdrop-blur-sm"><div className="w-full max-w-xl overflow-hidden rounded-2xl border border-border/90 bg-surface shadow-2xl"><header className="border-b border-border/90 p-5"><p className="text-[9px] font-semibold uppercase tracking-widest text-emerald-300">Production activation</p><h3 className="mt-1 text-base font-semibold text-white">Set {activationTarget.version} as Production?</h3><p className="mt-1 text-[10px] leading-5 text-muted">A new immutable Production Release will be created. Existing Sessions and Runs remain pinned to their original versions.</p></header><div className="space-y-4 p-5"><div className="grid grid-cols-[1fr_auto_1fr] items-center gap-3 rounded-xl border border-border/80 bg-background/35 p-3 text-[10px]"><div><p className="text-muted">Current</p><p className="mt-1 font-mono text-white">{productionVersion?.version ?? 'None'}</p></div><ArrowRight className="h-4 w-4 text-muted" /><div><p className="text-muted">Selected</p><p className="mt-1 font-mono text-white">{activationTarget.version}</p></div></div><section><p className="text-[10px] font-medium text-white">Changes from current Production</p><ul className="mt-2 space-y-1.5 text-[10px] leading-5 text-muted">{changes.map((change) => <li key={change}>• {change}</li>)}</ul></section><label className="block text-[10px] text-muted">Reason for changing Production<textarea value={description} onChange={(event) => setDescription(event.target.value)} maxLength={2000} placeholder="Describe why this Release should become Production." className="mt-2 min-h-24 w-full resize-none rounded-xl border border-border bg-background/50 p-3 text-xs text-white outline-none focus:border-primary/40" /></label></div><footer className="flex justify-end gap-2 border-t border-border/90 p-4"><button type="button" disabled={pending} onClick={() => setActivateId(null)} className="rounded-lg border border-border px-3 py-2 text-[10px] text-muted hover:text-white disabled:opacity-50">Cancel</button><button type="button" disabled={pending || description.trim().length < 3} onClick={() => void confirmActivation()} className="rounded-lg bg-emerald-500/90 px-4 py-2 text-[10px] font-semibold text-white disabled:cursor-not-allowed disabled:opacity-45">{pending ? 'Activating…' : 'Activate Release'}</button></footer></div></div> : null}</div>
}

function VersionButton({ selected, label, detail, tone, onClick }: { selected: boolean; label: string; detail: string; tone: 'draft' | 'staging' | 'production' | 'history'; onClick: () => void }) {
  const toneClass = tone === 'production' ? 'text-emerald-300' : tone === 'staging' ? 'text-indigo-300' : tone === 'draft' ? 'text-primary-light' : 'text-slate-300'
  return <button type="button" onClick={onClick} className={cn('w-full rounded-lg border px-3 py-2.5 text-left transition-colors', selected ? 'border-primary/35 bg-primary/10' : 'border-transparent bg-background/25 hover:border-border/80 hover:bg-background/50')}><div className="flex items-center gap-2"><Network className={cn('h-3.5 w-3.5 shrink-0', toneClass)} /><div className="min-w-0"><p className="truncate font-mono text-[10px] text-white">{label}</p><p className="mt-0.5 truncate text-[9px] text-muted">{detail}</p></div></div></button>
}

function EmptyVersion({ label }: { label: string }) {
  return <div className="rounded-lg border border-dashed border-border/70 px-3 py-3 text-[9px] text-muted">{label}</div>
}
