import { useMemo, useState, type ReactNode } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { useAgents } from '@/features/agents/hooks'
import { CreateAgentFlowModal } from '@/features/agents/components/CreateAgentFlowModal'
import { LoadingState } from '@/components/common/LoadingState'
import { ErrorState } from '@/components/common/ErrorState'
import { StatusBadge } from '@/components/common/StatusBadge'
import { CreateResourceCard } from '@/components/common/CreateResourceCard'
import { Input } from '@/components/ui/Input'
import { ArrowRight, Bot, Search } from 'lucide-react'
import { orgProjectPath } from '@/lib/constants/routes'
import type { Agent } from '@/features/agents/types'

function providerLabel(agent: Agent) {
  return [agent.provider, agent.model].filter(Boolean).join(' / ') || 'Model not configured'
}

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

export default function AgentsPage() {
  const { organizationId, projectId } = useParams<{ organizationId?: string; projectId: string }>()
  const navigate = useNavigate()
  const { data: agents, isLoading, isError, error, refetch } = useAgents(projectId)
  const [query, setQuery] = useState('')
  const [showCreateAgent, setShowCreateAgent] = useState(false)

  const p = (currentProjectId: string, ...segments: string[]) => orgProjectPath(organizationId, currentProjectId, ...segments)
  const items = agents ?? []

  const visibleAgents = useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase()
    if (!normalizedQuery) return items

    return items.filter((agent) => (
      agent.name.toLowerCase().includes(normalizedQuery)
      || agent.provider?.toLowerCase().includes(normalizedQuery)
      || agent.model?.toLowerCase().includes(normalizedQuery)
      || agent.status?.toLowerCase().includes(normalizedQuery)
    ))
  }, [items, query])

  if (isLoading) return <LoadingState />
  if (isError) return <ErrorState error={error} onRetry={refetch} />
  if (!projectId) return <ErrorState message="Project not found" />

  const hasSearchMiss = query.trim().length > 0 && visibleAgents.length === 0

  return (
    <MinimalShell
      title="Agents"
      description="Create and operate model-backed agents for this project."
    >
      <div className="relative max-w-3xl">
        <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted" />
        <Input
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Search agents..."
          className="h-11 pl-9"
        />
      </div>

      {hasSearchMiss && (
        <div className="rounded-xl border border-border/80 bg-surface/50 px-5 py-4">
          <h2 className="text-sm font-semibold text-white">No agents found</h2>
          <p className="mt-1 text-sm text-muted">Create a new agent or adjust the search term.</p>
        </div>
      )}

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
        <CreateResourceCard
          title="New agent"
          description="Set up the provider, model and agent in one guided flow"
          onClick={() => setShowCreateAgent(true)}
        />

        {visibleAgents.map((agent: Agent) => (
          <button
            key={agent.id}
            type="button"
            aria-label={`Open agent playground for ${agent.name}`}
            onClick={() => navigate(p(projectId, 'agents', agent.id, 'playground'))}
            className="group flex min-h-[240px] flex-col rounded-xl border border-border/90 bg-surface/70 p-6 text-left transition-[border-color,background-color,box-shadow] duration-200 hover:border-primary/35 hover:bg-surface/85 hover:shadow-lg hover:shadow-primary/5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/30 focus-visible:ring-offset-2 focus-visible:ring-offset-background"
          >
            <span className="flex items-start justify-between gap-3">
              <span className="flex h-12 w-12 items-center justify-center rounded-xl border border-border bg-background text-primary-light shadow-sm transition-colors duration-200 group-hover:border-primary/30 group-hover:bg-primary/10">
                <Bot className="h-5 w-5" />
              </span>
              <StatusBadge status={agent.status} />
            </span>

            <span className="mt-6 block min-w-0">
              <span className="block truncate text-base font-semibold text-white">{agent.name}</span>
              <span className="mt-1 block truncate text-sm text-muted">{providerLabel(agent)}</span>
            </span>

            <span className="my-5 block h-px bg-border/80" />

            <span className="block min-h-[48px] text-sm leading-6 text-muted">
              Open the playground to test, edit and iterate on this agent.
            </span>

            <span className="mt-auto flex w-full items-center justify-between pt-5 text-sm font-medium text-primary-light transition-colors duration-200 group-hover:text-white">
              Open playground
              <ArrowRight className="h-3.5 w-3.5 transition-transform duration-200 group-hover:translate-x-0.5" />
            </span>
          </button>
        ))}
      </div>

      <CreateAgentFlowModal
        open={showCreateAgent}
        onClose={() => setShowCreateAgent(false)}
        projectId={projectId}
        onCreated={(agent) => {
          setShowCreateAgent(false)
          navigate(p(projectId, 'agents', agent.id, 'playground'))
        }}
      />
    </MinimalShell>
  )
}
