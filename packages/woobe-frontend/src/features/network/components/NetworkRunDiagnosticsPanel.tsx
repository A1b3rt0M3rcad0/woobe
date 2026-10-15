import { ContributionBars } from '@woobe/ui'
import { RunMetrics } from '@/features/traces/components/RunMetrics'
import { useQuery } from '@tanstack/react-query'
import {
  AlertTriangle,
  Brain,
  CheckCircle,
  ChevronRight,
  Database,
  GitBranch,
  XCircle,
} from 'lucide-react'

import { getNetworkRunDiagnostics } from '@/features/network/api'
import { formatCurrency, formatLatency, formatTokens } from '@/lib/formatters/number'
import { cn } from '@/lib/utils'

import type { NetworkAgentInvocation } from './networkChatExecution'
import type { NetworkContextOverview, NetworkRunDiagnostics } from './networkRunDiagnosticsTypes'

function telemetryLabel(status: NetworkRunDiagnostics['telemetry_status']) {
  if (status === 'complete') return 'complete'
  if (status === 'partial') return 'partial'
  return 'unavailable'
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
    .sort(([, left], [, right]) => (right.units ?? 0) - (left.units ?? 0))
  const trackedUnits = sources.reduce((total, [, value]) => total + (value.units ?? 0), 0)

  return (
    <section className="rounded-control border border-border bg-background px-ui-sm py-ui-sm">
      <div className="flex items-end justify-between gap-ui-md">
        <div>
          <p className="font-mono text-system-label font-medium uppercase tracking-ui-label text-muted-foreground">Input composition</p>
          <p className="mt-ui-hairline font-sans text-product-caption text-slate-300">Cumulative across {context.model_invocation_count} Model Invocation{context.model_invocation_count === 1 ? '' : 's'}</p>
        </div>
        <div className="text-right">
          <p className="font-sans text-product-small text-foreground">{sources.some(([, value]) => value.units != null) ? `${formatTokens(trackedUnits)}${sources.some(([, value]) => value.units == null) ? ' known' : ''}` : '—'}</p>
          <p className="font-mono text-system-meta text-muted-foreground">{context.input_measurement}</p>
        </div>
      </div>

      {context.telemetry_status === 'unknown' || context.model_invocation_count === 0 ? (
        <p className="mt-ui-md font-sans text-product-caption text-muted-foreground">Context evidence is not available for the child Agent Runs yet.</p>
      ) : sources.length ? (
        <div className="mt-ui-md"><ContributionBars unit="Persisted contribution units" rows={sources.map(([source, value]) => ({ id: source, label: sourceLabel(source), value: value.units ?? null, share: value.share ?? (trackedUnits > 0 && value.units != null ? value.units / trackedUnits : null) }))} /></div>
      ) : (
        <p className="mt-ui-md font-sans text-product-caption text-muted-foreground">No source-level Context composition was persisted for this Network Run.</p>
      )}

      <div className="mt-ui-sm flex flex-wrap gap-x-ui-md gap-y-ui-xs font-mono text-system-meta text-muted-foreground">
        {context.median_utilization != null ? <span>Median utilization {formatPercent(context.median_utilization)}</span> : null}
        {context.peak_utilization != null ? <span>Peak {formatPercent(context.peak_utilization)}</span> : null}
        {context.budget_unknown_count > 0 ? <span className="text-warning">Budget unavailable on {context.budget_unknown_count}</span> : null}
        {(context.compaction_saving_units ?? 0) > 0 ? <span>Compaction saved {formatTokens(context.compaction_saving_units ?? 0)}</span> : null}
        {context.truncation_count > 0 ? <span className="text-warning">{context.truncation_count} truncated</span> : null}
      </div>

      {context.budget_unknown_count > 0 ? (
        <p className="mt-ui-sm font-sans text-system-meta leading-4 text-warning">
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
  if (status === 'error') return { label: 'Failed', className: 'text-error' }
  if (status === 'cancelled') return { label: 'Cancelled', className: 'text-slate-300' }
  if (status === 'running' || status === 'pending') return { label: 'Running', className: 'text-primary-light' }
  if (status === 'skipped') return { label: 'Skipped', className: 'text-warning' }
  return { label: 'Completed', className: 'text-success' }
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
              <p className="mt-ui-hairline break-words font-sans text-product-small font-medium text-slate-200">{invocation.agentName}</p>
              <p className="break-all font-mono text-system-meta text-muted-foreground">{invocation.source} · {invocation.version}{invocation.provider || invocation.model ? ` · ${invocation.provider || '—'}/${invocation.model || '—'}` : ''}</p>
            </div>
            <div className="shrink-0 text-right">
              <p className="font-mono text-system-label text-slate-300">{totalTokens == null ? '—' : formatTokens(totalTokens)}</p>
              <p className="font-mono text-system-meta text-muted-foreground">{invocation.durationMs == null ? (invocation.status === 'running' || invocation.status === 'pending' ? 'Running' : 'Unavailable') : formatLatency(invocation.durationMs)} · {invocation.costUsd == null ? 'Unknown' : formatCurrency(invocation.costUsd)}</p>
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
      <p className="font-mono text-system-label font-medium uppercase tracking-ui-label text-muted-foreground">Execution breakdown</p>
      <dl className="divide-y divide-border">
        {[['Network wall time', data.network_wall_latency_ms], ['Agent work Σ', data.agent_work_latency_ms], ['Model work Σ', data.llm_runtime_latency_ms], ['Tool / Skill work Σ', data.tool_work_latency_ms]].map(([label, value]) => <div key={String(label)} className="flex justify-between gap-ui-md py-ui-sm"><dt className="font-sans text-chrome-label text-muted-foreground">{label}</dt><dd className="whitespace-nowrap font-mono text-system-meta text-foreground">{formatLatency(value as number | null)}</dd></div>)}
      </dl>
      <p className="font-sans text-system-meta text-muted-foreground">Work totals may overlap. Network wall time measures elapsed time.</p>
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
      <p className="font-mono text-system-label font-medium uppercase tracking-ui-label text-muted-foreground">Context by Agent</p>
      <div className="space-y-ui-xs">
        {context.agents.map((agent) => (
          <div key={agent.agent_id} className="rounded-control border border-border/70 bg-background/35 px-ui-sm py-ui-sm">
            <div className="flex items-center justify-between gap-ui-sm">
              <p className="truncate font-mono text-product-caption font-medium text-slate-300">{names.get(agent.agent_id) || `Agent ${agent.agent_id.slice(0, 8)}`}</p>
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
        <p className="font-sans text-product-body font-medium text-foreground">Network Run Analytics</p>
        <p className="font-sans text-product-caption text-muted-foreground">Loading Network Run metrics…</p>
      </section>
    )
  }

  if (isError || !data) {
    return (
      <section className="space-y-ui-sm rounded-control border border-border bg-background px-ui-md py-ui-md">
        <div className="flex items-center gap-ui-xs text-warning"><AlertTriangle className="h-3.5 w-3.5" /><p className="font-mono text-product-caption font-medium">Network Run Analytics unavailable</p></div>
        <p className="font-sans text-product-caption text-muted-foreground">The Network Run remains inspectable through Path and Evidence.</p>
      </section>
    )
  }

  const totalTokens = data.total_tokens ?? (data.input_tokens != null && data.output_tokens != null ? data.input_tokens + data.output_tokens : null)

  return (
    <section className="space-y-ui-md">
      <div className="flex items-start justify-between gap-ui-md">
        <div>
          <p className="font-sans text-product-body font-medium text-foreground">Network Run Analytics</p>
          <p className="mt-ui-xs font-sans text-product-caption text-muted-foreground">Totals for this Network Run.</p>
        </div>
        {data.fallback_count > 0 ? <span className="rounded-technical border border-amber-500/25 bg-amber-500/10 px-ui-sm py-ui-hairline font-mono text-system-meta text-warning">{data.fallback_count} fallback{data.fallback_count === 1 ? '' : 's'}</span> : null}
      </div>

      <RunMetrics cost={data.cost_usd} costStatus={data.cost_status} tokens={totalTokens} runtime={data.network_wall_latency_ms} counts={[
        { label: 'Agent Runs', value: data.agent_run_count },
        { label: 'Model invocations', value: data.llm_call_count },
        { label: 'Tool / Skill operations', value: data.tool_call_count },
      ]} />

      <div className="flex flex-wrap items-center gap-x-ui-md gap-y-ui-xs font-mono text-system-meta text-muted-foreground">
        {data.input_tokens != null || data.output_tokens != null ? (
          <span>Tokens {data.input_tokens == null ? '—' : formatTokens(data.input_tokens)} in → {data.output_tokens == null ? '—' : formatTokens(data.output_tokens)} out{data.usage_complete ? '' : ' · partial'}</span>
        ) : <span>Token usage unavailable</span>}
        <span className="inline-flex items-center gap-ui-xs"><GitBranch className="h-3 w-3" />{data.delegation_count} delegation{data.delegation_count === 1 ? '' : 's'}</span>
        {data.source_count > 0 ? <span><Brain className="mr-ui-xs inline h-3 w-3" />{data.source_count} source{data.source_count === 1 ? '' : 's'}</span> : null}
        <span className="inline-flex items-center gap-ui-xs text-success"><CheckCircle className="h-3 w-3" />{data.successful_tool_calls}</span>
        {data.failed_tool_calls > 0 ? <span className="inline-flex items-center gap-ui-xs text-error"><XCircle className="h-3 w-3" />{data.failed_tool_calls}</span> : null}
        <span>Telemetry {telemetryLabel(data.telemetry_status)}</span>

      </div>

      <ContextComposition context={data.context} />

      <details className="group rounded-control border border-border/80 bg-background/30 px-ui-sm">
        <summary className="flex cursor-pointer list-none items-center gap-ui-sm py-ui-sm font-sans text-system-micro font-medium text-muted-foreground transition-colors hover:text-foreground">
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
