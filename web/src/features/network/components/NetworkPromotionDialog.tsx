import { AlertTriangle, Bot, CheckCircle2, Crown, X } from 'lucide-react'
import type { Agent } from '@/features/agents/types'
import type { NetworkDefinition } from '../types'
import type { NetworkEditorIssue } from '../editor/types'

export function NetworkPromotionDialog({
  environment,
  definition,
  agents,
  issues,
  pending,
  onClose,
  onConfirm,
}: {
  environment: 'staging' | 'production'
  definition: NetworkDefinition
  agents: Agent[]
  issues: NetworkEditorIssue[]
  pending: boolean
  onClose: () => void
  onConfirm: () => void
}) {
  const agentsById = new Map(agents.map((agent) => [agent.id, agent]))
  const errors = issues.filter((issue) => issue.severity === 'error')
  const unavailable = definition.nodes.filter((node) => !agentsById.has(node.agent_id))
  const blocked = errors.length > 0 || unavailable.length > 0 || pending
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 p-4 backdrop-blur-sm">
      <div className="flex max-h-[86vh] w-full max-w-2xl flex-col overflow-hidden rounded-2xl border border-border bg-surface shadow-2xl">
        <header className="flex items-start gap-3 border-b border-border p-5"><div className="min-w-0 flex-1"><p className="text-[9px] font-semibold uppercase tracking-widest text-primary-light">Draft → {environment}</p><h2 className="mt-1 text-base font-semibold text-white">Create immutable Network {environment === 'staging' ? 'Staging' : 'Release'}?</h2><p className="mt-1 text-[10px] leading-4 text-muted">The backend will resolve the latest compatible {environment} version for every Agent and pin those exact IDs in the Network snapshot.</p></div><button type="button" onClick={onClose} className="rounded-lg border border-border p-2 text-muted hover:text-white"><X className="h-4 w-4" /></button></header>
        <div className="min-h-0 flex-1 space-y-2 overflow-y-auto p-5">
          {definition.nodes.map((node) => {
            const agent = agentsById.get(node.agent_id)
            const root = node.id === definition.root_node_id
            return <article key={node.id} className="flex items-center gap-3 rounded-xl border border-border bg-background/35 p-3"><div className="flex h-9 w-9 items-center justify-center rounded-xl border border-border bg-background/50 text-primary-light">{root ? <Crown className="h-4 w-4" /> : <Bot className="h-4 w-4" />}</div><div className="min-w-0 flex-1"><p className="truncate text-[10px] font-medium text-white">{node.label}</p><p className="mt-1 truncate text-[9px] text-muted">{agent ? `${agent.provider}/${agent.model}` : 'Agent unavailable'}</p></div>{agent ? <span className="flex items-center gap-1 rounded-md border border-emerald-500/20 bg-emerald-500/5 px-2 py-1 text-[8px] font-medium text-emerald-300"><CheckCircle2 className="h-3 w-3" />Resolve version</span> : <span className="text-[8px] text-red-300">Unavailable</span>}</article>
          })}
          {errors.length ? <div className="rounded-xl border border-red-500/25 bg-red-500/5 p-4"><div className="flex items-center gap-2 text-[10px] font-medium text-red-200"><AlertTriangle className="h-4 w-4" />Resolve the composition before promotion</div><ul className="mt-2 space-y-1">{errors.map((issue, index) => <li key={`${issue.code}-${index}`} className="text-[9px] leading-4 text-red-200">• {issue.message}</li>)}</ul></div> : null}
        </div>
        <footer className="flex items-center justify-end gap-2 border-t border-border p-4"><button type="button" onClick={onClose} className="rounded-lg border border-border px-3 py-2 text-[10px] text-muted hover:text-white">Cancel</button><button type="button" disabled={blocked} onClick={onConfirm} className="rounded-lg bg-primary px-4 py-2 text-[10px] font-semibold text-white disabled:cursor-not-allowed disabled:opacity-45">{pending ? 'Promoting…' : environment === 'staging' ? 'Create Staging' : 'Publish Release'}</button></footer>
      </div>
    </div>
  )
}

