import { useEffect, useMemo, useState } from 'react'
import { AlertTriangle, Bot, CheckCircle2, Crown, GitBranch, ShieldCheck, X } from 'lucide-react'
import { useQuery } from '@tanstack/react-query'

import type { Agent } from '@/features/agents/types'
import { previewNetworkPromotion } from '../api'
import type { NetworkDefinition, PromotionPreview, PromotionPreviewNode } from '../types'
import type { NetworkEditorIssue } from '../editor/types'

interface ExtendedPreviewNode extends PromotionPreviewNode {
  result_ref?: string | null
  result_version?: string | null
  result_will_be_created?: boolean
  result_resolution?: 'promoted' | 'equivalent_reused' | 'retained' | 'blocked'
}

interface ExtendedPreview extends PromotionPreview {
  draft_promotions?: number
  staging_retained?: number
  release_promotions?: number
  releases_retained?: number
  equivalent_snapshots_reused?: number
}

function bindingLabel(source: string, version?: string | null, willCreate?: boolean) {
  const label = source.charAt(0).toUpperCase() + source.slice(1)
  if (version) return `${label} · ${version}`
  if (willCreate) return `${label} · new snapshot`
  return label
}

function actionLabel(action: ExtendedPreviewNode['action_required']) {
  if (action === 'promote_draft_to_staging') return 'Create immutable Agent Staging'
  if (action === 'publish_staging_to_release') return 'Create immutable Agent Release'
  return null
}

function statusLabel(item: ExtendedPreviewNode) {
  if (item.blocking_reason || item.result_resolution === 'blocked') return 'Blocked'
  if (item.result_resolution === 'equivalent_reused') return 'Equivalent reused'
  if (item.result_resolution === 'retained') return 'Retained'
  if (item.result_resolution === 'promoted' || item.action_required) return 'Promotion required'
  return item.reuse_reason ? 'Equivalent reused' : 'Retained'
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
  const previewQuery = useQuery({
    queryKey: ['network-promotion-preview', networkId, projectId, environment, JSON.stringify(definition.nodes.map((node) => node.binding))],
    queryFn: () => previewNetworkPromotion(networkId, projectId, environment),
    enabled: Boolean(networkId && projectId),
    retry: false,
  })
  const preview = previewQuery.data as ExtendedPreview | undefined
  const [approved, setApproved] = useState<Set<string>>(new Set())

  useEffect(() => {
    setApproved(new Set(preview?.actions.map((action) => action.id) ?? []))
  }, [preview])

  const errors = issues.filter((issue) => issue.severity === 'error')
  const agentIds = new Set(agents.map((agent) => agent.id))
  const unavailable = definition.nodes.filter((node) => !agentIds.has(node.agent_id))
  const requiredIds = useMemo(() => new Set(preview?.actions.map((action) => action.id) ?? []), [preview])
  const allApproved = [...requiredIds].every((id) => approved.has(id))
  const blocked = pending || previewQuery.isLoading || !preview?.ready || errors.length > 0 || unavailable.length > 0 || !allApproved
  const actionCount = preview?.actions.length ?? 0

  const toggle = (id: string) => setApproved((current) => {
    const next = new Set(current)
    if (next.has(id)) next.delete(id)
    else next.add(id)
    return next
  })

  const summary = environment === 'staging'
    ? `${preview?.draft_promotions ?? actionCount} Draft promotion${(preview?.draft_promotions ?? actionCount) === 1 ? '' : 's'} · ${preview?.staging_retained ?? 0} Staging retained · ${preview?.releases_retained ?? 0} Release${(preview?.releases_retained ?? 0) === 1 ? '' : 's'} retained`
    : `${preview?.release_promotions ?? actionCount} Agent Release${(preview?.release_promotions ?? actionCount) === 1 ? '' : 's'} created · ${preview?.releases_retained ?? 0} existing Release${(preview?.releases_retained ?? 0) === 1 ? '' : 's'} retained · 0 Agent Productions changed`

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 p-4 backdrop-blur-sm">
      <div className="flex max-h-[90vh] w-full max-w-3xl flex-col overflow-hidden rounded-2xl border border-border bg-surface shadow-2xl">
        <header className="flex items-start gap-3 border-b border-border p-5">
          <div className="min-w-0 flex-1">
            <p className="text-[9px] font-semibold uppercase tracking-widest text-primary-light">{environment === 'staging' ? 'Draft → Network Staging' : 'Network Staging → Network Release'}</p>
            <h2 className="mt-1 text-base font-semibold text-white">{environment === 'staging' ? 'Create immutable Network Staging?' : 'Publish immutable Network Release?'}</h2>
            <p className="mt-1 text-[10px] leading-4 text-muted">The source Network snapshot remains unchanged. Only incompatible Agent bindings require a new snapshot.</p>
          </div>
          <button type="button" onClick={onClose} className="rounded-lg border border-border p-2 text-muted hover:text-white"><X className="h-4 w-4" /></button>
        </header>

        <div className="scrollbar-thin min-h-0 flex-1 space-y-3 overflow-y-auto overscroll-contain p-5">
          <section className="rounded-xl border border-primary/25 bg-primary/[0.04] p-4">
            <div className="flex items-start gap-3"><ShieldCheck className="mt-0.5 h-4 w-4 text-primary-light" /><div><p className="text-[9px] font-semibold uppercase tracking-wider text-muted">Result</p><p className="mt-2 text-[10px] leading-5 text-slate-200">{summary}</p>{environment === 'production' ? <p className="mt-2 rounded-lg border border-emerald-500/20 bg-emerald-500/[0.04] p-2 text-[9px] leading-4 text-emerald-200">Agent Releases created here are pinned to this Network Release. They do not become active in the standalone Agent Playground.</p> : null}</div></div>
          </section>

          {(preview?.nodes as ExtendedPreviewNode[] | undefined)?.map((item) => {
            const node = definition.nodes.find((candidate) => candidate.id === item.node_id)
            const root = node?.id === definition.root_node_id
            const requiresApproval = Boolean(item.action_id && item.action_required)
            const checked = item.action_id ? approved.has(item.action_id) : true
            const resultVersion = item.result_version ?? (item.result_resolution === 'equivalent_reused' ? item.selected_version : null)
            return <article key={item.node_id} className="rounded-xl border border-border bg-background/35 p-3">
              <div className="flex items-start gap-3">
                <div className="flex h-9 w-9 items-center justify-center rounded-xl border border-border bg-background/50 text-primary-light">{root ? <Crown className="h-4 w-4" /> : <Bot className="h-4 w-4" />}</div>
                <div className="min-w-0 flex-1"><p className="truncate text-[10px] font-medium text-white">{node?.label ?? item.agent_name}</p><p className="mt-1 truncate text-[9px] text-muted">{item.agent_name}</p><div className="mt-2 flex flex-wrap items-center gap-1.5 text-[8px]"><span className="rounded border border-border bg-background/50 px-1.5 py-1 text-slate-300">{bindingLabel(item.selected_source, item.selected_version)}</span><span className="text-muted">→</span><span className="rounded border border-primary/25 bg-primary/5 px-1.5 py-1 text-primary-light">{bindingLabel(item.result_source, resultVersion, item.result_will_be_created ?? requiresApproval)}</span></div></div>
                {requiresApproval ? <label className="flex cursor-pointer items-center gap-2 rounded-lg border border-amber-500/25 bg-amber-500/5 px-2 py-1.5 text-[8px] text-amber-100"><input type="checkbox" checked={checked} onChange={() => toggle(item.action_id!)} />Approve</label> : <span className="flex items-center gap-1 rounded-md border border-emerald-500/20 bg-emerald-500/5 px-2 py-1 text-[8px] text-emerald-300"><CheckCircle2 className="h-3 w-3" />{statusLabel(item)}</span>}
              </div>
              {item.action_required ? <p className="mt-3 flex items-center gap-2 border-t border-border/70 pt-2 text-[9px] text-amber-100"><GitBranch className="h-3.5 w-3.5" />{actionLabel(item.action_required)}</p> : null}
              {item.reuse_reason ? <p className="mt-2 text-[9px] leading-4 text-emerald-200">{item.reuse_reason}</p> : null}
              {item.blocking_reason ? <p className="mt-2 text-[9px] leading-4 text-red-200">{item.blocking_reason}</p> : null}
            </article>
          })}

          {previewQuery.isLoading ? <div className="rounded-xl border border-border bg-background/35 p-4 text-[9px] text-muted">Resolving exact Agent snapshots…</div> : null}
          {previewQuery.isError ? <div className="rounded-xl border border-red-500/25 bg-red-500/5 p-4 text-[9px] text-red-200">{previewQuery.error instanceof Error ? previewQuery.error.message : 'Unable to validate this promotion'}</div> : null}
          {errors.length ? <div className="rounded-xl border border-red-500/25 bg-red-500/5 p-4"><p className="flex items-center gap-2 text-[10px] text-red-200"><AlertTriangle className="h-4 w-4" />Resolve the composition before promotion</p>{errors.map((issue, index) => <p key={`${issue.code}-${index}`} className="mt-1 text-[9px] text-red-200">• {issue.message}</p>)}</div> : null}
        </div>

        <footer className="flex items-center justify-end gap-2 border-t border-border p-4"><button type="button" onClick={onClose} className="rounded-lg border border-border px-3 py-2 text-[10px] text-muted hover:text-white">Cancel</button><button type="button" disabled={blocked} onClick={() => preview && onConfirm(preview, [...approved])} className="rounded-lg bg-primary px-4 py-2 text-[10px] font-semibold text-white disabled:opacity-45">{pending ? 'Applying…' : environment === 'staging' ? 'Create Network Staging' : 'Publish Network Release'}</button></footer>
      </div>
    </div>
  )
}
