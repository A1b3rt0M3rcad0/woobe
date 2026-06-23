import { useEffect, useState } from 'react'
import { useParams, useSearchParams } from 'react-router-dom'
import { useTools, useSecrets, useCreateSecret } from '@/features/tools/hooks'
import { bulkUpdateMcpToolPermissions, disconnectMcpOAuth, startMcpOAuth, updateMcpToolPermissions } from '@/features/tools/api'
import { ToolsCreateDialog } from '@/pages/ToolsCreateDialog'
import { ProjectPageShell } from '@/components/common/ProjectPageShell'
import { GuidedEmptyState } from '@/components/common/GuidedEmptyState'
import { ResourceCard } from '@/components/common/ResourceCard'
import { ResourceSummaryCard } from '@/components/common/ResourceSummaryCard'
import { LoadingState } from '@/components/common/LoadingState'
import { ErrorState } from '@/components/common/ErrorState'
import { Button } from '@/components/ui/Button'
import { Dialog } from '@/components/ui/Dialog'
import { Input } from '@/components/ui/Input'
import { Select } from '@/components/ui/Select'
import { Tabs } from '@/components/ui/Tabs'
import { StatusBadge } from '@/components/common/StatusBadge'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { createSecretSchema, type CreateSecretFormData } from '@/features/tools/schemas'
import { Key, LockKeyhole, Plus, ShieldCheck, Wrench } from 'lucide-react'
import { toast } from 'sonner'
import type { DiscoveredMcpTool, McpToolConfig, McpToolPermissionMode, Secret, Tool } from '@/features/tools/types'

const MCP_CONNECT_STATE_PREFIX = 'projectrai:mcp-connect:'

function RiskBadge({ risk }: { risk?: string | null }) {
  const value = risk || 'low'
  const tone = value === 'critical'
    ? 'border-red-500/40 bg-red-500/10 text-red-300'
    : value === 'high'
      ? 'border-amber-500/40 bg-amber-500/10 text-amber-300'
      : value === 'medium'
        ? 'border-blue-500/40 bg-blue-500/10 text-blue-300'
        : 'border-primary/40 bg-primary/10 text-primary-light'
  return <span className={`rounded-full border px-2 py-0.5 text-xs font-medium ${tone}`}>{value}</span>
}

function PermissionBadge({ mode }: { mode: McpToolPermissionMode }) {
  const tone = mode === 'allow'
    ? 'border-green-500/40 bg-green-500/10 text-green-300'
    : mode === 'deny'
      ? 'border-red-500/40 bg-red-500/10 text-red-300'
      : 'border-amber-500/40 bg-amber-500/10 text-amber-300'
  return <span className={`rounded-full border px-2 py-0.5 text-[10px] font-medium uppercase ${tone}`}>{mode}</span>
}

function isMcpProvider(tool: Tool): boolean {
  const config = (tool.config || {}) as Record<string, unknown>
  return String(tool.type).includes('mcp') || config.protocol === 'mcp'
}

function mcpConnectStatus(tool: Tool): string {
  const config = (tool.config || {}) as { oauth?: { status?: string } }
  return config.oauth?.status || 'disconnected'
}

function mcpDiscoveredTools(tool: Tool): DiscoveredMcpTool[] {
  const config = (tool.config || {}) as McpToolConfig
  return Array.isArray(config.discovered_tools) ? config.discovered_tools : []
}

function permissionMode(tool: DiscoveredMcpTool): McpToolPermissionMode {
  const mode = tool.permission?.mode
  return mode === 'allow' || mode === 'deny' || mode === 'review' ? mode : 'review'
}

function permissionSummary(tools: DiscoveredMcpTool[]) {
  return tools.reduce(
    (acc, tool) => {
      acc[permissionMode(tool)] += 1
      return acc
    },
    { allow: 0, deny: 0, review: 0 } as Record<McpToolPermissionMode, number>,
  )
}

export default function ToolsPage() {
  const { projectId } = useParams<{ projectId: string }>()
  const [searchParams, setSearchParams] = useSearchParams()
  const { data: tools, isLoading: toolsLoading, isError: toolsError, refetch: refetchTools } = useTools(projectId)
  const { data: secrets, isLoading: secLoading } = useSecrets(projectId)
  const createSecret = useCreateSecret()
  const [showTool, setShowTool] = useState(false)
  const [showSecret, setShowSecret] = useState(false)
  const [connectingToolId, setConnectingToolId] = useState<string | null>(null)
  const [permissionToolId, setPermissionToolId] = useState<string | null>(null)
  const [permissionSavingKey, setPermissionSavingKey] = useState<string | null>(null)

  useEffect(() => {
    const requestedToolId = searchParams.get('configure_mcp_permissions')
    if (requestedToolId) setPermissionToolId(requestedToolId)
  }, [searchParams])

  const secretForm = useForm<CreateSecretFormData>({ resolver: zodResolver(createSecretSchema) })

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

  const handleConnectMcp = async (tool: Tool) => {
    try {
      setConnectingToolId(tool.id)
      const redirectUri = `${window.location.origin}/tools/mcp/oauth/callback`
      const result = await startMcpOAuth({ tool_id: tool.id, redirect_uri: redirectUri })
      window.localStorage.setItem(
        `${MCP_CONNECT_STATE_PREFIX}${result.state}`,
        JSON.stringify({ toolId: tool.id, returnTo: `${window.location.pathname}?configure_mcp_permissions=${tool.id}` }),
      )
      window.location.assign(result.authorization_url)
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to start MCP connection')
      setConnectingToolId(null)
    }
  }

  const handleDisconnectMcp = async (tool: Tool) => {
    try {
      setConnectingToolId(tool.id)
      await disconnectMcpOAuth({ tool_id: tool.id })
      await refetchTools()
      toast.success('MCP disconnected')
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to disconnect MCP')
    } finally {
      setConnectingToolId(null)
    }
  }

  const handleBulkPermission = async (tool: Tool, mode: McpToolPermissionMode) => {
    try {
      setPermissionSavingKey(`${tool.id}:bulk:${mode}`)
      await bulkUpdateMcpToolPermissions({ tool_id: tool.id, mode })
      await refetchTools()
      toast.success(`MCP tools set to ${mode}`)
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to update MCP permissions')
    } finally {
      setPermissionSavingKey(null)
    }
  }

  const handleSinglePermission = async (tool: Tool, remoteToolName: string, mode: McpToolPermissionMode) => {
    try {
      setPermissionSavingKey(`${tool.id}:${remoteToolName}:${mode}`)
      await updateMcpToolPermissions({ tool_id: tool.id, permissions: [{ remote_tool_name: remoteToolName, mode }] })
      await refetchTools()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to update MCP permission')
    } finally {
      setPermissionSavingKey(null)
    }
  }

  const closePermissionConfig = () => {
    setPermissionToolId(null)
    setSearchParams(prev => {
      const next = new URLSearchParams(prev)
      next.delete('configure_mcp_permissions')
      return next
    })
  }

  if (toolsLoading || secLoading) return <LoadingState />
  if (toolsError) return <ErrorState onRetry={refetchTools} />

  const toolItems = tools ?? []
  const secretItems = secrets ?? []
  const highRiskTools = toolItems.filter((tool) => tool.risk_level === 'high' || tool.risk_level === 'critical').length

  const tabs = [
    {
      id: 'tools',
      label: 'Tools',
      content: toolItems.length > 0 ? (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
          {toolItems.map((tool: Tool) => {
            const mcpProvider = isMcpProvider(tool)
            const connectStatus = mcpConnectStatus(tool)
            const connected = connectStatus === 'connected'
            const discovered = mcpDiscoveredTools(tool)
            const summary = permissionSummary(discovered)
            const configuring = permissionToolId === tool.id
            return (
              <ResourceCard
                key={tool.id}
                icon={<Wrench className="h-5 w-5" />}
                title={tool.name}
                description={tool.description || tool.type}
                badge={<RiskBadge risk={tool.risk_level} />}
                metadata={
                  <div className="space-y-3 rounded-lg border border-border/70 bg-background/70 p-3 text-sm text-muted">
                    <div className="flex items-center justify-between gap-3"><span>Type</span><span className="font-medium text-white">{tool.type}</span></div>
                    <div className="flex items-center justify-between gap-3"><span>Status</span><StatusBadge status={tool.status} /></div>
                    {mcpProvider ? (
                      <div className="space-y-3 border-t border-border/70 pt-3">
                        <div className="flex items-center justify-between gap-3"><span>MCP connection</span><StatusBadge status={connected ? 'connected' : connectStatus} /></div>
                        <div className="flex flex-wrap gap-2">
                          <Button size="sm" onClick={() => handleConnectMcp(tool)} loading={connectingToolId === tool.id}>{connected ? 'Reconnect' : 'Connect'}</Button>
                          {connected ? <Button size="sm" variant="outline" onClick={() => handleDisconnectMcp(tool)} loading={connectingToolId === tool.id}>Disconnect</Button> : null}
                          {discovered.length > 0 ? <Button size="sm" variant="outline" onClick={() => setPermissionToolId(configuring ? null : tool.id)}>{configuring ? 'Hide permissions' : 'Configure permissions'}</Button> : null}
                        </div>
                        {discovered.length > 0 ? (
                          <div className="rounded-lg border border-border/70 bg-card/40 p-2">
                            <div className="flex flex-wrap items-center gap-2 text-xs">
                              <span>{discovered.length} discovered</span>
                              <span className="text-green-300">{summary.allow} allow</span>
                              <span className="text-red-300">{summary.deny} deny</span>
                              <span className="text-amber-300">{summary.review} review</span>
                            </div>
                            {configuring ? (
                              <div className="mt-3 space-y-3">
                                <div className="flex flex-wrap gap-2">
                                  <Button size="sm" onClick={() => handleBulkPermission(tool, 'allow')} loading={permissionSavingKey === `${tool.id}:bulk:allow`}>Allow all</Button>
                                  <Button size="sm" variant="outline" onClick={() => handleBulkPermission(tool, 'deny')} loading={permissionSavingKey === `${tool.id}:bulk:deny`}>Deny all</Button>
                                  <Button size="sm" variant="ghost" onClick={closePermissionConfig}>Done</Button>
                                </div>
                                <div className="max-h-72 space-y-2 overflow-y-auto pr-1">
                                  {discovered.map(item => {
                                    const mode = permissionMode(item)
                                    return (
                                      <div key={item.name} className="rounded-lg border border-border/70 bg-background/70 p-2">
                                        <div className="mb-2 flex items-start justify-between gap-2">
                                          <div className="min-w-0"><p className="text-xs font-medium text-white break-words">{item.title || item.name}</p><p className="text-[10px] font-mono text-muted break-all">{item.name}</p></div>
                                          <PermissionBadge mode={mode} />
                                        </div>
                                        <div className="flex flex-wrap gap-2">
                                          <Button size="sm" variant={mode === 'allow' ? 'default' : 'outline'} onClick={() => handleSinglePermission(tool, item.name, 'allow')} loading={permissionSavingKey === `${tool.id}:${item.name}:allow`}>Allow</Button>
                                          <Button size="sm" variant={mode === 'deny' ? 'destructive' : 'outline'} onClick={() => handleSinglePermission(tool, item.name, 'deny')} loading={permissionSavingKey === `${tool.id}:${item.name}:deny`}>Deny</Button>
                                          <Button size="sm" variant={mode === 'review' ? 'secondary' : 'ghost'} onClick={() => handleSinglePermission(tool, item.name, 'review')} loading={permissionSavingKey === `${tool.id}:${item.name}:review`}>Review</Button>
                                        </div>
                                      </div>
                                    )
                                  })}
                                </div>
                              </div>
                            ) : null}
                          </div>
                        ) : null}
                      </div>
                    ) : null}
                  </div>
                }
              />
            )
          })}
        </div>
      ) : (
        <GuidedEmptyState icon={<Wrench className="h-6 w-6" />} title="No tools" description="Create tools to let agents call external systems, functions or MCP endpoints." actionLabel="Create tool" onAction={() => setShowTool(true)} next={["Define capability", "Set risk level", "Attach to an agent"]} />
      ),
    },
    {
      id: 'secrets',
      label: 'Secrets',
      content: secretItems.length > 0 ? (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
          {secretItems.map((secret: Secret) => <ResourceCard key={secret.id} icon={<LockKeyhole className="h-5 w-5" />} title={secret.name} description={secret.type} badge={<StatusBadge status={secret.status || 'stored'} />} metadata={<p className="rounded-lg border border-border/70 bg-background/70 p-3 text-sm text-muted">Secret values are stored securely and are not displayed here.</p>} />)}
        </div>
      ) : (
        <GuidedEmptyState icon={<Key className="h-6 w-6" />} title="No secrets" description="Store API keys and credentials so tools can use them without exposing raw values." actionLabel="Create secret" onAction={() => setShowSecret(true)} next={["Store credential", "Reference it from tools", "Keep values hidden"]} />
      ),
    },
  ]

  return (
    <ProjectPageShell eyebrow="Integrations" title="Tools" description="Connect external capabilities and store credentials your agents can use safely." actions={<><Button variant="outline" onClick={() => setShowSecret(true)}><Key className="mr-2 h-4 w-4" />Create secret</Button><Button onClick={() => setShowTool(true)}><Plus className="mr-2 h-4 w-4" />Create tool</Button></>}>
      <div className="grid gap-4 md:grid-cols-3">
        <ResourceSummaryCard label="Tools" value={toolItems.length} detail="External capabilities" icon={<Wrench className="h-5 w-5" />} />
        <ResourceSummaryCard label="Secrets" value={secretItems.length} detail="Stored credentials" icon={<LockKeyhole className="h-5 w-5" />} />
        <ResourceSummaryCard label="High risk" value={highRiskTools} detail="High or critical tools" icon={<ShieldCheck className="h-5 w-5" />} />
      </div>

      <Tabs tabs={tabs} />
      <ToolsCreateDialog open={showTool} projectId={projectId!} onClose={() => setShowTool(false)} />

      <Dialog open={showSecret} onClose={() => setShowSecret(false)} title="Create Secret">
        <form onSubmit={secretForm.handleSubmit(handleCreateSecret)} className="space-y-4">
          <Input {...secretForm.register('name')} error={secretForm.formState.errors.name?.message} placeholder="Secret name" />
          <Select {...secretForm.register('type')} options={[{ value: 'custom', label: 'Custom' }, { value: 'api_key', label: 'API Key' }, { value: 'bearer', label: 'Bearer Token' }]} placeholder="Type" />
          <Input type="password" {...secretForm.register('value')} error={secretForm.formState.errors.value?.message} placeholder="Secret value" />
          <p className="text-xs text-muted">Secret values are stored securely and are not shown after saving.</p>
          <div className="flex justify-end gap-2"><Button type="button" variant="outline" onClick={() => setShowSecret(false)}>Cancel</Button><Button type="submit" loading={createSecret.isPending}>Create</Button></div>
        </form>
      </Dialog>
    </ProjectPageShell>
  )
}
