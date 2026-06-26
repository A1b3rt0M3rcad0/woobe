import { useMemo, useState, type ReactNode } from 'react'
import { useParams } from 'react-router-dom'
import { Plus, RefreshCw, Search, ShieldCheck, Trash2, Wrench } from 'lucide-react'
import { toast } from 'sonner'
import { ErrorState } from '@/components/common/ErrorState'
import { LoadingState } from '@/components/common/LoadingState'
import { StatusBadge } from '@/components/common/StatusBadge'
import { Button } from '@/components/ui/Button'
import { Dialog } from '@/components/ui/Dialog'
import { Input } from '@/components/ui/Input'
import { Select } from '@/components/ui/Select'
import { bulkUpdateMcpToolPermissions, refreshMcpTools, updateMcpToolPermissions } from '@/features/tools/api'
import { useDeleteTool, useTools, useUpdateTool, useUpdateToolStatus } from '@/features/tools/hooks'
import type { DiscoveredMcpTool, McpToolConfig, McpToolPermissionMode, Tool } from '@/features/tools/types'
import { ToolsCreateDialog } from '@/pages/ToolsCreateDialog'

function MinimalShell({ title, description, children }: { title: string; description: string; children: ReactNode }) {
  return (
    <div className="mx-auto w-full max-w-[1500px] space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight text-white">{title}</h1>
        <p className="mt-2 max-w-3xl text-sm text-muted">{description}</p>
      </div>
      {children}
    </div>
  )
}

function CreateCard({ title, description, onClick }: { title: string; description: string; onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="group flex min-h-[240px] flex-col items-center justify-center rounded-xl border border-dashed border-primary/40 bg-surface/35 p-6 text-center transition-[border-color,background-color,box-shadow] duration-200 hover:border-primary/60 hover:bg-primary/5 hover:shadow-lg hover:shadow-primary/5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/30 focus-visible:ring-offset-2 focus-visible:ring-offset-background"
    >
      <span className="flex h-14 w-14 items-center justify-center rounded-full border border-primary/50 bg-primary/10 text-primary-light transition-colors duration-200 group-hover:bg-primary/15">
        <Plus className="h-6 w-6" />
      </span>
      <span className="mt-5 text-base font-semibold text-white">{title}</span>
      <span className="mt-2 max-w-[220px] text-sm leading-6 text-muted">{description}</span>
    </button>
  )
}

function NoResults() {
  return (
    <div className="rounded-xl border border-border/80 bg-surface/50 px-5 py-4">
      <h2 className="text-sm font-semibold text-white">No tools found</h2>
      <p className="mt-1 text-sm text-muted">Create a new tool or adjust the search term.</p>
    </div>
  )
}

function Section({ title, description, children }: { title: string; description?: string; children: ReactNode }) {
  return (
    <section className="rounded-xl border border-border/80 bg-surface/65 p-4">
      <div className="mb-4">
        <h3 className="text-sm font-semibold text-white">{title}</h3>
        {description && <p className="mt-1 text-xs leading-5 text-muted">{description}</p>}
      </div>
      {children}
    </section>
  )
}

function getMcpConfig(tool: Tool): McpToolConfig {
  return (tool.config || {}) as McpToolConfig
}

function isMcpTool(tool: Tool) {
  const config = (tool.config || {}) as Record<string, unknown>
  return String(tool.type).toLowerCase().includes('mcp') || config.protocol === 'mcp'
}

function getDiscoveredTools(tool: Tool): DiscoveredMcpTool[] {
  const config = getMcpConfig(tool)
  return Array.isArray(config.discovered_tools) ? config.discovered_tools : []
}

function getPermissionMode(tool: DiscoveredMcpTool): McpToolPermissionMode {
  const mode = tool.permission?.mode
  return mode === 'allow' || mode === 'deny' || mode === 'review' ? mode : 'review'
}

function permissionCounts(tools: DiscoveredMcpTool[]) {
  return tools.reduce(
    (acc, tool) => {
      acc[getPermissionMode(tool)] += 1
      return acc
    },
    { allow: 0, deny: 0, review: 0 } as Record<McpToolPermissionMode, number>,
  )
}

function PermissionBadge({ mode }: { mode: McpToolPermissionMode }) {
  const tone = mode === 'allow'
    ? 'border-green-500/40 bg-green-500/10 text-green-300'
    : mode === 'deny'
      ? 'border-red-500/40 bg-red-500/10 text-red-300'
      : 'border-amber-500/40 bg-amber-500/10 text-amber-300'
  return <span className={`rounded-full border px-2 py-0.5 text-[10px] font-medium uppercase ${tone}`}>{mode}</span>
}

function Pill({ children, tone = 'default' }: { children: ReactNode; tone?: 'default' | 'primary' | 'danger' }) {
  const toneClass = tone === 'primary'
    ? 'border-primary/30 bg-primary/10 text-primary-light'
    : tone === 'danger'
      ? 'border-red-500/30 bg-red-500/10 text-red-200'
      : 'border-border/80 bg-background/70 text-muted'
  return <span className={`rounded-full border px-2.5 py-1 text-xs ${toneClass}`}>{children}</span>
}

export default function ToolsPage() {
  const { projectId } = useParams<{ projectId: string }>()
  const { data: tools, isLoading, isError, error, refetch } = useTools(projectId)
  const updateToolMutation = useUpdateTool()
  const updateToolStatusMutation = useUpdateToolStatus()
  const deleteToolMutation = useDeleteTool()
  const [showCreate, setShowCreate] = useState(false)
  const [query, setQuery] = useState('')
  const [selectedToolId, setSelectedToolId] = useState<string | null>(null)
  const [busyToolId, setBusyToolId] = useState<string | null>(null)
  const [permissionSavingKey, setPermissionSavingKey] = useState<string | null>(null)
  const [editName, setEditName] = useState('')
  const [editDescription, setEditDescription] = useState('')
  const [editRiskLevel, setEditRiskLevel] = useState('')
  const [editTimeoutMs, setEditTimeoutMs] = useState('')

  const items = tools ?? []
  const selectedTool = items.find((tool) => tool.id === selectedToolId) ?? null
  const discoveredTools = selectedTool ? getDiscoveredTools(selectedTool) : []
  const counts = permissionCounts(discoveredTools)

  const visibleTools = useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase()
    if (!normalizedQuery) return items

    return items.filter((tool) => (
      tool.name.toLowerCase().includes(normalizedQuery)
      || tool.description?.toLowerCase().includes(normalizedQuery)
      || String(tool.type).toLowerCase().includes(normalizedQuery)
      || tool.status?.toLowerCase().includes(normalizedQuery)
      || tool.risk_level?.toLowerCase().includes(normalizedQuery)
    ))
  }, [items, query])

  const openToolModal = (tool: Tool) => {
    setSelectedToolId(tool.id)
    setEditName(tool.name)
    setEditDescription(tool.description || '')
    setEditRiskLevel(tool.risk_level || 'low')
    setEditTimeoutMs(tool.timeout_ms ? String(tool.timeout_ms) : '')
  }

  const closeToolModal = () => {
    setSelectedToolId(null)
    setBusyToolId(null)
    setPermissionSavingKey(null)
  }

  const handleSaveTool = async () => {
    if (!selectedTool) return

    if (!editName.trim()) {
      toast.error('Tool name is required')
      return
    }

    if (editTimeoutMs && Number.isNaN(Number(editTimeoutMs))) {
      toast.error('Timeout must be a number')
      return
    }

    try {
      await updateToolMutation.mutateAsync({
        toolId: selectedTool.id,
        data: {
          name: editName.trim(),
          description: editDescription.trim() || undefined,
          risk_level: editRiskLevel,
          timeout_ms: editTimeoutMs ? Number(editTimeoutMs) : undefined,
        },
      })
      await refetch()
      toast.success('Tool updated')
      closeToolModal()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to update tool')
    }
  }

  const handleToggleStatus = async () => {
    if (!selectedTool) return
    const nextStatus = selectedTool.status === 'active' ? 'inactive' : 'active'

    try {
      setBusyToolId(selectedTool.id)
      await updateToolStatusMutation.mutateAsync({
        toolId: selectedTool.id,
        data: { status: nextStatus },
      })
      await refetch()
      toast.success(nextStatus === 'active' ? 'Tool enabled' : 'Tool disabled')
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to update tool status')
    } finally {
      setBusyToolId(null)
    }
  }

  const handleRefreshMcp = async () => {
    if (!selectedTool) return

    try {
      setBusyToolId(selectedTool.id)
      await refreshMcpTools({ tool_id: selectedTool.id })
      await refetch()
      toast.success('MCP tools refreshed')
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to refresh MCP tools')
    } finally {
      setBusyToolId(null)
    }
  }

  const handleBulkPermission = async (mode: McpToolPermissionMode) => {
    if (!selectedTool) return

    try {
      setPermissionSavingKey(`bulk:${mode}`)
      await bulkUpdateMcpToolPermissions({ tool_id: selectedTool.id, mode })
      await refetch()
      toast.success(`MCP tools set to ${mode}`)
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to update MCP permissions')
    } finally {
      setPermissionSavingKey(null)
    }
  }

  const handleSinglePermission = async (remoteToolName: string, mode: McpToolPermissionMode) => {
    if (!selectedTool) return

    try {
      setPermissionSavingKey(`${remoteToolName}:${mode}`)
      await updateMcpToolPermissions({
        tool_id: selectedTool.id,
        permissions: [{ remote_tool_name: remoteToolName, mode }],
      })
      await refetch()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to update MCP permission')
    } finally {
      setPermissionSavingKey(null)
    }
  }

  const handleDeleteTool = async () => {
    if (!selectedTool) return
    if (!window.confirm(`Delete tool "${selectedTool.name}"? This action cannot be undone.`)) return

    try {
      setBusyToolId(selectedTool.id)
      await deleteToolMutation.mutateAsync(selectedTool.id)
      await refetch()
      toast.success('Tool deleted')
      closeToolModal()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to delete tool')
    } finally {
      setBusyToolId(null)
    }
  }

  if (isLoading) return <LoadingState />
  if (isError) return <ErrorState error={error} onRetry={refetch} />

  const hasSearchMiss = query.trim().length > 0 && visibleTools.length === 0

  return (
    <MinimalShell
      title="Tools"
      description="Connect and review external capabilities available to agents in this project."
    >
      <div className="relative max-w-3xl">
        <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted" />
        <Input
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Search tools..."
          className="h-11 pl-9"
        />
      </div>

      {hasSearchMiss && <NoResults />}

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
        {visibleTools.map((tool: Tool) => (
          <button
            key={tool.id}
            type="button"
            aria-label={`Open tool settings for ${tool.name}`}
            onClick={() => openToolModal(tool)}
            className="group flex min-h-[240px] flex-col rounded-xl border border-border/90 bg-surface/70 p-6 text-left transition-[border-color,background-color,box-shadow] duration-200 hover:border-primary/35 hover:bg-surface/85 hover:shadow-lg hover:shadow-primary/5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/30 focus-visible:ring-offset-2 focus-visible:ring-offset-background"
          >
            <span className="flex items-start justify-between gap-3">
              <span className="flex h-12 w-12 items-center justify-center rounded-xl border border-border bg-background text-primary-light shadow-sm transition-colors duration-200 group-hover:border-primary/30 group-hover:bg-primary/10">
                <Wrench className="h-5 w-5" />
              </span>
              <StatusBadge status={tool.status} />
            </span>

            <span className="mt-6 block min-w-0">
              <span className="block truncate text-base font-semibold text-white">{tool.name}</span>
              <span className="mt-2 block line-clamp-2 text-sm leading-6 text-muted">{tool.description || tool.type}</span>
            </span>

            <span className="my-5 block h-px bg-border/80" />

            <span className="mt-auto flex flex-wrap gap-2 text-xs text-muted">
              <Pill>{String(tool.type)}</Pill>
              {tool.risk_level && <Pill tone={tool.risk_level === 'critical' || tool.risk_level === 'high' ? 'danger' : 'default'}>Risk · {tool.risk_level}</Pill>}
              {isMcpTool(tool) && <Pill tone="primary">MCP</Pill>}
            </span>
          </button>
        ))}

        <CreateCard
          title="New tool"
          description="Connect an external capability"
          onClick={() => setShowCreate(true)}
        />
      </div>

      <ToolsCreateDialog open={showCreate} projectId={projectId!} onClose={() => setShowCreate(false)} />

      <Dialog open={Boolean(selectedTool)} onClose={closeToolModal} title="Tool settings" className="max-h-[calc(100svh-2rem)] max-w-5xl overflow-hidden">
        {selectedTool && (
          <div className="max-h-[calc(100svh-8rem)] overflow-y-auto pr-1">
            <div className="grid gap-6 lg:grid-cols-[280px_minmax(0,1fr)]">
              <aside className="space-y-4 lg:sticky lg:top-0 lg:self-start">
                <div className="rounded-xl border border-border/90 bg-surface/70 p-4">
                  <div className="flex h-11 w-11 items-center justify-center rounded-xl border border-border bg-background text-primary-light">
                    <Wrench className="h-5 w-5" />
                  </div>
                  <div className="mt-5 min-w-0">
                    <h2 className="truncate text-base font-semibold text-white">{selectedTool.name}</h2>
                    <p className="mt-1 truncate text-sm text-muted">{String(selectedTool.type)}</p>
                  </div>
                  <div className="mt-5 flex flex-wrap gap-2">
                    <StatusBadge status={selectedTool.status} />
                    <Pill tone={editRiskLevel === 'critical' || editRiskLevel === 'high' ? 'danger' : 'default'}>Risk · {editRiskLevel || 'unset'}</Pill>
                    {isMcpTool(selectedTool) && <Pill tone="primary">MCP</Pill>}
                  </div>
                </div>

                <div className="rounded-xl border border-border/90 bg-background/60 p-4">
                  <p className="text-sm font-semibold text-white">Runtime status</p>
                  <p className="mt-1 text-xs leading-5 text-muted">Control whether this tool can be used by agents.</p>
                  <Button className="mt-4 w-full" size="sm" variant="outline" onClick={handleToggleStatus} loading={busyToolId === selectedTool.id || updateToolStatusMutation.isPending}>
                    {selectedTool.status === 'active' ? 'Disable tool' : 'Enable tool'}
                  </Button>
                </div>

                <section className="rounded-xl border border-red-500/25 bg-red-500/5 p-4">
                  <h3 className="text-sm font-semibold text-red-100">Danger zone</h3>
                  <p className="mt-1 text-xs leading-5 text-red-200/80">Delete this tool permanently.</p>
                  <Button className="mt-4 w-full" variant="destructive" size="sm" onClick={handleDeleteTool} loading={busyToolId === selectedTool.id || deleteToolMutation.isPending}>
                    <Trash2 className="mr-2 h-4 w-4" />
                    Delete tool
                  </Button>
                </section>
              </aside>

              <main className="space-y-5">
                <Section title="General" description="Edit customer-safe tool metadata. Structural configuration stays managed by the platform.">
                  <div className="grid gap-3 md:grid-cols-2">
                    <Input value={editName} onChange={(event) => setEditName(event.target.value)} placeholder="Tool name" />
                    <Select
                      value={editRiskLevel}
                      onChange={(event) => setEditRiskLevel(event.target.value)}
                      options={[
                        { value: 'low', label: 'Low risk' },
                        { value: 'medium', label: 'Medium risk' },
                        { value: 'high', label: 'High risk' },
                        { value: 'critical', label: 'Critical risk' },
                      ]}
                    />
                    <Input value={editDescription} onChange={(event) => setEditDescription(event.target.value)} placeholder="Description" />
                    <Input value={editTimeoutMs} onChange={(event) => setEditTimeoutMs(event.target.value)} placeholder="Timeout ms" inputMode="numeric" />
                  </div>
                </Section>

                {isMcpTool(selectedTool) && (
                  <Section title="MCP permissions" description="Choose which discovered MCP tools are exposed to agents.">
                    <div className="rounded-xl border border-border/80 bg-background/60 p-4">
                      <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
                        <div>
                          <p className="text-sm font-medium text-white">Discovered tools</p>
                          <p className="mt-1 text-xs text-muted">
                            {discoveredTools.length} found · {counts.allow} allow · {counts.review} review · {counts.deny} deny
                          </p>
                        </div>
                        <Button size="sm" variant="outline" onClick={handleRefreshMcp} loading={busyToolId === selectedTool.id}>
                          <RefreshCw className="mr-2 h-3.5 w-3.5" />
                          Refresh
                        </Button>
                      </div>

                      <div className="mt-4 flex flex-wrap gap-2">
                        <Button size="sm" onClick={() => handleBulkPermission('allow')} loading={permissionSavingKey === 'bulk:allow'}>
                          Allow all
                        </Button>
                        <Button size="sm" variant="outline" onClick={() => handleBulkPermission('review')} loading={permissionSavingKey === 'bulk:review'}>
                          Review all
                        </Button>
                        <Button size="sm" variant="outline" onClick={() => handleBulkPermission('deny')} loading={permissionSavingKey === 'bulk:deny'}>
                          Deny all
                        </Button>
                      </div>

                      <div className="mt-4 max-h-72 space-y-2 overflow-y-auto pr-1">
                        {discoveredTools.length === 0 ? (
                          <p className="rounded-lg border border-border/70 bg-surface/50 p-3 text-sm text-muted">No discovered MCP tools yet. Refresh to load available tools.</p>
                        ) : discoveredTools.map((item) => {
                          const mode = getPermissionMode(item)
                          return (
                            <div key={item.name} className="grid gap-3 rounded-lg border border-border/70 bg-surface/60 p-3 lg:grid-cols-[minmax(0,1fr)_auto] lg:items-center">
                              <div className="min-w-0">
                                <div className="flex flex-wrap items-center gap-2">
                                  <p className="break-words text-sm font-medium text-white">{item.title || item.name}</p>
                                  <PermissionBadge mode={mode} />
                                </div>
                                <p className="mt-1 break-all font-mono text-[10px] text-muted">{item.name}</p>
                              </div>
                              <div className="flex flex-wrap gap-2 lg:justify-end">
                                <Button size="sm" variant={mode === 'allow' ? 'default' : 'outline'} onClick={() => handleSinglePermission(item.name, 'allow')} loading={permissionSavingKey === `${item.name}:allow`}>
                                  Allow
                                </Button>
                                <Button size="sm" variant={mode === 'review' ? 'secondary' : 'outline'} onClick={() => handleSinglePermission(item.name, 'review')} loading={permissionSavingKey === `${item.name}:review`}>
                                  Review
                                </Button>
                                <Button size="sm" variant={mode === 'deny' ? 'destructive' : 'outline'} onClick={() => handleSinglePermission(item.name, 'deny')} loading={permissionSavingKey === `${item.name}:deny`}>
                                  Deny
                                </Button>
                              </div>
                            </div>
                          )
                        })}
                      </div>
                    </div>
                  </Section>
                )}
              </main>
            </div>

            <div className="sticky bottom-0 -mx-1 mt-6 flex justify-end gap-2 border-t border-border bg-surface/95 px-1 py-4 backdrop-blur">
              <Button variant="outline" onClick={closeToolModal}>Cancel</Button>
              <Button onClick={handleSaveTool} loading={updateToolMutation.isPending}>
                <ShieldCheck className="mr-2 h-4 w-4" />
                Save changes
              </Button>
            </div>
          </div>
        )}
      </Dialog>
    </MinimalShell>
  )
}
