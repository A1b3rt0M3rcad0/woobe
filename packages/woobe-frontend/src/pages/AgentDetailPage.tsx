import { useParams, Link, useNavigate } from 'react-router-dom'
import { useAgent } from '@/features/agents/hooks'
import { PageHeader } from '@/components/common/PageHeader'
import { LoadingState } from '@/components/common/LoadingState'
import { ErrorState } from '@/components/common/ErrorState'
import { Tabs } from '@/components/ui/Tabs'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Textarea } from '@/components/ui/Textarea'
import { StatusBadge } from '@/components/common/StatusBadge'
import { CopyButton } from '@/components/common/CopyButton'
import { JsonCodeBlock } from '@/components/ui/JsonCodeBlock'
import { ScrollArea } from '@/components/ui/ScrollArea'
import { workspaceProjectPath } from '@/lib/constants/routes'
import { Play, Key, ExternalLink, Pencil } from 'lucide-react'

export default function AgentDetailPage() {
  const { workspaceId, projectId, agentId } = useParams<{ workspaceId?: string; projectId: string; agentId: string }>()
  const navigate = useNavigate()
  const { data: agent, isLoading, isError, error, refetch } = useAgent(agentId)

  const p = (projId: string, ...segments: string[]) => workspaceProjectPath(workspaceId, projId, ...segments)

  const tabs = [
    {
      id: 'general',
      label: 'General',
      content: agent ? (
        <div className="space-y-4">
          <Card>
            <CardHeader><CardTitle>Agent Details</CardTitle></CardHeader>
            <CardContent className="space-y-3">
              <div className="flex justify-between"><span className="text-muted text-sm">Name</span><span className="text-sm">{agent.name}</span></div>
              <div className="flex justify-between"><span className="text-muted text-sm">Description</span><span className="text-sm">{agent.description || '—'}</span></div>
              <div className="flex justify-between"><span className="text-muted text-sm">Status</span><StatusBadge status={agent.status} /></div>
              <div className="flex justify-between"><span className="text-muted text-sm">Session Mode</span><span className="text-sm">{agent.session_mode || 'stateful'}</span></div>
            </CardContent>
          </Card>
        </div>
      ) : null,
    },
    {
      id: 'prompt',
      label: 'Prompt',
      content: agent ? (
        <Card>
          <CardHeader><CardTitle>System Prompt</CardTitle></CardHeader>
          <CardContent>
            <Textarea
              defaultValue={agent.system_prompt || ''}
              className="min-h-[200px] font-mono text-sm"
            />
            <div className="flex justify-end mt-4">
              <Button size="sm">Save</Button>
            </div>
          </CardContent>
        </Card>
      ) : null,
    },
    {
      id: 'model',
      label: 'Model',
      content: agent ? (
        <Card>
          <CardHeader><CardTitle>Model Configuration</CardTitle></CardHeader>
          <CardContent className="space-y-3">
            <div className="flex justify-between"><span className="text-muted text-sm">Provider</span><span className="text-sm">{agent.provider}</span></div>
            <div className="flex justify-between"><span className="text-muted text-sm">Model</span><span className="text-sm">{agent.model}</span></div>
            <div className="flex justify-between"><span className="text-muted text-sm">Temperature</span><span className="text-sm">{agent.temperature ?? '—'}</span></div>
            <div className="flex justify-between"><span className="text-muted text-sm">Max Output Tokens</span><span className="text-sm">{agent.max_output_tokens ?? '—'}</span></div>
          </CardContent>
        </Card>
      ) : null,
    },
    {
      id: 'api',
      label: 'API',
      content: agent ? (
        <Card>
          <CardHeader><CardTitle>API Reference</CardTitle></CardHeader>
          <CardContent className="space-y-4">
            <div>
              <p className="text-sm text-muted mb-1">Agent ID</p>
              <div className="flex items-center gap-2 rounded-lg border border-border bg-background p-3">
                <code className="text-sm flex-1">{agent.id}</code>
                <CopyButton text={agent.id} />
              </div>
            </div>
            <div>
              <p className="text-sm text-muted mb-1">Endpoint</p>
              <div className="flex items-center gap-2 rounded-lg border border-border bg-background p-3">
                <code className="text-sm flex-1">POST /runtime/ask</code>
                <CopyButton text="POST /runtime/ask" />
              </div>
            </div>
            <div>
              <p className="text-sm text-muted mb-1">cURL example</p>
              <ScrollArea orientation="horizontal" className="rounded-lg border border-border bg-background">
                <pre className="p-4 text-xs">
{`curl -X POST http://localhost:8000/runtime/ask \\
  -H "Authorization: Bearer <API_KEY>" \\
  -H "Content-Type: application/json" \\
  -d '{
  "session_id": "<session_id>",
  "content": "Hello, agent!"
}'`}
                </pre>
              </ScrollArea>
              <CopyButton text={`curl -X POST http://localhost:8000/runtime/ask -H "Authorization: Bearer <API_KEY>" -H "Content-Type: application/json" -d '{"session_id": "<session_id>", "content": "Hello, agent!"}'`} />
            </div>
            <Link to={p(projectId!, 'api-keys')} className="inline-flex items-center gap-2 text-sm text-primary hover:underline">
              <Key className="h-4 w-4" />
              Manage API Keys
            </Link>
          </CardContent>
        </Card>
      ) : null,
    },
  ]

  if (isLoading) return <LoadingState />
  if (isError) return <ErrorState error={error} onRetry={refetch} />
  if (!agent) return <ErrorState message="Agent not found" />

  return (
    <div>
      <PageHeader
        title={agent.name}
        description={`${agent.provider} / ${agent.model}`}
        actions={
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              onClick={() => navigate(p(projectId!, 'agents', agentId!, 'edit'))}
            >
              <Pencil className="mr-2 h-4 w-4" />
              Edit
            </Button>
            <Button
              size="lg"
              onClick={() => navigate(p(projectId!, 'agents', agentId!, 'playground'))}
            >
              <Play className="mr-2 h-4 w-4" />
              Open in Playground
            </Button>
            <Button variant="outline" onClick={() => navigate(p(projectId!, 'agents'))}>
              <ExternalLink className="mr-2 h-4 w-4" />
              Back to Agents
            </Button>
          </div>
        }
      />
      <Tabs tabs={tabs} />
    </div>
  )
}
