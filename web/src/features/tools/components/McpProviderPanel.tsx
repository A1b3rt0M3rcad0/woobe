import { useState } from 'react'
import { Button } from '@/components/ui/Button'
import { Dialog } from '@/components/ui/Dialog'
import { bulkUpdateMcpToolPermissions, disconnectMcpOAuth, refreshMcpTools, startMcpOAuth, updateMcpToolPermissions } from '@/features/tools/api'
import type { DiscoveredMcpTool, McpReadiness, McpToolConfig, McpToolPermissionMode, Tool } from '@/features/tools/types'
import { PlugZap, Settings2 } from 'lucide-react'
import { toast } from 'sonner'

const MCP_CONNECT_STATE_PREFIX = 'projectrai:mcp-connect:'
const MCP_AUTH_REQUIRED_STATES = new Set(['needs_connection', 'oauth_required', 'metadata_required'])
const MCP_TOKEN_REJECTED_STATES = new Set(['token_invalid', 'token_rejected'])

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

function oauthConnected(tool: Tool): boolean {
  const oauth = mcpConfig(tool).oauth as { status?: string } | undefined
  return oauth?.status === 'connected'
}

function hasAuthChallenge(tool: Tool): boolean {
  const config = mcpConfig(tool) as McpToolConfig & {
    mcp_discovery?: { http_status?: number; www_authenticate?: string | null; status?: string | null }
    mcp_resource_metadata?: { resource?: string; authorization_servers?: unknown[] }
  }
  const diagnostic = config.mcp_discovery
  const status = String(config.mcp_status || diagnostic?.status || '')
  return MCP_AUTH_REQUIRED_STATES.has(status)
    || MCP_TOKEN_REJECTED_STATES.has(status)
    || diagnostic?.http_status === 401
    || Boolean(diagnostic?.www_authenticate)
    || Boolean(config.mcp_resource_metadata?.resource || config.mcp_resource_metadata?.authorization_servers?.length)
}

function shouldShowConnect(tool: Tool, state: McpReadiness, discovered: DiscoveredMcpTool[]): boolean {
  if (oauthConnected(tool)) return false
  if (discovered.length > 0 && !hasAuthChallenge(tool)) return false
  return state.action === 'connect' && hasAuthChallenge(tool)
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
  const authRequired = hasAuthChallenge(tool)

  const state = connected && ready && counts.allow > 0
    ? 'ready'
    : discovered.length > 0 && counts.allow > 0
      ? 'ready'
      : discovered.length > 0
        ? 'needs_permission'
        : authRequired
          ? 'needs_connection'
          : status === 'provider_client_rejected'
            ? 'provider_not_supported'
            : 'needs_discovery'

  return {
    state,
    label: state === 'ready' ? 'Ready' : state === 'needs_permission' ? 'Needs permission' : state === 'needs_discovery' ? 'Load tools' : state === 'needs_connection' ? 'Connect' : state === 'provider_not_supported' ? 'Provider setup needed' : 'Not ready',
    message: state === 'ready' ? `${counts.allow} tools available to this agent.` : state === 'needs_permission' ? 'Choose which MCP tools this agent can use.' : state === 'needs_discovery' ? 'Load this MCP provider to see its tools.' : state === 'needs_connection' ? 'Connect this provider to load protected MCP tools.' : state === 'provider_not_supported' ? 'This provider needs a provider-issued client or alternate OAuth flow.' : 'MCP tools are not available yet.',
    action: state === 'needs_connection' ? 'connect' : state === 'needs_permission' || state === 'ready' ? 'manage_tools' : state === 'provider_not_supported' ? 'provider_credentials' : 'refresh',
    can_use_tools: state === 'ready',
    oauth_connected: connected,
    mcp_ready: ready || discovered.length > 0,
    discovered_count: discovered.length,
    exposed_count: counts.allow,
    supports_device_code: false,
    needs_provider_client: state === 'provider_not_supported',
  }
}

function readiness(tool: Tool): McpReadiness {
  return mcpConfig(tool).mcp_readiness || fallbackReadiness(tool)
}

function ReadinessPill({ state, label }: { state: string; label: string }) {
  const tone = state === 'ready'
    ? 'border-emerald-500/40 bg-emerald-500/10 text-emerald-300'
    : state === 'provider_not_supported' || state === 'token_rejected'
      ? 'border-amber-500/30 bg-amber-500/10 text-amber-200'
      : state === 'needs_permission'
        ? 'border-blue-500/30 bg-blue-500/10 text-blue-300'
        : 'border-border bg-surface/70 text-muted'

  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-medium ${tone}`}>
      {state === 'ready' ? <span className="h-1.5 w-1.5 rounded-full bg-emerald-300" /> : null}
      {label}
    </span>
  )
}

interface Props {
  tool: Tool
  onChanged?: () => void | Promise<void>
}

export function McpProviderPanel({ tool, onChanged }: Props) {
  const [manageOpen, setManageOpen] = useState(false)
  const [busyKey, setBusyKey] = useState<string | null>(null)
  const discovered = discoveredTools(tool)
  const counts = summary(discovered)
  const state = readiness(tool)
  const showConnect = shouldShowConnect(tool, state, discovered)
  const showLoadTools = !showConnect && discovered.length === 0 && state.state !== 'provider_not_supported'
  const visibleLabel = showConnect ? state.label : discovered.length > 0 ? (counts.allow > 0 ? 'Ready' : 'Needs permission') : state.label
  const visibleState = discovered.length > 0 && counts.allow > 0 ? 'ready' : state.state

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

  return (
    <div className="space-y-4 rounded-2xl border border-border/70 bg-background/55 p-4">
      <div className="flex items-start justify-between gap-3">
        <div className="flex min-w-0 items-start gap-3">
          <div className="mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-primary/10 text-primary-light ring-1 ring-primary/20">
            <PlugZap className="h-4 w-4" />
          </div>
          <div className="min-w-0">
            <p className="font-semibold text-white">MCP tools</p>
            <p className="text-xs text-muted">{state.exposed_count} available · {state.discovered_count} found</p>
          </div>
        </div>
        <ReadinessPill state={visibleState} label={visibleLabel} />
      </div>

      <p className="text-sm leading-relaxed text-muted">
        {showConnect ? state.message : discovered.length > 0 ? 'Choose which MCP tools this agent can use.' : state.message}
      </p>

      <div className="flex flex-wrap gap-2">
        {showConnect ? <Button size="sm" onClick={handleConnect} loading={busyKey === 'connect'}>Connect</Button> : null}
        {showLoadTools ? <Button size="sm" onClick={handleRefresh} loading={busyKey === 'refresh'}>{state.oauth_connected ? 'Refresh' : 'Load tools'}</Button> : null}
        {state.state === 'provider_not_supported' ? <Button size="sm" variant="outline" disabled>Provider setup needed</Button> : null}
        {discovered.length > 0 ? (
          <Button size="sm" variant="outline" onClick={() => setManageOpen(true)}>
            <Settings2 className="mr-2 h-4 w-4" />
            Manage tools
          </Button>
        ) : null}
        {state.oauth_connected && state.action !== 'refresh' && !state.can_use_tools ? <Button size="sm" variant="ghost" onClick={handleRefresh} loading={busyKey === 'refresh'}>Refresh</Button> : null}
        {state.oauth_connected ? <Button size="sm" variant="ghost" onClick={handleDisconnect} loading={busyKey === 'disconnect'}>Disconnect</Button> : null}
      </div>

      {state.state === 'provider_not_supported' ? <p className="rounded-md border border-amber-500/30 bg-amber-500/10 p-2 text-xs text-amber-200">This provider does not accept the normal ProjectRAI connection. Use a provider-issued client or device-code flow.</p> : null}

      <Dialog open={manageOpen} onClose={() => setManageOpen(false)} title={`Manage MCP tools: ${tool.name}`}>
        <div className="space-y-4">
          <div className="rounded-md border border-border/70 bg-background/70 p-3">
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="text-xs font-medium text-white">Discovered tools</p>
                <p className="mt-1 text-xs text-muted">Choose which remote MCP tools this agent may use.</p>
              </div>
              <ReadinessPill state={counts.allow > 0 ? 'ready' : 'needs_permission'} label={counts.allow > 0 ? 'Ready' : 'Needs permission'} />
            </div>
            <div className="mt-3 flex flex-wrap items-center gap-2 text-xs text-muted">
              <span>{counts.allow} allowed</span>
              <span>{counts.review} review</span>
              <span>{counts.deny} blocked</span>
            </div>
          </div>

          <div className="flex flex-wrap gap-2">
            <Button size="sm" onClick={() => handleBulk('allow')} loading={busyKey === 'bulk:allow'}>Allow all</Button>
            <Button size="sm" variant="outline" onClick={() => handleBulk('review')} loading={busyKey === 'bulk:review'}>Review all</Button>
            <Button size="sm" variant="outline" onClick={() => handleBulk('deny')} loading={busyKey === 'bulk:deny'}>Block all</Button>
            <Button size="sm" variant="ghost" onClick={handleRefresh} loading={busyKey === 'refresh'}>Refresh tools</Button>
          </div>

          {discovered.length > 0 ? (
            <div className="max-h-[460px] space-y-2 overflow-y-auto pr-1">
              {discovered.map(item => {
                const mode = permissionMode(item)
                return (
                  <div key={item.name} className="rounded-md border border-border/70 bg-background/70 p-3">
                    <div className="mb-3 flex items-start justify-between gap-2">
                      <div className="min-w-0">
                        <p className="break-words text-xs font-medium text-white">{item.title || item.name}</p>
                        <p className="mt-0.5 break-all font-mono text-[10px] text-muted">{item.name}</p>
                        {item.description ? <p className="mt-1 line-clamp-2 text-[10px] text-muted">{item.description}</p> : null}
                      </div>
                      <span className="rounded-full border border-border px-2 py-0.5 text-[10px] text-muted">{mode}</span>
                    </div>
                    <div className="flex flex-wrap gap-2">
                      <Button size="sm" variant={mode === 'allow' ? 'default' : 'outline'} onClick={() => handleSingle(item.name, 'allow')} loading={busyKey === `${item.name}:allow`}>Allow</Button>
                      <Button size="sm" variant={mode === 'review' ? 'secondary' : 'ghost'} onClick={() => handleSingle(item.name, 'review')} loading={busyKey === `${item.name}:review`}>Review</Button>
                      <Button size="sm" variant={mode === 'deny' ? 'destructive' : 'ghost'} onClick={() => handleSingle(item.name, 'deny')} loading={busyKey === `${item.name}:deny`}>Block</Button>
                    </div>
                  </div>
                )
              })}
            </div>
          ) : (
            <div className="rounded-md border border-border/70 bg-background/70 p-4 text-xs text-muted">
              No MCP tools have been loaded yet. Refresh tools or connect the provider if OAuth is required.
            </div>
          )}

          <div className="flex justify-end gap-2 border-t border-border pt-3">
            <Button variant="outline" onClick={() => setManageOpen(false)}>Done</Button>
          </div>
        </div>
      </Dialog>
    </div>
  )
}
