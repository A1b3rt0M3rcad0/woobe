import { Link } from 'react-router-dom'
import { Card, CardContent } from '@/components/ui/Card'
import { CopyButton } from '@/components/common/CopyButton'
import { Separator } from '@/components/ui/Separator'
import { Badge } from '@/components/ui/Badge'
import { Key } from 'lucide-react'
import type { Agent } from '@/features/agents/types'

interface ApiExamplePanelProps {
  agent: Agent
  projectId: string
  orgProjectPathFn: (projId: string, ...segments: string[]) => string
}

function getResponseFormat(agent: Agent) {
  const settings = agent.settings || {}
  return (settings as Record<string, unknown>).response_format as
    | Record<string, unknown>
    | undefined
}

const STRUCTURED_RESPONSE_CURL = `curl -X POST http://localhost:8000/runtime/ask \\
  -H "Authorization: Bearer <API_KEY>" \\
  -H "Content-Type: application/json" \\
  -d '{
  "session_id": "<session_id>",
  "content": "Classify this ticket"
}'`

const STRUCTURED_RESPONSE_EXAMPLE = `{
  "success": true,
  "data": {
    "answer": "{\\"category\\": \\"support\\", \\"priority\\": \\"high\\", \\"summary\\": \\"...\\", \\"should_escalate\\": true}",
    "parsed_output": {
      "category": "support",
      "priority": "high",
      "summary": "Customer needs help with billing.",
      "should_escalate": true
    },
    "output_parse_error": null
  }
}`

export function ApiExamplePanel({ agent, projectId, orgProjectPathFn }: ApiExamplePanelProps) {
  const p = orgProjectPathFn
  const responseFormat = getResponseFormat(agent)
  const jsonEnabled = Boolean(responseFormat?.enabled && responseFormat?.type === 'json')

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

        {jsonEnabled && (
          <>
            <Separator />
            <div>
              <div className="flex items-center gap-2 mb-1">
                <p className="text-xs font-medium text-muted">Structured JSON Output</p>
                <Badge variant="success" className="text-[10px]">Enabled</Badge>
              </div>
              <pre className="rounded-lg border border-border bg-background p-4 text-xs overflow-x-auto">
{STRUCTURED_RESPONSE_CURL}
              </pre>
              <CopyButton text={STRUCTURED_RESPONSE_CURL} />
              <div className="mt-2">
                <p className="text-xs font-medium text-muted mb-1">Response:</p>
                <pre className="rounded-lg border border-border bg-background p-4 text-xs overflow-x-auto">
{STRUCTURED_RESPONSE_EXAMPLE}
                </pre>
                <CopyButton text={STRUCTURED_RESPONSE_EXAMPLE} />
              </div>
            </div>
          </>
        )}

        <Separator />
        <Link to={p(projectId!, 'api-keys')} className="inline-flex items-center gap-2 text-sm text-primary hover:underline">
          <Key className="h-4 w-4" />
          Manage API Keys
        </Link>
      </CardContent>
    </Card>
  )
}
