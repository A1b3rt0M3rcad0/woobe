import { useEffect, useMemo, useState } from 'react'
import { useQueries, useQuery } from '@tanstack/react-query'
import { useParams } from 'react-router-dom'
import {
  Activity,
  Clock3,
  Eye,
  FilePenLine,
  GitBranch,
  History,
  Layers3,
  Lock,
  Network,
  Rocket,
  ShieldCheck,
} from 'lucide-react'

import { Dialog } from '@/components/ui/Dialog'
import { getRelease } from '@/features/agents/api'
import type { Agent } from '@/features/agents/types'
import { getNetwork, getNetworkProductionActivations } from '@/features/network/api'
import type {
  NetworkAgentBindingSource,
  NetworkDefinition,
  NetworkProductionActivation,
  NetworkVersion,
} from '@/features/network/types'
import { cn } from '@/lib/utils'
import { NetworkBindingBadge } from './NetworkBindingBadge'

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

type Section = 'draft' | 'staging' | 'production' | 'releases' | 'staging-history' | 'activity'

function formatDate(value?: string | null) {
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

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' && !Array.isArray(value)
    ? value as Record<string, unknown>
    : {}
}

function propertyType(value: unknown) {
  const record = asRecord(value)
  const type = record.type
  if (Array.isArray(type)) return type.map(String).join(' | ')
  return typeof type === 'string' ? type : 'any'
}

function resolvedBindingSource(version: NetworkVersion, nodeId: string): NetworkAgentBindingSource {
  const binding = version.resolved_bindings[nodeId]
  if (binding?.binding_source === 'draft' || binding?.binding_source === 'staging' || binding?.binding_source === 'release') return binding.binding_source
  if (binding?.snapshot_kind === 'staging') return 'staging'
  return version.kind === 'release' ? 'release' : 'staging'
}

function NavigationItem({
  active,
  icon: Icon,
  title,
  version,
  detail,
  count,
  onClick,
}: {
  active: boolean
  icon: typeof Network
  title: string
  version?: string
  detail?: string
  count?: number
  onClick: () => void
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        'flex min-w-[180px] items-start gap-2.5 rounded-xl border px-3 py-2.5 text-left transition lg:min-w-0',
        active ? 'border-primary/35 bg-primary/10' : 'border-transparent bg-transparent hover:border-border hover:bg-background/35',
      )}
    >
      <span className={cn('mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-lg border', active ? 'border-primary/30 bg-primary/10 text-primary-light' : 'border-border bg-background/45 text-muted')}>
        <Icon className="h-3.5 w-3.5" />
      </span>
      <span className="min-w-0 flex-1">
        <span className="flex items-center gap-2">
          <span className={cn('truncate text-[10px] font-semibold', active ? 'text-white' : 'text-slate-300')}>{title}</span>
          {count != null ? <span className="ml-auto rounded border border-border bg-background/45 px-1.5 py-0.5 text-[8px] text-muted">{count}</span> : null}
        </span>
        {version ? <span className="mt-0.5 block truncate font-mono text-[9px] text-primary-light">{version}</span> : null}
        {detail ? <span className="mt-0.5 block truncate text-[8px] text-muted">{detail}</span> : null}
      </span>
    </button>
  )
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="min-w-0 border-r border-border/70 px-3 last:border-r-0">
      <p className="text-[8px] font-semibold uppercase tracking-wide text-muted">{label}</p>
      <p className="mt-1 truncate text-[11px] font-medium text-white" title={value}>{value}</p>
    </div>
  )
}

function DetailSection({ title, description, children }: { title: string; description?: string; children: React.ReactNode }) {
  return (
    <section className="grid gap-3 border-b border-border/70 py-4 last:border-b-0 md:grid-cols-[155px_minmax(0,1fr)]">
      <div>
        <p className="text-[9px] font-semibold uppercase tracking-wide text-slate-300">{title}</p>
        {description ? <p className="mt-1 text-[8px] leading-4 text-muted">{description}</p> : null}
      </div>
      <div className="min-w-0">{children}</div>
    </section>
  )
}

function VersionList({
  versions,
  selectedId,
  activeId,
  onSelect,
}: {
  versions: NetworkVersion[]
  selectedId: string | null
  activeId?: string | null
  onSelect: (version: NetworkVersion) => void
}) {
  if (!versions.length) return <div className="m-3 rounded-xl border border-dashed border-border p-5 text-center text-[10px] text-muted">No versions in this category.</div>
  return (
    <div className="space-y-1.5 p-2.5">
      {versions.map((version) => (
        <button
          key={version.id}
          type="button"
          onClick={() => onSelect(version)}
          className={cn(
            'flex w-full items-start gap-2.5 rounded-xl border p-3 text-left transition',
            selectedId === version.id ? 'border-primary/35 bg-primary/10' : 'border-border/70 bg-background/30 hover:border-primary/25',
          )}
        >
          <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border border-border bg-surface/60 text-primary-light"><Network className="h-3.5 w-3.5" /></span>
          <span className="min-w-0 flex-1">
            <span className="flex items-center gap-2">
              <span className="truncate font-mono text-[10px] text-white">{version.version}</span>
              {version.id === activeId ? <span className="rounded border border-emerald-500/30 bg-emerald-500/10 px-1.5 py-0.5 text-[7px] font-semibold uppercase text-emerald-300">Active</span> : null}
            </span>
            <span className="mt-1 block truncate text-[8px] text-muted">{changeLabel(version)}</span>
            <span className="mt-0.5 block truncate text-[8px] text-muted">{formatDate(version.created_at)}</span>
          </span>
        </button>
      ))}
    </div>
  )
}

function ActivityList({
  activations,
  versions,
  selectedId,
  onSelect,
}: {
  activations: NetworkProductionActivation[]
  versions: NetworkVersion[]
  selectedId: string | null
  onSelect: (activation: NetworkProductionActivation) => void
}) {
  const versionById = new Map(versions.map((version) => [version.id, version]))
  if (!activations.length) return <div className="m-3 rounded-xl border border-dashed border-border p-5 text-center text-[10px] text-muted">No Production activity recorded yet.</div>
  return (
    <div className="space-y-1.5 p-2.5">
      {activations.map((activation) => (
        <button
          key={activation.id}
          type="button"
          onClick={() => onSelect(activation)}
          className={cn(
            'w-full rounded-xl border p-3 text-left transition',
            selectedId === activation.id ? 'border-emerald-500/35 bg-emerald-500/[0.06]' : 'border-border/70 bg-background/30 hover:border-emerald-500/25',
          )}
        >
          <span className="flex items-center gap-2 text-[9px] font-medium capitalize text-white"><Activity className="h-3.5 w-3.5 text-emerald-300" />{activation.activation_kind}</span>
          <span className="mt-1 block truncate font-mono text-[9px] text-emerald-300">{versionById.get(activation.version_id)?.version ?? activation.version_id}</span>
          <span className="mt-1 block text-[8px] text-muted">{formatDate(activation.created_at)}</span>
        </button>
      ))}
    </div>
  )
}

function ContractView({ version }: { version: NetworkVersion }) {
  const contract = version.public_output_contract
  if (!contract?.enabled) {
    return <div className="rounded-xl border border-border/70 bg-background/35 px-3 py-3"><p className="text-[10px] font-medium text-white">Text response</p><p className="mt-1 text-[9px] leading-4 text-muted">No structured output contract is configured for this immutable Network snapshot.</p></div>
  }
  const schema = asRecord(contract.schema)
  const properties = asRecord(schema.properties)
  const required = new Set(Array.isArray(schema.required) ? schema.required.map(String) : [])
  const rows = Object.entries(properties)
  return (
    <div className="overflow-hidden rounded-xl border border-border/70 bg-background/35">
      <div className="flex flex-wrap items-center gap-2 border-b border-border/70 px-3 py-2.5">
        <span className="text-[10px] font-medium text-white">Structured JSON</span>
        <span className="rounded border border-border bg-surface/60 px-1.5 py-0.5 text-[8px] text-muted">{contract.strict ? 'Strict validation' : 'Loose validation'}</span>
        <span className="ml-auto text-[8px] text-muted">{rows.length} fields</span>
      </div>
      {rows.length ? (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[420px] text-left">
            <thead className="bg-surface/45 text-[8px] uppercase tracking-wide text-muted"><tr><th className="px-3 py-2">Field</th><th className="px-3 py-2">Type</th><th className="px-3 py-2">Required</th></tr></thead>
            <tbody>{rows.map(([name, definition]) => <tr key={name} className="border-t border-border/60 text-[9px]"><td className="px-3 py-2 font-mono text-slate-200">{name}</td><td className="px-3 py-2 text-muted">{propertyType(definition)}</td><td className="px-3 py-2 text-muted">{required.has(name) ? 'Yes' : 'No'}</td></tr>)}</tbody>
          </table>
        </div>
      ) : <p className="px-3 py-3 text-[9px] text-muted">The contract does not declare top-level properties.</p>}
    </div>
  )
}

function AgentManifest({ version, agents }: { version: NetworkVersion; agents: Agent[] }) {
  const agentsById = new Map(agents.map((agent) => [agent.id, agent]))
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
    <div className="overflow-hidden rounded-xl border border-border/70 bg-background/35">
      <div className="overflow-x-auto">
        <table className="w-full min-w-[620px] text-left">
          <thead className="bg-surface/45 text-[8px] uppercase tracking-wide text-muted"><tr><th className="px-3 py-2">Role</th><th className="px-3 py-2">Agent</th><th className="px-3 py-2">Binding</th><th className="px-3 py-2">Model</th></tr></thead>
          <tbody>{manifest.map((item) => {
            const node = version.definition.nodes.find((candidate) => candidate.id === item.node_id)
            const agent = agentsById.get(item.agent_id)
            const binding = version.resolved_bindings[item.node_id]
            return <tr key={item.node_id} className="border-t border-border/60 text-[9px]"><td className="px-3 py-2 text-muted">{item.role === 'entry' ? 'Entry' : 'Specialist'}</td><td className="max-w-[190px] truncate px-3 py-2 font-medium text-white">{node?.label ?? agent?.name ?? item.agent_id}</td><td className="px-3 py-2"><NetworkBindingBadge source={resolvedBindingSource(version, item.node_id)} version={binding?.release_version ?? item.release_version} /></td><td className="max-w-[190px] truncate px-3 py-2 text-muted">{agent ? `${agent.provider}/${agent.model}` : 'Agent snapshot'}</td></tr>
          })}</tbody>
        </table>
      </div>
    </div>
  )
}

function DraftDetails({
  definition,
  revision,
  dirty,
  agents,
  releaseVersionByRef,
}: {
  definition: NetworkDefinition
  revision: number
  dirty: boolean
  agents: Agent[]
  releaseVersionByRef: Map<string, string>
}) {
  const agentsById = new Map(agents.map((agent) => [agent.id, agent]))
  const root = definition.nodes.find((node) => node.id === definition.root_node_id)
  return (
    <div className="p-4">
      <div className="flex flex-wrap items-center gap-2"><FilePenLine className="h-4 w-4 text-primary-light" /><h3 className="font-mono text-base font-semibold text-white">Draft r{revision}</h3><span className={cn('rounded border px-2 py-0.5 text-[8px] font-semibold uppercase', dirty ? 'border-amber-500/30 bg-amber-500/10 text-amber-200' : 'border-primary/30 bg-primary/10 text-primary-light')}>{dirty ? 'Unsaved changes' : 'Saved'}</span></div>
      <p className="mt-1 text-[9px] text-muted">Editable composition. Agent Drafts and pinned snapshots are resolved again when the Network is staged.</p>
      <div className="mt-4 grid grid-cols-2 rounded-xl border border-border/70 bg-background/35 py-3 md:grid-cols-4"><Metric label="Agents" value={String(definition.nodes.length)} /><Metric label="Delegations" value={String(definition.edges.length)} /><Metric label="Session mode" value={definition.settings.session_mode} /><Metric label="Entry point" value={root?.label ?? 'Not configured'} /></div>
      <DetailSection title="Agent bindings" description="Exact Agent source selected by each Network node.">
        <div className="overflow-hidden rounded-xl border border-border/70 bg-background/35"><div className="overflow-x-auto"><table className="w-full min-w-[600px] text-left"><thead className="bg-surface/45 text-[8px] uppercase tracking-wide text-muted"><tr><th className="px-3 py-2">Role</th><th className="px-3 py-2">Agent</th><th className="px-3 py-2">Binding</th><th className="px-3 py-2">Model</th></tr></thead><tbody>{definition.nodes.map((node) => {
          const agent = agentsById.get(node.agent_id)
          const source = node.binding.source
          const ref = node.binding.release_id ?? ''
          const version = source === 'draft' ? `r${revision}` : releaseVersionByRef.get(ref) ?? 'pinned'
          return <tr key={node.id} className="border-t border-border/60 text-[9px]"><td className="px-3 py-2 text-muted">{node.id === definition.root_node_id ? 'Entry' : 'Specialist'}</td><td className="max-w-[190px] truncate px-3 py-2 font-medium text-white">{node.label}</td><td className="px-3 py-2"><NetworkBindingBadge source={source} version={version} /></td><td className="max-w-[190px] truncate px-3 py-2 text-muted">{agent ? `${agent.provider}/${agent.model}` : 'Agent unavailable'}</td></tr>
        })}</tbody></table></div></div>
      </DetailSection>
      <DetailSection title="Public output" description="The Network contract is inherited from the entry Agent when this Draft is promoted."><div className="rounded-xl border border-border/70 bg-background/35 px-3 py-3"><p className="text-[10px] font-medium text-white">Inherited from {root?.label ?? 'entry Agent'}</p><p className="mt-1 text-[9px] leading-4 text-muted">The immutable contract snapshot becomes visible after Staging is created.</p></div></DetailSection>
      <DetailSection title="Runtime"><div className="grid grid-cols-2 rounded-xl border border-border/70 bg-background/35 py-3 md:grid-cols-4"><Metric label="Session mode" value={definition.settings.session_mode} /><Metric label="Max depth" value={String(definition.settings.max_depth)} /><Metric label="Max invocations" value={String(definition.settings.max_invocations)} /><Metric label="Timeout" value={`${definition.settings.timeout_seconds}s`} /></div></DetailSection>
      <details className="mt-4 rounded-xl border border-border/70 bg-background/35 p-4"><summary className="cursor-pointer text-[9px] font-semibold uppercase tracking-wide text-muted">Advanced technical details</summary><pre className="scrollbar-thin mt-3 max-h-64 overflow-auto rounded-lg border border-border/70 bg-black/20 p-3 text-[9px] leading-5 text-slate-300">{JSON.stringify(definition, null, 2)}</pre></details>
    </div>
  )
}

function SnapshotDetails({ version, agents, productionId }: { version: NetworkVersion; agents: Agent[]; productionId?: string | null }) {
  const root = version.definition.nodes.find((node) => node.id === version.definition.root_node_id)
  const activeProduction = version.id === productionId
  return (
    <div className="p-4">
      <div className="flex flex-wrap items-center gap-2"><Lock className="h-4 w-4 text-primary-light" /><h3 className="font-mono text-base font-semibold text-white">{version.version}</h3>{activeProduction ? <span className="rounded border border-emerald-500/30 bg-emerald-500/10 px-2 py-0.5 text-[8px] font-semibold uppercase text-emerald-300">Active Production</span> : <span className="rounded border border-border bg-background/45 px-2 py-0.5 text-[8px] font-semibold uppercase text-muted">{version.kind === 'staging' ? 'Staging snapshot' : changeLabel(version)}</span>}</div>
      <p className="mt-1 text-[9px] text-muted">{version.change_description || 'Immutable Network snapshot.'}</p>
      <div className="mt-4 grid grid-cols-2 rounded-xl border border-border/70 bg-background/35 py-3 md:grid-cols-4"><Metric label="Agents" value={String(version.definition.nodes.length)} /><Metric label="Delegations" value={String(version.definition.edges.length)} /><Metric label="Public output" value={contractLabel(version)} /><Metric label="Created" value={formatDate(version.created_at)} /></div>
      <DetailSection title="Release identity" description="Immutable lineage used by Sessions and Runs."><div className="grid gap-3 rounded-xl border border-border/70 bg-background/35 p-3 sm:grid-cols-2"><div><p className="text-[8px] uppercase tracking-wide text-muted">Entry Agent</p><p className="mt-1 text-[10px] text-white">{root?.label ?? 'Not configured'}</p></div><div><p className="text-[8px] uppercase tracking-wide text-muted">Entry Agent binding</p><div className="mt-1"><NetworkBindingBadge source={resolvedBindingSource(version, version.definition.root_node_id)} version={version.entry_agent_release_version ?? version.resolved_bindings[version.definition.root_node_id]?.release_version ?? 'legacy'} /></div></div><div><p className="text-[8px] uppercase tracking-wide text-muted">Source Draft</p><p className="mt-1 font-mono text-[10px] text-slate-200">{version.source_draft_revision != null ? `r${version.source_draft_revision}` : 'Legacy snapshot'}</p></div><div><p className="text-[8px] uppercase tracking-wide text-muted">Change classification</p><p className="mt-1 text-[10px] text-slate-200">{changeLabel(version)}</p></div></div></DetailSection>
      <DetailSection title="Public output contract" description="Inherited and frozen from the entry Agent binding."><ContractView version={version} /></DetailSection>
      <DetailSection title="Agent bindings" description="Every Agent snapshot used by this Network version."><AgentManifest version={version} agents={agents} /></DetailSection>
      <DetailSection title="Runtime"><div className="grid grid-cols-2 rounded-xl border border-border/70 bg-background/35 py-3 md:grid-cols-4"><Metric label="Session mode" value={version.definition.settings.session_mode} /><Metric label="Max depth" value={String(version.definition.settings.max_depth)} /><Metric label="Max invocations" value={String(version.definition.settings.max_invocations)} /><Metric label="Timeout" value={`${version.definition.settings.timeout_seconds}s`} /></div></DetailSection>
      <details className="mt-4 rounded-xl border border-border/70 bg-background/35 p-4"><summary className="cursor-pointer text-[9px] font-semibold uppercase tracking-wide text-muted">Advanced technical details</summary><div className="mt-3 grid gap-3 text-[9px] sm:grid-cols-2"><div><p className="uppercase tracking-wide text-muted">Network Version ID</p><p className="mt-1 break-all font-mono text-slate-300">{version.id}</p></div><div><p className="uppercase tracking-wide text-muted">Composition hash</p><p className="mt-1 break-all font-mono text-slate-300">{version.composition_hash}</p></div><div><p className="uppercase tracking-wide text-muted">Contract hash</p><p className="mt-1 break-all font-mono text-slate-300">{version.public_output_contract_hash ?? 'Unavailable'}</p></div><div><p className="uppercase tracking-wide text-muted">Release fingerprint</p><p className="mt-1 break-all font-mono text-slate-300">{version.release_fingerprint ?? 'Unavailable'}</p></div></div><pre className="scrollbar-thin mt-3 max-h-64 overflow-auto rounded-lg border border-border/70 bg-black/20 p-3 text-[9px] leading-5 text-slate-300">{JSON.stringify({ public_output_contract: version.public_output_contract, definition: version.definition, resolved_bindings: version.resolved_bindings }, null, 2)}</pre></details>
    </div>
  )
}

function ActivationDetails({
  target,
  current,
  changes,
  description,
  onDescription,
}: {
  target: NetworkVersion
  current: NetworkVersion | null
  changes: string[]
  description: string
  onDescription: (value: string) => void
}) {
  return (
    <div className="p-4">
      <div className="flex items-center gap-2"><Rocket className="h-4 w-4 text-emerald-300" /><h3 className="text-base font-semibold text-white">Activate {target.version}</h3></div>
      <p className="mt-1 text-[9px] text-muted">This changes the Production pointer. It does not create a duplicate Release.</p>
      <div className="mt-4 grid gap-3 sm:grid-cols-2"><div className="rounded-xl border border-border/70 bg-background/35 p-3"><p className="text-[8px] uppercase tracking-wide text-muted">Current Production</p><p className="mt-1 font-mono text-[11px] text-white">{current?.version ?? 'None'}</p></div><div className="rounded-xl border border-emerald-500/25 bg-emerald-500/[0.05] p-3"><p className="text-[8px] uppercase tracking-wide text-emerald-300">Selected Release</p><p className="mt-1 font-mono text-[11px] text-white">{target.version}</p></div></div>
      <DetailSection title="Changes" description="Operational differences from the active Production snapshot."><ul className="space-y-1.5 rounded-xl border border-border/70 bg-background/35 p-3">{changes.map((change) => <li key={change} className="text-[9px] leading-4 text-slate-300">• {change}</li>)}</ul></DetailSection>
      <DetailSection title="Reason for change" description="Required for the Production activation audit trail."><textarea value={description} onChange={(event) => onDescription(event.target.value)} rows={5} className="w-full resize-none rounded-xl border border-border bg-background/50 p-3 text-[11px] text-white outline-none focus:border-primary/40" placeholder="Explain why this immutable Release should become Production." /></DetailSection>
      <div className="rounded-xl border border-border/70 bg-background/35 px-3 py-3 text-[9px] leading-4 text-muted">Existing Sessions and Runs remain pinned to their original Network versions.</div>
    </div>
  )
}

export function NetworkVersionsModal({
  open,
  networkName,
  draftDefinition,
  draftRevision,
  draftDirty,
  stagingVersion,
  productionVersion,
  versions,
  agents,
  pending,
  onClose,
  onStage,
  onPublish,
  onViewVersion,
  onActivate,
}: NetworkVersionsModalProps) {
  const { projectId } = useParams<{ projectId: string }>()
  const networkResource = useQuery({ queryKey: ['network-version-modal-resource', projectId], queryFn: () => getNetwork(projectId!), enabled: Boolean(open && projectId), staleTime: 30_000 })
  const activations = useQuery({ queryKey: ['network-production-activations', networkResource.data?.id, projectId], queryFn: () => getNetworkProductionActivations(networkResource.data!.id, projectId!), enabled: Boolean(open && projectId && networkResource.data?.id) })
  const releases = useMemo(() => versions.filter((version) => version.kind === 'release'), [versions])
  const stagingSnapshots = useMemo(() => versions.filter((version) => version.kind === 'staging'), [versions])
  const pinnedDraftBindings = useMemo(() => draftDefinition.nodes.filter((node) => node.binding.source !== 'draft' && node.binding.release_id).map((node) => ({ agentId: node.agent_id, releaseId: node.binding.release_id! })), [draftDefinition.nodes])
  const pinnedDraftQueries = useQueries({ queries: pinnedDraftBindings.map((binding) => ({ queryKey: ['release', binding.agentId, binding.releaseId], queryFn: () => getRelease(binding.agentId, binding.releaseId), staleTime: 60_000 })) })
  const releaseVersionByRef = useMemo(() => {
    const result = new Map<string, string>()
    pinnedDraftQueries.forEach((query, index) => {
      const binding = pinnedDraftBindings[index]
      if (binding && query.data?.version) result.set(binding.releaseId, query.data.version)
    })
    return result
  }, [pinnedDraftBindings, pinnedDraftQueries])
  const [section, setSection] = useState<Section>('draft')
  const [selectedVersionId, setSelectedVersionId] = useState<string | null>(null)
  const [selectedActivationId, setSelectedActivationId] = useState<string | null>(null)
  const [activateId, setActivateId] = useState<string | null>(null)
  const [description, setDescription] = useState('')

  useEffect(() => {
    if (!open) return
    const initialSection: Section = productionVersion ? 'production' : stagingVersion ? 'staging' : 'draft'
    setSection(initialSection)
    setSelectedVersionId(initialSection === 'production' ? productionVersion?.id ?? null : initialSection === 'staging' ? stagingVersion?.id ?? null : null)
    setSelectedActivationId(null)
    setActivateId(null)
    setDescription('')
  }, [open, productionVersion, stagingVersion])

  const productionActivations = activations.data ?? []
  const selectedActivation = productionActivations.find((activation) => activation.id === selectedActivationId) ?? productionActivations[0] ?? null
  const activationVersion = selectedActivation ? versions.find((version) => version.id === selectedActivation.version_id) ?? null : null
  const selectedVersion = section === 'staging'
    ? stagingVersion
    : section === 'production'
      ? productionVersion
      : section === 'releases'
        ? releases.find((version) => version.id === selectedVersionId) ?? releases[0] ?? null
        : section === 'staging-history'
          ? stagingSnapshots.find((version) => version.id === selectedVersionId) ?? stagingSnapshots[0] ?? null
          : section === 'activity'
            ? activationVersion
            : null
  const activationTarget = activateId ? versions.find((version) => version.id === activateId) ?? null : null
  const activationChanges = activationTarget ? diffVersion(productionVersion, activationTarget) : []
  const showList = section === 'releases' || section === 'staging-history' || section === 'activity'

  const selectSection = (next: Section) => {
    setSection(next)
    setActivateId(null)
    setDescription('')
    if (next === 'releases') setSelectedVersionId(productionVersion?.id ?? releases[0]?.id ?? null)
    else if (next === 'staging-history') setSelectedVersionId(stagingVersion?.id ?? stagingSnapshots[0]?.id ?? null)
    else if (next === 'staging') setSelectedVersionId(stagingVersion?.id ?? null)
    else if (next === 'production') setSelectedVersionId(productionVersion?.id ?? null)
    if (next === 'activity') setSelectedActivationId(productionActivations[0]?.id ?? null)
  }

  const confirmActivation = async () => {
    if (!activationTarget || description.trim().length < 3) return
    await onActivate(activationTarget.id, description.trim())
    setActivateId(null)
    setDescription('')
    await activations.refetch()
  }

  const footerContext = activationTarget
    ? `Activating ${activationTarget.version} as the Production Release.`
    : section === 'draft'
      ? `Draft r${draftRevision} ${draftDirty ? 'has unsaved changes.' : 'is saved and ready for validation.'}`
      : selectedVersion
        ? selectedVersion.id === productionVersion?.id
          ? `${selectedVersion.version} is currently serving Production.`
          : selectedVersion.kind === 'staging'
            ? `${selectedVersion.version} is an immutable validation snapshot.`
            : `${selectedVersion.version} is an immutable historical Release.`
        : section === 'activity'
          ? 'Production deployment and rollback history.'
          : 'No snapshot is available in this section.'

  return (
    <Dialog open={open} onClose={onClose} title="Manage Network Versions" className="max-h-[90svh] max-w-[1200px] overflow-hidden">
      <div className="-m-6 grid h-[calc(90svh-6rem)] max-h-[760px] grid-rows-[auto_minmax(0,1fr)_auto] overflow-hidden">
        <div className="flex flex-wrap items-center gap-3 border-b border-border/80 bg-background/25 px-4 py-3">
          <div className="flex h-9 w-9 items-center justify-center rounded-xl border border-primary/25 bg-primary/10 text-primary-light"><History className="h-4 w-4" /></div>
          <div className="min-w-0"><p className="truncate text-[12px] font-semibold text-white">{networkName}</p><p className="mt-0.5 text-[9px] text-muted">Draft, validation snapshots, Releases and Production activations.</p></div>
          <span className={cn('ml-auto rounded-lg border px-2.5 py-1 font-mono text-[9px]', productionVersion ? 'border-emerald-500/30 bg-emerald-500/10 text-emerald-300' : 'border-border bg-background/45 text-muted')}>{productionVersion ? `Production · ${productionVersion.version}` : 'No Production Release'}</span>
        </div>

        <div className={cn('grid min-h-0 overflow-y-auto lg:overflow-hidden', showList ? 'lg:grid-cols-[220px_280px_minmax(0,1fr)]' : 'lg:grid-cols-[220px_minmax(0,1fr)]')}>
          <nav className="flex gap-2 overflow-x-auto border-b border-border/80 bg-surface/30 p-3 lg:min-h-0 lg:flex-col lg:overflow-y-auto lg:border-b-0 lg:border-r">
            <p className="hidden px-2 pt-1 text-[8px] font-semibold uppercase tracking-widest text-muted lg:block">Pipeline</p>
            <NavigationItem active={section === 'draft'} icon={FilePenLine} title="Draft" version={`r${draftRevision}`} detail={draftDirty ? 'Unsaved changes' : 'Editable · Saved'} onClick={() => selectSection('draft')} />
            <NavigationItem active={section === 'staging'} icon={ShieldCheck} title="Staging" version={stagingVersion?.version ?? 'Not created'} detail={stagingVersion ? 'Immutable validation' : 'No snapshot'} onClick={() => selectSection('staging')} />
            <NavigationItem active={section === 'production'} icon={Rocket} title="Production" version={productionVersion?.version ?? 'Not published'} detail={productionVersion ? 'Active' : 'No Release'} onClick={() => selectSection('production')} />
            <p className="hidden px-2 pt-3 text-[8px] font-semibold uppercase tracking-widest text-muted lg:block">History</p>
            <NavigationItem active={section === 'releases'} icon={Layers3} title="Releases" count={releases.length} onClick={() => selectSection('releases')} />
            <NavigationItem active={section === 'staging-history'} icon={GitBranch} title="Staging snapshots" count={stagingSnapshots.length} onClick={() => selectSection('staging-history')} />
            <NavigationItem active={section === 'activity'} icon={Activity} title="Production activity" count={productionActivations.length} onClick={() => selectSection('activity')} />
          </nav>

          {showList ? (
            <aside className="min-h-0 overflow-y-auto border-b border-border/80 bg-background/20 lg:border-b-0 lg:border-r">
              <div className="sticky top-0 z-10 flex items-center gap-2 border-b border-border/70 bg-surface/95 px-3 py-2.5"><Clock3 className="h-3.5 w-3.5 text-muted" /><p className="text-[9px] font-semibold uppercase tracking-wide text-slate-300">{section === 'releases' ? 'Network Releases' : section === 'staging-history' ? 'Staging snapshots' : 'Production activity'}</p></div>
              {section === 'releases' ? <VersionList versions={releases} selectedId={selectedVersion?.id ?? null} activeId={productionVersion?.id} onSelect={(version) => setSelectedVersionId(version.id)} /> : section === 'staging-history' ? <VersionList versions={stagingSnapshots} selectedId={selectedVersion?.id ?? null} activeId={stagingVersion?.id} onSelect={(version) => setSelectedVersionId(version.id)} /> : <ActivityList activations={productionActivations} versions={versions} selectedId={selectedActivation?.id ?? null} onSelect={(activation) => setSelectedActivationId(activation.id)} />}
            </aside>
          ) : null}

          <main className="min-h-0 overflow-y-auto bg-surface/10">
            {activationTarget ? <ActivationDetails target={activationTarget} current={productionVersion} changes={activationChanges} description={description} onDescription={setDescription} /> : section === 'draft' ? <DraftDetails definition={draftDefinition} revision={draftRevision} dirty={draftDirty} agents={agents} releaseVersionByRef={releaseVersionByRef} /> : selectedVersion ? <SnapshotDetails version={selectedVersion} agents={agents} productionId={productionVersion?.id} /> : <div className="flex h-full min-h-[260px] items-center justify-center p-6 text-center"><div><Network className="mx-auto h-5 w-5 text-muted" /><p className="mt-3 text-[11px] font-medium text-white">No version available</p><p className="mt-1 text-[9px] text-muted">Create the corresponding lifecycle snapshot to inspect it here.</p></div></div>}
          </main>
        </div>

        <footer className="flex flex-wrap items-center gap-3 border-t border-border/80 bg-background/30 px-4 py-3">
          <p className="min-w-0 flex-1 truncate text-[9px] text-muted">{footerContext}</p>
          {activationTarget ? (
            <>
              <button type="button" onClick={() => { setActivateId(null); setDescription('') }} className="rounded-lg border border-border px-3 py-2 text-[10px] text-muted hover:text-white">Cancel</button>
              <button type="button" disabled={pending || description.trim().length < 3} onClick={() => void confirmActivation()} className="rounded-lg bg-emerald-600 px-3 py-2 text-[10px] font-semibold text-white disabled:cursor-not-allowed disabled:opacity-45">{pending ? 'Activating…' : 'Activate Release'}</button>
            </>
          ) : (
            <>
              <button type="button" onClick={onClose} className="rounded-lg border border-border px-3 py-2 text-[10px] text-muted hover:text-white">Close</button>
              {selectedVersion ? <button type="button" onClick={() => onViewVersion(selectedVersion)} className="inline-flex items-center gap-2 rounded-lg border border-border bg-background/45 px-3 py-2 text-[10px] font-medium text-primary-light hover:border-primary/30 hover:text-white"><Eye className="h-3.5 w-3.5" />View on Canvas</button> : null}
              {section === 'draft' ? <button type="button" disabled={pending} onClick={onStage} className="rounded-lg bg-primary px-3 py-2 text-[10px] font-semibold text-white disabled:cursor-not-allowed disabled:opacity-45">Stage Network</button> : null}
              {selectedVersion?.id === stagingVersion?.id ? <button type="button" disabled={pending} onClick={onPublish} className="inline-flex items-center gap-2 rounded-lg bg-primary px-3 py-2 text-[10px] font-semibold text-white disabled:cursor-not-allowed disabled:opacity-45"><Rocket className="h-3.5 w-3.5" />Publish Release</button> : null}
              {selectedVersion?.kind === 'release' && selectedVersion.id !== productionVersion?.id ? <button type="button" disabled={pending} onClick={() => setActivateId(selectedVersion.id)} className="rounded-lg border border-emerald-500/40 bg-emerald-500/10 px-3 py-2 text-[10px] font-medium text-emerald-300 disabled:cursor-not-allowed disabled:opacity-45">Set as Production</button> : null}
            </>
          )}
        </footer>
      </div>
    </Dialog>
  )
}
