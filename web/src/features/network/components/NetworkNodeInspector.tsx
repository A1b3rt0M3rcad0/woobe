import { useState } from 'react'
import { Bot, Copy, ExternalLink, Info, MoreHorizontal, Trash2 } from 'lucide-react'

import { useReleases } from '@/features/agents/hooks'
import type { Agent, AgentRelease } from '@/features/agents/types'
import { cn } from '@/lib/utils'

import type { NetworkAgentBindingSelector, NetworkDefinition, NetworkNode } from '../types'
import { delegationToolName } from '../editor/networkGraphValidation'
import type { NetworkDefinitionChange } from '../editor/types'
import type { NetworkBinding } from './networkWorkspaceTypes'
import { NetworkInspectorModal, networkInspectorAction, networkInspectorInput } from './NetworkInspectorModal'

function snapshotKind(release: AgentRelease): 'draft' | 'staging' | 'release' {
  if (release.snapshot_kind) return release.snapshot_kind
  if (release.status === 'draft') return 'draft'
  if (release.status === 'staging' || release.version.startsWith('staging')) return 'staging'
  return 'release'
}

function bindingValue(binding: NetworkAgentBindingSelector) {
  return binding.source === 'draft' ? 'draft' : `${binding.source}:${binding.release_id}`
}

function Help({ text }: { text: string }) {
  return <span title={text} aria-label={text} className="inline-flex h-5 w-5 items-center justify-center rounded-full border border-border bg-background/45 text-muted"><Info className="h-3 w-3" /></span>
}

function AgentBindingPicker({ node, agent, resolvedVersion, readOnly, onChange }: {
  node: NetworkNode
  agent: Agent
  resolvedVersion?: string | null
  readOnly: boolean
  onChange: (binding: NetworkAgentBindingSelector) => void
}) {
  const releasesQuery = useReleases(agent.id)
  const releases = releasesQuery.data ?? []
  const [open, setOpen] = useState(false)
  const [pending, setPending] = useState(bindingValue(node.binding))
  const selected = node.binding.source === 'draft' ? null : releases.find((release) => release.id === node.binding.release_id) ?? null
  const staging = releases.filter((release) => snapshotKind(release) === 'staging')
  const production = releases.filter((release) => snapshotKind(release) === 'release')
  const version = node.binding.source === 'draft'
    ? 'Draft · current configuration'
    : `${node.binding.source === 'staging' ? 'Staging' : 'Release'} · ${resolvedVersion ?? selected?.version ?? 'pinned snapshot'}`

  const apply = () => {
    if (pending === 'draft') onChange({ source: 'draft', release_id: null })
    else {
      const [source, releaseId] = pending.split(':', 2)
      if ((source === 'staging' || source === 'release') && releaseId) onChange({ source, release_id: releaseId })
    }
    setOpen(false)
  }

  return (
    <>
      <section className="rounded-xl border border-border bg-background/30 p-3">
        <div className="flex items-center gap-3">
          <div className="min-w-0 flex-1">
            <p className="text-[9px] font-semibold uppercase tracking-wider text-muted">Agent version</p>
            <p className="mt-1 truncate text-[10px] text-slate-200">{version}</p>
          </div>
          <button type="button" disabled={releasesQuery.isLoading} onClick={() => { setPending(bindingValue(node.binding)); setOpen(true) }} className={networkInspectorAction}>{readOnly ? 'View' : 'Change'}</button>
        </div>
      </section>
      {open ? (
        <NetworkInspectorModal
          title="Agent version used by this node"
          description="This binding belongs only to the Network node."
          onClose={() => setOpen(false)}
          footer={readOnly ? (
            <button type="button" onClick={() => setOpen(false)} className={networkInspectorAction}>Close</button>
          ) : (
            <>
              <button type="button" onClick={() => setOpen(false)} className={networkInspectorAction}>Cancel</button>
              <button type="button" onClick={apply} className="rounded-lg bg-primary px-3 py-2 text-[10px] font-semibold text-white">Apply</button>
            </>
          )}
        >
          <label className="block text-[10px] text-muted">
            Version
            <select disabled={readOnly} className={networkInspectorInput} value={pending} onChange={(event) => setPending(event.target.value)}>
              <option value="draft">Draft · current configuration</option>
              {staging.map((release) => <option key={release.id} value={`staging:${release.id}`}>Staging · {release.version}</option>)}
              {production.map((release) => <option key={release.id} value={`release:${release.id}`}>Release · {release.version}</option>)}
            </select>
          </label>
        </NetworkInspectorModal>
      ) : null}
    </>
  )
}

export function NetworkNodeInspector({
  definition,
  node,
  agent,
  binding,
  readOnly,
  onChange,
  onOpenAgent,
  onLocateOnCanvas,
}: {
  definition: NetworkDefinition
  node: NetworkNode
  agent: Agent | null
  binding: NetworkBinding | null
  readOnly: boolean
  onChange: (change: NetworkDefinitionChange) => void
  onOpenAgent?: () => void
  onLocateOnCanvas?: () => void
}) {
  const rootMustBeReassigned = definition.root_node_id === node.id && definition.nodes.length > 1

  return (
    <>
      <header className="border-b border-border p-4">
        <div className="flex items-start gap-3">
          <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl border border-primary/20 bg-primary/5 text-primary-light"><Bot className="h-4 w-4" /></div>
          <div className="min-w-0 flex-1">
            <p className="text-[8px] font-semibold uppercase tracking-widest text-primary-light">Agent in Network</p>
            <div className="mt-1 flex min-w-0 items-center gap-2">
              <h2 className="truncate text-sm font-semibold text-white">{node.label}</h2>
              {definition.root_node_id === node.id ? <span className="shrink-0 rounded border border-primary/25 bg-primary/5 px-1.5 py-0.5 text-[8px] uppercase text-primary-light">Entry point</span> : null}
            </div>
            <p className="mt-1 truncate text-[9px] text-muted">{binding ? `${binding.source} · ${binding.version}` : agent ? `${agent.provider}/${agent.model}` : node.agent_id}</p>
          </div>
          {onOpenAgent ? <button type="button" onClick={onOpenAgent} className={networkInspectorAction}><ExternalLink className="mr-1 inline h-3 w-3" />Open Agent</button> : null}
          <details className="relative">
            <summary className="flex h-7 w-7 cursor-pointer list-none items-center justify-center rounded-lg border border-border bg-background/45 text-muted [&::-webkit-details-marker]:hidden"><MoreHorizontal className="h-3.5 w-3.5" /></summary>
            <div className="absolute right-0 z-20 mt-1 w-44 rounded-xl border border-border bg-surface p-1 shadow-xl">
              {onLocateOnCanvas ? <button type="button" onClick={onLocateOnCanvas} className="w-full rounded-lg px-2.5 py-2 text-left text-[9px] text-muted hover:bg-background/60 hover:text-white">Locate on Canvas</button> : null}
              <button type="button" disabled={readOnly || rootMustBeReassigned} title={rootMustBeReassigned ? 'Choose another Entry Point first' : undefined} onClick={() => onChange({ type: 'remove-node', nodeId: node.id })} className="flex w-full items-center gap-2 rounded-lg px-2.5 py-2 text-[9px] text-red-300 disabled:opacity-45"><Trash2 className="h-3.5 w-3.5" />Remove from Network</button>
            </div>
          </details>
        </div>
      </header>

      <div className="space-y-4 p-4">
        <section className="space-y-4">
          <div className="flex items-center gap-2"><p className="text-[9px] font-semibold uppercase tracking-wider text-slate-300">In this Network</p><Help text="These settings affect only this Network node. Prompt, model, Tools and Knowledge remain owned by the shared Agent." /></div>
          <label className="block text-[10px] text-muted">Node label<input disabled={readOnly} className={networkInspectorInput} value={node.label} onChange={(event) => onChange({ type: 'rename-node', nodeId: node.id, label: event.target.value })} /></label>
          <label className="block text-[10px] text-muted">
            <span className="inline-flex items-center gap-2">Delegation capability <Help text="Connected upstream Agents use this description to decide when work should be delegated to this node." /></span>
            <textarea disabled={readOnly} maxLength={2000} className={cn(networkInspectorInput, 'min-h-28 resize-y leading-5')} value={node.capability_description} onChange={(event) => onChange({ type: 'describe-node', nodeId: node.id, description: event.target.value })} />
          </label>
        </section>

        {agent ? <AgentBindingPicker key={node.id} node={node} agent={agent} resolvedVersion={binding?.version} readOnly={readOnly} onChange={(next) => onChange({ type: 'set-binding', nodeId: node.id, binding: next })} /> : null}

        <section className="rounded-xl border border-border bg-background/30 p-3">
          <div className="flex items-center gap-3">
            <div className="min-w-0 flex-1">
              <p className="text-[9px] font-semibold uppercase tracking-wider text-muted">Role</p>
              <p className="mt-1 text-[10px] text-slate-200">{definition.root_node_id === node.id ? 'Entry point and final responder' : 'Specialist Agent'}</p>
            </div>
            {!readOnly && definition.root_node_id !== node.id ? <button type="button" onClick={() => onChange({ type: 'set-root', nodeId: node.id })} className={networkInspectorAction}>Set as Entry Point</button> : null}
          </div>
        </section>

        <details className="rounded-xl border border-border bg-background/30">
          <summary className="cursor-pointer list-none px-3 py-3 text-[9px] font-semibold uppercase tracking-wider text-muted [&::-webkit-details-marker]:hidden">Advanced <span className="float-right">›</span></summary>
          <div className="flex items-center gap-2 border-t border-border px-3 py-3">
            <p className="min-w-0 flex-1 break-all font-mono text-[10px] text-slate-200">{delegationToolName(node)}</p>
            <button type="button" onClick={() => void navigator.clipboard.writeText(delegationToolName(node))} className={networkInspectorAction}><Copy className="h-3 w-3" /></button>
          </div>
        </details>
      </div>
    </>
  )
}
