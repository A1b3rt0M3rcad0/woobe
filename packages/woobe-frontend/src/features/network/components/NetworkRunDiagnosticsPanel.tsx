import { useQuery } from '@tanstack/react-query'
import {
  Activity,
  AlertTriangle,
  Bot,
  Brain,
  CheckCircle,
  ChevronRight,
  Cpu,
  Database,
  GitBranch,
  Wrench,
  XCircle,
} from 'lucide-react'

import { getNetworkRunDiagnostics } from '@/features/network/api'
import { formatCurrency, formatLatency, formatTokens } from '@/lib/formatters/number'

import type { NetworkContextOverview, NetworkRunDiagnostics } from './networkRunDiagnosticsTypes'

type DiagnosticsMode = 'execution' | 'context' | 'all'

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

function contextTelemetryLabel(status: NetworkContextOverview['telemetry_status']) {
  if (status === 'complete') return 'Complete'
  if (status === 'partial') return 'Partial'
  return 'Unavailable'
}

function costLabel(diagnostics: NetworkRunDiagnostics) {
  if (diagnostics.cost_status === 'unknown' || diagnostics.cost_usd == null) {
    return 'Cost unknown'
  }
  const value = formatCurrency(diagnostics.cost_usd)
  return diagnostics.cost_status === 'partial' ? `Cost ${value}+ (partial)` : `Cost ${value}`
}

function formatPercent(value: number | null | undefined) {
  if (value == null || !Number.isFinite(value)) return '—'
  return `${(value * 100).toFixed(value >= 0.1 ? 1 : 2)}%`
}

function sourceLabel(source: string) {
  switch (source) {
    case 'SYSTEM': return 'System'
    case 'SESSION': return 'Conversation'
    case 'USER_INPUT': return 'Current input'
    case 'KNOWLEDGE': return 'Knowledge'
    case 'TOOL': return 'Tool/Skill results'
    case 'DELEGATION': return 'Delegation'
    case 'RUNTIME': return 'Runtime'
    case 'ARTIFACT': return 'Artifacts'
    case 'MEMORY': return 'Memory'
    case 'CHECKPOINT': return 'Checkpoint'
    default: return source
  }
}

function NetworkContextOverviewPanel({ context, standalone = false }: { context: NetworkContextOverview; standalone?: boolean }) {
  const surfaceClass = standalone
    ? 'rounded-xl border border-border/75 bg-background/30 p-3'
    : 'mt-3 border-t border-border/70 pt-3'

  if (context.telemetry_status === 'unknown' || context.model_invocation_count === 0) {
    return (
      <section className={surfaceClass}>
        <div className="flex items-center gap-2">
          <Brain className="h-3.5 w-3.5 text-muted" />
          <p className="text-[10px] font-medium text-white">Context overview</p>
        </div>
        <p className="mt-1.5 text-[9px] text-muted">Context evidence is not available for the child Agent Runs yet.</p>
      </section>
    )
  }

  const sources = Object.entries(context.source_units)
    .filter(([, value]) => (value.units ?? 0) > 0)
    .sort(([, left], [, right]) => (right.units ?? 0) - (left.units ?? 0))

  return (
    <section className={surfaceClass}>
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-center gap-2">
          <Brain className="h-3.5 w-3.5 text-primary-light" />
          <div>
            <p className="text-[10px] font-medium text-white">Context overview</p>
            <p className="text-[9px] text-muted">Aggregated from child Model Invocations, not a Network Context Snapshot</p>
          </div>
        </div>
        <span className="rounded-full border border-border bg-background px-2 py-0.5 text-[8px] text-muted">
          {contextTelemetryLabel(context.telemetry_status)}
        </span>
      </div>

      <div className="mt-2.5 grid grid-cols-2 gap-1.5">
        <div className="rounded-lg border border-border bg-background px-2.5 py-2">
          <p className="text-[8px] uppercase tracking-wide text-muted">Model input</p>
          <p className="mt-0.5 font-mono text-[12px] text-white">{context.input_units == null ? '—' : formatTokens(context.input_units)}</p>
          <p className="text-[8px] text-muted">{context.input_measurement}</p>
        </div>
        <div className="rounded-lg border border-border bg-background px-2.5 py-2">
          <p className="text-[8px] uppercase tracking-wide text-muted">Model invocations</p>
          <p className="mt-0.5 font-mono text-[12px] text-white">{context.model_invocation_count}</p>
          <p className="text-[8px] text-muted">across {context.agents.length} Agent{context.agents.length === 1 ? '' : 's'}</p>
        </div>
      </div>

      <div className="mt-2 flex flex-wrap gap-x-3 gap-y-1 text-[9px] text-muted">
        {context.median_utilization != null ? <span>Median utilization {formatPercent(context.median_utilization)}</span> : null}
        {context.peak_utilization != null ? <span>Peak {formatPercent(context.peak_utilization)}</span> : null}
        {context.budget_unknown_count > 0 ? (
          <span className="inline-flex items-center gap-1 text-amber-300">
            <AlertTriangle className="h-3 w-3" />
            Budget unavailable on {context.budget_unknown_count} invocation{context.budget_unknown_count === 1 ? '' : 's'}
          </span>
        ) : null}
        {(context.compaction_saving_units ?? 0) > 0 ? <span>Compaction saved {formatTokens(context.compaction_saving_units ?? 0)}</span> : null}
        {context.truncation_count > 0 ? <span className="text-amber-300">{context.truncation_count} truncated</span> : null}
        {context.selection_ratio != null && context.selection_ratio < 0.999 ? <span>Selected {formatPercent(context.selection_ratio)}</span> : null}
      </div>

      {sources.length > 0 ? (
        <div className="mt-2.5 space-y-1">
          <p className="text-[8px] uppercase tracking-wide text-muted">Composition</p>
          {sources.map(([source, value]) => (
            <div key={source} className="grid grid-cols-[minmax(0,1fr)_auto_auto] items-center gap-2 text-[9px]">
              <span className="truncate text-slate-300">{sourceLabel(source)}</span>
              <span className="font-mono text-slate-200">{value.units == null ? '—' : formatTokens(value.units)}</span>
              <span className="w-11 text-right text-muted">{formatPercent(value.share)}</span>
            </div>
          ))}
        </div>
      ) : null}

      {context.agents.length > 1 ? (
        <details className="group mt-2.5 border-t border-border/60 pt-2">
          <summary className="flex cursor-pointer list-none items-center gap-1 text-[9px] text-muted hover:text-white">
            <ChevronRight className="h-3 w-3 transition-transform group-open:rotate-90" />
            Context by Agent
          </summary>
          <div className="mt-2 space-y-1.5">
            {context.agents.map((agent) => (
              <div key={agent.agent_id} className="rounded-lg border border-border/70 bg-background/45 px-2.5 py-2">
                <div className="flex items-center justify-between gap-2">
                  <code className="truncate text-[9px] text-slate-300">Agent {agent.agent_id.slice(0, 8)}</code>
                  <span className="text-[8px] text-muted">{agent.model_invocation_count} invocation{agent.model_invocation_count === 1 ? '' : 's'}</span>
                </div>
                <div className="mt-1 flex flex-wrap gap-x-3 gap-y-1 text-[8px] text-muted">
                  <span>Input {agent.input_units == null ? '—' : formatTokens(agent.input_units)}</span>
                  {agent.peak_utilization != null ? <span>Peak {formatPercent(agent.peak_utilization)}</span> : null}
                  {(agent.delegation_units ?? 0) > 0 ? <span>Delegation {formatTokens(agent.delegation_units ?? 0)} · {formatPercent(agent.delegation_share)}</span> : null}
                </div>
              </div>
            ))}
          </div>
        </details>
      ) : null}
    </section>
  )
}

function ExecutionDiagnostics({ data }: { data: NetworkRunDiagnostics }) {
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
        <Metric label="Tool/Skill work" value={formatLatency(data.tool_work_latency_ms)} icon={Wrench} />
      </div>

      <div className="mt-3 flex flex-wrap items-center gap-x-3 gap-y-1 text-[10px] text-muted">
        <span>{data.agent_run_count} Agent Run{data.agent_run_count === 1 ? '' : 's'}</span>
        <span className="inline-flex items-center gap-1"><GitBranch className="h-3 w-3" />{data.delegation_count} delegation{data.delegation_count === 1 ? '' : 's'}</span>
        <span>{data.llm_call_count} LLM call{data.llm_call_count === 1 ? '' : 's'}</span>
        <span>{data.tool_call_count} Tool/Skill operations</span>
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

export function NetworkRunDiagnosticsPanel({
  executionId,
  projectId,
  running,
  mode = 'all',
}: {
  executionId: string
  projectId: string
  running: boolean
  mode?: DiagnosticsMode
}) {
  const { data, isLoading, isError } = useQuery({
    queryKey: ['network-run-diagnostics', projectId, executionId],
    queryFn: () => getNetworkRunDiagnostics(executionId, projectId),
    refetchInterval: running ? 1_500 : false,
    refetchIntervalInBackground: false,
    staleTime: running ? 0 : 30_000,
  })

  const label = mode === 'context' ? 'Context overview' : 'Execution diagnostics'

  if (isLoading) {
    return (
      <section className="rounded-xl border border-border/75 bg-background/30 p-3">
        <p className="text-[9px] font-semibold uppercase tracking-wide text-muted">{label}</p>
        <p className="mt-2 text-[10px] text-muted">Loading Network Run metrics…</p>
      </section>
    )
  }

  if (isError || !data) {
    return (
      <section className="rounded-xl border border-border/75 bg-background/30 p-3">
        <p className="text-[9px] font-semibold uppercase tracking-wide text-muted">{label}</p>
        <p className="mt-2 text-[10px] text-muted">Network Run metrics are unavailable.</p>
      </section>
    )
  }

  if (mode === 'execution') return <ExecutionDiagnostics data={data} />
  if (mode === 'context') return <NetworkContextOverviewPanel context={data.context} standalone />

  return (
    <section className="space-y-3">
      <ExecutionDiagnostics data={data} />
      <NetworkContextOverviewPanel context={data.context} standalone />
    </section>
  )
}
