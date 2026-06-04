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
  const normalizedEnvelope = lastResponse
    ? { success: true, data: lastResponse }
    : null

  return (
    <div className="space-y-4">
      <Card>
        <CardContent className="p-4 space-y-4">
          {lastResponse && (
            <>
              <div>
                <div className="flex items-center justify-between mb-2">
                  <p className="text-xs font-medium text-muted">Normalized Response</p>
                  {normalizedEnvelope && <CopyButton text={JSON.stringify(normalizedEnvelope, null, 2)} />}
                </div>
                <pre className="text-xs text-muted overflow-x-auto max-h-60 bg-background rounded p-2 border border-border">
                  {JSON.stringify(normalizedEnvelope, null, 2)}
                </pre>
              </div>
              <Separator />
            </>
          )}

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

          {lastResponse && (
            <div className="space-y-3">
              <p className="text-xs font-semibold text-muted">Metrics</p>
              <div className="grid grid-cols-2 gap-2">
                {lastResponse.latency_ms != null && (
                  <div>
                    <p className="text-xs text-muted">Latency</p>
                    <p className="text-xs text-white">{Math.round(lastResponse.latency_ms)}ms</p>
                  </div>
                )}
                {lastResponse.model && (
                  <div>
                    <p className="text-xs text-muted">Model / Provider</p>
                    <p className="text-xs text-white">{lastResponse.provider || '—'} / {lastResponse.model}</p>
                  </div>
                )}
                {lastResponse.trace_id && (
                  <div className="col-span-2">
                    <p className="text-xs text-muted">Trace ID</p>
                    <p className="text-xs text-white break-all">{lastResponse.trace_id}</p>
                  </div>
                )}
              </div>

              {lastResponse.usage && (
                <div>
                  <p className="text-xs text-muted mb-1">Usage</p>
                  <p className="text-xs text-white">
                    Input: {formatNumber(lastResponse.usage.input_tokens, 0)} tokens · Output: {formatNumber(lastResponse.usage.output_tokens, 0)} tokens
                  </p>
                  {lastResponse.usage.total_tokens != null && (
                    <p className="text-xs text-muted">Total: {formatNumber(lastResponse.usage.total_tokens, 0)} tokens</p>
                  )}
                  <p className="text-xs text-muted">Cost: {formatCurrency(lastResponse.usage.cost_usd, 6)}</p>
                </div>
              )}

              {lastResponse.sources && lastResponse.sources.length > 0 && (
                <div>
                  <p className="text-xs text-muted mb-1">Sources ({lastResponse.sources.length})</p>
                  <pre className="text-xs text-muted overflow-x-auto max-h-40 bg-background rounded p-2 border border-border">
                    {JSON.stringify(lastResponse.sources, null, 2)}
                  </pre>
                </div>
              )}

              {lastResponse.tool_calls && lastResponse.tool_calls.length > 0 && (
                <div>
                  <p className="text-xs text-muted mb-1">Tool Calls ({lastResponse.tool_calls.length})</p>
                  <pre className="text-xs text-muted overflow-x-auto max-h-40 bg-background rounded p-2 border border-border">
                    {JSON.stringify(lastResponse.tool_calls, null, 2)}
                  </pre>
                </div>
              )}
            </div>
          )}

          {lastResponse && (
            <Separator />
          )}

          {lastResponse?.parsed_output && (
            <div>
              <p className="text-xs font-medium text-muted mb-2">Structured Output</p>
              <pre className="text-xs text-green-400 overflow-x-auto max-h-40 bg-background rounded p-2 border border-border">
                {JSON.stringify(lastResponse.parsed_output, null, 2)}
              </pre>
            </div>
          )}

          {lastResponse?.output_parse_error && (
            <div>
              <p className="text-xs font-medium text-red-400 mb-2">Parse Error</p>
              <div className="rounded bg-red-500/10 border border-red-500/30 p-2">
                <p className="text-xs text-red-400">
                  The model did not return valid JSON.
                </p>
                <p className="text-xs text-muted mt-1 break-all">{lastResponse.output_parse_error}</p>
              </div>
            </div>
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
