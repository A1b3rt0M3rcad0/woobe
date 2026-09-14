import { useMemo, useState, type ReactNode } from 'react'
import { Settings2, Search } from 'lucide-react'

import { Button } from '@/components/ui/Button'
import { Dialog } from '@/components/ui/Dialog'
import { Input } from '@/components/ui/Input'
import { isHttpToolGroup } from '@/features/tools/httpToolContract'
import type {
  HttpRouteConfig,
  HttpToolConfig,
  McpToolPermission,
  McpToolPermissionMode,
  Tool,
} from '@/features/tools/types'

interface HttpProviderPanelProps {
  footerActions?: ReactNode
  summaryNote?: ReactNode
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
    || (route.operation_id ? overrides?.[route.operation_id] : undefined)
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

function PermissionControl({
  mode,
  onChange,
}: {
  mode: McpToolPermissionMode
  onChange?: (mode: McpToolPermissionMode) => void
}) {
  if (!onChange) {
    return <span className="rounded-control border border-border/80 bg-background px-ui-sm py-ui-xs font-mono text-system-micro capitalize text-muted-foreground">{mode}</span>
  }
  return (
    <div className="inline-flex rounded-control border border-border/80 bg-background/60 p-ui-hairline">
      {(['allow', 'review', 'deny'] as McpToolPermissionMode[]).map((value) => (
        <button
          key={value}
          type="button"
          onClick={() => onChange(value)}
          className={`rounded-technical px-ui-sm py-ui-xs font-mono text-system-micro font-medium transition-colors ${mode === value ? 'bg-accent text-white' : 'text-muted-foreground hover:text-white'}`}
        >
          {value === 'deny' ? 'Block' : value[0].toUpperCase() + value.slice(1)}
        </button>
      ))}
    </div>
  )
}

export function HttpProviderPanel({ tool, footerActions, summaryNote, permissionOverrides, onPermissionOverridesChange }: HttpProviderPanelProps) {
  const [manageOpen, setManageOpen] = useState(false)
  const [query, setQuery] = useState('')
  const allRoutes = useMemo(() => routes(tool).filter((route) => route.status !== 'inactive'), [tool])
  const counts = permissionCounts(allRoutes, permissionOverrides)
  const canEditPermissions = Boolean(onPermissionOverridesChange)
  const filtered = useMemo(() => {
    const normalized = query.trim().toLowerCase()
    if (!normalized) return allRoutes
    return allRoutes.filter((route) => [route.name, route.description, route.path, route.operation_id]
      .some((value) => String(value || '').toLowerCase().includes(normalized)))
  }, [allRoutes, query])

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

  const ready = counts.allow > 0

  return (
    <div className="mt-ui-sm">
      <div className={footerActions ? 'min-w-0 pl-ui-xl' : 'min-w-0'}>
        <p title={providerHost(tool)} className="truncate font-mono text-system-micro text-muted-foreground">{providerHost(tool)}</p>
        <p className="mt-ui-sm font-mono text-system-micro text-muted-foreground">HTTP · {allRoutes.length} routes · {counts.allow} allowed</p>
        <p className="mt-ui-sm flex items-center gap-ui-xs font-mono text-system-micro text-muted-foreground"><span className={`h-1.5 w-1.5 shrink-0 rounded-full ${ready ? 'bg-emerald-300' : 'bg-amber-300'}`} />{ready ? 'Ready' : 'Needs permission'}</p>
      </div>
      {summaryNote}
      <div className="mt-ui-md grid grid-cols-2 gap-ui-sm border-t border-border/75 pt-ui-md">
        <Button size="sm" variant="outline" onClick={() => setManageOpen(true)}><Settings2 className="h-icon-sm w-icon-sm" />Configure</Button>
        {footerActions}
      </div>

      <Dialog open={manageOpen} onClose={() => setManageOpen(false)} title={`Manage HTTP routes: ${tool.name}`} className="max-w-3xl" scrollMode="content">
        <div className="space-y-4">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <p className="text-sm font-medium text-white">{counts.allow} allowed · {counts.review} review · {counts.deny} blocked</p>
              <p className="mt-1 text-xs text-muted">Each allowed route is exposed independently to this Agent.</p>
            </div>
            {canEditPermissions ? (
              <div className="flex flex-wrap gap-2">
                <Button type="button" size="sm" onClick={() => updateAll('allow')}>Allow all</Button>
                <Button type="button" size="sm" variant="outline" onClick={() => updateAll('review')}>Review all</Button>
                <Button type="button" size="sm" variant="outline" onClick={() => updateAll('deny')}>Block all</Button>
              </div>
            ) : null}
          </div>

          {allRoutes.length > 10 ? (
            <div className="relative">
              <Search className="pointer-events-none absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted" />
              <Input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search routes" className="pl-9" />
            </div>
          ) : null}

          <div className="divide-y divide-border/70 border-y border-border/70">
            {filtered.map((route) => {
              const permission = permissionFor(route, permissionOverrides)
              const showRisk = route.risk_level && route.risk_level !== 'low'
              return (
                <div key={route.id} className="grid gap-3 py-3 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-center">
                  <div className="min-w-0">
                    <div className="flex min-w-0 items-center gap-2">
                      <span className="shrink-0 rounded-md border border-border/80 bg-background px-2 py-1 font-mono text-[9px] font-semibold text-primary-light">{route.method}</span>
                      <p className="truncate text-xs font-medium text-white">{route.name}</p>
                      {showRisk ? <span className="shrink-0 text-[9px] capitalize text-amber-200">{route.risk_level} risk</span> : null}
                    </div>
                    <p className="mt-1 truncate font-mono text-[10px] text-muted">{route.path}</p>
                    <p className="mt-1 line-clamp-2 text-[10px] leading-4 text-muted">{route.description}</p>
                  </div>
                  <PermissionControl
                    mode={permission.mode}
                    onChange={canEditPermissions ? (mode) => updatePermission(route, mode) : undefined}
                  />
                </div>
              )
            })}
          </div>

          {filtered.length === 0 ? <div className="py-8 text-center text-xs text-muted">No routes match this search.</div> : null}

          <div className="flex justify-end border-t border-border pt-3">
            <Button variant="outline" onClick={() => setManageOpen(false)}>Done</Button>
          </div>
        </div>
      </Dialog>
    </div>
  )
}
