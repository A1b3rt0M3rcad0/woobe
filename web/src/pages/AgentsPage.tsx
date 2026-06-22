import { useNavigate, useParams } from 'react-router-dom'
import { useAgents } from '@/features/agents/hooks'
import { ProjectPageShell } from '@/components/common/ProjectPageShell'
import { GuidedEmptyState } from '@/components/common/GuidedEmptyState'
import { ResourceCard } from '@/components/common/ResourceCard'
import { ResourceSummaryCard } from '@/components/common/ResourceSummaryCard'
import { LoadingState } from '@/components/common/LoadingState'
import { ErrorState } from '@/components/common/ErrorState'
import { Button } from '@/components/ui/Button'
import { StatusBadge } from '@/components/common/StatusBadge'
import { Bot, Boxes, BrainCircuit, Plus, Settings, TestTube2 } from 'lucide-react'
import { orgProjectPath } from '@/lib/constants/routes'
import type { Agent } from '@/features/agents/types'

function providerLabel(agent: Agent) {
  return [agent.provider, agent.model].filter(Boolean).join(' / ') || 'Model not configured'
}

export default function AgentsPage() {
  const { organizationId, projectId } = useParams<{ organizationId?: string; projectId: string }>()
  const navigate = useNavigate()
  const { data: agents, isLoading, isError, error, refetch } = useAgents(projectId)

  const p = (projectId: string, ...segments: string[]) => orgProjectPath(organizationId, projectId, ...segments)

  if (isLoading) return <LoadingState />
  if (isError) return <ErrorState error={error} onRetry={refetch} />

  const items = agents ?? []
  const activeAgents = items.filter((agent) => agent.status === 'active').length
  const configuredModels = new Set(items.map((agent) => agent.model).filter(Boolean)).size

  return (
    <ProjectPageShell
      eyebrow="Build"
      title="Agents"
      description="Create production agents that combine instructions, models, knowledge and tools."
      actions={
        <Button onClick={() => navigate(p(projectId!, 'agents', 'new'))}>
          <Plus className="mr-2 h-4 w-4" />
          Create agent
        </Button>
      }
    >
      <div className="grid gap-4 md:grid-cols-3">
        <ResourceSummaryCard label="Agents" value={items.length} detail="Configured in this project" icon={<Bot className="h-5 w-5" />} />
        <ResourceSummaryCard label="Active" value={activeAgents} detail="Ready for runtime use" icon={<TestTube2 className="h-5 w-5" />} />
        <ResourceSummaryCard label="Models" value={configuredModels} detail="Unique configured models" icon={<BrainCircuit className="h-5 w-5" />} />
      </div>

      {items.length === 0 ? (
        <GuidedEmptyState
          icon={<Bot className="h-6 w-6" />}
          title="No agents yet"
          description="Create an agent to connect a model, write instructions, attach knowledge and enable tools."
          actionLabel="Create agent"
          onAction={() => navigate(p(projectId!, 'agents', 'new'))}
          next={["Choose a model", "Write instructions", "Test from the agent page"]}
        />
      ) : (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
          {items.map((agent: Agent) => (
            <ResourceCard
              key={agent.id}
              icon={<Bot className="h-5 w-5" />}
              title={agent.name}
              description={providerLabel(agent)}
              badge={<StatusBadge status={agent.status} />}
              metadata={
                <div className="rounded-lg border border-border/70 bg-background/70 p-3 text-sm text-muted">
                  <div className="flex items-center gap-2">
                    <Boxes className="h-4 w-4 text-primary-light" />
                    <span>Attach knowledge and tools from the agent settings.</span>
                  </div>
                </div>
              }
              actions={
                <>
                  <Button className="flex-1" size="sm" onClick={() => navigate(p(projectId!, 'agents', agent.id))}>
                    <Settings className="mr-1.5 h-3.5 w-3.5" />
                    Open agent
                  </Button>
                  <Button size="sm" variant="outline" onClick={() => navigate(p(projectId!, 'agents', agent.id, 'playground'))}>
                    <TestTube2 className="mr-1.5 h-3.5 w-3.5" />
                    Test
                  </Button>
                </>
              }
            />
          ))}
        </div>
      )}
    </ProjectPageShell>
  )
}
