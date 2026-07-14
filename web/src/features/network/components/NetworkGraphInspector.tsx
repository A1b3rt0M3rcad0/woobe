import { AlertTriangle, Crown, Link2, Settings2, Trash2, Workflow } from 'lucide-react'
import type { Agent } from '@/features/agents/types'
import { cn } from '@/lib/utils'
import type { NetworkDefinition } from '../types'
import { delegationToolName } from '../editor/networkGraphValidation'
import type { NetworkDefinitionChange, NetworkEditorIssue, NetworkEditorSelection } from '../editor/types'

const input = 'mt-1.5 w-full rounded-xl border border-border bg-background/50 px-3 py-2.5 text-xs text-white outline-none focus:border-primary/40 disabled:opacity-50'

export function NetworkGraphInspector({
  definition,
  agents,
  issues,
  selection,
  readOnly,
  name,
  description,
  onMetadata,
  onChange,
}: {
  definition: NetworkDefinition
  agents: Agent[]
  issues: NetworkEditorIssue[]
  selection: NetworkEditorSelection
  readOnly: boolean
  name: string
  description: string
  onMetadata: (metadata: { name?: string; description?: string }) => void
  onChange: (change: NetworkDefinitionChange) => void
}) {
  const node = selection.type === 'node' ? definition.nodes.find((item) => item.id === selection.id) : null
  const edge = selection.type === 'edge' ? definition.edges.find((item) => item.id === selection.id) : null
  const agent = node ? agents.find((item) => item.id === node.agent_id) : null
  const source = edge ? definition.nodes.find((item) => item.id === edge.source_node_id) : null
  const target = edge ? definition.nodes.find((item) => item.id === edge.target_node_id) : null
  const errors = issues.filter((item) => item.severity === 'error')
  const rootMustBeReassigned = Boolean(node && definition.root_node_id === node.id && definition.nodes.length > 1)

  return (
    <aside className="flex h-full min-h-0 w-[min(94vw,390px)] shrink-0 flex-col border-l border-border bg-surface/85">
      <header className="border-b border-border p-4"><p className="text-[9px] font-semibold uppercase tracking-widest text-primary-light">{node ? 'Agent node' : edge ? 'Delegation' : 'Network'}</p><h2 className="mt-1 truncate text-sm font-semibold text-white">{node?.label ?? (edge ? `${source?.label ?? 'Agent'} → ${target?.label ?? 'Agent'}` : name)}</h2></header>
      <div className="min-h-0 flex-1 space-y-5 overflow-y-auto p-4">
        {node ? <>
          <div className="rounded-xl border border-border bg-background/35 p-3"><p className="text-[10px] font-medium text-white">{agent?.name ?? 'Agent unavailable'}</p><p className="mt-1 text-[9px] text-muted">{agent ? `${agent.provider}/${agent.model}` : node.agent_id}</p></div>
          <label className="block text-[10px] text-muted">Node label<input disabled={readOnly} className={input} value={node.label} onChange={(event) => onChange({ type: 'rename-node', nodeId: node.id, label: event.target.value })} /></label>
          <label className="block text-[10px] text-muted">
            Delegation capability
            <textarea disabled={readOnly} maxLength={2000} className={cn(input, 'min-h-28 resize-y leading-5')} value={node.capability_description} onChange={(event) => onChange({ type: 'describe-node', nodeId: node.id, description: event.target.value })} placeholder="Describe what this Agent does and when another Agent should delegate work to it." />
            <span className="mt-1.5 block text-[9px] leading-4 text-muted">Connected upstream Agents receive this description in the internal delegation Tool. The Agent system prompt remains private.</span>
            {!readOnly && agent?.description && node.capability_description !== agent.description.trim().slice(0, 2000) ? <button type="button" onClick={() => onChange({ type: 'describe-node', nodeId: node.id, description: agent.description ?? '' })} className="mt-2 text-[9px] font-medium text-primary-light hover:text-white">Restore Agent description</button> : null}
          </label>
          <div className="rounded-xl border border-border bg-background/35 p-3"><p className="text-[9px] uppercase tracking-wide text-muted">Delegation tool</p><p className="mt-1 break-all font-mono text-[10px] text-slate-200">{delegationToolName(node)}</p></div>
          {definition.root_node_id === node.id ? <div className="flex items-center gap-2 rounded-xl border border-primary/25 bg-primary/5 p-3 text-[10px] text-primary-light"><Crown className="h-4 w-4" />Entry point and final responder</div> : <button disabled={readOnly} type="button" onClick={() => onChange({ type: 'set-root', nodeId: node.id })} className="flex w-full items-center justify-center gap-2 rounded-xl border border-primary/30 bg-primary/5 px-3 py-2.5 text-[10px] font-medium text-primary-light disabled:opacity-50"><Crown className="h-3.5 w-3.5" />Set as Entry Point</button>}
          <button disabled={readOnly || rootMustBeReassigned} type="button" title={rootMustBeReassigned ? 'Set another Agent as Entry Point before removing this node' : undefined} onClick={() => onChange({ type: 'remove-node', nodeId: node.id })} className="flex w-full items-center justify-center gap-2 rounded-xl border border-red-500/25 bg-red-500/5 px-3 py-2.5 text-[10px] font-medium text-red-300 disabled:cursor-not-allowed disabled:opacity-50"><Trash2 className="h-3.5 w-3.5" />{rootMustBeReassigned ? 'Choose another Entry Point first' : 'Remove from Network'}</button>
        </> : edge ? <>
          <div className="rounded-xl border border-border bg-background/35 p-4"><div className="flex items-center gap-2 text-xs text-white"><span className="truncate">{source?.label}</span><Link2 className="h-3.5 w-3.5 shrink-0 text-primary-light" /><span className="truncate">{target?.label}</span></div><p className="mt-3 text-[9px] leading-4 text-muted">This permission lets the source Agent delegate a task to the target Agent. Results return automatically through the invocation hierarchy.</p></div>
          <button disabled={readOnly} type="button" onClick={() => onChange({ type: 'remove-edge', edgeId: edge.id })} className="flex w-full items-center justify-center gap-2 rounded-xl border border-red-500/25 bg-red-500/5 px-3 py-2.5 text-[10px] font-medium text-red-300 disabled:opacity-50"><Trash2 className="h-3.5 w-3.5" />Remove delegation</button>
        </> : <>
          <label className="block text-[10px] text-muted">Network name<input disabled={readOnly} className={input} value={name} onChange={(event) => onMetadata({ name: event.target.value })} /></label>
          <label className="block text-[10px] text-muted">Description<textarea disabled={readOnly} className={cn(input, 'min-h-24 resize-none')} value={description} onChange={(event) => onMetadata({ description: event.target.value })} /></label>
          <section><div className="flex items-center gap-2"><Settings2 className="h-3.5 w-3.5 text-primary-light" /><p className="text-[10px] font-medium text-white">Runtime limits</p></div><div className="mt-3 grid grid-cols-2 gap-3">
            <label className="text-[9px] text-muted">Session mode<select disabled={readOnly} className={input} value={definition.settings.session_mode} onChange={(event) => onChange({ type: 'settings', settings: { ...definition.settings, session_mode: event.target.value as 'stateful' | 'stateless' } })}><option value="stateful">Stateful</option><option value="stateless">Stateless</option></select></label>
            <label className="text-[9px] text-muted">Max depth<input disabled={readOnly} type="number" min={1} max={8} className={input} value={definition.settings.max_depth} onChange={(event) => onChange({ type: 'settings', settings: { ...definition.settings, max_depth: Number(event.target.value) } })} /></label>
            <label className="text-[9px] text-muted">Max invocations<input disabled={readOnly} type="number" min={1} max={64} className={input} value={definition.settings.max_invocations} onChange={(event) => onChange({ type: 'settings', settings: { ...definition.settings, max_invocations: Number(event.target.value) } })} /></label>
            <label className="text-[9px] text-muted">Timeout (seconds)<input disabled={readOnly} type="number" min={1} max={300} className={input} value={definition.settings.timeout_seconds} onChange={(event) => onChange({ type: 'settings', settings: { ...definition.settings, timeout_seconds: Number(event.target.value) } })} /></label>
          </div></section>
        </>}

        <section className={cn('rounded-xl border p-3', errors.length ? 'border-red-500/25 bg-red-500/5' : 'border-emerald-500/20 bg-emerald-500/5')}>
          <div className="flex items-center gap-2">{errors.length ? <AlertTriangle className="h-3.5 w-3.5 text-red-400" /> : <Workflow className="h-3.5 w-3.5 text-emerald-400" />}<p className="text-[10px] font-medium text-white">{errors.length ? `${errors.length} issue${errors.length === 1 ? '' : 's'} to resolve` : 'Composition valid'}</p></div>
          {errors.length ? <ul className="mt-2 space-y-1.5">{errors.map((issue, index) => <li key={`${issue.code}-${issue.nodeId ?? issue.edgeId ?? index}`} className="text-[9px] leading-4 text-red-200">• {issue.message}</li>)}</ul> : <p className="mt-1 text-[9px] text-muted">Ready to save this Draft.</p>}
        </section>
      </div>
    </aside>
  )
}
