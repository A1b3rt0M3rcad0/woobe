import { useState } from 'react'
import { Button } from '@/components/ui/Button'
import { StatusBadge } from '@/components/common/StatusBadge'
import { bulkUpdateMcpToolPermissions, disconnectMcpOAuth, startMcpOAuth, updateMcpToolPermissions } from '@/features/tools/api'
import type { DiscoveredMcpTool, McpToolConfig, McpToolPermissionMode, Tool } from '@/features/tools/types'
import { AlertTriangle, PlugZap } from 'lucide-react'
import { toast } from 'sonner'

const MCP_CONNECT_STATE_PREFIX = 'projectrai:mcp-connect:'

export function isMcpProviderTool(tool: Tool): boolean {
  const config = (tool.config || {}) as Record<string, unknown>
  return String(tool.type).toLowerCase().includes('mcp') || config.protocol === 'mcp'
}

function mcpConfig(tool: Tool): McpToolConfig {
  return (tool.config || {}) as McpToolConfig
}

function discoveredTools(tool: Tool): DiscoveredMcpTool[] {
  const config = mcpConfig(tool)
  return Array.isArray(config.discovered_tools) ? config.discovered_tools : []
}

function status(tool: Tool): string {
  const oauth = mcpConfig(tool).oauth as { status?: string } | undefined
  return oauth?.status || 'disconnected'
}

function errorText(tool: Tool): string | null {
  const config = (tool.config || {}) as Record<string, unknown>
  return typeof config.oauth_discovery_error === 'string' ? config.oauth_discovery_error : null
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

interface Props {
  tool: Tool
  onChanged?: () => void | Promise<void>
}

export function McpProviderPanel({ tool, onChanged }: Props) {
  const [open, setOpen] = useState(false)
  const [busyKey, setBusyKey] = useState<string | null>(null)
  const discovered = discoveredTools(tool)
  const counts = summary(discovered)
  const connected = status(tool) === 'connected'
  const visibleError = errorText(tool)

  const handleConnect = async () => {
    try {
      setBusyKey('connect')
      const redirectUri = `${window.location.origin}/mcp/oauth/callback`
      const result = await startMcpOAuth({ tool_id: tool.id, redirect_uri: redirectUri })
      window.localStorage.setItem(
        `${MCP_CONNECT_STATE_PREFIX}${result.state}`,
        JSON.stringify({ toolId: tool.id, returnTo: `${window.location.pathname}?configure_mcp_permissions=${tool.id}` }),
      )
      window.location.assign(result.authorization_url)
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to start MCP connection')
      setBusyKey(null)
    }
  }

  const handleDisconnect = async () => {
    try {
      setBusyKey('disconnect')
      await disconnectMcpOAuth({ tool_id: tool.id })
      toast.success('MCP disconnected')
      await onChanged?.()
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
      toast.success(`MCP tools set to ${mode}`)
      await onChanged?.()
      setOpen(true)
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to update MCP permissions')
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
      toast.error(err instanceof Error ? err.message : 'Failed to update MCP permission')
    } finally {
      setBusyKey(null)
    }
  }

  if (!isMcpProviderTool(tool)) return null

  return (
    <div className="rounded-lg border border-border/70 bg-background/70 p-2 space-y-3">
      <div className="flex items-center justify-between gap-2">
        <div className="flex min-w-0 items-center gap-2">
          <PlugZap className="h-4 w-4 shrink-0 text-primary-light" />
          <div className="min-w-0">
            <p className="text-xs font-medium text-white">MCP tools</p>
            <p className="truncate text-[10px] text-muted">{counts.allow} exposed to agent · {discovered.length} discovered</p>
          </div>
        </div>
        <StatusBadge status={connected ? 'connected' : status(tool)} />
      </div>

      <div className="flex flex-wrap gap-2">
        <Button size="sm" onClick={handleConnect} loading={busyKey === 'connect'}>{connected ? 'Reconnect / rediscover' : 'Connect'}</Button>
        {connected ? <Button size="sm" variant="outline" onClick={handleDisconnect} loading={busyKey === 'disconnect'}>Disconnect</Button> : null}
      </div>

      {connected && discovered.length === 0 ? (
        <div className="flex gap-2 rounded-md border border-amber-500/30 bg-amber-500/10 p-2 text-xs text-amber-200">
          <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
          <span>Connected provider, but no remote MCP tools are visible to the agent. Use Reconnect / rediscover to request a new token and run authenticated discovery again.</span>
        </div>
      ) : null}

      {discovered.length > 0 && counts.allow === 0 ? (
        <div className="flex gap-2 rounded-md border border-amber-500/30 bg-amber-500/10 p-2 text-xs text-amber-200">
          <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
          <span>Remote MCP tools were discovered, but none are allowed yet.</span>
        </div>
      ) : null}

      {visibleError ? <div className="rounded-md border border-red-500/30 bg-red-500/10 p-2 text-xs text-red-200">Discovery error: {visibleError}</div> : null}

      {discovered.length > 0 ? (
        <div className="space-y-3">
          <div className="flex flex-wrap items-center gap-2 text-xs text-muted">
            <span>{counts.allow} allow</span>
            <span>{counts.review} review</span>
            <span>{counts.deny} deny</span>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button size="sm" onClick={() => handleBulk('allow')} loading={busyKey === 'bulk:allow'}>Allow all</Button>
            <Button size="sm" variant="outline" onClick={() => handleBulk('review')} loading={busyKey === 'bulk:review'}>Review all</Button>
            <Button size="sm" variant="outline" onClick={() => handleBulk('deny')} loading={busyKey === 'bulk:deny'}>Deny all</Button>
            <Button size="sm" variant="ghost" onClick={() => setOpen(value => !value)}>{open ? 'Hide' : 'Show'} tools</Button>
          </div>
          {open ? (
            <div className="max-h-72 space-y-2 overflow-y-auto pr-1">
              {discovered.map(item => {
                const mode = permissionMode(item)
                return (
                  <div key={item.name} className="rounded-lg border border-border/70 bg-card/40 p-2">
                    <div className="mb-2 flex items-start justify-between gap-2">
                      <div className="min-w-0">
                        <p className="break-words text-xs font-medium text-white">{item.title || item.name}</p>
                        <p className="break-all font-mono text-[10px] text-muted">{item.name}</p>
                        {item.description ? <p className="mt-1 text-[10px] text-muted">{item.description}</p> : null}
                      </div>
                      <span className="rounded-full border border-border px-2 py-0.5 text-[10px] uppercase text-muted">{mode}</span>
                    </div>
                    <div className="flex flex-wrap gap-2">
                      <Button size="sm" variant={mode === 'allow' ? 'default' : 'outline'} onClick={() => handleSingle(item.name, 'allow')} loading={busyKey === `${item.name}:allow`}>Allow</Button>
                      <Button size="sm" variant={mode === 'review' ? 'secondary' : 'ghost'} onClick={() => handleSingle(item.name, 'review')} loading={busyKey === `${item.name}:review`}>Review</Button>
                      <Button size="sm" variant={mode === 'deny' ? 'destructive' : 'outline'} onClick={() => handleSingle(item.name, 'deny')} loading={busyKey === `${item.name}:deny`}>Deny</Button>
                    </div>
                  </div>
                )
              })}
            </div>
          ) : null}
        </div>
      ) : null}
    </div>
  )
}
