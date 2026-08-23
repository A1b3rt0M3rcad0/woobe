import { useQuery } from '@tanstack/react-query'
import {
  Activity,
  Bot,
  CheckCircle,
  Cpu,
  Database,
  GitBranch,
  Wrench,
  XCircle,
} from 'lucide-react'

import { getNetworkRunDiagnostics } from '@/features/network/api'
import { formatCurrency, formatLatency, formatTokens } from '@/lib/formatters/number'

import type { NetworkRunDiagnostics } from './networkRunDiagnosticsTypes'

function Metric({
  label,
  value,
  icon: Icon,
}: {
  label: string
  value: string
  icon: typeof Activity
}) {
  return (
    <div className="rounded-lg border border-border bg-background p-2.5">
      <div className="flex items-center gap-1.5 text-muted">
        <Icon className="h-3.5 w-3.5" />
        <span className="text-[10px] uppercase tracking-wide">{label}</span>
      </div>
      <p className="mt-1 font-mono text-sm text-white">{value}</p>
    </div>
  )
}

function telemetryLabel(status: NetworkRunDiagnostics['telemetry_status']) {
  if (status === 'complete') return 'Complete telemetry'
  if (status === 'partial') return 'Partial telemetry'
  return 'Telemetry unavailable'
}

function costLabel(diagnostics: NetworkRunDiagnostics) {
  if (diagnostics.cost_status === 'unknown' || diagnostics.cost_usd == null) {
    return 'Cost unknown'
  }
  const value = formatCurrency(diagnostics.cost_usd)
  return diagnostics.cost_status === 'partial' ? `Cost ${value}+ (partial)` : `Cost ${value}`
}

export function NetworkRunDiagnosticsPanel({
  executionId,
  projectId,
  running,
}: {
  executionId: string
  projectId: string
  running: boolean
}) {
  const { data, isLoading, isError } = useQuery({
    queryKey: ['network-run-diagnostics', projectId, executionId],
    queryFn: () => getNetworkRunDiagnostics(executionId, projectId),
    refetchInterval: running ? 1_500 : false,
    refetchIntervalInBackground: false,
    staleTime: running ? 0 : 30_000,
  })

  if (isLoading) {
    return (
      <section className="rounded-xl border border-border/75 bg-background/30 p-3">
        <p className="text-[9px] font-semibold uppercase tracking-wide text-muted">Execution diagnostics</p>
        <p className="mt-2 text-[10px] text-muted">Loading Network Run metrics…</p>
      </section>
    )
  }

  if (isError || !data) {
    return (
      <section className="rounded-xl border border-border/75 bg-background/30 p-3">
        <p className="text-[9px] font-semibold uppercase tracking-wide text-muted">Execution diagnostics</p>
        <p className="mt-2 text-[10px] text-muted">Network Run metrics are unavailable.</p>
      </section>
    )
  }

  return (
    <section className="rounded-xl border border-border/75 bg-background/30 p-3">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-[11px] font-medium text-white">Execution diagnostics</p>
          <p className="mt-0.5 text-[9px] text-muted">Measured across the complete Network Run</p>
        </div>
        <span className="rounded-full border border-border bg-background px-2 py-0.5 text-[9px] text-muted">
          {telemetryLabel(data.telemetry_status)}
        </span>
      </div>

      <div className="mt-3 grid grid-cols-2 gap-1.5">
        <Metric label="Network wall" value={formatLatency(data.network_wall_latency_ms)} icon={Activity} />
        <Metric label="Agent work" value={formatLatency(data.agent_work_latency_ms)} icon={Bot} />
        <Metric label="LLM total" value={formatLatency(data.llm_runtime_latency_ms)} icon={Cpu} />
        <Metric label="Tool work" value={formatLatency(data.tool_work_latency_ms)} icon={Wrench} />
      </div>

      <div className="mt-3 flex flex-wrap items-center gap-x-3 gap-y-1 text-[10px] text-muted">
        <span>{data.agent_run_count} Agent Run{data.agent_run_count === 1 ? '' : 's'}</span>
        <span className="inline-flex items-center gap-1"><GitBranch className="h-3 w-3" />{data.delegation_count} delegation{data.delegation_count === 1 ? '' : 's'}</span>
        <span>{data.llm_call_count} LLM call{data.llm_call_count === 1 ? '' : 's'}</span>
        <span>{data.tool_call_count} Tool call{data.tool_call_count === 1 ? '' : 's'}</span>
        <span className="inline-flex items-center gap-1 text-emerald-400"><CheckCircle className="h-3 w-3" />{data.successful_tool_calls}</span>
        <span className="inline-flex items-center gap-1 text-red-400"><XCircle className="h-3 w-3" />{data.failed_tool_calls}</span>
        <span>Depth {data.max_depth}</span>
        <span>Fan-out {data.max_fan_out}</span>
        {data.prepare_latency_ms != null ? <span>Setup Σ {formatLatency(data.prepare_latency_ms)}</span> : null}
        {data.persistence_latency_ms != null ? <span className="inline-flex items-center gap-1"><Database className="h-3 w-3" />Persist Σ {formatLatency(data.persistence_latency_ms)}</span> : null}
        {data.orchestration_latency_ms != null ? <span>Agent orchestration Σ {formatLatency(data.orchestration_latency_ms)}</span> : null}
        {data.input_tokens != null && data.output_tokens != null
          ? <span>Tokens {formatTokens(data.input_tokens)} → {formatTokens(data.output_tokens)}{data.usage_complete ? '' : ' (partial)'}</span>
          : <span>Token usage unavailable</span>}
        {data.source_count ? <span>{data.source_count} source{data.source_count === 1 ? '' : 's'}</span> : null}
        {data.fallback_count ? <span>{data.fallback_count} fallback{data.fallback_count === 1 ? '' : 's'}</span> : null}
        <span>{costLabel(data)}</span>
      </div>
    </section>
  )
}
