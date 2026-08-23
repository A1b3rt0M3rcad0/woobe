import { Activity, CheckCircle, Cpu, Database, Gauge, Wrench, XCircle } from 'lucide-react'
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
    const payload = asRecord(asRecord(item).payload)
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
  const d = findDiagnostics(data)
  if (Object.keys(d).length === 0) return null

  const runtime = numberOrNull(d.agent_runtime_latency_ms)
  const llm = numberOrNull(d.llm_runtime_latency_ms)
  const toolWall = numberOrNull(d.tool_wall_latency_ms ?? d.tool_runtime_latency_ms)
  const toolWork = numberOrNull(d.tool_call_duration_sum_ms ?? d.tool_runtime_latency_ms)
  const prepare = numberOrNull(d.prepare_latency_ms)
  const persistence = numberOrNull(d.persistence_latency_ms)
  const orchestration = numberOrNull(d.orchestration_latency_ms)
  const toolShare = numberOrNull(d.tool_share_percent)
  const toolCount = numberOrNull(d.tool_call_count) ?? 0
  const llmCount = numberOrNull(d.llm_call_count) ?? 0
  const successes = numberOrNull(d.successful_tool_calls) ?? 0
  const failures = numberOrNull(d.failed_tool_calls) ?? 0
  const inputTokens = numberOrNull(d.input_tokens)
  const outputTokens = numberOrNull(d.output_tokens)
  const usageComplete = d.usage_complete === true
  const costStatus = typeof d.cost_status === 'string' ? d.cost_status : 'unknown'

  return (
    <div className="border-b border-border px-4 py-3 space-y-2">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-xs font-medium text-white">Execution diagnostics</p>
          <p className="text-[10px] text-muted">Measured by execution phase</p>
        </div>
        {toolShare != null && (
          <span className="rounded-full border border-border bg-background px-2 py-0.5 text-[10px] font-mono text-muted">
            Tool wall {toolShare.toFixed(1)}%
          </span>
        )}
      </div>

      <div className="grid grid-cols-2 gap-1.5">
        <Metric label="Agent runtime" value={runtime == null ? '—' : formatLatency(runtime)} icon={Activity} />
        <Metric label="LLM total" value={llm == null ? '—' : formatLatency(llm)} icon={Cpu} />
        <Metric label="Tool wall" value={toolWall == null ? '—' : formatLatency(toolWall)} icon={Wrench} />
        <Metric label="Tool work" value={toolWork == null ? '—' : formatLatency(toolWork)} icon={Wrench} />
      </div>

      <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-[10px] text-muted">
        <span>{llmCount} LLM call{llmCount === 1 ? '' : 's'}</span>
        <span>{toolCount} tool call{toolCount === 1 ? '' : 's'}</span>
        <span className="inline-flex items-center gap-1 text-emerald-400"><CheckCircle className="h-3 w-3" /> {successes}</span>
        <span className="inline-flex items-center gap-1 text-red-400"><XCircle className="h-3 w-3" /> {failures}</span>
        {prepare != null && <span>Setup {formatLatency(prepare)}</span>}
        {persistence != null && <span className="inline-flex items-center gap-1"><Database className="h-3 w-3" /> Persist {formatLatency(persistence)}</span>}
        {orchestration != null && <span>Orchestration {formatLatency(orchestration)}</span>}
        {inputTokens != null && outputTokens != null
          ? <span>Tokens {formatTokens(inputTokens)} → {formatTokens(outputTokens)}{usageComplete ? '' : ' (partial)'}</span>
          : <span>Token usage unavailable</span>}
        <span>Cost {costStatus === 'known' ? 'reported' : 'unknown'}</span>
      </div>
    </div>
  )
}
