import { Activity, CheckCircle, Gauge, Network, Wrench, XCircle } from 'lucide-react'
import { useTraceDetail } from '@/features/traces/hooks'
import { formatLatency, formatTokens } from '@/lib/formatters/number'

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' && !Array.isArray(value)
    ? value as Record<string, unknown>
    : {}
}

function numberOrNull(value: unknown): number | null {
  if (typeof value === 'number' && Number.isFinite(value)) return value
  if (typeof value === 'string' && value.trim()) {
    const parsed = Number(value)
    return Number.isFinite(parsed) ? parsed : null
  }
  return null
}

function findDiagnostics(raw: unknown): Record<string, unknown> {
  const trace = asRecord(raw)
  const data = asRecord(trace.data)
  const persisted = asRecord(data.diagnostics)
  if (Object.keys(persisted).length > 0) return persisted

  const events = Array.isArray(trace.events) ? trace.events : []
  for (const item of events) {
    const event = asRecord(item)
    const payload = asRecord(event.payload)
    if (payload.event === 'observability.execution.summary.v1') return payload
  }
  return {}
}

function Metric({ label, value, icon: Icon }: {
  label: string
  value: string
  icon: typeof Gauge
}) {
  return (
    <div className="rounded-lg border border-border bg-background p-2.5">
      <div className="flex items-center gap-1.5 text-muted">
        <Icon className="h-3.5 w-3.5" />
        <span className="text-[10px] uppercase tracking-wide">{label}</span>
      </div>
      <p className="mt-1 text-sm font-mono text-white">{value}</p>
    </div>
  )
}

export function TraceDiagnosticsPanel({ traceId }: { traceId: string }) {
  const { data } = useTraceDetail(traceId)
  const diagnostics = findDiagnostics(data)
  if (Object.keys(diagnostics).length === 0) return null

  const runtime = numberOrNull(diagnostics.agent_runtime_latency_ms)
  const nonTool = numberOrNull(diagnostics.non_tool_runtime_latency_ms)
  const tools = numberOrNull(diagnostics.tool_runtime_latency_ms)
  const http = numberOrNull(diagnostics.tool_http_latency_ms)
  const overhead = numberOrNull(diagnostics.tool_overhead_latency_ms)
  const toolShare = numberOrNull(diagnostics.tool_share_percent)
  const toolCount = numberOrNull(diagnostics.tool_call_count) ?? 0
  const successes = numberOrNull(diagnostics.successful_tool_calls) ?? 0
  const failures = numberOrNull(diagnostics.failed_tool_calls) ?? 0
  const inputTokens = numberOrNull(diagnostics.input_tokens)
  const outputTokens = numberOrNull(diagnostics.output_tokens)
  const sourceCount = numberOrNull(diagnostics.source_count) ?? 0

  return (
    <div className="border-b border-border px-4 py-3 space-y-2">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-xs font-medium text-white">Execution diagnostics</p>
          <p className="text-[10px] text-muted">Measured inside the Agent runtime</p>
        </div>
        {toolShare != null && (
          <span className="rounded-full border border-border bg-background px-2 py-0.5 text-[10px] font-mono text-muted">
            Tools {toolShare.toFixed(1)}%
          </span>
        )}
      </div>

      <div className="grid grid-cols-2 gap-1.5">
        <Metric label="Runtime" value={runtime == null ? '—' : formatLatency(runtime)} icon={Activity} />
        <Metric label="Non-tool" value={nonTool == null ? '—' : formatLatency(nonTool)} icon={Gauge} />
        <Metric label="Tools" value={tools == null ? '—' : formatLatency(tools)} icon={Wrench} />
        <Metric label="Tool HTTP" value={http == null ? '—' : formatLatency(http)} icon={Network} />
      </div>

      <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-[10px] text-muted">
        <span>{toolCount} tool call{toolCount === 1 ? '' : 's'}</span>
        <span className="inline-flex items-center gap-1 text-emerald-400">
          <CheckCircle className="h-3 w-3" /> {successes}
        </span>
        <span className="inline-flex items-center gap-1 text-red-400">
          <XCircle className="h-3 w-3" /> {failures}
        </span>
        {overhead != null && <span>Tool overhead {formatLatency(overhead)}</span>}
        {inputTokens != null && outputTokens != null && (
          <span>Tokens {formatTokens(inputTokens)} → {formatTokens(outputTokens)}</span>
        )}
        <span>Sources {sourceCount}</span>
      </div>
    </div>
  )
}
