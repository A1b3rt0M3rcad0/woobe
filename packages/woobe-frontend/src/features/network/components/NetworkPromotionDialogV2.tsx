import { useEffect, useMemo, useState } from 'react'
import { AlertTriangle, Bot, CheckCircle2, Crown, GitBranch, ShieldCheck } from 'lucide-react'
import { useQuery } from '@tanstack/react-query'
import {
  Alert,
  AlertDescription,
  Badge,
  Button,
  Checkbox,
  Dialog,
  SectionBlock,
  Skeleton,
  TechnicalListItem,
} from '@woobe/ui'

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

function statusVariant(item: ExtendedPreviewNode) {
  if (item.blocking_reason || item.result_resolution === 'blocked') return 'destructive' as const
  if (item.action_required || item.result_resolution === 'promoted') return 'warning' as const
  return 'success' as const
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
  const title = environment === 'staging' ? 'Create immutable Network Staging?' : 'Publish immutable Network Release?'

  return (
    <Dialog open onClose={onClose} title={title} className="max-w-dialog-wide" scrollMode="content">
      <div className="grid gap-ui-md">
        <SectionBlock
          title="Promotion result"
          eyebrow={environment === 'staging' ? 'Draft → Network Staging' : 'Network Staging → Network Release'}
          density="compact"
          actions={<ShieldCheck className="h-icon w-icon text-primary-light" />}
        >
          <p className="font-mono text-system-control text-accent-foreground">{summary}</p>
          <p className="mt-ui-sm font-sans text-product-caption leading-5 text-muted-foreground">
            The source Network snapshot remains unchanged. Only incompatible Agent bindings require a new snapshot.
          </p>
          {environment === 'production' ? (
            <Alert variant="success" className="mt-ui-md">
              <AlertDescription>
                Agent Releases created here are pinned to this Network Release. They do not become active in the standalone Agent Playground.
              </AlertDescription>
            </Alert>
          ) : null}
        </SectionBlock>

        {previewQuery.isLoading ? (
          <SectionBlock title="Resolving Agent snapshots" density="compact">
            <div className="grid gap-ui-xs">
              <Skeleton className="h-control-row w-full" />
              <Skeleton className="h-control-row w-full" />
            </div>
          </SectionBlock>
        ) : null}

        <div className="grid gap-ui-xs">
          {(preview?.nodes as ExtendedPreviewNode[] | undefined)?.map((item) => {
            const node = definition.nodes.find((candidate) => candidate.id === item.node_id)
            const root = node?.id === definition.root_node_id
            const requiresApproval = Boolean(item.action_id && item.action_required)
            const checked = item.action_id ? approved.has(item.action_id) : true
            const resultVersion = item.result_version ?? (item.result_resolution === 'equivalent_reused' ? item.selected_version : null)

            return (
              <TechnicalListItem
                key={item.node_id}
                label={node?.label ?? item.agent_name}
                description={item.agent_name}
                leading={(
                  <span className="flex h-control-sm w-control-sm items-center justify-center rounded-control border border-border bg-control text-primary-light">
                    {root ? <Crown className="h-icon w-icon" /> : <Bot className="h-icon w-icon" />}
                  </span>
                )}
                meta={(
                  <div className="flex flex-wrap items-center gap-ui-xs">
                    <Badge variant="outline" size="compact">{bindingLabel(item.selected_source, item.selected_version)}</Badge>
                    <span className="font-mono text-system-meta text-muted-foreground">→</span>
                    <Badge variant="default" size="compact">{bindingLabel(item.result_source, resultVersion, item.result_will_be_created ?? requiresApproval)}</Badge>
                  </div>
                )}
                trailing={requiresApproval ? (
                  <label className="flex cursor-pointer items-center gap-ui-xs rounded-control border border-warning/25 bg-warning/[0.05] px-ui-sm py-ui-xs font-mono text-system-label text-warning">
                    <Checkbox checked={checked} onChange={() => toggle(item.action_id!)} />
                    Approve
                  </label>
                ) : (
                  <Badge variant={statusVariant(item)} size="compact">
                    <CheckCircle2 className="h-icon-sm w-icon-sm" />
                    {statusLabel(item)}
                  </Badge>
                )}
              >
                {item.action_required ? (
                  <div className="mt-ui-sm flex items-center gap-ui-xs border-t border-border pt-ui-sm font-sans text-product-caption text-warning">
                    <GitBranch className="h-icon-sm w-icon-sm" />
                    {actionLabel(item.action_required)}
                  </div>
                ) : null}
                {item.reuse_reason ? <p className="mt-ui-xs font-sans text-product-caption leading-5 text-success">{item.reuse_reason}</p> : null}
                {item.blocking_reason ? <p className="mt-ui-xs font-sans text-product-caption leading-5 text-error">{item.blocking_reason}</p> : null}
              </TechnicalListItem>
            )
          })}
        </div>

        {previewQuery.isError ? (
          <Alert variant="destructive">
            <AlertDescription>{previewQuery.error instanceof Error ? previewQuery.error.message : 'Unable to validate this promotion'}</AlertDescription>
          </Alert>
        ) : null}

        {errors.length ? (
          <Alert variant="destructive">
            <AlertDescription>
              <span className="flex items-center gap-ui-xs font-mono text-system-label font-semibold">
                <AlertTriangle className="h-icon-sm w-icon-sm" />Resolve the composition before promotion
              </span>
              {errors.map((issue, index) => <span key={`${issue.code}-${index}`} className="mt-ui-xs block">• {issue.message}</span>)}
            </AlertDescription>
          </Alert>
        ) : null}

        <footer className="flex items-center justify-end gap-ui-sm border-t border-border pt-ui-md">
          <Button type="button" variant="outline" onClick={onClose}>Cancel</Button>
          <Button type="button" disabled={blocked} onClick={() => preview && onConfirm(preview, [...approved])}>
            {pending ? 'Applying…' : environment === 'staging' ? 'Create Network Staging' : 'Publish Network Release'}
          </Button>
        </footer>
      </div>
    </Dialog>
  )
}
