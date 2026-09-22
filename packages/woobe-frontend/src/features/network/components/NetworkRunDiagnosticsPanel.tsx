import { useQuery } from '@tanstack/react-query'
import {
  Activity,
  AlertTriangle,
  Bot,
  Brain,
  CheckCircle,
  ChevronRight,
  Coins,
  Cpu,
  Database,
  Gauge,
  GitBranch,
  Wrench,
  XCircle,
  type LucideIcon,
} from 'lucide-react'

import { getNetworkRunDiagnostics } from '@/features/network/api'
import { formatCurrency, formatLatency, formatTokens } from '@/lib/formatters/number'
import { cn } from '@/lib/utils'

import type { NetworkAgentInvocation } from './networkChatExecution'
import type { NetworkContextOverview, NetworkRunDiagnostics } from './networkRunDiagnosticsTypes'

function MetricCard({
  label,
  value,
  icon: Icon,
  hint,
}: {
  label: string
  value: string
  icon: LucideIcon
  hint?: string
}) {
  return (
    <div className="rounded-control border border-border bg-background px-ui-sm py-ui-sm" title={hint}>
      <div className="flex items-center gap-ui-xs text-muted-foreground">
        <Icon className="h-3.5 w-3.5" />
        <span className="font-mono text-system-meta uppercase tracking-ui-label">{label}</span>
      </div>
      <p className="mt-ui-xs truncate font-mono text-system-heading text-white">{value}</p>
    </div>
  )
}

function telemetryLabel(status: NetworkRunDiagnostics['telemetry_status']) {
  if (status === 'complete') return 'complete'
  if (status === 'partial') return 'partial'
  return 'unavailable'
}

function costValue(diagnostics: NetworkRunDiagnostics) {
  if (diagnostics.cost_status === 'unknown' || diagnostics.cost_usd == null) return 'Unknown'
  const value = formatCurrency(diagnostics.cost_usd)
  return diagnostics.cost_status === 'partial' ? `${value}+` : value
}

function formatPercent(value: number | null | undefined) {
  if (value == null || !Number.isFinite(value)) return '—'
  return `${(value * 100).toFixed(value >= 0.1 ? 1 : 2)}%`
}

function sourceLabel(source: string) {
  switch (source) {
    case 'SYSTEM': return 'System instructions'
    case 'SKILL': return 'Skills'
    case 'SESSION': return 'Conversation'
    case 'USER_INPUT': return 'Current input'
    case 'KNOWLEDGE': return 'Knowledge'
    case 'TOOL': return 'Tool/Skill results'
    case 'DELEGATION': return 'Delegation'
    case 'RUNTIME': return 'Runtime instructions'
    case 'ARTIFACT': return 'Artifacts'
    case 'MEMORY': return 'Memory'
    case 'CHECKPOINT': return 'Checkpoint'
    case 'TOOL_DEFINITIONS': return 'Tool/Skill definitions'
    default: return source
  }
}

function ContextComposition({ context }: { context: NetworkContextOverview }) {
  const sources = Object.entries(context.source_units)
    .filter(([, value]) => (value.units ?? 0) > 0)
    .sort(([, left], [, right]) => (right.units ?? 0) - (left.units ?? 0))
  const trackedUnits = sources.reduce((total, [, value]) => total + (value.units ?? 0), 0)

  return (
    <section className="rounded-control border border-border bg-background px-ui-sm py-ui-sm">
      <div className="flex items-end justify-between gap-ui-md">
        <div>
          <p className="font-mono text-system-label font-semibold uppercase tracking-ui-label text-muted-foreground">Input composition</p>
          <p className="mt-ui-hairline font-sans text-product-caption text-slate-300">Cumulative across {context.model_invocation_count} Model Invocation{context.model_invocation_count === 1 ? '' : 's'}</p>
        </div>
        <div className="text-right">
          <p className="font-mono text-product-small text-white">{trackedUnits > 0 ? formatTokens(trackedUnits) : '—'}</p>
          <p className="font-mono text-system-meta text-muted-foreground">{context.input_measurement}</p>
        </div>
      </div>

      {context.telemetry_status === 'unknown' || context.model_invocation_count === 0 ? (
        <p className="mt-ui-md font-sans text-product-caption text-muted-foreground">Context evidence is not available for the child Agent Runs yet.</p>
      ) : sources.length ? (
        <div className="mt-ui-md space-y-ui-sm">
          {sources.map(([source, value]) => {
            const share = value.share ?? (trackedUnits > 0 && value.units != null ? value.units / trackedUnits : null)
            return (
              <div key={source}>
                <div className="grid grid-cols-[minmax(0,1fr)_auto_auto] items-center gap-ui-sm font-mono text-system-meta">
                  <span className="truncate text-slate-300">{sourceLabel(source)}</span>
                  <span className="text-slate-200">{value.units == null ? '—' : formatTokens(value.units)}</span>
                  <span className="w-11 text-right text-muted-foreground">{formatPercent(share)}</span>
                </div>
                <div className="mt-ui-xs h-1 overflow-hidden rounded-technical bg-surface">
                  <div className="h-full bg-primary/45" style={{ width: `${Math.max(0, Math.min(100, (share ?? 0) * 100))}%` }} />
                </div>
              </div>
            )
          })}
        </div>
      ) : (
        <p className="mt-ui-md font-sans text-product-caption text-muted-foreground">No source-level Context composition was persisted for this Network Run.</p>
      )}

      <div className="mt-ui-sm flex flex-wrap gap-x-ui-md gap-y-ui-xs font-mono text-system-meta text-muted-foreground">
        {context.median_utilization != null ? <span>Median utilization {formatPercent(context.median_utilization)}</span> : null}
        {context.peak_utilization != null ? <span>Peak {formatPercent(context.peak_utilization)}</span> : null}
        {context.budget_unknown_count > 0 ? <span className="text-amber-300">Budget unavailable on {context.budget_unknown_count}</span> : null}
        {(context.compaction_saving_units ?? 0) > 0 ? <span>Compaction saved {formatTokens(context.compaction_saving_units ?? 0)}</span> : null}
        {context.truncation_count > 0 ? <span className="text-amber-300">{context.truncation_count} truncated</span> : null}
      </div>

      {context.budget_unknown_count > 0 ? (
        <p className="mt-ui-sm font-sans text-system-meta leading-4 text-amber-300">
          Input usage is still counted. For future Runs, configure the Context Window of each invoked Model or set a Custom input budget in Agent Context Configuration.
        </p>
      ) : null}
      <p className="mt-ui-sm font-sans text-system-meta leading-4 text-muted-foreground">Source shares use persisted Context units aggregated from child Model Invocations. They are not a proportional allocation of USD cost.</p>
    </section>
  )
}

type AgentRunRow = {
  invocation: NetworkAgentInvocation
  depth: number
}

function flattenAgentRuns(root: NetworkAgentInvocation): AgentRunRow[] {
  const rows: AgentRunRow[] = []
  const visit = (invocation: NetworkAgentInvocation, depth: number) => {
    rows.push({ invocation, depth })
    invocation.children.forEach((child) => visit(child, depth + 1))
  }
  visit(root, 0)
  return rows
}

function invocationTotalTokens(invocation: NetworkAgentInvocation): number | null {
  if (!invocation.usage) return null
  if (invocation.usage.total_tokens != null) return invocation.usage.total_tokens
  if (invocation.usage.input_tokens == null || invocation.usage.output_tokens == null) return null
  return invocation.usage.input_tokens + invocation.usage.output_tokens
}

function statusMeta(status: NetworkAgentInvocation['status']) {
  if (status === 'error') return { label: 'Failed', className: 'text-red-300' }
  if (status === 'cancelled') return { label: 'Cancelled', className: 'text-slate-300' }
  if (status === 'running' || status === 'pending') return { label: 'Running', className: 'text-blue-300' }
  if (status === 'skipped') return { label: 'Skipped', className: 'text-amber-300' }
  return { label: 'Completed', className: 'text-emerald-300' }
}

function AgentRunDetails({
  root,
  onOpenAgentRun,
}: {
  root: NetworkAgentInvocation
  onOpenAgentRun?: (invocation: NetworkAgentInvocation) => void
}) {
  const rows = flattenAgentRuns(root)

  return (
    <div>
      {rows.map(({ invocation, depth }) => {
        const totalTokens = invocationTotalTokens(invocation)
        const status = statusMeta(invocation.status)
        return (
          <button
            key={invocation.spanId}
            type="button"
            disabled={!onOpenAgentRun}
            onClick={() => onOpenAgentRun?.(invocation)}
            className={cn(
              'flex w-full items-center gap-ui-sm border-t border-border/70 py-ui-sm text-left first:border-t-0',
              onOpenAgentRun ? 'hover:bg-background/35' : 'cursor-default',
            )}
          >
            <ChevronRight className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-ui-xs font-mono text-system-meta uppercase tracking-ui-label">
                <span className="text-muted-foreground">{depth === 0 ? 'Entry Agent' : 'Delegated Agent'}</span>
                <span className={status.className}>· {status.label}</span>
              </div>
              <p className="mt-ui-hairline truncate font-sans text-product-caption font-medium text-slate-200">{invocation.agentName}</p>
              <p className="truncate font-mono text-system-meta text-muted-foreground">{invocation.source} · {invocation.version}{invocation.provider || invocation.model ? ` · ${invocation.provider || '—'}/${invocation.model || '—'}` : ''}</p>
            </div>
            <div className="shrink-0 text-right">
              <p className="font-mono text-system-label text-slate-300">{totalTokens == null ? '—' : formatTokens(totalTokens)}</p>
              <p className="font-mono text-system-meta text-muted-foreground">{invocation.durationMs == null ? 'Running' : formatLatency(invocation.durationMs)} · {invocation.costUsd == null ? 'Unknown' : formatCurrency(invocation.costUsd)}</p>
            </div>
          </button>
        )
      })}
    </div>
  )
}

function ExecutionBreakdown({ data }: { data: NetworkRunDiagnostics }) {
  return (
    <div className="space-y-ui-sm border-t border-border/70 pt-ui-md">
      <p className="font-mono text-system-label font-semibold uppercase tracking-ui-label text-muted-foreground">Execution breakdown</p>
      <div className="grid grid-cols-2 gap-ui-xs">
        <MetricCard label="Network wall" value={formatLatency(data.network_wall_latency_ms)} icon={Activity} />
        <MetricCard label="Agent work Σ" value={formatLatency(data.agent_work_latency_ms)} icon={Bot} />
        <MetricCard label="LLM work Σ" value={formatLatency(data.llm_runtime_latency_ms)} icon={Cpu} />
        <MetricCard label="Tool/Skill work Σ" value={formatLatency(data.tool_work_latency_ms)} icon={Wrench} />
      </div>
      <div className="flex flex-wrap gap-x-ui-md gap-y-ui-xs font-mono text-system-meta text-muted-foreground">
        {data.prepare_latency_ms != null ? <span>Setup Σ {formatLatency(data.prepare_latency_ms)}</span> : null}
        {data.persistence_latency_ms != null ? <span className="inline-flex items-center gap-ui-xs"><Database className="h-3 w-3" />Persistence Σ {formatLatency(data.persistence_latency_ms)}</span> : null}
        {data.orchestration_latency_ms != null ? <span>Agent orchestration Σ {formatLatency(data.orchestration_latency_ms)}</span> : null}
        <span>Depth {data.max_depth}</span>
        <span>Fan-out {data.max_fan_out}</span>
      </div>
    </div>
  )
}

function ContextByAgent({ context, root }: { context: NetworkContextOverview; root: NetworkAgentInvocation }) {
  if (context.agents.length <= 1) return null
  const names = new Map(flattenAgentRuns(root).map(({ invocation }) => [invocation.agentId, invocation.agentName]))

  return (
    <div className="space-y-ui-sm border-t border-border/70 pt-ui-md">
      <p className="font-mono text-system-label font-semibold uppercase tracking-ui-label text-muted-foreground">Context by Agent</p>
      <div className="space-y-ui-xs">
        {context.agents.map((agent) => (
          <div key={agent.agent_id} className="rounded-control border border-border/70 bg-background/35 px-ui-sm py-ui-sm">
            <div className="flex items-center justify-between gap-ui-sm">
              <p className="truncate font-sans text-product-caption font-medium text-slate-300">{names.get(agent.agent_id) || `Agent ${agent.agent_id.slice(0, 8)}`}</p>
              <span className="font-mono text-system-meta text-muted-foreground">{agent.model_invocation_count} invocation{agent.model_invocation_count === 1 ? '' : 's'}</span>
            </div>
            <div className="mt-ui-xs flex flex-wrap gap-x-ui-md gap-y-ui-xs font-mono text-system-meta text-muted-foreground">
              <span>{agent.agent_run_count} Agent Run{agent.agent_run_count === 1 ? '' : 's'}</span>
              <span>Input {agent.input_units == null ? '—' : formatTokens(agent.input_units)}</span>
              {agent.peak_utilization != null ? <span>Peak {formatPercent(agent.peak_utilization)}</span> : null}
              {(agent.delegation_units ?? 0) > 0 ? <span>Delegation {formatTokens(agent.delegation_units ?? 0)} · {formatPercent(agent.delegation_share)}</span> : null}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

export function NetworkRunDiagnosticsPanel({
  executionId,
  projectId,
  running,
  root,
  onOpenAgentRun,
}: {
  executionId: string
  projectId: string
  running: boolean
  root: NetworkAgentInvocation
  onOpenAgentRun?: (invocation: NetworkAgentInvocation) => void
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
      <section className="space-y-ui-sm">
        <p className="font-mono text-system-heading font-medium text-white">Network Run Analytics</p>
        <p className="font-sans text-product-caption text-muted-foreground">Loading Network Run metrics…</p>
      </section>
    )
  }

  if (isError || !data) {
    return (
      <section className="space-y-ui-sm rounded-control border border-border bg-background px-ui-md py-ui-md">
        <div className="flex items-center gap-ui-xs text-amber-300"><AlertTriangle className="h-3.5 w-3.5" /><p className="font-sans text-product-caption font-medium">Network Run Analytics unavailable</p></div>
        <p className="font-sans text-product-caption text-muted-foreground">The Network Run remains inspectable through Path and Evidence.</p>
      </section>
    )
  }

  const totalTokens = data.total_tokens ?? (data.input_tokens != null && data.output_tokens != null ? data.input_tokens + data.output_tokens : null)

  return (
    <section className="space-y-ui-md">
      <div className="flex items-start justify-between gap-ui-md">
        <div>
          <p className="font-mono text-system-heading font-medium text-white">Network Run Analytics</p>
          <p className="mt-ui-xs font-sans text-product-caption text-muted-foreground">Network-level totals first; individual Agent Runs remain available on demand.</p>
        </div>
        {data.fallback_count > 0 ? <span className="rounded-technical border border-amber-500/25 bg-amber-500/10 px-ui-sm py-ui-hairline font-mono text-system-meta text-amber-300">{data.fallback_count} fallback{data.fallback_count === 1 ? '' : 's'}</span> : null}
      </div>

      <div className="grid grid-cols-3 gap-ui-xs">
        <MetricCard label="Cost" value={costValue(data)} icon={Coins} hint="Aggregated Network Run cost across child Agent Runs when pricing is known." />
        <MetricCard label="Total tokens" value={totalTokens == null ? '—' : formatTokens(totalTokens)} icon={Gauge} hint="Aggregated token usage across the Network Run." />
        <MetricCard label="Runtime" value={formatLatency(data.network_wall_latency_ms)} icon={Activity} />
        <MetricCard label="Agent Runs" value={String(data.agent_run_count)} icon={Bot} />
        <MetricCard label="Model invocations" value={String(data.llm_call_count)} icon={Cpu} />
        <MetricCard label="Tool/Skill ops" value={String(data.tool_call_count)} icon={Wrench} />
      </div>

      <div className="flex flex-wrap items-center gap-x-ui-md gap-y-ui-xs font-mono text-system-meta text-muted-foreground">
        {data.input_tokens != null || data.output_tokens != null ? (
          <span>Tokens {data.input_tokens == null ? '—' : formatTokens(data.input_tokens)} in → {data.output_tokens == null ? '—' : formatTokens(data.output_tokens)} out{data.usage_complete ? '' : ' · partial'}</span>
        ) : <span>Token usage unavailable</span>}
        <span className="inline-flex items-center gap-ui-xs"><GitBranch className="h-3 w-3" />{data.delegation_count} delegation{data.delegation_count === 1 ? '' : 's'}</span>
        {data.source_count > 0 ? <span><Brain className="mr-ui-xs inline h-3 w-3" />{data.source_count} source{data.source_count === 1 ? '' : 's'}</span> : null}
        <span className="inline-flex items-center gap-ui-xs text-emerald-400"><CheckCircle className="h-3 w-3" />{data.successful_tool_calls}</span>
        {data.failed_tool_calls > 0 ? <span className="inline-flex items-center gap-ui-xs text-red-300"><XCircle className="h-3 w-3" />{data.failed_tool_calls}</span> : null}
        <span>Telemetry {telemetryLabel(data.telemetry_status)}</span>
        <span>Cost telemetry {data.cost_status}</span>
      </div>

      <ContextComposition context={data.context} />

      <details className="group rounded-control border border-border/80 bg-background/30 px-ui-sm">
        <summary className="flex cursor-pointer list-none items-center gap-ui-sm py-ui-sm font-mono text-system-micro font-medium text-muted-foreground transition-colors hover:text-white">
          <ChevronRight className="h-3.5 w-3.5 transition-transform group-open:rotate-90" />
          More details
          <span className="ml-auto text-system-meta font-normal text-muted-foreground">{data.agent_run_count} Agent Run{data.agent_run_count === 1 ? '' : 's'} · {data.llm_call_count} Model Invocation{data.llm_call_count === 1 ? '' : 's'}</span>
        </summary>
        <div className="border-t border-border/70 pb-ui-md">
          <AgentRunDetails root={root} onOpenAgentRun={onOpenAgentRun} />
          <ExecutionBreakdown data={data} />
          <ContextByAgent context={data.context} root={root} />
        </div>
      </details>
    </section>
  )
}
