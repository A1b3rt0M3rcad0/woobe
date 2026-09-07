import { Link } from 'react-router-dom'
import {
  AlertTriangle,
  ChevronRight,
  Database,
  ExternalLink,
  Gauge,
  Layers3,
  Network,
  Workflow,
} from 'lucide-react'

import type {
  ProjectUsageBreakdownRow,
  ProjectUsageComposition,
  ProjectUsageDataQuality,
  ProjectUsageExecution,
  UsageGroupBy,
} from '../types'
import { formatKnownMoney } from '@/lib/formatters/money'
import { cn } from '@/lib/utils'

const groupLabels: Record<UsageGroupBy, { singular: string; plural: string }> = {
  agent: { singular: 'Agent', plural: 'Agents' },
  network: { singular: 'Network', plural: 'Networks' },
  model: { singular: 'Model', plural: 'Models' },
  provider: { singular: 'Provider', plural: 'Providers' },
  environment: { singular: 'Environment', plural: 'Environments' },
  release: { singular: 'Release', plural: 'Releases' },
}

function formatNumber(value: number) {
  return new Intl.NumberFormat('en-US', {
    notation: value >= 10_000 ? 'compact' : 'standard',
    maximumFractionDigits: 1,
  }).format(value)
}

function formatDuration(value: number | null) {
  if (value === null) return '—'
  if (value < 1_000) return `${Math.round(value)}ms`
  return `${(value / 1_000).toFixed(value >= 10_000 ? 1 : 2)}s`
}

function isUuid(value: string) {
  return /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(value)
}

function canDrill(groupBy: UsageGroupBy, row: ProjectUsageBreakdownRow) {
  if (row.key === 'unattributed' || row.key === 'direct' || row.key === 'others') return false
  if (groupBy === 'provider') return false
  if (groupBy === 'model') return isUuid(row.key)
  return true
}

function aggregateOthers(rows: ProjectUsageBreakdownRow[]): ProjectUsageBreakdownRow | null {
  if (!rows.length) return null
  const knownRows = rows.filter((row) => row.known_cost_usd !== null)
  const agentRuns = rows.reduce((sum, row) => sum + row.agent_runs, 0)
  const pricedRuns = rows.reduce((sum, row) => (
    sum + ((row.cost_coverage_percent ?? 0) / 100) * row.agent_runs
  ), 0)
  const knownCost = knownRows.length
    ? knownRows.reduce((sum, row) => sum + (row.known_cost_usd ?? 0), 0)
    : null
  const unitCost = knownCost !== null && pricedRuns ? knownCost / pricedRuns : null

  return {
    key: 'others',
    label: 'Others',
    known_cost_usd: knownCost,
    share_percent: rows.reduce((sum, row) => sum + row.share_percent, 0),
    agent_runs: agentRuns,
    network_runs: rows.reduce((sum, row) => sum + row.network_runs, 0),
    successful_agent_runs: rows.reduce((sum, row) => sum + row.successful_agent_runs, 0),
    llm_calls: rows.reduce((sum, row) => sum + row.llm_calls, 0),
    input_tokens: rows.reduce((sum, row) => sum + row.input_tokens, 0),
    output_tokens: rows.reduce((sum, row) => sum + row.output_tokens, 0),
    cost_per_priced_agent_run: unitCost,
    cost_coverage_percent: agentRuns ? (pricedRuns / agentRuns) * 100 : null,
    runtime_requests: agentRuns,
    successful_requests: rows.reduce((sum, row) => sum + row.successful_agent_runs, 0),
    cost_per_priced_request: unitCost,
  }
}

export function UsageOperations({
  breakdown,
  composition,
  quality,
  executions,
  groupBy,
  contextLabel,
  workspaceId,
  projectId,
  onSelectDriver,
}: {
  breakdown: ProjectUsageBreakdownRow[]
  composition: ProjectUsageComposition
  quality: ProjectUsageDataQuality
  executions: ProjectUsageExecution[]
  groupBy: UsageGroupBy
  contextLabel: string
  workspaceId: string
  projectId: string
  onSelectDriver: (row: ProjectUsageBreakdownRow) => void
}) {
  const primaryRows = breakdown.slice(0, 5)
  const others = aggregateOthers(breakdown.slice(5))
  const driverRows = others ? [...primaryRows, others] : primaryRows
  const totalRuns = breakdown.reduce((sum, row) => sum + row.agent_runs, 0)
  const totalCalls = breakdown.reduce((sum, row) => sum + row.llm_calls, 0)
  const totalTokens = breakdown.reduce((sum, row) => sum + row.input_tokens + row.output_tokens, 0)
  const knownSpend = breakdown.reduce((sum, row) => sum + (row.known_cost_usd ?? 0), 0)
  const callsPerRun = totalRuns ? totalCalls / totalRuns : 0
  const tokensPerRun = totalRuns ? totalTokens / totalRuns : 0
  const costPerRun = totalRuns ? knownSpend / totalRuns : 0
  const agentCoverageBase = quality.fully_priced_agent_runs + quality.partial_agent_runs + quality.unpriced_agent_runs
  const agentCoverage = agentCoverageBase ? (quality.fully_priced_agent_runs / agentCoverageBase) * 100 : null
  const networkCoverageBase = quality.fully_priced_network_runs + quality.partial_network_runs + quality.unpriced_network_runs
  const networkCoverage = networkCoverageBase ? (quality.fully_priced_network_runs / networkCoverageBase) * 100 : null
  const labels = groupLabels[groupBy]

  return (
    <div className="space-y-4">
      <div className="grid gap-4 xl:grid-cols-12">
        <section className="overflow-hidden rounded-xl border border-border/90 bg-surface/70 xl:col-span-8">
          <div className="flex flex-col gap-2 border-b border-border px-4 py-3 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <h2 className="text-sm font-semibold text-white">Operational cost by {labels.singular}</h2>
              <p className="mt-1 text-xs text-muted">{contextLabel} Cost is attributed from Agent Runs; Network rows aggregate their internal Agent Runs.</p>
            </div>
            <span className="w-fit rounded-md border border-border/80 bg-background/45 px-2 py-1 text-[10px] font-semibold uppercase tracking-wider text-muted">
              {labels.singular}
            </span>
          </div>

          {driverRows.length === 0 ? (
            <div className="px-4 py-10 text-center text-sm text-muted">No attributed run cost for this scope.</div>
          ) : (
            <div className="space-y-2 p-4">
              {driverRows.map((row, index) => {
                const drillable = canDrill(groupBy, row)
                const content = (
                  <div className="flex min-w-0 items-center gap-3">
                    <span className="w-5 shrink-0 text-[10px] font-semibold text-muted">
                      {row.key === 'others' ? '—' : index + 1}
                    </span>
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center justify-between gap-3">
                        <p className="truncate text-xs font-medium text-white" title={row.label}>{row.label}</p>
                        <div className="flex shrink-0 items-center gap-3 text-xs">
                          <span className="text-muted">{row.share_percent.toFixed(1)}%</span>
                          <span className="min-w-[84px] text-right font-medium text-white">{formatKnownMoney(row.known_cost_usd)}</span>
                          {drillable && <ChevronRight className="h-3.5 w-3.5 text-primary-light" />}
                        </div>
                      </div>
                      <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-background/60">
                        <div
                          className={row.key === 'others' ? 'h-full rounded-full bg-muted/50' : 'h-full rounded-full bg-primary'}
                          style={{ width: `${Math.max(Math.min(row.share_percent, 100), row.share_percent > 0 ? 2 : 0)}%` }}
                        />
                      </div>
                      <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-[10px] text-muted">
                        <span>{formatNumber(row.agent_runs)} Agent Runs</span>
                        {row.network_runs > 0 && <span>{formatNumber(row.network_runs)} Network Runs</span>}
                        <span>{formatKnownMoney(row.cost_per_priced_agent_run)} / priced Agent Run</span>
                        <span>{row.cost_coverage_percent === null ? 'No price coverage' : `${row.cost_coverage_percent.toFixed(1)}% priced`}</span>
                      </div>
                    </div>
                  </div>
                )

                return drillable ? (
                  <button
                    key={row.key}
                    type="button"
                    onClick={() => onSelectDriver(row)}
                    className="w-full rounded-lg border border-border/70 bg-background/20 p-3 text-left transition-colors hover:border-primary/30 hover:bg-primary/5"
                  >
                    {content}
                  </button>
                ) : (
                  <div key={row.key} className="rounded-lg border border-border/70 bg-background/20 p-3">
                    {content}
                  </div>
                )
              })}
            </div>
          )}
        </section>

        <div className="space-y-4 xl:col-span-4">
          <section className="rounded-xl border border-border/90 bg-surface/70 p-4">
            <div className="flex items-center gap-2">
              <Gauge className="h-4 w-4 text-primary-light" />
              <h2 className="text-sm font-semibold text-white">Agent Run efficiency</h2>
            </div>
            <div className="mt-4 grid grid-cols-2 gap-2">
              <div className="rounded-lg border border-border/60 bg-background/25 p-3">
                <p className="text-[9px] uppercase tracking-wider text-muted">Known cost / run</p>
                <p className="mt-1 text-sm font-semibold text-white">{formatKnownMoney(costPerRun)}</p>
              </div>
              <div className="rounded-lg border border-border/60 bg-background/25 p-3">
                <p className="text-[9px] uppercase tracking-wider text-muted">LLM calls / run</p>
                <p className="mt-1 text-sm font-semibold text-white">{callsPerRun.toFixed(2)}</p>
              </div>
              <div className="rounded-lg border border-border/60 bg-background/25 p-3">
                <p className="text-[9px] uppercase tracking-wider text-muted">Tokens / run</p>
                <p className="mt-1 text-sm font-semibold text-white">{formatNumber(tokensPerRun)}</p>
              </div>
              <div className="rounded-lg border border-border/60 bg-background/25 p-3">
                <p className="text-[9px] uppercase tracking-wider text-muted">Tool/Skill operations</p>
                <p className="mt-1 text-sm font-semibold text-white">{formatNumber(composition.tool_calls)}</p>
              </div>
            </div>
            <div className="mt-3 rounded-lg border border-border/60 bg-background/25 p-3 text-[10px] leading-4 text-muted">
              <Layers3 className="mr-1 inline h-3.5 w-3.5 text-primary-light" />
              {formatNumber(composition.input_tokens)} input · {formatNumber(composition.output_tokens)} output · {formatNumber(composition.embedding_tokens)} embedding tokens
            </div>
          </section>

          <section className="rounded-xl border border-border/90 bg-surface/70 p-4">
            <div className="flex items-center gap-2">
              <Database className="h-4 w-4 text-primary-light" />
              <h2 className="text-sm font-semibold text-white">Cost coverage</h2>
            </div>
            <div className="mt-4 space-y-4">
              <div>
                <div className="flex items-center justify-between text-xs">
                  <span className="text-muted">Agent Runs</span>
                  <span className={agentCoverage === 100 ? 'font-semibold text-emerald-300' : 'font-semibold text-amber-300'}>
                    {agentCoverage === null ? '—' : `${agentCoverage.toFixed(1)}%`}
                  </span>
                </div>
                <div className="mt-2 h-2 overflow-hidden rounded-full bg-background/60">
                  <div className={agentCoverage === 100 ? 'h-full rounded-full bg-emerald-400' : 'h-full rounded-full bg-amber-300'} style={{ width: `${agentCoverage ?? 0}%` }} />
                </div>
                <p className="mt-1 text-[10px] text-muted">{quality.partial_agent_runs} partial · {quality.unpriced_agent_runs} unpriced</p>
              </div>
              <div>
                <div className="flex items-center justify-between text-xs">
                  <span className="text-muted">Network Runs</span>
                  <span className={networkCoverage === 100 ? 'font-semibold text-emerald-300' : 'font-semibold text-amber-300'}>
                    {networkCoverage === null ? '—' : `${networkCoverage.toFixed(1)}%`}
                  </span>
                </div>
                <div className="mt-2 h-2 overflow-hidden rounded-full bg-background/60">
                  <div className={networkCoverage === 100 ? 'h-full rounded-full bg-emerald-400' : 'h-full rounded-full bg-amber-300'} style={{ width: `${networkCoverage ?? 0}%` }} />
                </div>
                <p className="mt-1 text-[10px] text-muted">{quality.partial_network_runs} partial · {quality.unpriced_network_runs} unpriced</p>
              </div>
            </div>
            {(quality.partial_agent_runs > 0 || quality.unpriced_agent_runs > 0) && (
              <div className="mt-4 flex gap-2 rounded-lg border border-amber-400/20 bg-amber-400/5 p-3 text-[10px] leading-4 text-amber-200">
                <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
                Known cost is a subtotal when pricing is partial. Missing cost is never converted to zero.
              </div>
            )}
          </section>
        </div>
      </div>

      <section className="overflow-hidden rounded-xl border border-border/90 bg-surface/70">
        <div className="flex flex-col gap-2 border-b border-border px-4 py-3 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h2 className="text-sm font-semibold text-white">Most expensive Runs</h2>
            <p className="mt-1 text-xs text-muted">Direct Agent Runs and Network Runs. Internal Agent Runs are represented inside their Network Run to avoid duplicate operational rows.</p>
          </div>
          <Link
            to={`/workspaces/${workspaceId}/projects/${projectId}/traces`}
            className="inline-flex w-fit items-center gap-1 text-xs font-medium text-primary-light hover:text-white"
          >
            Open diagnostics <ExternalLink className="h-3 w-3" />
          </Link>
        </div>

        {executions.length === 0 ? (
          <div className="px-4 py-10 text-center text-sm text-muted">No terminal Runs in this scope.</div>
        ) : (
          <div className="divide-y divide-border/70">
            {executions.slice(0, 8).map((execution) => {
              const isNetwork = execution.run_type === 'network'
              const targetUrl = isNetwork
                ? `/workspaces/${workspaceId}/projects/${projectId}/network?network_run_id=${execution.run_id}`
                : `/workspaces/${workspaceId}/projects/${projectId}/traces?trace_id=${execution.trace_id ?? execution.run_id}`
              return (
                <div key={`${execution.run_type}-${execution.run_id}`} className="grid gap-3 px-4 py-3 transition-colors hover:bg-background/25 md:grid-cols-[minmax(0,1fr)_auto_auto] md:items-center">
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      {isNetwork ? <Network className="h-3.5 w-3.5 text-violet-300" /> : <Workflow className="h-3.5 w-3.5 text-primary-light" />}
                      <p className="truncate text-xs font-medium text-white">
                        {isNetwork ? execution.network_name ?? 'Network Run' : execution.agent_name ?? 'Unattributed Agent'}
                      </p>
                      <span className="rounded-md border border-border/80 bg-background/45 px-1.5 py-0.5 text-[9px] font-semibold uppercase tracking-wider text-muted">
                        {isNetwork ? 'Network Run' : 'Agent Run'}
                      </span>
                      <span className={cn(
                        'rounded-md border px-1.5 py-0.5 text-[9px] font-semibold uppercase tracking-wider',
                        execution.status === 'completed'
                          ? 'border-emerald-400/20 bg-emerald-400/5 text-emerald-300'
                          : 'border-amber-400/20 bg-amber-400/5 text-amber-300',
                      )}>
                        {execution.status}
                      </span>
                    </div>
                    <p className="mt-1 truncate text-[10px] text-muted">
                      {execution.environment ?? 'unknown environment'}
                      {isNetwork
                        ? ` · ${execution.agent_runs_count} Agent Runs`
                        : ` · ${execution.provider ?? 'Unknown provider'} / ${execution.model ?? 'Unknown model'}`}
                    </p>
                  </div>
                  <div className="flex flex-wrap gap-3 text-[10px] text-muted md:justify-end">
                    <span>{formatDuration(execution.duration_ms)}</span>
                    <span>{execution.llm_calls} LLM calls</span>
                    <span>{formatNumber(execution.input_tokens + execution.output_tokens)} tokens</span>
                  </div>
                  <div className="flex items-center justify-between gap-3 md:justify-end">
                    <span className={execution.cost_status === 'known' ? 'text-xs font-semibold text-white' : 'text-xs font-semibold text-amber-300'}>
                      {formatKnownMoney(execution.known_cost_usd)}
                    </span>
                    <Link to={targetUrl} className="inline-flex items-center gap-1 text-[10px] font-medium text-primary-light hover:text-white">
                      Open <ExternalLink className="h-3 w-3" />
                    </Link>
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </section>
    </div>
  )
}
