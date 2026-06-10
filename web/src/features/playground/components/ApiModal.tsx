import { Link } from 'react-router-dom'
import { CopyButton } from '@/components/common/CopyButton'
import { Badge } from '@/components/ui/Badge'
import { ScrollArea } from '@/components/ui/ScrollArea'
import { Key, X } from 'lucide-react'
import { useEffect, useRef } from 'react'
import type { Agent } from '@/features/agents/types'

interface ApiModalProps {
  open: boolean
  onClose: () => void
  agent: Agent
  orgProjectPathFn: (projId: string, ...segments: string[]) => string
  projectId: string
}

function getResponseFormat(agent: Agent) {
  const settings = agent.settings || {}
  return (settings as Record<string, unknown>).response_format as
    | Record<string, unknown>
    | undefined
}

const ASK_CURL = `curl -X POST http://localhost:8000/runtime/ask \\
  -H "Authorization: Bearer <API_KEY>" \\
  -H "Content-Type: application/json" \\
  -d '{
  "project_id": "<project_id>",
  "agent_id": "<agent_id>",
  "message": "Hello!",
  "session_id": "<session_id>"
}'`

const ASK_RESPONSE_EXAMPLE = `{
  "success": true,
  "data": {
    "answer": "Hello! How can I help you?",
    "session_id": "uuid",
    "message_id": "uuid",
    "usage": {
      "input_tokens": 42,
      "output_tokens": 17,
      "total_tokens": 59,
      "cost_usd": 0.0003
    },
    "sources": [],
    "tool_calls": [],
    "trace_id": "uuid",
    "model": "gpt-4o-mini",
    "provider": "openai",
    "fallback_used": false,
    "latency_ms": 843,
    "parsed_output": null,
    "output_parse_error": null
  }
}`

const STRUCTURED_RESPONSE_CURL = `curl -X POST http://localhost:8000/runtime/ask \\
  -H "Authorization: Bearer <API_KEY>" \\
  -H "Content-Type: application/json" \\
  -d '{
  "project_id": "<project_id>",
  "agent_id": "<agent_id>",
  "message": "Classify this ticket: customer cant login",
  "session_id": "<session_id>"
}'`

const STRUCTURED_RESPONSE_EXAMPLE = `{
  "success": true,
  "data": {
    "answer": "{\\"category\\": \\"support\\", \\"priority\\": \\"high\\", \\"summary\\": \\"...\\", \\"should_escalate\\": true}",
    "session_id": "uuid",
    "message_id": "uuid",
    "usage": {
      "input_tokens": 58,
      "output_tokens": 22,
      "total_tokens": 80,
      "cost_usd": 0.0005
    },
    "sources": [],
    "tool_calls": [],
    "trace_id": "uuid",
    "model": "gpt-4o-mini",
    "provider": "openai",
    "fallback_used": false,
    "latency_ms": 1024,
    "parsed_output": {
      "category": "support",
      "priority": "high",
      "summary": "Customer needs help with billing.",
      "should_escalate": true
    },
    "output_parse_error": null
  }
}`

export function ApiModal({ open, onClose, agent, orgProjectPathFn, projectId }: ApiModalProps) {
  const overlayRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', handler)
    return () => document.removeEventListener('keydown', handler)
  }, [open, onClose])

  if (!open) return null

  const p = orgProjectPathFn
  const responseFormat = getResponseFormat(agent)
  const jsonEnabled = Boolean(responseFormat?.enabled && responseFormat?.type === 'json')

  return (
    <div
      ref={overlayRef}
      className="fixed inset-0 z-50 flex items-start justify-center pt-12 bg-black/60"
      onClick={(e) => { if (e.target === overlayRef.current) onClose() }}
    >
      <ScrollArea className="w-full max-w-2xl max-h-[80vh] rounded-xl border border-border bg-surface shadow-xl">
        <div className="flex items-center justify-between p-4 border-b border-border sticky top-0 bg-surface z-10">
          <h2 className="text-sm font-semibold text-white">API Reference</h2>
          <button onClick={onClose} className="p-1 rounded-md text-muted hover:text-white hover:bg-accent transition-colors">
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="p-4 space-y-5">
          <div>
            <p className="text-xs font-medium text-muted mb-1">Agent ID</p>
            <div className="flex items-center gap-2 rounded-lg border border-border bg-background p-3">
              <code className="text-sm flex-1 break-all">{agent.id}</code>
              <CopyButton text={agent.id} />
            </div>
          </div>

          <div>
            <p className="text-xs font-medium text-muted mb-1">Endpoints</p>
            <div className="space-y-1">
              <div className="flex items-center gap-2 rounded-lg border border-border bg-background p-2">
                <span className="text-xs font-medium text-primary">POST</span>
                <code className="text-xs flex-1">/runtime/ask</code>
                <CopyButton text="POST /runtime/ask" />
              </div>
              <div className="flex items-center gap-2 rounded-lg border border-border bg-background p-2">
                <span className="text-xs font-medium text-primary">POST</span>
                <code className="text-xs flex-1">/runtime/ask/stream</code>
                <CopyButton text="POST /runtime/ask/stream" />
              </div>
              <div className="flex items-center gap-2 rounded-lg border border-border bg-background p-2">
                <span className="text-xs font-medium text-primary">POST</span>
                <code className="text-xs flex-1">/runtime/ask/jobs</code>
                <CopyButton text="POST /runtime/ask/jobs" />
              </div>
            </div>
          </div>

          <div>
            <p className="text-xs font-medium text-muted mb-1">cURL Example</p>
            <ScrollArea orientation="horizontal" className="rounded-lg border border-border bg-background">
              <pre className="p-4 text-xs text-muted">
                {ASK_CURL}
              </pre>
            </ScrollArea>
          </div>

          <div>
            <p className="text-xs font-medium text-muted mb-1">Response Contract</p>
            <ScrollArea orientation="horizontal" className="rounded-lg border border-border bg-background">
              <pre className="p-4 text-xs text-muted">
                {ASK_RESPONSE_EXAMPLE}
              </pre>
            </ScrollArea>
          </div>

          {jsonEnabled && (
            <>
              <div>
                <div className="flex items-center gap-2 mb-1">
                  <p className="text-xs font-medium text-muted">Structured JSON Output</p>
                  <Badge variant="success" className="text-[10px]">Enabled</Badge>
                </div>
                <ScrollArea orientation="horizontal" className="rounded-lg border border-border bg-background">
                  <pre className="p-4 text-xs text-muted">
                    {STRUCTURED_RESPONSE_CURL}
                  </pre>
                </ScrollArea>
              </div>
              <div>
                <p className="text-xs font-medium text-muted mb-1">Expected Response:</p>
                <ScrollArea orientation="horizontal" className="rounded-lg border border-border bg-background">
                  <pre className="p-4 text-xs text-muted">
                    {STRUCTURED_RESPONSE_EXAMPLE}
                  </pre>
                </ScrollArea>
              </div>
            </>
          )}

          <Link
            to={p(projectId, 'api-keys')}
            className="inline-flex items-center gap-2 text-sm text-primary hover:underline"
          >
            <Key className="h-4 w-4" />
            Manage API Keys
          </Link>
        </div>
      </ScrollArea>
    </div>
  )
}
