import { useMemo, useState } from 'react'
import { Globe2, Settings2 } from 'lucide-react'

import { Button } from '@/components/ui/Button'
import { Dialog } from '@/components/ui/Dialog'
import { isHttpToolGroup } from '@/features/tools/httpToolContract'
import type { HttpRouteConfig, HttpToolConfig, McpToolPermission, McpToolPermissionMode, Tool } from '@/features/tools/types'

interface HttpProviderPanelProps {
  tool: Tool
  permissionOverrides?: Record<string, McpToolPermission>
  onPermissionOverridesChange?: (permissions: Record<string, McpToolPermission>) => void
}

function httpConfig(tool: Tool): HttpToolConfig {
  return (tool.config || {}) as HttpToolConfig
}

export function isHttpProviderTool(tool: Tool): boolean {
  const config = httpConfig(tool)
  return String(tool.type).toLowerCase() !== 'mcp'
    && config.protocol === 'http'
    && isHttpToolGroup(config)
}

function routes(tool: Tool): HttpRouteConfig[] {
  const config = httpConfig(tool)
  return Array.isArray(config.routes) ? config.routes : []
}

function defaultPermission(route: HttpRouteConfig): McpToolPermissionMode {
  const mode = route.permission?.mode || route.default_permission
  return mode === 'allow' || mode === 'deny' || mode === 'review' ? mode : 'review'
}

function permissionFor(route: HttpRouteConfig, overrides?: Record<string, McpToolPermission>): McpToolPermission {
  return overrides?.[route.id]
    || overrides?.[route.operation_id]
    || route.permission
    || { mode: defaultPermission(route), risk_level: route.risk_level }
}

function permissionCounts(items: HttpRouteConfig[], overrides?: Record<string, McpToolPermission>) {
  return items.reduce((counts, route) => {
    const mode = permissionFor(route, overrides).mode
    counts[mode] += 1
    return counts
  }, { allow: 0, review: 0, deny: 0 } as Record<McpToolPermissionMode, number>)
}

function providerHost(tool: Tool): string {
  try { return new URL(httpConfig(tool).base_url || '').hostname } catch { return 'HTTP API' }
}

function MethodBadge({ method }: { method: string }) {
  return <span className="rounded-md border border-border/80 bg-background px-2 py-1 font-mono text-[9px] font-semibold text-primary-light">{method}</span>
}

function PermissionButton({ active, children, onClick }: { active: boolean; children: string; onClick: () => void }) {
  return <Button type="button" size="sm" variant={active ? 'secondary' : 'outline'} onClick={onClick}>{children}</Button>
}

export function HttpProviderPanel({ tool, permissionOverrides, onPermissionOverridesChange }: HttpProviderPanelProps) {
  const [manageOpen, setManageOpen] = useState(false)
  const allRoutes = useMemo(() => routes(tool).filter((route) => route.status !== 'inactive'), [tool])
  const counts = permissionCounts(allRoutes, permissionOverrides)
  const canEditPermissions = Boolean(onPermissionOverridesChange)

  const updatePermission = (route: HttpRouteConfig, mode: McpToolPermissionMode) => {
    if (!onPermissionOverridesChange) return
    onPermissionOverridesChange({
      ...(permissionOverrides || {}),
      [route.id]: { mode, risk_level: route.risk_level },
    })
  }

  const updateAll = (mode: McpToolPermissionMode) => {
    if (!onPermissionOverridesChange) return
    const next = { ...(permissionOverrides || {}) }
    for (const route of allRoutes) next[route.id] = { mode, risk_level: route.risk_level }
    onPermissionOverridesChange(next)
  }

  if (!isHttpProviderTool(tool)) return null

  return (
    <div className="mt-3 space-y-3 rounded-xl border border-border/70 bg-background/55 p-3">
      <div className="flex items-start justify-between gap-3">
        <div className="flex min-w-0 items-start gap-2">
          <span className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary-light ring-1 ring-primary/20">
            <Globe2 className="h-3.5 w-3.5" />
          </span>
          <div className="min-w-0">
            <p className="truncate text-xs font-medium text-white">{providerHost(tool)}</p>
            <p className="mt-0.5 text-[10px] text-muted">{allRoutes.length} routes · {counts.allow} allowed · {counts.review} review</p>
          </div>
        </div>
        <span className={`rounded-full border px-2 py-0.5 text-[9px] font-medium ${counts.allow > 0 ? 'border-emerald-500/35 bg-emerald-500/10 text-emerald-300' : 'border-amber-500/35 bg-amber-500/10 text-amber-200'}`}>
          {counts.allow > 0 ? 'Ready' : 'Needs permission'}
        </span>
      </div>

      <Button type="button" size="sm" variant="outline" className="h-7 px-2 text-[11px]" onClick={() => setManageOpen(true)}>
        <Settings2 className="mr-1.5 h-3.5 w-3.5" />
        Manage routes
      </Button>

      <Dialog open={manageOpen} onClose={() => setManageOpen(false)} title={`Manage HTTP routes: ${tool.name}`} className="max-w-4xl">
        <div className="space-y-4">
          <div className="rounded-xl border border-border/80 bg-background/60 p-3">
            <p className="text-sm font-medium text-white">Routes available to this Agent</p>
            <p className="mt-1 text-xs leading-5 text-muted">The HTTP API remains one Tool. Each allowed route is exposed to the model as an independent function.</p>
            {canEditPermissions ? (
              <div className="mt-3 flex flex-wrap gap-2">
                <Button type="button" size="sm" onClick={() => updateAll('allow')}>Allow all</Button>
                <Button type="button" size="sm" variant="outline" onClick={() => updateAll('review')}>Review all</Button>
                <Button type="button" size="sm" variant="outline" onClick={() => updateAll('deny')}>Deny all</Button>
              </div>
            ) : null}
          </div>

          <div className="max-h-[55vh] space-y-2 overflow-y-auto pr-1">
            {allRoutes.map((route) => {
              const permission = permissionFor(route, permissionOverrides)
              return (
                <div key={route.id} className="grid gap-3 rounded-xl border border-border/70 bg-surface/60 p-3 lg:grid-cols-[minmax(0,1fr)_auto] lg:items-center">
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <MethodBadge method={route.method} />
                      <p className="text-sm font-medium text-white">{route.name}</p>
                      <span className="rounded-full border border-border bg-background px-2 py-0.5 text-[9px] text-muted">Risk · {route.risk_level || 'low'}</span>
                    </div>
                    <p className="mt-2 text-xs leading-5 text-muted">{route.description}</p>
                    <p className="mt-2 break-all font-mono text-[10px] text-muted">{route.path}</p>
                  </div>
                  <div className="flex flex-wrap gap-2 lg:justify-end">
                    {canEditPermissions ? (
                      <>
                        <PermissionButton active={permission.mode === 'allow'} onClick={() => updatePermission(route, 'allow')}>Allow</PermissionButton>
                        <PermissionButton active={permission.mode === 'review'} onClick={() => updatePermission(route, 'review')}>Review</PermissionButton>
                        <PermissionButton active={permission.mode === 'deny'} onClick={() => updatePermission(route, 'deny')}>Deny</PermissionButton>
                      </>
                    ) : <span className="rounded-full border border-border bg-background px-2 py-1 text-[10px] text-muted">{permission.mode}</span>}
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      </Dialog>
    </div>
  )
}
