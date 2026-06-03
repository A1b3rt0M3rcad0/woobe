import { useNavigate, useParams } from 'react-router-dom'
import { useAgents } from '@/features/agents/hooks'
import { PageHeader } from '@/components/common/PageHeader'
import { LoadingState } from '@/components/common/LoadingState'
import { ErrorState } from '@/components/common/ErrorState'
import { EmptyState } from '@/components/common/EmptyState'
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { StatusBadge } from '@/components/common/StatusBadge'
import { Bot, Plus, Play, Settings } from 'lucide-react'
import { orgProjectPath } from '@/lib/constants/routes'
import type { Agent } from '@/features/agents/types'

export default function AgentsPage() {
  const { organizationId, projectId } = useParams<{ organizationId?: string; projectId: string }>()
  const navigate = useNavigate()
  const { data: agents, isLoading, isError, error, refetch } = useAgents(projectId)

  const p = (projectId: string, ...segments: string[]) => orgProjectPath(organizationId, projectId, ...segments)

  if (isLoading) return <LoadingState />
  if (isError) return <ErrorState error={error} onRetry={refetch} />

  return (
    <div>
      <PageHeader
        title="Agents"
        description="Configure and manage AI agents"
        actions={
          <Button onClick={() => navigate(p(projectId!, 'new'))}>
            <Plus className="mr-2 h-4 w-4" />
            New Agent
          </Button>
        }
      />

      {!agents || agents.length === 0 ? (
        <EmptyState
          icon={<Bot className="h-12 w-12" />}
          title="No agents yet"
          description="Create your first agent to get started."
          action={
            <Button onClick={() => navigate(p(projectId!, 'new'))}>
              <Plus className="mr-2 h-4 w-4" />
              Create Agent
            </Button>
          }
        />
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {agents.map((agent: Agent) => (
            <Card key={agent.id} className="hover:border-primary/50 transition-colors">
              <CardHeader>
                <CardTitle className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Bot className="h-5 w-5 text-primary" />
                    {agent.name}
                  </div>
                  <StatusBadge status={agent.status} />
                </CardTitle>
                <CardDescription>
                  {agent.provider} / {agent.model}
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="flex gap-2">
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => navigate(p(projectId!, 'agents', agent.id))}
                  >
                    <Settings className="mr-1 h-3 w-3" />
                    Edit
                  </Button>
                  <Button
                    size="sm"
                    onClick={() => navigate(p(projectId!, 'agents', agent.id, 'playground'))}
                  >
                    <Play className="mr-1 h-3 w-3" />
                    Playground
                  </Button>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  )
}
