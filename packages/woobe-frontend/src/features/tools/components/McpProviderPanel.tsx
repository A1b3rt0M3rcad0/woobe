import { useMemo, useState, type ReactNode } from 'react'
import { Settings2, Search } from 'lucide-react'
import { toast } from 'sonner'

import { Button } from '@/components/ui/Button'
import { Dialog } from '@/components/ui/Dialog'
import { Input } from '@/components/ui/Input'
import {
  invalidToolInputBindingTargets,
  toolInputBindingsForSchema,
  ToolInputBindingsEditor,
} from '@/features/tools/components/ToolInputBindingsEditor'
import {
  bulkUpdateMcpToolPermissions,
  disconnectMcpOAuth,
  refreshMcpTools,
  startMcpOAuth,
  updateMcpToolPermissions,
} from '@/features/tools/api'
import { useUpdateTool } from '@/features/tools/hooks'
import type {
  DiscoveredMcpTool,
  McpReadiness,
  McpToolConfig,
  McpToolPermission,
  McpToolPermissionMode,
  Tool,
  ToolInputBindings,
} from '@/features/tools/types'

const MCP_CONNECT_STATE_PREFIX = 'projectrai:mcp-connect:'
const MCP_REFRESHABLE_STATES = new Set(['needs_discovery', 'discovery_failed', 'no_tools', 'unavailable'])

export function isMcpProviderTool(tool: Tool): boolean {
  const config = (tool.config || {}) as Record<string, unknown>
  return String(tool.type).toLowerCase() === 'mcp' || config.protocol === 'mcp'
}

function mcpConfig(tool: Tool): McpToolConfig {
  return (tool.config || {}) as McpToolConfig
}

function discoveredTools(tool: Tool): DiscoveredMcpTool[] {
  const config = mcpConfig(tool)
  return Array.isArray(config.discovered_tools) ? config.discovered_tools : []
}

function providerHost(tool: Tool): string {
  try { return new URL(mcpConfig(tool).server?.url || '').hostname } catch { return 'MCP Server' }
}

function oauthConnected(tool: Tool): boolean {
  const oauth = mcpConfig(tool).oauth as { status?: string } | undefined
  return oauth?.status === 'connected'
}

function hasValidatedOAuth(tool: Tool): boolean {
  const config = mcpConfig(tool) as McpToolConfig & {
    mcp_oauth_discovery?: {
      status?: string | null
      authorization_endpoint?: string | null
      token_endpoint?: string | null
    }
    oauth?: {
      authorization_endpoint?: string | null
      token_endpoint?: string | null
    }
  }
  const oauth = config.oauth
  if (oauth?.authorization_endpoint && oauth?.token_endpoint) return true
  const discovery = config.mcp_oauth_discovery
  return discovery?.status === 'valid'
    && Boolean(discovery.authorization_endpoint)
    && Boolean(discovery.token_endpoint)
}

function shouldShowConnect(tool: Tool, state: McpReadiness, discovered: DiscoveredMcpTool[]): boolean {
  if (oauthConnected(tool)) return false
  if (discovered.length > 0 && !hasValidatedOAuth(tool)) return false
  return state.action === 'connect' && hasValidatedOAuth(tool)
}

function permissionMode(tool: DiscoveredMcpTool): McpToolPermissionMode {
  const mode = tool.permission?.mode
  return mode === 'allow' || mode === 'deny' || mode === 'review' ? mode : 'review'
}

function summary(tools: DiscoveredMcpTool[]) {
  return tools.reduce((acc, item) => {
    acc[permissionMode(item)] += 1
    return acc
  }, { allow: 0, deny: 0, review: 0 } as Record<McpToolPermissionMode, number>)
}

function fallbackReadiness(tool: Tool): McpReadiness {
  const discovered = discoveredTools(tool)
  const counts = summary(discovered)
  const connected = oauthConnected(tool)
  const config = mcpConfig(tool)
  const status = String(config.mcp_status || '')
  const ready = status === 'ready'
  const authRequired = hasValidatedOAuth(tool)

  const state = connected && ready && counts.allow > 0
    ? 'ready'
    : discovered.length > 0 && counts.allow > 0
      ? 'ready'
      : discovered.length > 0
        ? 'needs_permission'
        : status === 'provider_client_rejected'
          ? 'provider_not_supported'
          : status === 'provider_managed'
            ? 'provider_managed'
            : status === 'oauth_metadata_invalid' || (status === 'oauth_required' && !authRequired)
              ? 'oauth_metadata_invalid'
              : authRequired
                ? 'needs_connection'
                : status === 'needs_credentials' || status === 'unauthorized'
                  ? 'needs_credentials'
                  : status === 'scope_denied'
                    ? 'scope_denied'
                    : status === 'invalid_endpoint'
                      ? 'invalid_endpoint'
                      : status === 'unavailable'
                        ? 'unavailable'
                        : status === 'discovery_failed'
                          ? 'discovery_failed'
                          : status === 'empty' || status === 'no_tools'
                            ? 'no_tools'
                            : 'needs_discovery'

  const labels: Record<string, string> = {
    ready: 'Ready',
    needs_permission: 'Needs permission',
    needs_discovery: 'Load tools',
    needs_connection: 'Connect',
    provider_not_supported: 'Provider setup needed',
    provider_managed: 'Managed connection required',
    oauth_metadata_invalid: 'OAuth metadata invalid',
    needs_credentials: 'Credentials required',
    scope_denied: 'Permission denied',
    invalid_endpoint: 'Invalid endpoint',
    unavailable: 'Unavailable',
    discovery_failed: 'Discovery failed',
    no_tools: 'No tools',
  }
  const messages: Record<string, string> = {
    ready: `${counts.allow} tools available to this agent.`,
    needs_permission: 'Choose which MCP tools this agent can use.',
    needs_discovery: 'Load this MCP provider to see its tools.',
    needs_connection: 'This provider exposed a complete OAuth configuration. Connect before loading protected tools.',
    provider_not_supported: 'This provider needs a provider-issued client or alternate OAuth flow.',
    provider_managed: 'This endpoint requires a provider-managed MCP connection instead of direct OAuth discovery.',
    oauth_metadata_invalid: 'The server advertised OAuth, but Woobe could not validate authorization and token endpoints.',
    needs_credentials: 'Configure the required API key or connection headers.',
    scope_denied: 'The configured credential does not have permission to access this MCP server.',
    invalid_endpoint: 'The URL is not accepting MCP requests. Verify the endpoint path.',
    unavailable: 'The MCP server is temporarily unavailable.',
    discovery_failed: 'Woobe could not complete MCP discovery.',
    no_tools: 'The MCP server connected, but did not expose any tools.',
  }
  const actions: Record<string, string> = {
    needs_connection: 'connect',
    ready: 'manage_tools',
    needs_permission: 'manage_tools',
    provider_not_supported: 'provider_credentials',
    provider_managed: 'provider_credentials',
    oauth_metadata_invalid: 'review_provider',
    needs_credentials: 'configure_credentials',
    scope_denied: 'configure_credentials',
    invalid_endpoint: 'edit_endpoint',
    unavailable: 'refresh',
    discovery_failed: 'refresh',
    no_tools: 'refresh',
    needs_discovery: 'refresh',
  }

  return {
    state,
    label: labels[state] || 'Not ready',
    message: messages[state] || 'MCP tools are not available yet.',
    action: actions[state] || 'refresh',
    can_use_tools: state === 'ready',
    oauth_connected: connected,
    mcp_ready: ready || discovered.length > 0,
    discovered_count: discovered.length,
    exposed_count: counts.allow,
    supports_device_code: false,
    needs_provider_client: state === 'provider_not_supported' || state === 'provider_managed',
  }
}

function readiness(tool: Tool): McpReadiness {
  return mcpConfig(tool).mcp_readiness || fallbackReadiness(tool)
}

function statusTone(state: string): string {
  if (state === 'ready') return 'bg-emerald-300'
  if (state === 'needs_permission' || state === 'needs_connection') return 'bg-amber-300'
  if (state === 'needs_discovery' || state === 'no_tools') return 'bg-blue-300'
  return 'bg-red-300'
}

function PermissionControl({
  mode,
  busyKey,
  itemName,
  onChange,
}: {
  mode: McpToolPermissionMode
  busyKey: string | null
  itemName: string
  onChange: (mode: McpToolPermissionMode) => void
}) {
  return (
    <div className="inline-flex rounded-control border border-border/80 bg-background/60 p-ui-hairline">
      {(['allow', 'review', 'deny'] as McpToolPermissionMode[]).map((value) => (
        <button
          key={value}
          type="button"
          disabled={busyKey === `${itemName}:${value}`}
          onClick={() => onChange(value)}
          className={`rounded-technical px-ui-sm py-ui-xs font-mono text-system-micro font-medium transition-colors disabled:opacity-50 ${mode === value ? 'bg-accent text-white' : 'text-muted-foreground hover:text-white'}`}
        >
          {value === 'deny' ? 'Block' : value[0].toUpperCase() + value.slice(1)}
        </button>
      ))}
    </div>
  )
}

interface Props {
  footerActions?: ReactNode
  summaryNote?: ReactNode
  tool: Tool
  onChanged?: () => void | Promise<void>
  allowBindingEdit?: boolean
  permissionOverrides?: Record<string, McpToolPermission>
  onPermissionOverridesChange?: (permissions: Record<string, McpToolPermission>) => void
}

export function McpProviderPanel({ tool, footerActions, summaryNote, onChanged, allowBindingEdit = false, permissionOverrides, onPermissionOverridesChange }: Props) {
  const updateTool = useUpdateTool()
  const [manageOpen, setManageOpen] = useState(false)
  const [bindingToolName, setBindingToolName] = useState<string | null>(null)
  const [bindingDraft, setBindingDraft] = useState<ToolInputBindings>({})
  const [busyKey, setBusyKey] = useState<string | null>(null)
  const [query, setQuery] = useState('')
  const draftPermissionMode = permissionOverrides !== undefined && Boolean(onPermissionOverridesChange)
  const baseDiscovered = discoveredTools(tool)
  const discovered = draftPermissionMode
    ? baseDiscovered.map((item) => ({
        ...item,
        permission: permissionOverrides?.[item.name] ?? { mode: 'review', risk_level: 'unknown' },
      }))
    : baseDiscovered
  const effectiveTool = draftPermissionMode
    ? { ...tool, config: { ...mcpConfig(tool), discovered_tools: discovered } }
    : tool
  const counts = summary(discovered)
  const state = draftPermissionMode ? fallbackReadiness(effectiveTool) : readiness(tool)
  const showConnect = shouldShowConnect(tool, state, discovered)
  const showLoadTools = !showConnect && discovered.length === 0 && MCP_REFRESHABLE_STATES.has(state.state)
  const visibleLabel = showConnect ? state.label : discovered.length > 0 ? (counts.allow > 0 ? 'Ready' : 'Needs permission') : state.label
  const visibleState = discovered.length > 0 && counts.allow > 0 ? 'ready' : state.state
  const filtered = useMemo(() => {
    const normalized = query.trim().toLowerCase()
    if (!normalized) return discovered
    return discovered.filter((item) => [item.name, item.title, item.description].some((value) => String(value || '').toLowerCase().includes(normalized)))
  }, [discovered, query])
  const bindingTool = bindingToolName ? baseDiscovered.find((item) => item.name === bindingToolName) ?? null : null

  const handleConnect = async () => {
    try {
      setBusyKey('connect')
      const redirectUri = `${window.location.origin}/mcp/oauth/callback`
      const result = await startMcpOAuth({ tool_id: tool.id, redirect_uri: redirectUri })
      window.localStorage.setItem(`${MCP_CONNECT_STATE_PREFIX}${result.state}`, JSON.stringify({ toolId: tool.id, returnTo: window.location.pathname }))
      window.location.assign(result.authorization_url)
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'This provider needs setup before it can connect.')
      setBusyKey(null)
    }
  }

  const handleRefresh = async () => {
    try {
      setBusyKey('refresh')
      await refreshMcpTools({ tool_id: tool.id })
      await onChanged?.()
      toast.success('MCP tools updated')
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to load MCP tools')
    } finally {
      setBusyKey(null)
    }
  }

  const openBindings = (item: DiscoveredMcpTool) => {
    setBindingToolName(item.name)
    setBindingDraft(item.bindings || {})
  }

  const closeBindings = () => {
    setBindingToolName(null)
    setBindingDraft({})
  }

  const saveBindings = async () => {
    if (!bindingTool) return
    const invalid = invalidToolInputBindingTargets(bindingDraft)
    if (invalid.length) {
      toast.error(`Configure the External Context field for: ${invalid.join(', ')}`)
      return
    }
    try {
      setBusyKey(`bindings:${bindingTool.name}`)
      const config = mcpConfig(tool)
      const nextDiscovered = (config.discovered_tools || []).map((item) => (
        item.name === bindingTool.name
          ? { ...item, bindings: toolInputBindingsForSchema(bindingTool.input_schema || undefined, bindingDraft) }
          : item
      ))
      await updateTool.mutateAsync({
        toolId: tool.id,
        data: {
          config: {
            ...config,
            discovered_tools: nextDiscovered,
          },
        },
      })
      await onChanged?.()
      toast.success(`Input bindings updated for ${bindingTool.title || bindingTool.name}`)
      closeBindings()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to update MCP input bindings')
    } finally {
      setBusyKey(null)
    }
  }

  const handleDisconnect = async () => {
    try {
      setBusyKey('disconnect')
      await disconnectMcpOAuth({ tool_id: tool.id })
      await onChanged?.()
      toast.success('MCP disconnected')
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to disconnect MCP')
    } finally {
      setBusyKey(null)
    }
  }

  const handleBulk = async (mode: McpToolPermissionMode) => {
    if (draftPermissionMode && onPermissionOverridesChange) {
      const next = Object.fromEntries(
        discovered.map((item) => [item.name, mode === 'review' ? { mode, risk_level: 'unknown' } : { mode }]),
      ) as Record<string, McpToolPermission>
      onPermissionOverridesChange(next)
      toast.success(`Draft MCP tools set to ${mode}`)
      return
    }

    try {
      setBusyKey(`bulk:${mode}`)
      await bulkUpdateMcpToolPermissions({ tool_id: tool.id, mode })
      await onChanged?.()
      toast.success(`MCP tools set to ${mode}`)
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to update MCP tools')
    } finally {
      setBusyKey(null)
    }
  }

  const handleSingle = async (remoteToolName: string, mode: McpToolPermissionMode) => {
    if (draftPermissionMode && onPermissionOverridesChange) {
      onPermissionOverridesChange({
        ...(permissionOverrides || {}),
        [remoteToolName]: mode === 'review' ? { mode, risk_level: 'unknown' } : { mode },
      })
      return
    }

    try {
      setBusyKey(`${remoteToolName}:${mode}`)
      await updateMcpToolPermissions({ tool_id: tool.id, permissions: [{ remote_tool_name: remoteToolName, mode }] })
      await onChanged?.()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to update tool permission')
    } finally {
      setBusyKey(null)
    }
  }

  if (!isMcpProviderTool(tool)) return null

  const handleSummaryClick = () => {
    if (discovered.length > 0) setManageOpen(true)
    else if (showConnect) void handleConnect()
    else if (showLoadTools) void handleRefresh()
  }

  const actionable = discovered.length > 0 || showConnect || showLoadTools
  const diagnostic = !['ready', 'needs_permission', 'needs_discovery', 'no_tools'].includes(visibleState)

  return (
    <div className="mt-ui-sm">
      <div className={footerActions ? 'min-w-0 pl-ui-xl' : 'min-w-0'}>
        <p title={providerHost(tool)} className="truncate font-mono text-system-micro text-muted-foreground">{providerHost(tool)}</p>
        <p className="mt-ui-sm font-mono text-system-micro text-muted-foreground">MCP · {state.discovered_count} tools · {state.exposed_count} allowed</p>
        <p className="mt-ui-sm flex items-center gap-ui-xs font-mono text-system-micro text-muted-foreground"><span className={`h-1.5 w-1.5 shrink-0 rounded-full ${statusTone(visibleState)}`} />{visibleLabel}</p>
      </div>
      {summaryNote}
      <div className="mt-ui-md grid grid-cols-2 gap-ui-sm border-t border-border/75 pt-ui-md">
        <Button size="sm" variant="outline" disabled={!actionable || busyKey !== null} onClick={handleSummaryClick}><Settings2 className="h-icon-sm w-icon-sm" />{discovered.length > 0 ? 'Configure' : showConnect ? 'Connect' : 'Load tools'}</Button>
        {footerActions}
      </div>

      {diagnostic ? <p className="mt-ui-xs line-clamp-2 px-ui-xs font-mono text-system-meta leading-4 text-amber-200">{state.message}</p> : null}
      {state.oauth_connected ? (
        <button type="button" onClick={() => void handleDisconnect()} className="mt-ui-xs px-ui-xs font-mono text-system-micro text-muted-foreground hover:text-white">Disconnect</button>
      ) : null}

      <Dialog open={manageOpen} onClose={() => setManageOpen(false)} title={`Manage MCP tools: ${tool.name}`} className="max-w-3xl" scrollMode="content">
        <div className="space-y-4">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <p className="text-sm font-medium text-white">{counts.allow} allowed · {counts.review} review · {counts.deny} blocked</p>
              <p className="mt-1 text-xs text-muted">Each allowed MCP tool is exposed independently to this Agent.</p>
            </div>
            <div className="flex flex-wrap gap-2">
              <Button size="sm" onClick={() => handleBulk('allow')} loading={busyKey === 'bulk:allow'}>Allow all</Button>
              <Button size="sm" variant="outline" onClick={() => handleBulk('review')} loading={busyKey === 'bulk:review'}>Review all</Button>
              <Button size="sm" variant="outline" onClick={() => handleBulk('deny')} loading={busyKey === 'bulk:deny'}>Block all</Button>
              <Button size="sm" variant="ghost" onClick={handleRefresh} loading={busyKey === 'refresh'}>Refresh</Button>
            </div>
          </div>

          {discovered.length > 10 ? (
            <div className="relative">
              <Search className="pointer-events-none absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted" />
              <Input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search tools" className="pl-9" />
            </div>
          ) : null}

          {filtered.length > 0 ? (
            <div className="divide-y divide-border/70 border-y border-border/70">
              {filtered.map((item) => {
                const mode = permissionMode(item)
                return (
                  <div key={item.name} className="grid gap-3 py-3 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-center">
                    <div className="min-w-0">
                      <p className="truncate text-xs font-medium text-white">{item.title || item.name}</p>
                      <p className="mt-0.5 truncate font-mono text-[10px] text-muted">{item.name}</p>
                      {item.description ? <p className="mt-1 line-clamp-2 text-[10px] leading-4 text-muted">{item.description}</p> : null}
                      {Object.keys(item.bindings || {}).length ? (
                        <p className="mt-1 font-mono text-[9px] text-primary-light">
                          {Object.keys(item.bindings || {}).length} context binding{Object.keys(item.bindings || {}).length === 1 ? '' : 's'}
                        </p>
                      ) : null}
                    </div>
                    <div className="flex flex-wrap items-center justify-end gap-2">
                      {allowBindingEdit && item.input_schema ? (
                        <Button type="button" size="sm" variant="outline" onClick={() => openBindings(item)}>
                          Inputs
                        </Button>
                      ) : null}
                      <PermissionControl mode={mode} busyKey={busyKey} itemName={item.name} onChange={(next) => handleSingle(item.name, next)} />
                    </div>
                  </div>
                )
              })}
            </div>
          ) : (
            <div className="py-8 text-center text-xs text-muted">
              {discovered.length > 0 ? 'No tools match this search.' : 'No MCP tools have been loaded yet.'}
            </div>
          )}

          <div className="flex justify-end border-t border-border pt-3">
            <Button variant="outline" onClick={() => setManageOpen(false)}>Done</Button>
          </div>
        </div>
      </Dialog>

      <Dialog
        open={Boolean(bindingTool)}
        onClose={closeBindings}
        title={bindingTool ? `Input bindings: ${bindingTool.title || bindingTool.name}` : 'Input bindings'}
        className="max-w-3xl"
        scrollMode="content"
      >
        {bindingTool ? (
          <div className="space-y-4">
            <div>
              <p className="text-sm font-medium text-white">Input sources</p>
              <p className="mt-1 text-xs text-muted">
                Agent inputs remain model-provided. External Context inputs are injected from the immutable Run snapshot.
              </p>
            </div>
            <ToolInputBindingsEditor
              schema={bindingTool.input_schema || undefined}
              bindings={bindingDraft}
              disabled={busyKey === `bindings:${bindingTool.name}`}
              onChange={setBindingDraft}
            />
            <div className="flex justify-end gap-2 border-t border-border pt-3">
              <Button type="button" variant="outline" onClick={closeBindings}>Cancel</Button>
              <Button type="button" loading={busyKey === `bindings:${bindingTool.name}`} onClick={() => void saveBindings()}>
                Save bindings
              </Button>
            </div>
          </div>
        ) : null}
      </Dialog>
    </div>
  )
}
