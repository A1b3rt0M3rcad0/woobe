import { useEffect, useMemo, useState } from 'react'
import { useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { Bot, Plus } from 'lucide-react'

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
import { CreateAgentFlowModal } from '@/features/agents/components/CreateAgentFlowModal'
import { FirstAgentInstructionsDialog } from '@/features/agents/components/FirstAgentInstructionsDialog'
import { useAgents } from '@/features/agents/hooks'
import type { Agent } from '@/features/agents/types'
import { orgProjectPath } from '@/lib/constants/routes'

type AgentStatusFilter = 'all' | 'active' | 'inactive' | 'archived'

function providerLabel(agent: Agent) {
  return [agent.provider, agent.model].filter(Boolean).join(' · ') || 'Model not configured'
}

function formatDate(value?: string | null) {
  return value ? new Date(value).toLocaleString() : 'Not recorded'
}

export default function AgentsPage() {
  const { organizationId, projectId } = useParams<{ organizationId?: string; projectId: string }>()
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()
  const { data: agents, isLoading, isError, error, refetch } = useAgents(projectId)
  const [query, setQuery] = useState('')
  const [statusFilter, setStatusFilter] = useState<AgentStatusFilter>('all')
  const [showCreateAgent, setShowCreateAgent] = useState(false)
  const [pendingAgent, setPendingAgent] = useState<Agent | null>(null)

  const p = (currentProjectId: string, ...segments: string[]) => orgProjectPath(organizationId, currentProjectId, ...segments)
  const items = agents ?? []

  useEffect(() => {
    if (searchParams.get('create') !== '1') return

    setShowCreateAgent(true)
    const next = new URLSearchParams(searchParams)
    next.delete('create')
    setSearchParams(next, { replace: true })
  }, [searchParams, setSearchParams])

  const statusCounts = useMemo(() => ({
    all: items.length,
    active: items.filter((agent) => agent.status?.toLowerCase() === 'active').length,
    inactive: items.filter((agent) => agent.status?.toLowerCase() === 'inactive').length,
    archived: items.filter((agent) => agent.status?.toLowerCase() === 'archived').length,
  }), [items])

  const visibleAgents = useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase()
    return items.filter((agent) => {
      const matchesStatus = statusFilter === 'all' || agent.status?.toLowerCase() === statusFilter
      const matchesQuery = !normalizedQuery || [
        agent.name,
        agent.description ?? '',
        agent.provider ?? '',
        agent.model ?? '',
        agent.status ?? '',
        agent.session_mode ?? '',
      ].some((value) => value.toLowerCase().includes(normalizedQuery))
      return matchesStatus && matchesQuery
    })
  }, [items, query, statusFilter])

  if (!projectId) return <ErrorState message="Project not found" />

  const hasFilters = Boolean(query.trim()) || statusFilter !== 'all'
  const resultCount = hasFilters ? `${visibleAgents.length} of ${items.length}` : items.length
  const openPlayground = (agent: Agent) => {
    setPendingAgent(null)
    navigate(p(projectId, 'agents', agent.id, 'playground'))
  }

  return (
    <ResourcePage
      title="Agents"
      description="Create and operate model-backed Agents for this Project."
      action={(
        <Button type="button" onClick={() => setShowCreateAgent(true)}>
          <Plus className="mr-2 h-4 w-4" />
          Create Agent
        </Button>
      )}
    >
      <ResourceToolbar>
        <ResourceTabs
          value={statusFilter}
          onChange={setStatusFilter}
          label="Filter Agents by status"
          tabs={[
            { value: 'all', label: 'All', count: statusCounts.all },
            { value: 'active', label: 'Active', count: statusCounts.active },
            { value: 'inactive', label: 'Inactive', count: statusCounts.inactive },
            { value: 'archived', label: 'Archived', count: statusCounts.archived },
          ]}
        />
        <ResourceSearch
          value={query}
          onChange={setQuery}
          placeholder="Search Agents, models or providers..."
          label="Search Agents"
        />
      </ResourceToolbar>

      <section>
        <ResourceSectionHeader
          title="Agents"
          description="Open an Agent to test, configure and release it."
          count={resultCount}
        />

        {isLoading ? (
          <LoadingState message="Loading Agents" variant="panel" layout="compact-cards" />
        ) : isError ? (
          <ErrorState error={error} onRetry={refetch} className="rounded-xl border border-border/80 bg-surface/40 py-10" />
        ) : visibleAgents.length > 0 ? (
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
            {visibleAgents.map((agent) => (
              <ResourceCard
                key={agent.id}
                aria-label={`Open Agent playground for ${agent.name}`}
                onClick={() => navigate(p(projectId, 'agents', agent.id, 'playground'))}
                icon={<Bot className="h-4 w-4" />}
                title={agent.name}
                subtitle={providerLabel(agent)}
                status={<StatusBadge status={agent.status || 'inactive'} size="compact" />}
                metadata={agent.session_mode ? <ResourcePill tone="primary">{agent.session_mode}</ResourcePill> : undefined}
                footer={`Updated · ${formatDate(agent.updated_at || agent.created_at)}`}
              />
            ))}
          </div>
        ) : (
          <ResourceEmptyState
            icon={<Bot className="h-4 w-4" />}
            title={items.length === 0 ? 'Create your first Agent' : 'No Agents found'}
            description={items.length === 0
              ? 'Create an Agent with instructions, a provider connection and a reusable generation model.'
              : 'Adjust the search or clear the active status filter.'}
            action={items.length === 0 ? (
              <Button type="button" size="sm" onClick={() => setShowCreateAgent(true)}>
                Create Agent
              </Button>
            ) : hasFilters ? (
              <Button type="button" size="sm" variant="outline" onClick={() => { setQuery(''); setStatusFilter('all') }}>
                Clear filters
              </Button>
            ) : undefined}
          />
        )}
      </section>

      <CreateAgentFlowModal
        open={showCreateAgent}
        onClose={() => setShowCreateAgent(false)}
        projectId={projectId}
        onCreated={(agent) => {
          setShowCreateAgent(false)
          if (items.length === 0 && !agent.system_prompt?.trim()) {
            setPendingAgent(agent)
            return
          }
          openPlayground(agent)
        }}
      />

      <FirstAgentInstructionsDialog
        open={Boolean(pendingAgent)}
        agent={pendingAgent}
        onComplete={openPlayground}
      />
    </ResourcePage>
  )
}
