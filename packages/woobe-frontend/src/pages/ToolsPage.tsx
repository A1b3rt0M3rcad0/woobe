import { useMemo, useState } from 'react'
import { useParams } from 'react-router-dom'
import { Plus, Wrench } from 'lucide-react'
import { Button, Select } from '@woobe/ui'

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
import { ToolSettingsModal } from '@/features/tools/components/ToolSettingsModal'
import { useTools } from '@/features/tools/hooks'
import type { McpToolConfig, Tool } from '@/features/tools/types'
import { ToolsCreateDialog } from '@/pages/ToolsCreateDialog'

type ToolStatusFilter = 'all' | 'active' | 'inactive' | 'deprecated'
type ToolProtocolFilter = 'all' | 'mcp' | 'http' | 'other'
type ToolRiskFilter = 'all' | 'low' | 'medium' | 'high' | 'critical'

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

function discoveredMcpCount(tool: Tool): number {
  if (!isMcpTool(tool)) return 0
  const config = (tool.config || {}) as McpToolConfig
  return Array.isArray(config.discovered_tools) ? config.discovered_tools.length : 0
}

export default function ToolsPage() {
  const { projectId } = useParams<{ projectId: string }>()
  const { data: tools, isLoading, isError, error, refetch } = useTools(projectId)
  const [showCreate, setShowCreate] = useState(false)
  const [query, setQuery] = useState('')
  const [statusFilter, setStatusFilter] = useState<ToolStatusFilter>('all')
  const [protocolFilter, setProtocolFilter] = useState<ToolProtocolFilter>('all')
  const [riskFilter, setRiskFilter] = useState<ToolRiskFilter>('all')
  const [selectedToolId, setSelectedToolId] = useState<string | null>(null)

  const items = tools ?? []
  const selectedTool = items.find((tool) => tool.id === selectedToolId) ?? null

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

  if (!projectId) return <ErrorState message="Project not found" />

  const hasFilters = Boolean(query.trim()) || statusFilter !== 'all' || protocolFilter !== 'all' || riskFilter !== 'all'
  const resultCount = hasFilters ? `${visibleTools.length} of ${items.length}` : items.length

  return (
    <ResourcePage
      title="Tools"
      description="Connect and govern external capabilities available to Agents in this Project."
      action={(
        <Button type="button" onClick={() => setShowCreate(true)}>
          <Plus className="h-3.5 w-3.5" />
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
        <div className="grid gap-2.5 lg:grid-cols-[minmax(0,1fr)_180px_160px]">
          <ResourceSearch value={query} onChange={setQuery} placeholder="Search Tools, protocols or risk..." label="Search Tools" />
          <Select
            value={protocolFilter}
            onChange={(event) => setProtocolFilter(event.target.value as ToolProtocolFilter)}
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
          <ErrorState error={error} onRetry={refetch} className="rounded-container border border-border bg-surface/70 py-10" />
        ) : visibleTools.length > 0 ? (
          <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3">
            {visibleTools.map((tool) => (
              <ResourceCard
                key={tool.id}
                aria-label={`Open Tool settings for ${tool.name}`}
                onClick={() => setSelectedToolId(tool.id)}
                icon={<Wrench className="h-4 w-4" />}
                title={tool.name}
                subtitle={tool.description || String(tool.type)}
                status={<StatusBadge status={tool.status} size="compact" />}
                metadata={(
                  <>
                    <ResourcePill>{String(tool.type)}</ResourcePill>
                    {tool.risk_level ? (
                      <ResourcePill tone={tool.risk_level === 'critical' || tool.risk_level === 'high' ? 'danger' : 'default'}>
                        Risk · {tool.risk_level}
                      </ResourcePill>
                    ) : null}
                    {isMcpTool(tool) ? <ResourcePill tone="primary">MCP · {discoveredMcpCount(tool)} discovered</ResourcePill> : null}
                  </>
                )}
                footer={`Updated · ${formatDate(tool.updated_at || tool.created_at)}`}
              />
            ))}
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

      <ToolsCreateDialog
        open={showCreate}
        projectId={projectId}
        onClose={() => setShowCreate(false)}
        onCreated={async () => {
          await refetch()
          setShowCreate(false)
        }}
      />

      <ToolSettingsModal
        tool={selectedTool}
        projectControls
        onClose={() => setSelectedToolId(null)}
        onSaved={async () => { await refetch() }}
      />
    </ResourcePage>
  )
}
