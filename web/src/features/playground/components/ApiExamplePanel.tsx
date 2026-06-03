import { Link } from 'react-router-dom'
import { Card, CardContent } from '@/components/ui/Card'
import { CopyButton } from '@/components/common/CopyButton'
import { Separator } from '@/components/ui/Separator'
import { Key } from 'lucide-react'
import type { Agent } from '@/features/agents/types'

interface ApiExamplePanelProps {
  agent: Agent
  projectId: string
  orgProjectPathFn: (projId: string, ...segments: string[]) => string
}

export function ApiExamplePanel({ agent, projectId, orgProjectPathFn }: ApiExamplePanelProps) {
  const p = orgProjectPathFn
  return (
    <Card>
      <CardContent className="p-4 space-y-4">
        <div>
          <p className="text-xs font-medium text-muted mb-1">Agent ID</p>
          <div className="flex items-center gap-2 rounded-lg border border-border bg-background p-3">
            <code className="text-sm flex-1 break-all">{agent.id}</code>
            <CopyButton text={agent.id} />
          </div>
        </div>
        <Separator />
        <div>
          <p className="text-xs font-medium text-muted mb-1">Endpoint</p>
          <div className="flex items-center gap-2 rounded-lg border border-border bg-background p-3">
            <code className="text-sm flex-1">POST /runtime/ask</code>
            <CopyButton text="POST /runtime/ask" />
          </div>
        </div>
        <Separator />
        <div>
          <p className="text-xs font-medium text-muted mb-1">cURL example</p>
          <pre className="rounded-lg border border-border bg-background p-4 text-xs overflow-x-auto">
{`curl -X POST http://localhost:8000/runtime/ask \\
  -H "Authorization: Bearer <API_KEY>" \\
  -H "Content-Type: application/json" \\
  -d '{
  "session_id": "<session_id>",
  "content": "Hello, agent!"
}'`}
          </pre>
          <CopyButton text={`curl -X POST http://localhost:8000/runtime/ask -H "Authorization: Bearer <API_KEY>" -H "Content-Type: application/json" -d '{"session_id": "<session_id>", "content": "Hello, agent!"}'`} />
        </div>
        <Separator />
        <Link to={p(projectId!, 'api-keys')} className="inline-flex items-center gap-2 text-sm text-primary hover:underline">
          <Key className="h-4 w-4" />
          Manage API Keys
        </Link>
      </CardContent>
    </Card>
  )
}
