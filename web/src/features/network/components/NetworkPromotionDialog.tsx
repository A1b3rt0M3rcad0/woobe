import { useEffect, useMemo, useState } from 'react'
import { AlertTriangle, Bot, CheckCircle2, Crown, GitBranch, ShieldCheck, X } from 'lucide-react'
import { useQuery } from '@tanstack/react-query'
import type { Agent } from '@/features/agents/types'
import { previewNetworkPromotion } from '../api'
import type { NetworkDefinition, PromotionPreview } from '../types'
import type { NetworkEditorIssue } from '../editor/types'

function actionLabel(action: 'promote_draft_to_staging' | 'publish_staging_to_release') {
  return action === 'promote_draft_to_staging'
    ? 'Promote changed Agent Draft to immutable Staging'
    : 'Publish changed Agent Staging as a Release'
}

function bindingLabel(source: string, version: string | null) {
  const label = source.charAt(0).toUpperCase() + source.slice(1)
  return version ? `${label} ${version}` : label
}

function impactLabel(kind?: string) {
  if (kind === 'compatibility') return 'Compatibility change'
  if (kind === 'feature') return 'Feature change'
  return 'Internal change'
}

export function NetworkPromotionDialog({
  environment,
  networkId,
  projectId,
  definition,
  agents,
  issues,
  pending,
  onClose,
  onConfirm,
}: {
  environment: 'staging' | 'production'
  networkId: string
  projectId: string
  definition: NetworkDefinition
  agents: Agent[]
  issues: NetworkEditorIssue[]
  pending: boolean
  onClose: () => void
  onConfirm: (preview: PromotionPreview, approvedActionIds: string[]) => void
}) {
  const agentsById = new Map(agents.map((agent) => [agent.id, agent]))
  const preview = useQuery({
    queryKey: ['network-promotion-preview', networkId, projectId, environment, JSON.stringify(definition.nodes.map((node) => node.binding))],
    queryFn: () => previewNetworkPromotion(networkId, projectId, environment),
    enabled: Boolean(networkId && projectId),
    retry: false,
  })
  const [approved, setApproved] = useState<Set<string>>(() => new Set())

  useEffect(() => {
    setApproved(new Set(preview.data?.actions.map((action) => action.id) ?? []))
  }, [preview.data])

  const errors = issues.filter((issue) => issue.severity === 'error')
  const unavailable = definition.nodes.filter((node) => !agentsById.has(node.agent_id))
  const requiredActionIds = useMemo(() => new Set(preview.data?.actions.map((action) => action.id) ?? []), [preview.data])
  const allApproved = [...requiredActionIds].every((id) => approved.has(id))
  const blocked = errors.length > 0
    || unavailable.length > 0
    || pending
    || preview.isLoading
    || !preview.data?.ready
    || !allApproved

  const toggleAction = (id: string) => {
    setApproved((current) => {
      const next = new Set(current)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  const actionCount = preview.data?.actions.length ?? 0
  const confirmLabel = pending
    ? 'Promoting…'
    : actionCount > 0
      ? environment === 'staging'
        ? `Promote ${actionCount} changed Agent${actionCount === 1 ? '' : 's'} and create Staging`
        : `Publish ${actionCount} changed Agent${actionCount === 1 ? '' : 's'} and Network Release`
      : environment === 'staging'
        ? 'Create Network Staging'
        : 'Publish Network Release'

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 p-4 backdrop-blur-sm">
      <div className="flex max-h-[90vh] w-full max-w-3xl flex-col overflow-hidden rounded-2xl border border-border bg-surface shadow-2xl">
        <header className="flex items-start gap-3 border-b border-border p-5">
          <div className="min-w-0 flex-1">
            <p className="text-[9px] font-semibold uppercase tracking-widest text-primary-light">{environment === 'staging' ? 'Draft → Staging' : 'Staging → Production'}</p>
            <h2 className="mt-1 text-base font-semibold text-white">Create immutable Network {environment === 'staging' ? 'Staging' : 'Release'}?</h2>
            <p className="mt-1 text-[10px] leading-4 text-muted">Only changed Agent snapshots require approval. Equivalent Staging and Release snapshots are reused automatically.</p>
          </div>
          <button type="button" onClick={onClose} className="rounded-lg border border-border p-2 text-muted hover:text-white"><X className="h-4 w-4" /></button>
        </header>

        <div className="scrollbar-thin min-h-0 flex-1 space-y-3 overflow-y-auto overscroll-contain p-5">
          {environment === 'production' && preview.data?.release_preview ? (
            <section className="rounded-xl border border-primary/25 bg-primary/[0.04] p-4">
              <div className="flex items-start gap-3">
                <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0 text-primary-light" />
                <div className="min-w-0 flex-1">
                  <p className="text-[9px] font-semibold uppercase tracking-widest text-muted">Network Release impact</p>
                  <div className="mt-2 flex flex-wrap items-center gap-2"><span className="rounded border border-primary/25 bg-primary/10 px-2 py-1 text-[9px] font-medium text-primary-light">{impactLabel(preview.data.release_preview.change_kind)}</span><span className="font-mono text-[11px] font-semibold text-white">{preview.data.release_preview.next_version}</span></div>
                  <p className="mt-3 text-[10px] leading-5 text-slate-300">Public compatibility is inherited from the entry Agent Release <span className="font-mono text-white">{preview.data.release_preview.entry_agent_release_version ?? 'unavailable'}</span>.</p>
                  {preview.data.release_preview.internal_warnings.length ? <div className="mt-3 rounded-lg border border-amber-500/25 bg-amber-500/[0.05] p-3"><p className="text-[9px] font-medium text-amber-200">Internal dependency review</p>{preview.data.release_preview.internal_warnings.map((warning) => <p key={warning} className="mt-1 text-[9px] leading-4 text-amber-100">• {warning}</p>)}</div> : null}
                  <details className="mt-3"><summary className="cursor-pointer text-[9px] font-medium text-muted">View inherited output contract</summary><pre className="scrollbar-thin mt-2 max-h-52 overflow-auto rounded-lg border border-border/70 bg-black/20 p-3 text-[9px] leading-5 text-slate-300">{JSON.stringify(preview.data.release_preview.public_output_contract ?? { type: 'text' }, null, 2)}</pre></details>
                </div>
              </div>
            </section>
          ) : null}
          {environment === 'staging' && preview.data?.staging_preview ? <section className="rounded-xl border border-indigo-500/25 bg-indigo-500/[0.04] p-4"><p className="text-[9px] font-semibold uppercase tracking-widest text-indigo-300">Next validation snapshot</p><p className="mt-2 font-mono text-[13px] font-semibold text-white">{preview.data.staging_preview.next_version}</p><p className="mt-1 text-[9px] text-muted">{preview.data.staging_preview.reused_agent_count} Agent snapshots reused · {preview.data.staging_preview.promotion_count} promotions required</p></section> : null}

          {preview.data?.nodes.map((item) => {
            const node = definition.nodes.find((candidate) => candidate.id === item.node_id)
            const root = node?.id === definition.root_node_id
            const requiresAction = item.action_id && item.action_required
            const checked = item.action_id ? approved.has(item.action_id) : true
            const reused = Boolean(item.reuse_reason)
            return (
              <article key={item.node_id} className="rounded-xl border border-border bg-background/35 p-3">
                <div className="flex items-start gap-3">
                  <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl border border-border bg-background/50 text-primary-light">{root ? <Crown className="h-4 w-4" /> : <Bot className="h-4 w-4" />}</div>
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-[10px] font-medium text-white">{node?.label ?? item.agent_name}</p>
                    <p className="mt-1 truncate text-[9px] text-muted">{item.agent_name}</p>
                    <div className="mt-2 flex flex-wrap items-center gap-1.5 text-[8px]"><span className="rounded border border-border bg-background/50 px-1.5 py-1 text-slate-300">{bindingLabel(item.selected_source, item.selected_version)}</span><span className="text-muted">→</span><span className="rounded border border-primary/25 bg-primary/5 px-1.5 py-1 text-primary-light">{bindingLabel(item.result_source, item.selected_version)}</span></div>
                  </div>
                  {item.blocking_reason ? <span className="rounded-md border border-red-500/25 bg-red-500/5 px-2 py-1 text-[8px] text-red-300">Blocked</span> : requiresAction ? <label className="flex cursor-pointer items-center gap-2 rounded-lg border border-amber-500/25 bg-amber-500/5 px-2 py-1.5 text-[8px] text-amber-100"><input type="checkbox" checked={checked} onChange={() => toggleAction(item.action_id!)} />Approve</label> : <span className="flex items-center gap-1 rounded-md border border-emerald-500/20 bg-emerald-500/5 px-2 py-1 text-[8px] font-medium text-emerald-300"><CheckCircle2 className="h-3 w-3" />{reused ? 'Reused' : 'Pinned'}</span>}
                </div>
                {requiresAction ? <div className="mt-3 flex items-center gap-2 border-t border-border/70 pt-2 text-[9px] text-amber-100"><GitBranch className="h-3.5 w-3.5" />{actionLabel(item.action_required!)}</div> : null}
                {item.reuse_reason ? <p className="mt-3 border-t border-emerald-500/15 pt-2 text-[9px] leading-4 text-emerald-200">{item.reuse_reason}</p> : null}
                {item.blocking_reason ? <p className="mt-2 border-t border-red-500/15 pt-2 text-[9px] leading-4 text-red-200">{item.blocking_reason}</p> : null}
              </article>
            )
          })}

          {preview.isLoading ? <div className="rounded-xl border border-border bg-background/35 p-4 text-[9px] text-muted">Resolving Agent snapshots, contracts and release impact…</div> : null}
          {errors.length ? <div className="rounded-xl border border-red-500/25 bg-red-500/5 p-4"><div className="flex items-center gap-2 text-[10px] font-medium text-red-200"><AlertTriangle className="h-4 w-4" />Resolve the composition before promotion</div><ul className="mt-2 space-y-1">{errors.map((issue, index) => <li key={`${issue.code}-${index}`} className="text-[9px] leading-4 text-red-200">• {issue.message}</li>)}</ul></div> : null}
          {preview.data && !allApproved ? <div className="rounded-xl border border-amber-500/25 bg-amber-500/5 p-4 text-[9px] leading-4 text-amber-100">Approve each Agent snapshot that actually changed. Unchanged snapshots are reused without approval.</div> : null}
          {preview.isError ? <div className="rounded-xl border border-red-500/25 bg-red-500/5 p-4 text-[9px] text-red-200">{preview.error instanceof Error ? preview.error.message : 'Unable to validate this promotion'}</div> : null}
        </div>

        <footer className="flex items-center justify-end gap-2 border-t border-border p-4">
          <button type="button" onClick={onClose} className="rounded-lg border border-border px-3 py-2 text-[10px] text-muted hover:text-white">Cancel</button>
          <button type="button" disabled={blocked} onClick={() => preview.data && onConfirm(preview.data, [...approved])} className="rounded-lg bg-primary px-4 py-2 text-[10px] font-semibold text-white disabled:cursor-not-allowed disabled:opacity-45">{confirmLabel}</button>
        </footer>
      </div>
    </div>
  )
}
