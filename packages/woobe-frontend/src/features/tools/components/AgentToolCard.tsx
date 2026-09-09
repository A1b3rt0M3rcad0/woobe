import { AlertTriangle, MoreHorizontal, Pencil, Trash2, Wrench } from 'lucide-react'

import { HttpProviderPanel, isHttpProviderTool } from '@/features/tools/components/HttpProviderPanel'
import { McpProviderPanel, isMcpProviderTool } from '@/features/tools/components/McpProviderPanel'
import type { HttpToolConfig, McpToolPermission, Tool } from '@/features/tools/types'
import { cn } from '@/lib/utils'

export type AgentToolCardContext = 'playground' | 'network'

interface AgentToolCardProps {
  tool: Tool
  context?: AgentToolCardContext
  statusLoading?: boolean
  onChanged?: () => void | Promise<void>
  onToggleActive?: () => void
  onEdit?: () => void
  onRemove: () => void
  permissionOverrides?: Record<string, McpToolPermission>
  onPermissionOverridesChange?: (permissions: Record<string, McpToolPermission>) => void
}

function riskScore(risk?: string | null): number {
  const normalized = String(risk || '').toLowerCase()
  if (normalized === 'critical') return 4
  if (normalized === 'high') return 3
  if (normalized === 'medium') return 2
  if (normalized === 'low') return 1
  return 0
}

function effectiveRisk(tool: Tool): string | null | undefined {
  if (!isHttpProviderTool(tool)) return tool.risk_level
  const config = (tool.config || {}) as HttpToolConfig
  const activeRoutes = (config.routes || []).filter((route) => route.status !== 'inactive')
  if (activeRoutes.length === 0) return tool.risk_level
  return activeRoutes.reduce<string>((highest, route) => (
    riskScore(route.risk_level) > riskScore(highest) ? String(route.risk_level) : highest
  ), 'low')
}

function ToolStatusToggle({ active, loading, onClick }: { active: boolean; loading?: boolean; onClick: () => void }) {
  return (
    <button
      type="button"
      aria-label={active ? 'Turn tool off' : 'Turn tool on'}
      aria-pressed={active}
      disabled={loading}
      onClick={onClick}
      className={cn(
        'relative h-6 w-9 shrink-0 rounded-full border transition-all focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-primary disabled:pointer-events-none disabled:opacity-50',
        active ? 'border-primary/45 bg-primary/10' : 'border-border bg-background/80',
      )}
    >
      <span className={cn('absolute top-1/2 h-4 w-4 -translate-y-1/2 rounded-full transition-all', active ? 'left-4 bg-primary' : 'left-1 bg-muted')} />
    </button>
  )
}

function ActionsMenu({ canEdit, editLabel, onEdit, onRemove }: { canEdit: boolean; editLabel: string; onEdit?: () => void; onRemove: () => void }) {
  return (
    <details className="relative">
      <summary className="flex h-7 w-7 cursor-pointer list-none items-center justify-center rounded-lg border border-border/80 bg-background/50 text-muted transition-colors hover:bg-accent hover:text-white [&::-webkit-details-marker]:hidden" aria-label="Tool actions">
        <MoreHorizontal className="h-3.5 w-3.5" />
      </summary>
      <div className="absolute right-0 top-9 z-30 min-w-40 rounded-lg border border-border bg-surface p-1 shadow-xl">
        {canEdit && onEdit ? (
          <button type="button" onClick={onEdit} className="flex w-full items-center gap-2 rounded-md px-2.5 py-2 text-left text-xs text-white hover:bg-accent">
            <Pencil className="h-3.5 w-3.5" />
            {editLabel}
          </button>
        ) : null}
        <button type="button" onClick={onRemove} className="flex w-full items-center gap-2 rounded-md px-2.5 py-2 text-left text-xs text-red-200 hover:bg-red-500/10">
          <Trash2 className="h-3.5 w-3.5" />
          Remove from Agent
        </button>
      </div>
    </details>
  )
}

export function AgentToolCard({
  tool,
  context = 'playground',
  statusLoading,
  onChanged,
  onToggleActive,
  onEdit,
  onRemove,
  permissionOverrides,
  onPermissionOverridesChange,
}: AgentToolCardProps) {
  const isActive = tool.status === 'active'
  const isRetired = tool.status === 'deprecated'
  const isMcp = isMcpProviderTool(tool)
  const isHttpProvider = isHttpProviderTool(tool)
  const risk = effectiveRisk(tool)
  const showRisk = riskScore(risk) >= 2
  const showReadOnlyStatus = context === 'playground' && !onToggleActive

  return (
    <article className={cn(
      'rounded-xl border px-3 py-2.5 transition-colors',
      isRetired ? 'border-amber-500/30 bg-amber-500/5' : isActive ? 'border-border bg-background' : 'border-border/60 bg-background/45 opacity-75',
    )}>
      <div className="flex items-center gap-2.5">
        <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg border border-border/70 bg-surface/60 text-primary-light">
          <Wrench className="h-3.5 w-3.5" />
        </span>
        <div className="min-w-0 flex-1">
          <div className="flex min-w-0 items-center gap-2">
            <h3 className="truncate text-sm font-semibold text-white">{tool.name}</h3>
            {isRetired ? (
              <span className="shrink-0 text-[9px] text-amber-200">Retired</span>
            ) : showReadOnlyStatus ? (
              <span className="shrink-0 text-[9px] capitalize text-muted">{tool.status}</span>
            ) : null}
          </div>
        </div>
        <div className="flex shrink-0 items-center gap-1.5">
          {context === 'playground' && !isRetired && onToggleActive ? <ToolStatusToggle active={isActive} loading={statusLoading} onClick={onToggleActive} /> : null}
          <ActionsMenu canEdit={!isRetired && isHttpProvider} editLabel={context === 'playground' ? 'Edit Project Tool' : 'Edit Tool'} onEdit={onEdit} onRemove={onRemove} />
        </div>
      </div>

      {isMcp ? (
        <McpProviderPanel
          tool={tool}
          onChanged={onChanged}
          permissionOverrides={permissionOverrides}
          onPermissionOverridesChange={onPermissionOverridesChange}
        />
      ) : null}

      {isHttpProvider ? (
        <HttpProviderPanel
          tool={tool}
          permissionOverrides={permissionOverrides}
          onPermissionOverridesChange={onPermissionOverridesChange}
        />
      ) : null}

      {!isMcp && !isHttpProvider ? (
        <p className="mt-2 line-clamp-2 text-[11px] leading-4 text-muted">{tool.description || 'HTTP Tool'}</p>
      ) : null}

      {showRisk ? (
        <div className="mt-1.5 flex items-center gap-1.5 px-1 text-[10px] capitalize text-amber-200">
          <AlertTriangle className="h-3 w-3" />
          {risk} risk
        </div>
      ) : null}
    </article>
  )
}
