import { useEffect, useState } from 'react'
import { useParams, useSearchParams } from 'react-router-dom'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { Key, LockKeyhole, Plus, ShieldCheck, Trash2, Wrench } from 'lucide-react'
import { toast } from 'sonner'

import { ErrorState } from '@/components/common/ErrorState'
import { GuidedEmptyState } from '@/components/common/GuidedEmptyState'
import { LoadingState } from '@/components/common/LoadingState'
import { ProjectPageShell } from '@/components/common/ProjectPageShell'
import { ResourceCard } from '@/components/common/ResourceCard'
import { ResourceSummaryCard } from '@/components/common/ResourceSummaryCard'
import { StatusBadge } from '@/components/common/StatusBadge'
import { Button } from '@/components/ui/Button'
import { Dialog } from '@/components/ui/Dialog'
import { Input } from '@/components/ui/Input'
import { Select } from '@/components/ui/Select'
import { Tabs } from '@/components/ui/Tabs'
import { bulkUpdateMcpToolPermissions, disconnectMcpOAuth, refreshMcpTools, startMcpOAuth, updateMcpToolPermissions } from '@/features/tools/api'
import { useCreateSecret, useDeleteTool, useSecrets, useTools } from '@/features/tools/hooks'
import { createSecretSchema, type CreateSecretFormData } from '@/features/tools/schemas'
import type { DiscoveredMcpTool, McpReadiness, McpToolConfig, McpToolPermissionMode, Secret, Tool } from '@/features/tools/types'
import { ToolsCreateDialog } from '@/pages/ToolsCreateDialog'

const MCP_CONNECT_STATE_PREFIX = 'projectrai:mcp-connect:'
const MCP_AUTH_REQUIRED_STATES = new Set(['needs_connection', 'oauth_required', 'metadata_required'])
const MCP_TOKEN_REJECTED_STATES = new Set(['token_invalid', 'token_rejected'])

function RiskBadge({ risk }: { risk?: string | null }) {
  const value = risk || 'low'
  const tone = value === 'critical' ? 'border-red-500/40 bg-red-500/10 text-red-300' : value === 'high' ? 'border-amber-500/40 bg-amber-500/10 text-amber-300' : value === 'medium' ? 'border-blue-500/40 bg-blue-500/10 text-blue-300' : 'border-primary/40 bg-primary/10 text-primary-light'
  return <span className={`rounded-full border px-2 py-0.5 text-xs font-medium ${tone}`}>{value}</span>
}

function ReadinessBadge({ readiness }: { readiness: McpReadiness }) {
  const tone = readiness.state === 'ready' ? 'border-green-500/40 bg-green-500/10 text-green-300' : readiness.state === 'provider_not_supported' || readiness.state === 'token_rejected' ? 'border-amber-500/40 bg-amber-500/10 text-amber-300' : readiness.state === 'needs_permission' ? 'border-blue-500/40 bg-blue-500/10 text-blue-300' : 'border-border bg-surface/70 text-muted'
  return <span className={`rounded-full border px-2 py-0.5 text-xs font-medium ${tone}`}>{readiness.label}</span>
}

function PermissionBadge({ mode }: { mode: McpToolPermissionMode }) {
  const tone = mode === 'allow' ? 'border-green-500/40 bg-green-500/10 text-green-300' : mode === 'deny' ? 'border-red-500/40 bg-red-500/10 text-red-300' : 'border-amber-500/40 bg-amber-500/10 text-amber-300'
  return <span className={`rounded-full border px-2 py-0.5 text-[10px] font-medium uppercase ${tone}`}>{mode}</span>
}

function isMcpProvider(tool: Tool): boolean {
  const config = (tool.config || {}) as Record<string, unknown>
  return String(tool.type).toLowerCase().includes('mcp') || config.protocol === 'mcp'
}

function mcpConfig(tool: Tool): McpToolConfig {
  return (tool.config || {}) as McpToolConfig
}

function mcpDiscoveredTools(tool: Tool): DiscoveredMcpTool[] {
  const config = mcpConfig(tool)
  return Array.isArray(config.discovered_tools) ? config.discovered_tools : []
}

function oauthConnected(tool: Tool): boolean {
  const oauth = mcpConfig(tool).oauth as { status?: string } | undefined
  return oauth?.status === 'connected'
}

function hasMcpAuthChallenge(tool: Tool): boolean {
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

function permissionMode(tool: DiscoveredMcpTool): McpToolPermissionMode {
  const mode = tool.permission?.mode
  return mode === 'allow' || mode === 'deny' || mode === 'review' ? mode : 'review'
}

function permissionSummary(tools: DiscoveredMcpTool[]) {
  return tools.reduce((acc, tool) => { acc[permissionMode(tool)] += 1; return acc }, { allow: 0, deny: 0, review: 0 } as Record<McpToolPermissionMode, number>)
}

function fallbackReadiness(tool: Tool): McpReadiness {
  const discovered = mcpDiscoveredTools(tool)
  const exposed = discovered.filter(item => permissionMode(item) === 'allow').length
  const connected = oauthConnected(tool)
  const ready = mcpConfig(tool).mcp_status === 'ready'
  const authRequired = hasMcpAuthChallenge(tool)
  const state = exposed > 0 ? 'ready' : discovered.length > 0 ? 'needs_permission' : authRequired && !connected ? 'needs_connection' : 'needs_discovery'
  return {
    state,
    label: state === 'ready' ? 'Ready' : state === 'needs_permission' ? 'Needs permission' : state === 'needs_connection' ? 'Connect' : 'Load tools',
    message: state === 'ready' ? `${exposed} tools available to agents.` : state === 'needs_permission' ? 'Tools were found, but none are exposed to agents yet.' : state === 'needs_connection' ? 'Connect this MCP provider before agents can use its protected tools.' : 'Load this public MCP provider to see which tools it exposes.',
    action: state === 'needs_connection' ? 'connect' : state === 'ready' || state === 'needs_permission' ? 'configure_permissions' : 'refresh',
    can_use_tools: state === 'ready',
    oauth_connected: connected,
    mcp_ready: ready || discovered.length > 0,
    discovered_count: discovered.length,
    exposed_count: exposed,
    supports_device_code: false,
    needs_provider_client: false,
  }
}

function mcpReadiness(tool: Tool): McpReadiness {
  return mcpConfig(tool).mcp_readiness || fallbackReadiness(tool)
}

function shouldShowMcpConnect(tool: Tool, readiness: McpReadiness, discovered: DiscoveredMcpTool[]): boolean {
  if (oauthConnected(tool)) return false
  if (discovered.length > 0 && !hasMcpAuthChallenge(tool)) return false
  return readiness.action === 'connect' && hasMcpAuthChallenge(tool)
}

function visibleReadiness(tool: Tool, readiness: McpReadiness, discovered: DiscoveredMcpTool[]): McpReadiness {
  const summary = permissionSummary(discovered)
  if (!shouldShowMcpConnect(tool, readiness, discovered) && discovered.length > 0) {
    const ready = summary.allow > 0
    return {
      ...readiness,
      state: ready ? 'ready' : 'needs_permission',
      label: ready ? 'Ready' : 'Needs permission',
      message: ready ? `${summary.allow} MCP tool${summary.allow === 1 ? '' : 's'} available to agents.` : 'Tools were found, but none are exposed to agents yet.',
      action: 'configure_permissions',
      can_use_tools: ready,
      discovered_count: discovered.length,
      exposed_count: summary.allow,
    }
  }
  if (!shouldShowMcpConnect(tool, readiness, discovered) && discovered.length === 0 && readiness.state !== 'provider_not_supported' && readiness.state !== 'token_rejected') {
    return {
      ...readiness,
      state: 'needs_discovery',
      label: 'Load tools',
      message: 'Load this public MCP provider to see which tools it exposes.',
      action: 'refresh',
      can_use_tools: false,
      discovered_count: 0,
      exposed_count: 0,
    }
  }
  return readiness
}

export default function ToolsPage() {
  const { projectId } = useParams<{ projectId: string }>()
  const [searchParams, setSearchParams] = useSearchParams()
  const { data: tools, isLoading: toolsLoading, isError: toolsError, refetch: refetchTools } = useTools(projectId)
  const { data: secrets, isLoading: secLoading } = useSecrets(projectId)
  const createSecret = useCreateSecret()
  const deleteToolMutation = useDeleteTool()
  const [showTool, setShowTool] = useState(false)
  const [showSecret, setShowSecret] = useState(false)
  const [busyToolId, setBusyToolId] = useState<string | null>(null)
  const [permissionToolId, setPermissionToolId] = useState<string | null>(null)
  const [permissionSavingKey, setPermissionSavingKey] = useState<string | null>(null)
  const secretForm = useForm<CreateSecretFormData>({ resolver: zodResolver(createSecretSchema) })

  useEffect(() => {
    const requestedToolId = searchParams.get('configure_mcp_permissions')
    if (requestedToolId) setPermissionToolId(requestedToolId)
  }, [searchParams])

  const closePermissionConfig = () => {
    setPermissionToolId(null)
    setSearchParams(prev => { const next = new URLSearchParams(prev); next.delete('configure_mcp_permissions'); return next })
  }

  const handleCreateSecret = async (data: CreateSecretFormData) => {
    try {
      await createSecret.mutateAsync({ project_id: projectId!, name: data.name, type: data.type || 'custom', value: data.value })
      toast.success('Secret created')
      setShowSecret(false)
      secretForm.reset()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to create secret')
    }
  }

  const handleDeleteTool = async (tool: Tool) => {
    if (!window.confirm(`Delete tool "${tool.name}"? This action cannot be undone.`)) return
    try { setBusyToolId(tool.id); await deleteToolMutation.mutateAsync(tool.id); if (permissionToolId === tool.id) closePermissionConfig(); await refetchTools(); toast.success('Tool deleted') }
    catch (err) { toast.error(err instanceof Error ? err.message : 'Failed to delete tool') }
    finally { setBusyToolId(null) }
  }

  const handleConnectMcp = async (tool: Tool) => {
    try {
      setBusyToolId(tool.id)
      const redirectUri = `${window.location.origin}/mcp/oauth/callback`
      const result = await startMcpOAuth({ tool_id: tool.id, redirect_uri: redirectUri })
      window.localStorage.setItem(`${MCP_CONNECT_STATE_PREFIX}${result.state}`, JSON.stringify({ toolId: tool.id, returnTo: `${window.location.pathname}?configure_mcp_permissions=${tool.id}` }))
      window.location.assign(result.authorization_url)
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'This MCP provider needs device code or provider-issued OAuth credentials.')
      setBusyToolId(null)
    }
  }

  const handleDisconnectMcp = async (tool: Tool) => {
    try { setBusyToolId(tool.id); await disconnectMcpOAuth({ tool_id: tool.id }); await refetchTools(); toast.success('MCP disconnected') }
    catch (err) { toast.error(err instanceof Error ? err.message : 'Failed to disconnect MCP') }
    finally { setBusyToolId(null) }
  }

  const handleRefreshMcp = async (tool: Tool) => {
    try { setBusyToolId(tool.id); await refreshMcpTools({ tool_id: tool.id }); await refetchTools(); toast.success('MCP refreshed') }
    catch (err) { toast.error(err instanceof Error ? err.message : 'Failed to refresh MCP') }
    finally { setBusyToolId(null) }
  }

  const handleBulkPermission = async (tool: Tool, mode: McpToolPermissionMode) => {
    try { setPermissionSavingKey(`${tool.id}:bulk:${mode}`); await bulkUpdateMcpToolPermissions({ tool_id: tool.id, mode }); await refetchTools(); toast.success(`MCP tools set to ${mode}`) }
    catch (err) { toast.error(err instanceof Error ? err.message : 'Failed to update MCP permissions') }
    finally { setPermissionSavingKey(null) }
  }

  const handleSinglePermission = async (tool: Tool, remoteToolName: string, mode: McpToolPermissionMode) => {
    try { setPermissionSavingKey(`${tool.id}:${remoteToolName}:${mode}`); await updateMcpToolPermissions({ tool_id: tool.id, permissions: [{ remote_tool_name: remoteToolName, mode }] }); await refetchTools() }
    catch (err) { toast.error(err instanceof Error ? err.message : 'Failed to update MCP permission') }
    finally { setPermissionSavingKey(null) }
  }

  if (toolsLoading || secLoading) return <LoadingState />
  if (toolsError) return <ErrorState onRetry={refetchTools} />

  const toolItems = tools ?? []
  const secretItems = secrets ?? []
  const highRiskTools = toolItems.filter(tool => tool.risk_level === 'high' || tool.risk_level === 'critical').length

  const tabs = [
    {
      id: 'tools',
      label: 'Tools',
      content: toolItems.length > 0 ? (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
          {toolItems.map((tool: Tool) => {
            const mcpProvider = isMcpProvider(tool)
            const discovered = mcpDiscoveredTools(tool)
            const rawReadiness = mcpProvider ? mcpReadiness(tool) : null
            const readiness = rawReadiness ? visibleReadiness(tool, rawReadiness, discovered) : null
            const showConnect = mcpProvider && rawReadiness ? shouldShowMcpConnect(tool, rawReadiness, discovered) : false
            const showLoadTools = mcpProvider && readiness && !showConnect && discovered.length === 0 && readiness.state !== 'provider_not_supported' && readiness.state !== 'token_rejected'
            const summary = permissionSummary(discovered)
            const configuring = permissionToolId === tool.id
            return (
              <ResourceCard
                key={tool.id}
                icon={<Wrench className="h-5 w-5" />}
                title={tool.name}
                description={tool.description || tool.type}
                badge={<RiskBadge risk={tool.risk_level} />}
                metadata={(
                  <div className="space-y-3 rounded-lg border border-border/70 bg-background/70 p-3 text-sm text-muted">
                    <div className="flex items-center justify-between gap-3"><span>Type</span><span className="font-medium text-white">{tool.type}</span></div>
                    <div className="flex items-center justify-between gap-3"><span>Status</span><StatusBadge status={tool.status} /></div>
                    {mcpProvider && readiness ? (
                      <div className="space-y-3 border-t border-border/70 pt-3">
                        <div className="flex items-start justify-between gap-3">
                          <div><p className="font-medium text-white">MCP tools</p><p className="text-xs text-muted">{readiness.exposed_count} available · {readiness.discovered_count} discovered</p></div>
                          <ReadinessBadge readiness={readiness} />
                        </div>
                        <p className="text-xs leading-relaxed text-muted">{readiness.message}</p>
                        <div className="flex flex-wrap gap-2">
                          {showConnect ? <Button size="sm" onClick={() => handleConnectMcp(tool)} loading={busyToolId === tool.id}>Connect</Button> : null}
                          {showLoadTools ? <Button size="sm" onClick={() => handleRefreshMcp(tool)} loading={busyToolId === tool.id}>Load tools</Button> : null}
                          {readiness.state === 'provider_not_supported' ? <Button size="sm" variant="outline" disabled>Needs provider client</Button> : null}
                          {discovered.length > 0 ? <Button size="sm" variant="outline" onClick={() => setPermissionToolId(configuring ? null : tool.id)}>{configuring ? 'Hide tools' : 'Permissions'}</Button> : null}
                          {readiness.oauth_connected ? <Button size="sm" variant="outline" onClick={() => handleDisconnectMcp(tool)} loading={busyToolId === tool.id}>Disconnect</Button> : null}
                          {readiness.oauth_connected && !readiness.can_use_tools ? <Button size="sm" variant="ghost" onClick={() => handleRefreshMcp(tool)} loading={busyToolId === tool.id}>Refresh</Button> : null}
                        </div>
                        {readiness.state === 'provider_not_supported' ? <p className="rounded-lg border border-amber-500/30 bg-amber-500/10 p-2 text-xs text-amber-200">Normal OAuth is not accepted for this provider. Use device code API or credentials issued by the provider.</p> : null}
                        {discovered.length > 0 && configuring ? (
                          <div className="rounded-lg border border-border/70 bg-card/40 p-2">
                            <div className="flex flex-wrap items-center gap-2 text-xs"><span>{discovered.length} discovered</span><span className="text-green-300">{summary.allow} allow</span><span className="text-red-300">{summary.deny} deny</span><span className="text-amber-300">{summary.review} review</span></div>
                            <div className="mt-3 flex flex-wrap gap-2"><Button size="sm" onClick={() => handleBulkPermission(tool, 'allow')} loading={permissionSavingKey === `${tool.id}:bulk:allow`}>Allow all</Button><Button size="sm" variant="outline" onClick={() => handleBulkPermission(tool, 'deny')} loading={permissionSavingKey === `${tool.id}:bulk:deny`}>Deny all</Button><Button size="sm" variant="ghost" onClick={closePermissionConfig}>Done</Button></div>
                            <div className="mt-3 max-h-72 space-y-2 overflow-y-auto pr-1">
                              {discovered.map(item => {
                                const mode = permissionMode(item)
                                return (
                                  <div key={item.name} className="rounded-lg border border-border/70 bg-background/70 p-2">
                                    <div className="mb-2 flex items-start justify-between gap-2"><div className="min-w-0"><p className="text-xs font-medium text-white break-words">{item.title || item.name}</p><p className="text-[10px] font-mono text-muted break-all">{item.name}</p></div><PermissionBadge mode={mode} /></div>
                                    <div className="flex flex-wrap gap-2"><Button size="sm" variant={mode === 'allow' ? 'default' : 'outline'} onClick={() => handleSinglePermission(tool, item.name, 'allow')} loading={permissionSavingKey === `${tool.id}:${item.name}:allow`}>Allow</Button><Button size="sm" variant={mode === 'deny' ? 'destructive' : 'outline'} onClick={() => handleSinglePermission(tool, item.name, 'deny')} loading={permissionSavingKey === `${tool.id}:${item.name}:deny`}>Deny</Button><Button size="sm" variant={mode === 'review' ? 'secondary' : 'ghost'} onClick={() => handleSinglePermission(tool, item.name, 'review')} loading={permissionSavingKey === `${tool.id}:${item.name}:review`}>Review</Button></div>
                                  </div>
                                )
                              })}
                            </div>
                          </div>
                        ) : null}
                      </div>
                    ) : null}
                    <div className="flex flex-wrap gap-2 border-t border-border/70 pt-3"><Button size="sm" variant="destructive" onClick={() => handleDeleteTool(tool)} loading={busyToolId === tool.id}><Trash2 className="mr-1 h-3 w-3" />Delete</Button></div>
                  </div>
                )}
              />
            )
          })}
        </div>
      ) : <GuidedEmptyState icon={<Wrench className="h-6 w-6" />} title="No tools" description="Create tools to let agents call external systems, functions or MCP endpoints." actionLabel="Create tool" onAction={() => setShowTool(true)} next={["Define capability", "Set risk level", "Attach to an agent"]} />,
    },
    {
      id: 'secrets',
      label: 'Secrets',
      content: secretItems.length > 0 ? <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">{secretItems.map((secret: Secret) => <ResourceCard key={secret.id} icon={<LockKeyhole className="h-5 w-5" />} title={secret.name} description={secret.type} badge={<StatusBadge status={secret.status || 'stored'} />} metadata={<p className="rounded-lg border border-border/70 bg-background/70 p-3 text-sm text-muted">Secret values are stored securely and are not displayed here.</p>} />)}</div> : <GuidedEmptyState icon={<Key className="h-6 w-6" />} title="No secrets" description="Store API keys and credentials so tools can use them without exposing raw values." actionLabel="Create secret" onAction={() => setShowSecret(true)} next={["Store credential", "Reference it from tools", "Keep values hidden"]} />,
    },
  ]

  return <ProjectPageShell eyebrow="Integrations" title="Tools" description="Connect external capabilities and store credentials your agents can use safely." actions={<><Button variant="outline" onClick={() => setShowSecret(true)}><Key className="mr-2 h-4 w-4" />Create secret</Button><Button onClick={() => setShowTool(true)}><Plus className="mr-2 h-4 w-4" />Create tool</Button></>}><div className="grid gap-4 md:grid-cols-3"><ResourceSummaryCard label="Tools" value={toolItems.length} detail="External capabilities" icon={<Wrench className="h-5 w-5" />} /><ResourceSummaryCard label="Secrets" value={secretItems.length} detail="Stored credentials" icon={<LockKeyhole className="h-5 w-5" />} /><ResourceSummaryCard label="High risk" value={highRiskTools} detail="High or critical tools" icon={<ShieldCheck className="h-5 w-5" />} /></div><Tabs tabs={tabs} /><ToolsCreateDialog open={showTool} projectId={projectId!} onClose={() => setShowTool(false)} /><Dialog open={showSecret} onClose={() => setShowSecret(false)} title="Create Secret"><form onSubmit={secretForm.handleSubmit(handleCreateSecret)} className="space-y-4"><Input {...secretForm.register('name')} error={secretForm.formState.errors.name?.message} placeholder="Secret name" /><Select {...secretForm.register('type')} options={[{ value: 'custom', label: 'Custom' }, { value: 'api_key', label: 'API Key' }, { value: 'bearer', label: 'Bearer Token' }]} placeholder="Type" /><Input type="password" {...secretForm.register('value')} error={secretForm.formState.errors.value?.message} placeholder="Secret value" /><p className="text-xs text-muted">Secret values are stored securely and are not shown after saving.</p><div className="flex justify-end gap-2"><Button type="button" variant="outline" onClick={() => setShowSecret(false)}>Cancel</Button><Button type="submit" loading={createSecret.isPending}>Create</Button></div></form></Dialog></ProjectPageShell>
}
