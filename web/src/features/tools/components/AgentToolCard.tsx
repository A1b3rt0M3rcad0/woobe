import type { ReactNode } from 'react'
import { Pencil, Shield, Trash2 } from 'lucide-react'

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

const RISK_DOTS = [0, 1, 2, 3]

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

function riskDotTone(risk?: string | null): string {
  const normalized = String(risk || '').toLowerCase()
  if (normalized === 'critical') return 'bg-red-300 shadow-red-400/20'
  if (normalized === 'high') return 'bg-orange-300 shadow-orange-400/20'
  if (normalized === 'medium') return 'bg-amber-300 shadow-amber-400/20'
  return 'bg-primary shadow-primary/20'
}

function toolTypeLabel(tool: Tool): string {
  const config = (tool.config || {}) as Record<string, unknown>
  if (String(tool.type).toLowerCase() === 'mcp' || config.protocol === 'mcp') return 'MCP'
  if (isHttpProviderTool(tool)) return 'HTTP API'
  if (String(tool.type).toLowerCase().includes('http')) return 'HTTP'
  return String(tool.type || 'Tool').replace(/_/g, ' ').toUpperCase()
}

function ToolTypeBadge({ type }: { type: string }) {
  return <span className="inline-flex h-6 items-center rounded-lg bg-muted/15 px-2 text-[10px] font-semibold uppercase tracking-wide text-white ring-1 ring-border/70">{type}</span>
}

function RiskIndicator({ risk }: { risk?: string | null }) {
  const normalized = String(risk || 'unknown').toLowerCase()
  const activeDots = riskScore(risk)
  const dotTone = riskDotTone(risk)

  return (
    <span className="inline-flex h-6 max-w-full items-center gap-1.5 rounded-lg border border-border/80 bg-background/70 px-2 text-muted" title={`Risk: ${normalized}`} aria-label={`Risk: ${normalized}, ${activeDots} of 4`}>
      <Shield className="h-3.5 w-3.5 shrink-0 text-white/90" />
      <span className="flex min-w-0 items-center gap-0.5">
        {RISK_DOTS.map((index) => <span key={index} className={cn('h-1.5 w-1.5 shrink-0 rounded-full', index < activeDots ? `${dotTone} shadow-sm` : 'bg-muted/25')} />)}
      </span>
    </span>
  )
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
        active ? 'border-primary/45 bg-primary/10 shadow-sm shadow-primary/10' : 'border-border bg-background/80',
      )}
    >
      <span className={cn('absolute top-1/2 h-4 w-4 -translate-y-1/2 rounded-full transition-all', active ? 'left-4 bg-primary shadow-sm shadow-primary/20' : 'left-1 bg-muted')} />
    </button>
  )
}

function ToolIconButton({ label, tone = 'default', loading, onClick, children }: { label: string; tone?: 'default' | 'danger'; loading?: boolean; onClick: () => void; children: ReactNode }) {
  return (
    <button
      type="button"
      aria-label={label}
      title={label}
      disabled={loading}
      onClick={onClick}
      className={cn(
        'inline-flex h-7 w-7 shrink-0 items-center justify-center rounded-lg border bg-background/50 transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-primary disabled:pointer-events-none disabled:opacity-50',
        tone === 'danger' ? 'border-red-500/30 text-red-200 hover:bg-red-500/10 hover:text-red-100' : 'border-border/80 text-white/80 hover:bg-accent hover:text-white',
      )}
    >
      {children}
    </button>
  )
}

function StatusPill({ status }: { status?: string | null }) {
  const active = status === 'active'
  const retired = status === 'deprecated'
  return (
    <span className={cn(
      'shrink-0 rounded-full border px-2 py-0.5 text-[9px] font-medium',
      retired ? 'border-amber-500/35 bg-amber-500/10 text-amber-200' : active ? 'border-emerald-500/35 bg-emerald-500/10 text-emerald-300' : 'border-border bg-background/70 text-muted',
    )}>
      {retired ? 'Retired' : status || 'inactive'}
    </span>
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

  return (
    <article className={cn(
      'rounded-xl border p-3 shadow-sm transition-all',
      isRetired ? 'border-amber-500/30 bg-amber-500/5' : isActive ? 'border-border bg-background' : 'border-border/50 bg-background/50 opacity-75',
    )}>
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1 space-y-0.5">
          <div className="flex min-w-0 flex-wrap items-center gap-2">
            <h3 className="min-w-0 truncate text-sm font-semibold text-white">{tool.name}</h3>
            {context === 'network' ? <StatusPill status={tool.status} /> : isRetired ? <span className="rounded-full border border-amber-500/35 bg-amber-500/10 px-2 py-0.5 text-[10px] font-medium text-amber-200">Retired globally</span> : null}
          </div>
          <p className="line-clamp-2 break-words text-xs leading-relaxed text-muted">{tool.description || 'No description'}</p>
          {isRetired ? <p className="pt-1 text-[11px] leading-5 text-amber-200/80">Existing Agent snapshots remain valid. This Tool cannot be added to new Agent bindings.</p> : null}
        </div>

        <div className="flex shrink-0 items-center gap-1.5">
          {context === 'playground' && !isRetired && onToggleActive ? <ToolStatusToggle active={isActive} loading={statusLoading} onClick={onToggleActive} /> : null}
          {!isRetired && !isMcp && onEdit ? <ToolIconButton label="Edit tool" onClick={onEdit}><Pencil className="h-3.5 w-3.5" /></ToolIconButton> : null}
          <ToolIconButton label="Remove tool from draft" tone="danger" onClick={onRemove}><Trash2 className="h-3.5 w-3.5" /></ToolIconButton>
        </div>
      </div>

      <div className="mt-3 flex flex-wrap items-center gap-2">
        <ToolTypeBadge type={toolTypeLabel(tool)} />
        <RiskIndicator risk={risk} />
      </div>

      {isMcp ? (
        <div className="mt-3">
          <McpProviderPanel
            tool={tool}
            onChanged={onChanged}
            permissionOverrides={permissionOverrides}
            onPermissionOverridesChange={onPermissionOverridesChange}
          />
        </div>
      ) : null}

      {isHttpProvider ? (
        <HttpProviderPanel
          tool={tool}
          permissionOverrides={permissionOverrides}
          onPermissionOverridesChange={onPermissionOverridesChange}
        />
      ) : null}
    </article>
  )
}
