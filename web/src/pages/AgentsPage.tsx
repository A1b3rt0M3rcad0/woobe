import { useMemo, useState, type ReactNode } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { useAgents } from '@/features/agents/hooks'
import { LoadingState } from '@/components/common/LoadingState'
import { ErrorState } from '@/components/common/ErrorState'
import { StatusBadge } from '@/components/common/StatusBadge'
import { Input } from '@/components/ui/Input'
import { ArrowRight, Bot, Plus, Search } from 'lucide-react'
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

export default function AgentsPage() {
  const { organizationId, projectId } = useParams<{ organizationId?: string; projectId: string }>()
  const navigate = useNavigate()
  const { data: agents, isLoading, isError, error, refetch } = useAgents(projectId)
  const [query, setQuery] = useState('')

  const p = (projectId: string, ...segments: string[]) => orgProjectPath(organizationId, projectId, ...segments)
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
        {visibleAgents.map((agent: Agent) => (
          <button
            key={agent.id}
            type="button"
            aria-label={`Open agent ${agent.name}`}
            onClick={() => navigate(p(projectId!, 'agents', agent.id))}
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
              Instructions, model, knowledge and tool configuration for runtime use.
            </span>

            <span className="mt-auto flex w-full items-center justify-between pt-5 text-sm font-medium text-primary-light transition-colors duration-200 group-hover:text-white">
              Open agent
              <ArrowRight className="h-3.5 w-3.5 transition-transform duration-200 group-hover:translate-x-0.5" />
            </span>
          </button>
        ))}

        <CreateCard
          title="New agent"
          description="Create a production agent"
          onClick={() => navigate(p(projectId!, 'agents', 'new'))}
        />
      </div>
    </MinimalShell>
  )
}
