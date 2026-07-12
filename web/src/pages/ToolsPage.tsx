import { useMemo, useState, type ReactNode } from 'react'
import { useParams } from 'react-router-dom'
import { Archive, Plus, RefreshCw, ShieldCheck, Trash2, Wrench } from 'lucide-react'
import { toast } from 'sonner'
import { ErrorState } from '@/components/common/ErrorState'
import { LoadingState } from '@/components/common/LoadingState'
import { ResourceCard, ResourcePill } from '@/components/common/OperationalResourceCard'
import {
  ResourceEmptyState,
  ResourcePage,
  ResourceSearch,
  ResourceSectionHeader,
  ResourceTabs,
  ResourceToolbar,
} from '@/components/common/ResourcePage'
import { StatusBadge } from '@/components/common/StatusBadge'
import { Button } from '@/components/ui/Button'
import { Dialog } from '@/components/ui/Dialog'
import { Input } from '@/components/ui/Input'
import { Select } from '@/components/ui/Select'
import {
  bulkUpdateMcpToolPermissions,
  getToolUsageImpact,
  refreshMcpTools,
  updateMcpToolPermissions,
  type ToolUsageImpact,
} from '@/features/tools/api'
import { useDeleteTool, useTools, useUpdateTool, useUpdateToolStatus } from '@/features/tools/hooks'
import type { DiscoveredMcpTool, McpToolConfig, McpToolPermissionMode, Tool } from '@/features/tools/types'
import { ToolsCreateDialog } from '@/pages/ToolsCreateDialog'

type ToolStatusFilter = 'all' | 'active' | 'inactive' | 'deprecated'
type ToolProtocolFilter = 'all' | 'mcp' | 'http' | 'other'
type ToolRiskFilter = 'all' | 'low' | 'medium' | 'high' | 'critical'

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

function protocolGroup(tool: Tool): Exclude<ToolProtocolFilter, 'all'> {
  if (isMcpTool(tool)) return 'mcp'
  const protocol = String(tool.type).toLowerCase()
  if (protocol.includes('http') || protocol === 'api' || protocol === 'webhook') return 'http'
  return 'other'
}

function formatDate(value?: string | null) {
  return value ? new Date(value).toLocaleString() : 'Not recorded'
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

function ImpactStat({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-lg border border-border/80 bg-background/60 p-3">
      <p className="text-[10px] uppercase tracking-wider text-muted">{label}</p>
      <p className="mt-1 text-lg font-semibold text-white">{value}</p>
    </div>
  )
}

export default function ToolsPage() {
  const { projectId } = useParams<{ projectId: string }>()
  const { data: tools, isLoading, isError, error, refetch } = useTools(projectId)
  const updateToolMutation = useUpdateTool()
  const updateToolStatusMutation = useUpdateToolStatus()
  const deleteToolMutation = useDeleteTool()
  const [showCreate, setShowCreate] = useState(false)
  const [query, setQuery] = useState('')
  const [statusFilter, setStatusFilter] = useState<ToolStatusFilter>('all')
  const [protocolFilter, setProtocolFilter] = useState<ToolProtocolFilter>('all')
  const [riskFilter, setRiskFilter] = useState<ToolRiskFilter>('all')
  const [selectedToolId, setSelectedToolId] = useState<string | null>(null)
  const [busyToolId, setBusyToolId] = useState<string | null>(null)
  const [permissionSavingKey, setPermissionSavingKey] = useState<string | null>(null)
  const [editName, setEditName] = useState('')
  const [editDescription, setEditDescription] = useState('')
  const [editRiskLevel, setEditRiskLevel] = useState('')
  const [editTimeoutMs, setEditTimeoutMs] = useState('')
  const [usageImpact, setUsageImpact] = useState<ToolUsageImpact | null>(null)
  const [showLifecycleDialog, setShowLifecycleDialog] = useState(false)
  const [lifecycleBusy, setLifecycleBusy] = useState(false)

  const items = tools ?? []
  const selectedTool = items.find((tool) => tool.id === selectedToolId) ?? null
  const selectedToolRetired = selectedTool?.status === 'deprecated'
  const discoveredTools = selectedTool ? getDiscoveredTools(selectedTool) : []
  const counts = permissionCounts(discoveredTools)

  const visibleTools = useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase()
    return items.filter((tool) => (
      (statusFilter === 'all' || tool.status?.toLowerCase() === statusFilter)
      && (protocolFilter === 'all' || protocolGroup(tool) === protocolFilter)
      && (riskFilter === 'all' || tool.risk_level?.toLowerCase() === riskFilter)
      && (!normalizedQuery || [
        tool.name,
        tool.description ?? '',
        String(tool.type),
        tool.status ?? '',
        tool.risk_level ?? '',
      ].some((value) => value.toLowerCase().includes(normalizedQuery)))
    ))
  }, [items, protocolFilter, query, riskFilter, statusFilter])

  const statusCounts = useMemo(() => ({
    all: items.length,
    active: items.filter((tool) => tool.status?.toLowerCase() === 'active').length,
    inactive: items.filter((tool) => tool.status?.toLowerCase() === 'inactive').length,
    deprecated: items.filter((tool) => tool.status?.toLowerCase() === 'deprecated').length,
  }), [items])

  const openToolModal = (tool: Tool) => {
    setSelectedToolId(tool.id)
    setEditName(tool.name)
    setEditDescription(tool.description || '')
    setEditRiskLevel(tool.risk_level || 'low')
    setEditTimeoutMs(tool.timeout_ms ? String(tool.timeout_ms) : '')
  }

  const closeLifecycleDialog = () => {
    setShowLifecycleDialog(false)
    setUsageImpact(null)
  }

  const closeToolModal = () => {
    setSelectedToolId(null)
    setBusyToolId(null)
    setPermissionSavingKey(null)
    closeLifecycleDialog()
  }

  const handleSaveTool = async () => {
    if (!selectedTool || selectedToolRetired) return

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
    const nextStatus = selectedTool.status === 'deprecated'
      ? 'active'
      : selectedTool.status === 'active'
        ? 'inactive'
        : 'active'

    try {
      setBusyToolId(selectedTool.id)
      await updateToolStatusMutation.mutateAsync({
        toolId: selectedTool.id,
        data: { status: nextStatus },
      })
      await refetch()
      toast.success(
        selectedTool.status === 'deprecated'
          ? 'Tool reactivated'
          : nextStatus === 'active'
            ? 'Tool enabled'
            : 'Tool disabled',
      )
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to update tool status')
    } finally {
      setBusyToolId(null)
    }
  }

  const handleRefreshMcp = async () => {
    if (!selectedTool || selectedToolRetired) return

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
    if (!selectedTool || selectedToolRetired) return

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
    if (!selectedTool || selectedToolRetired) return

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

  const handleReviewRemoval = async () => {
    if (!selectedTool) return

    try {
      setBusyToolId(selectedTool.id)
      const impact = await getToolUsageImpact(selectedTool.id)
      setUsageImpact(impact)
      setShowLifecycleDialog(true)
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to inspect Tool usage')
    } finally {
      setBusyToolId(null)
    }
  }

  const handleConfirmLifecycle = async () => {
    if (!selectedTool || !usageImpact) return

    try {
      setLifecycleBusy(true)
      if (usageImpact.can_delete) {
        await deleteToolMutation.mutateAsync(selectedTool.id)
        await refetch()
        toast.success('Tool deleted permanently')
      } else if (usageImpact.can_retire) {
        await updateToolStatusMutation.mutateAsync({
          toolId: selectedTool.id,
          data: { status: 'deprecated' },
        })
        await refetch()
        toast.success('Tool retired. Existing Agent versions were preserved.')
      } else {
        return
      }
      closeToolModal()
    } catch (err) {
      try {
        const latestImpact = await getToolUsageImpact(selectedTool.id)
        setUsageImpact(latestImpact)
      } catch {
        // Preserve the original lifecycle error if impact refresh also fails.
      }
      toast.error(err instanceof Error ? err.message : 'Failed to update Tool lifecycle')
    } finally {
      setLifecycleBusy(false)
    }
  }

  if (!projectId) return <ErrorState message="Project not found" />

  const hasFilters = Boolean(query.trim()) || statusFilter !== 'all' || protocolFilter !== 'all' || riskFilter !== 'all'
  const resultCount = hasFilters ? `${visibleTools.length} of ${items.length}` : items.length
  const lifecycleTitle = usageImpact?.can_delete
    ? 'Delete Tool permanently'
    : usageImpact?.can_retire
      ? 'Retire Tool'
      : 'Tool is still in use'

  return (
    <ResourcePage
      title="Tools"
      description="Connect and govern external capabilities available to Agents in this Project."
      action={(
        <Button type="button" onClick={() => setShowCreate(true)}>
          <Plus className="mr-2 h-4 w-4" />
          New Tool
        </Button>
      )}
    >
      <ResourceToolbar>
        <ResourceTabs
          value={statusFilter}
          onChange={setStatusFilter}
          label="Filter Tools by status"
          tabs={[
            { value: 'all', label: 'All', count: statusCounts.all },
            { value: 'active', label: 'Active', count: statusCounts.active },
            { value: 'inactive', label: 'Inactive', count: statusCounts.inactive },
            { value: 'deprecated', label: 'Retired', count: statusCounts.deprecated },
          ]}
        />
        <div className="grid gap-3 lg:grid-cols-[minmax(0,1fr)_180px_160px]">
          <ResourceSearch value={query} onChange={setQuery} placeholder="Search Tools, protocols or risk..." label="Search Tools" />
          <Select
            value={protocolFilter}
            onChange={(event) => setProtocolFilter(event.target.value as ToolProtocolFilter)}
            className="h-10"
            options={[
              { value: 'all', label: 'All protocols' },
              { value: 'mcp', label: 'MCP' },
              { value: 'http', label: 'HTTP / API' },
              { value: 'other', label: 'Other' },
            ]}
          />
          <Select
            value={riskFilter}
            onChange={(event) => setRiskFilter(event.target.value as ToolRiskFilter)}
            className="h-10"
            options={[
              { value: 'all', label: 'All risks' },
              { value: 'low', label: 'Low risk' },
              { value: 'medium', label: 'Medium risk' },
              { value: 'high', label: 'High risk' },
              { value: 'critical', label: 'Critical risk' },
            ]}
          />
        </div>
      </ResourceToolbar>

      <section>
        <ResourceSectionHeader
          title="Tools"
          description="Open a Tool to review its runtime status, configuration and permissions."
          count={resultCount}
        />

        {isLoading ? (
          <LoadingState message="Loading Tools" variant="panel" layout="compact-cards" />
        ) : isError ? (
          <ErrorState error={error} onRetry={refetch} className="rounded-xl border border-border/80 bg-surface/40 py-10" />
        ) : visibleTools.length > 0 ? (
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
            {visibleTools.map((tool: Tool) => {
              const discoveredCount = isMcpTool(tool) ? getDiscoveredTools(tool).length : 0
              return (
                <ResourceCard
                  key={tool.id}
                  aria-label={`Open Tool settings for ${tool.name}`}
                  onClick={() => openToolModal(tool)}
                  icon={<Wrench className="h-4 w-4" />}
                  title={tool.name}
                  subtitle={tool.description || String(tool.type)}
                  status={<StatusBadge status={tool.status} size="compact" />}
                  metadata={(
                    <>
                      <ResourcePill>{String(tool.type)}</ResourcePill>
                      {tool.risk_level && (
                        <ResourcePill tone={tool.risk_level === 'critical' || tool.risk_level === 'high' ? 'danger' : 'default'}>
                          Risk · {tool.risk_level}
                        </ResourcePill>
                      )}
                      {isMcpTool(tool) && <ResourcePill tone="primary">MCP · {discoveredCount} discovered</ResourcePill>}
                    </>
                  )}
                  footer={`Updated · ${formatDate(tool.updated_at || tool.created_at)}`}
                />
              )
            })}
          </div>
        ) : (
          <ResourceEmptyState
            icon={<Wrench className="h-4 w-4" />}
            title={items.length === 0 ? 'No Tools yet' : 'No Tools found'}
            description={items.length === 0
              ? 'Connect the first external capability for this Project.'
              : 'Adjust the search or clear the active filters.'}
            action={hasFilters ? (
              <Button type="button" size="sm" variant="outline" onClick={() => { setQuery(''); setStatusFilter('all'); setProtocolFilter('all'); setRiskFilter('all') }}>
                Clear filters
              </Button>
            ) : undefined}
          />
        )}
      </section>

      <ToolsCreateDialog open={showCreate} projectId={projectId} onClose={() => setShowCreate(false)} onCreated={async () => { await refetch(); setShowCreate(false) }} />

      <Dialog open={Boolean(selectedTool)} onClose={closeToolModal} title="Tool settings" className="max-h-[calc(100svh-2rem)] max-w-5xl overflow-hidden">
        {selectedTool && (
          <div className="max-h-[calc(100svh-8rem)] overflow-y-auto pr-1">
            <div className="grid gap-5 lg:grid-cols-[280px_minmax(0,1fr)]">
              <aside className="space-y-4 lg:sticky lg:top-0 lg:self-start">
                <div className="rounded-xl border border-border/90 bg-surface/70 p-4">
                  <div className="flex h-11 w-11 items-center justify-center rounded-xl border border-border bg-background text-primary-light"><Wrench className="h-5 w-5" /></div>
                  <div className="mt-5 min-w-0"><h2 className="truncate text-base font-semibold text-white">{selectedTool.name}</h2><p className="mt-1 truncate text-sm text-muted">{String(selectedTool.type)}</p></div>
                  <div className="mt-5 flex flex-wrap gap-2"><StatusBadge status={selectedTool.status} /><ResourcePill tone={editRiskLevel === 'critical' || editRiskLevel === 'high' ? 'danger' : 'default'}>Risk · {editRiskLevel || 'unset'}</ResourcePill>{isMcpTool(selectedTool) && <ResourcePill tone="primary">MCP</ResourcePill>}</div>
                </div>

                <div className="rounded-xl border border-border/90 bg-background/60 p-4">
                  <p className="text-sm font-semibold text-white">Runtime status</p>
                  <p className="mt-1 text-xs leading-5 text-muted">
                    {selectedToolRetired
                      ? 'This Tool is retired globally and unavailable for new Agent bindings. Existing versioned usage remains preserved.'
                      : 'Control whether this tool can be used by agents.'}
                  </p>
                  <Button className="mt-4 w-full" size="sm" variant="outline" onClick={handleToggleStatus} loading={busyToolId === selectedTool.id || updateToolStatusMutation.isPending}>
                    {selectedToolRetired ? 'Reactivate tool' : selectedTool.status === 'active' ? 'Disable tool' : 'Enable tool'}
                  </Button>
                </div>

                <section className="rounded-xl border border-red-500/25 bg-red-500/5 p-4">
                  <h3 className="text-sm font-semibold text-red-100">Danger zone</h3>
                  <p className="mt-1 text-xs leading-5 text-red-200/80">Review Agent references before retiring or permanently deleting this Tool.</p>
                  <Button className="mt-4 w-full" variant="destructive" size="sm" onClick={handleReviewRemoval} loading={busyToolId === selectedTool.id}>
                    <Trash2 className="mr-2 h-4 w-4" />Review removal
                  </Button>
                </section>
              </aside>

              <main className="space-y-5">
                <Section title="General" description={selectedToolRetired ? 'Retired Tools are read-only until reactivated.' : 'Edit customer-safe tool metadata. Structural configuration stays managed by the platform.'}>
                  <div className="grid gap-3 md:grid-cols-2">
                    <Input disabled={selectedToolRetired} value={editName} onChange={(event) => setEditName(event.target.value)} placeholder="Tool name" />
                    <Select disabled={selectedToolRetired} value={editRiskLevel} onChange={(event) => setEditRiskLevel(event.target.value)} options={[{ value: 'low', label: 'Low risk' }, { value: 'medium', label: 'Medium risk' }, { value: 'high', label: 'High risk' }, { value: 'critical', label: 'Critical risk' }]} />
                    <Input disabled={selectedToolRetired} value={editDescription} onChange={(event) => setEditDescription(event.target.value)} placeholder="Description" />
                    <Input disabled={selectedToolRetired} value={editTimeoutMs} onChange={(event) => setEditTimeoutMs(event.target.value)} placeholder="Timeout ms" inputMode="numeric" />
                  </div>
                </Section>

                {isMcpTool(selectedTool) && (
                  <Section title="MCP permissions" description={selectedToolRetired ? 'Global defaults are read-only while the Tool is retired. Agent-scoped permissions remain versioned inside each Agent.' : 'Choose which discovered MCP tools are exposed to agents.'}>
                    <div className="rounded-xl border border-border/80 bg-background/60 p-4">
                      <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between"><div><p className="text-sm font-medium text-white">Discovered tools</p><p className="mt-1 text-xs text-muted">{discoveredTools.length} found · {counts.allow} allow · {counts.review} review · {counts.deny} deny</p></div><Button disabled={selectedToolRetired} size="sm" variant="outline" onClick={handleRefreshMcp} loading={busyToolId === selectedTool.id}><RefreshCw className="mr-2 h-3.5 w-3.5" />Refresh</Button></div>
                      <div className="mt-4 flex flex-wrap gap-2"><Button disabled={selectedToolRetired} size="sm" onClick={() => handleBulkPermission('allow')} loading={permissionSavingKey === 'bulk:allow'}>Allow all</Button><Button disabled={selectedToolRetired} size="sm" variant="outline" onClick={() => handleBulkPermission('review')} loading={permissionSavingKey === 'bulk:review'}>Review all</Button><Button disabled={selectedToolRetired} size="sm" variant="outline" onClick={() => handleBulkPermission('deny')} loading={permissionSavingKey === 'bulk:deny'}>Deny all</Button></div>
                      <div className="mt-4 max-h-72 space-y-2 overflow-y-auto pr-1">{discoveredTools.length === 0 ? <p className="rounded-lg border border-border/70 bg-surface/50 p-3 text-sm text-muted">No discovered MCP tools yet. Refresh to load available tools.</p> : discoveredTools.map((item) => { const mode = getPermissionMode(item); return <div key={item.name} className="grid gap-3 rounded-lg border border-border/70 bg-surface/60 p-3 lg:grid-cols-[minmax(0,1fr)_auto] lg:items-center"><div className="min-w-0"><div className="flex flex-wrap items-center gap-2"><p className="break-words text-sm font-medium text-white">{item.title || item.name}</p><PermissionBadge mode={mode} /></div><p className="mt-1 break-all font-mono text-[10px] text-muted">{item.name}</p></div><div className="flex flex-wrap gap-2 lg:justify-end"><Button disabled={selectedToolRetired} size="sm" variant={mode === 'allow' ? 'default' : 'outline'} onClick={() => handleSinglePermission(item.name, 'allow')} loading={permissionSavingKey === `${item.name}:allow`}>Allow</Button><Button disabled={selectedToolRetired} size="sm" variant={mode === 'review' ? 'secondary' : 'outline'} onClick={() => handleSinglePermission(item.name, 'review')} loading={permissionSavingKey === `${item.name}:review`}>Review</Button><Button disabled={selectedToolRetired} size="sm" variant={mode === 'deny' ? 'destructive' : 'outline'} onClick={() => handleSinglePermission(item.name, 'deny')} loading={permissionSavingKey === `${item.name}:deny`}>Deny</Button></div></div> })}</div>
                    </div>
                  </Section>
                )}
              </main>
            </div>

            <div className="sticky bottom-0 -mx-1 mt-6 flex justify-end gap-2 border-t border-border bg-surface/95 px-1 py-4 backdrop-blur"><Button variant="outline" onClick={closeToolModal}>Cancel</Button><Button disabled={selectedToolRetired} onClick={handleSaveTool} loading={updateToolMutation.isPending}><ShieldCheck className="mr-2 h-4 w-4" />Save changes</Button></div>
          </div>
        )}
      </Dialog>

      <Dialog open={showLifecycleDialog && Boolean(usageImpact)} onClose={closeLifecycleDialog} title={lifecycleTitle} className="max-w-2xl">
        {usageImpact && selectedTool && (
          <div className="space-y-5">
            <div>
              <p className="text-sm font-medium text-white">{selectedTool.name}</p>
              <p className="mt-2 text-sm leading-6 text-muted">
                {usageImpact.can_delete
                  ? 'No Agent version references this Tool. Permanent deletion is available and cannot be undone.'
                  : usageImpact.can_retire
                    ? 'This Tool is referenced by Agent versions. Retiring it prevents new Agent bindings while preserving existing Draft, Staging, Production and historical Release snapshots.'
                    : 'This Tool is already retired and still referenced. Remove it from every Agent version before permanent deletion becomes available.'}
              </p>
            </div>

            <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
              <ImpactStat label="Draft Agents" value={usageImpact.draft_agents} />
              <ImpactStat label="Staging Agents" value={usageImpact.staging_agents} />
              <ImpactStat label="Production Agents" value={usageImpact.production_agents} />
              <ImpactStat label="Historical Releases" value={usageImpact.historical_releases} />
            </div>

            <div className="rounded-lg border border-border/80 bg-background/50 p-3 text-xs leading-5 text-muted">
              Total version references: <span className="font-medium text-white">{usageImpact.total_references}</span>
            </div>

            <div className="flex justify-end gap-2 border-t border-border pt-4">
              <Button variant="outline" onClick={closeLifecycleDialog}>Cancel</Button>
              {usageImpact.can_delete && (
                <Button variant="destructive" onClick={handleConfirmLifecycle} loading={lifecycleBusy || deleteToolMutation.isPending}>
                  <Trash2 className="mr-2 h-4 w-4" />Delete permanently
                </Button>
              )}
              {!usageImpact.can_delete && usageImpact.can_retire && (
                <Button onClick={handleConfirmLifecycle} loading={lifecycleBusy || updateToolStatusMutation.isPending}>
                  <Archive className="mr-2 h-4 w-4" />Retire tool
                </Button>
              )}
            </div>
          </div>
        )}
      </Dialog>
    </ResourcePage>
  )
}
