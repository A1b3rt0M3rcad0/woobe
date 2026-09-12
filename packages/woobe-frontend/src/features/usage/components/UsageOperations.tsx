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

function CoverageRow({ label, value, partial, unpriced }: { label: string; value: number | null; partial: number; unpriced: number }) {
  const complete = value === 100
  return (
    <div className="py-3 first:pt-0 last:pb-0">
      <div className="flex items-center justify-between gap-3">
        <span className="font-mono text-[9px] font-medium text-slate-300">{label}</span>
        <span className={cn('font-mono text-[10px] font-bold tabular-nums', complete ? 'text-emerald-300' : 'text-amber-300')}>
          {value === null ? '—' : `${value.toFixed(1)}%`}
        </span>
      </div>
      <div className="mt-2 h-1 overflow-hidden bg-control">
        <div
          className={cn('h-full', complete ? 'bg-emerald-400/85' : 'bg-amber-300/85')}
          style={{ width: `${value ?? 0}%` }}
        />
      </div>
      <p className="mt-1.5 font-mono text-[8px] text-muted-foreground">{partial} partial · {unpriced} unpriced</p>
    </div>
  )
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
  const incompleteCoverage = quality.partial_agent_runs > 0 || quality.unpriced_agent_runs > 0 || quality.partial_network_runs > 0 || quality.unpriced_network_runs > 0

  return (
    <div className="space-y-4">
      <div className="grid gap-4 xl:grid-cols-12">
        <section className="overflow-hidden rounded-container border border-border bg-surface/[0.88] xl:col-span-8">
          <div className="flex flex-col gap-2 border-b border-border px-4 py-3 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <h2 className="font-mono text-[10px] font-bold text-slate-50">Operational cost by {labels.singular}</h2>
              <p className="mt-1 font-sans text-[10px] leading-4 text-muted-foreground">{contextLabel} Cost is attributed from Agent Runs; Network rows aggregate their internal Agent Runs.</p>
            </div>
            <span className="w-fit rounded-technical border border-border bg-control/50 px-2 py-1 font-mono text-[8px] font-semibold uppercase tracking-[0.11em] text-muted-foreground">{labels.singular}</span>
          </div>

          {driverRows.length === 0 ? (
            <div className="px-4 py-10 text-center font-mono text-[9px] text-muted-foreground">No attributed run cost for this scope.</div>
          ) : (
            <div className="divide-y divide-border/70">
              {driverRows.map((row, index) => {
                const drillable = canDrill(groupBy, row)
                const content = (
                  <div className="flex min-w-0 items-center gap-3 px-4 py-3">
                    <span className="w-5 shrink-0 font-mono text-[8px] font-semibold text-muted-foreground">{row.key === 'others' ? '—' : index + 1}</span>
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center justify-between gap-3">
                        <p className="truncate font-mono text-[9px] font-medium text-slate-100" title={row.label}>{row.label}</p>
                        <div className="flex shrink-0 items-center gap-3 font-mono text-[9px]">
                          <span className="text-muted-foreground">{row.share_percent.toFixed(1)}%</span>
                          <span className="min-w-[84px] text-right font-medium text-slate-100">{formatKnownMoney(row.known_cost_usd)}</span>
                          {drillable ? <ChevronRight className="h-3.5 w-3.5 text-primary-light" /> : null}
                        </div>
                      </div>
                      <div className="mt-2 h-1 overflow-hidden bg-control">
                        <div className={row.key === 'others' ? 'h-full bg-muted-foreground/40' : 'h-full bg-primary/85'} style={{ width: `${Math.max(Math.min(row.share_percent, 100), row.share_percent > 0 ? 2 : 0)}%` }} />
                      </div>
                      <div className="mt-1.5 flex flex-wrap gap-x-4 gap-y-1 font-mono text-[8px] text-muted-foreground">
                        <span>{formatNumber(row.agent_runs)} Agent Runs</span>
                        {row.network_runs > 0 ? <span>{formatNumber(row.network_runs)} Network Runs</span> : null}
                        <span>{formatKnownMoney(row.cost_per_priced_agent_run)} / priced Agent Run</span>
                        <span>{row.cost_coverage_percent === null ? 'No price coverage' : `${row.cost_coverage_percent.toFixed(1)}% priced`}</span>
                      </div>
                    </div>
                  </div>
                )

                return drillable ? (
                  <button key={row.key} type="button" onClick={() => onSelectDriver(row)} className="w-full text-left transition-colors hover:bg-control/25">{content}</button>
                ) : (
                  <div key={row.key}>{content}</div>
                )
              })}
            </div>
          )}
        </section>

        <div className="space-y-4 xl:col-span-4">
          <section className="rounded-container border border-border bg-surface/[0.88]">
            <div className="flex items-center gap-2 border-b border-border px-4 py-3">
              <Gauge className="h-3.5 w-3.5 text-primary-light" />
              <h2 className="font-mono text-[10px] font-bold text-slate-50">Agent Run efficiency</h2>
            </div>
            <div className="grid grid-cols-2 divide-x divide-y divide-border/70">
              <div className="p-3"><p className="font-mono text-[8px] uppercase tracking-[0.1em] text-muted-foreground">Known cost / run</p><p className="mt-1 font-mono text-[11px] font-bold text-slate-100">{formatKnownMoney(costPerRun)}</p></div>
              <div className="p-3"><p className="font-mono text-[8px] uppercase tracking-[0.1em] text-muted-foreground">LLM calls / run</p><p className="mt-1 font-mono text-[11px] font-bold text-slate-100">{callsPerRun.toFixed(2)}</p></div>
              <div className="p-3"><p className="font-mono text-[8px] uppercase tracking-[0.1em] text-muted-foreground">Tokens / run</p><p className="mt-1 font-mono text-[11px] font-bold text-slate-100">{formatNumber(tokensPerRun)}</p></div>
              <div className="p-3"><p className="font-mono text-[8px] uppercase tracking-[0.1em] text-muted-foreground">Tool/Skill operations</p><p className="mt-1 font-mono text-[11px] font-bold text-slate-100">{formatNumber(composition.tool_calls)}</p></div>
            </div>
            <div className="border-t border-border px-4 py-2.5 font-mono text-[8px] leading-4 text-muted-foreground">
              <Layers3 className="mr-1.5 inline h-3.5 w-3.5 text-primary-light" />
              {formatNumber(composition.input_tokens)} input · {formatNumber(composition.output_tokens)} output · {formatNumber(composition.embedding_tokens)} embedding tokens
            </div>
          </section>

          <section className="rounded-container border border-border bg-surface/[0.88]">
            <div className="flex items-center gap-2 border-b border-border px-4 py-3">
              <Database className="h-3.5 w-3.5 text-primary-light" />
              <div>
                <h2 className="font-mono text-[10px] font-bold text-slate-50">Cost coverage</h2>
                <p className="mt-0.5 font-sans text-[9px] text-muted-foreground">Share of Runs with complete pricing data.</p>
              </div>
            </div>
            <div className="divide-y divide-border/70 px-4 py-3">
              <CoverageRow label="Agent Runs" value={agentCoverage} partial={quality.partial_agent_runs} unpriced={quality.unpriced_agent_runs} />
              <CoverageRow label="Network Runs" value={networkCoverage} partial={quality.partial_network_runs} unpriced={quality.unpriced_network_runs} />
            </div>
            {incompleteCoverage ? (
              <div className="flex items-start gap-2 border-t border-border px-4 py-2.5 font-sans text-[9px] leading-4 text-muted-foreground">
                <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0 text-amber-300" />
                <span><span className="text-amber-200">Known cost is a subtotal</span> when pricing is partial. Missing cost is never converted to zero.</span>
              </div>
            ) : null}
          </section>
        </div>
      </div>

      <section className="overflow-hidden rounded-container border border-border bg-surface/[0.88]">
        <div className="flex flex-col gap-2 border-b border-border px-4 py-3 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h2 className="font-mono text-[10px] font-bold text-slate-50">Most expensive Runs</h2>
            <p className="mt-1 font-sans text-[10px] leading-4 text-muted-foreground">Direct Agent Runs and Network Runs. Internal Agent Runs are represented inside their Network Run to avoid duplicate operational rows.</p>
          </div>
          <Link to={`/workspaces/${workspaceId}/projects/${projectId}/traces`} className="inline-flex w-fit items-center gap-1 font-mono text-[9px] font-medium text-primary-light hover:text-slate-50">Open diagnostics <ExternalLink className="h-3 w-3" /></Link>
        </div>

        {executions.length === 0 ? (
          <div className="px-4 py-10 text-center font-mono text-[9px] text-muted-foreground">No terminal Runs in this scope.</div>
        ) : (
          <div className="divide-y divide-border/70">
            {executions.slice(0, 8).map((execution) => {
              const isNetwork = execution.run_type === 'network'
              const targetUrl = isNetwork
                ? `/workspaces/${workspaceId}/projects/${projectId}/network?network_run_id=${execution.run_id}`
                : `/workspaces/${workspaceId}/projects/${projectId}/traces?trace_id=${execution.trace_id ?? execution.run_id}`
              return (
                <div key={`${execution.run_type}-${execution.run_id}`} className="grid gap-3 px-4 py-3 transition-colors hover:bg-control/25 md:grid-cols-[minmax(0,1fr)_auto_auto] md:items-center">
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      {isNetwork ? <Network className="h-3.5 w-3.5 text-violet-300" /> : <Workflow className="h-3.5 w-3.5 text-primary-light" />}
                      <p className="truncate font-mono text-[9px] font-medium text-slate-100">{isNetwork ? execution.network_name ?? 'Network Run' : execution.agent_name ?? 'Unattributed Agent'}</p>
                      <span className="rounded-technical border border-border bg-control/50 px-1.5 py-0.5 font-mono text-[8px] uppercase tracking-[0.09em] text-muted-foreground">{isNetwork ? 'Network Run' : 'Agent Run'}</span>
                      <span className={cn('rounded-technical border px-1.5 py-0.5 font-mono text-[8px] uppercase tracking-[0.09em]', execution.status === 'completed' ? 'border-emerald-400/20 bg-emerald-400/[0.05] text-emerald-300' : 'border-amber-400/20 bg-amber-400/[0.05] text-amber-300')}>{execution.status}</span>
                    </div>
                    <p className="mt-1 truncate font-mono text-[8px] text-muted-foreground">{execution.environment ?? 'unknown environment'}{isNetwork ? ` · ${execution.agent_runs_count} Agent Runs` : ` · ${execution.provider ?? 'Unknown provider'} / ${execution.model ?? 'Unknown model'}`}</p>
                  </div>
                  <div className="flex flex-wrap gap-3 font-mono text-[8px] text-muted-foreground md:justify-end"><span>{formatDuration(execution.duration_ms)}</span><span>{execution.llm_calls} LLM calls</span><span>{formatNumber(execution.input_tokens + execution.output_tokens)} tokens</span></div>
                  <div className="flex items-center justify-between gap-3 md:justify-end">
                    <span className={cn('font-mono text-[9px] font-semibold', execution.cost_status === 'known' ? 'text-slate-100' : 'text-amber-300')}>{formatKnownMoney(execution.known_cost_usd)}</span>
                    <Link to={targetUrl} className="inline-flex items-center gap-1 font-mono text-[8px] font-medium text-primary-light hover:text-slate-50">Open <ExternalLink className="h-3 w-3" /></Link>
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
