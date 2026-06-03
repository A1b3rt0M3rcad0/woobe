import { Card, CardContent } from '@/components/ui/Card'
import { Separator } from '@/components/ui/Separator'
import { CopyButton } from '@/components/common/CopyButton'
import { formatNumber, formatCurrency } from '@/lib/formatters/number'
import type { Agent } from '@/features/agents/types'
import type { AskResponse } from '@/features/playground/types'

interface DebugPanelProps {
  sessionId: string | null
  agent: Agent
  lastResponse: AskResponse | null
  messagesCount: number
}

export function DebugPanel({ sessionId, agent, lastResponse, messagesCount }: DebugPanelProps) {
  return (
    <div className="space-y-4">
      <Card>
        <CardContent className="p-4 space-y-4">
          <div>
            <p className="text-xs font-medium text-muted mb-2">Session</p>
            <p className="text-xs text-white break-all">{sessionId || 'No active session'}</p>
          </div>
          <Separator />
          <div>
            <p className="text-xs font-medium text-muted mb-2">Agent</p>
            <p className="text-xs text-white">{agent.name}</p>
            <p className="text-xs text-muted">{agent.provider}/{agent.model}</p>
            {agent.temperature != null && <p className="text-xs text-muted">Temp: {agent.temperature}</p>}
          </div>
          <Separator />
          <div>
            <div className="flex items-center justify-between mb-2">
              <p className="text-xs font-medium text-muted">Response</p>
              {lastResponse && <CopyButton text={JSON.stringify(lastResponse, null, 2)} />}
            </div>
            <pre className="text-xs text-muted overflow-x-auto max-h-60 bg-background rounded p-2 border border-border">
              {lastResponse ? JSON.stringify(lastResponse, null, 2) : '—'}
            </pre>
          </div>
          {lastResponse?.sources && lastResponse.sources.length > 0 && (
            <>
              <Separator />
              <div>
                <p className="text-xs font-medium text-muted mb-2">Sources ({lastResponse.sources.length})</p>
                <pre className="text-xs text-muted overflow-x-auto max-h-40 bg-background rounded p-2 border border-border">
                  {JSON.stringify(lastResponse.sources, null, 2)}
                </pre>
              </div>
            </>
          )}
          {lastResponse && !lastResponse.sources && (
            <>
              <Separator />
              <div>
                <p className="text-xs font-medium text-muted mb-2">Sources</p>
                <p className="text-xs text-muted">No sources returned for this answer.</p>
              </div>
            </>
          )}
          {lastResponse?.tool_calls && lastResponse.tool_calls.length > 0 && (
            <>
              <Separator />
              <div>
                <p className="text-xs font-medium text-muted mb-2">Tool Calls ({lastResponse.tool_calls.length})</p>
                <pre className="text-xs text-muted overflow-x-auto max-h-40 bg-background rounded p-2 border border-border">
                  {JSON.stringify(lastResponse.tool_calls, null, 2)}
                </pre>
              </div>
            </>
          )}
          {lastResponse?.latency_ms != null && (
            <>
              <Separator />
              <div>
                <p className="text-xs font-medium text-muted mb-2">Latency</p>
                <p className="text-xs text-white">{lastResponse.latency_ms}ms</p>
              </div>
            </>
          )}
          {lastResponse?.usage && (
            <>
              <Separator />
              <div>
                <p className="text-xs font-medium text-muted mb-2">Usage</p>
                <p className="text-xs text-white">
                  Input: {formatNumber(lastResponse.usage.input_tokens, 0)} tokens · Output: {formatNumber(lastResponse.usage.output_tokens, 0)} tokens
                </p>
                <p className="text-xs text-muted">Cost: {formatCurrency(lastResponse.usage.cost_usd, 6)}</p>
              </div>
            </>
          )}
          <Separator />
          <div>
            <p className="text-xs font-medium text-muted mb-2">Messages: {messagesCount}</p>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
