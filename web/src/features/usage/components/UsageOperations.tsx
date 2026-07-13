import { Link } from 'react-router-dom'
import {
  AlertTriangle,
  ChevronRight,
  Database,
  ExternalLink,
  Gauge,
  Layers3,
  Workflow,
} from 'lucide-react'

import type {
  ProjectUsageBreakdownRow,
  ProjectUsageComposition,
  ProjectUsageDataQuality,
  ProjectUsageExecution,
  UsageGroupBy,
} from '../types'
import { formatKnownMoney, formatMoney } from '@/lib/formatters/money'
import { cn } from '@/lib/utils'

const groupLabels: Record<UsageGroupBy, { singular: string; plural: string }> = {
  agent: { singular: 'Agent', plural: 'Agents' },
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

function isUuid(value: string) {
  return /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(value)
}

function canDrill(groupBy: UsageGroupBy, row: ProjectUsageBreakdownRow) {
  if (row.key === 'unattributed') return false
  if (groupBy === 'provider') return false
  if (groupBy === 'model') return isUuid(row.key)
  return true
}

function aggregateOthers(rows: ProjectUsageBreakdownRow[]): ProjectUsageBreakdownRow | null {
  if (!rows.length) return null
  const knownRows = rows.filter((row) => row.known_cost_usd !== null)
  const runtimeRequests = rows.reduce((sum, row) => sum + row.runtime_requests, 0)
  const pricedRequests = rows.reduce((sum, row) => (
    sum + ((row.cost_coverage_percent ?? 0) / 100) * row.runtime_requests
  ), 0)
  const knownCost = knownRows.length
    ? knownRows.reduce((sum, row) => sum + (row.known_cost_usd ?? 0), 0)
    : null

  return {
    key: 'others',
    label: 'Others',
    known_cost_usd: knownCost,
    share_percent: rows.reduce((sum, row) => sum + row.share_percent, 0),
    runtime_requests: runtimeRequests,
    successful_requests: rows.reduce((sum, row) => sum + row.successful_requests, 0),
    llm_calls: rows.reduce((sum, row) => sum + row.llm_calls, 0),
    input_tokens: rows.reduce((sum, row) => sum + row.input_tokens, 0),
    output_tokens: rows.reduce((sum, row) => sum + row.output_tokens, 0),
    cost_per_priced_request: knownCost !== null && pricedRequests
      ? knownCost / pricedRequests
      : null,
    cost_coverage_percent: runtimeRequests
      ? (pricedRequests / runtimeRequests) * 100
      : null,
  }
}

export function UsageOperations({
  breakdown,
  composition,
  quality,
  executions,
  groupBy,
  contextLabel,
  organizationId,
  projectId,
  onSelectDriver,
}: {
  breakdown: ProjectUsageBreakdownRow[]
  composition: ProjectUsageComposition
  quality: ProjectUsageDataQuality
  executions: ProjectUsageExecution[]
  groupBy: UsageGroupBy
  contextLabel: string
  organizationId: string
  projectId: string
  onSelectDriver: (row: ProjectUsageBreakdownRow) => void
}) {
  const primaryRows = breakdown.slice(0, 5)
  const others = aggregateOthers(breakdown.slice(5))
  const driverRows = others ? [...primaryRows, others] : primaryRows
  const totalRequests = breakdown.reduce((sum, row) => sum + row.runtime_requests, 0)
  const totalCalls = breakdown.reduce((sum, row) => sum + row.llm_calls, 0)
  const totalTokens = breakdown.reduce((sum, row) => sum + row.input_tokens + row.output_tokens, 0)
  const knownSpend = breakdown.reduce((sum, row) => sum + (row.known_cost_usd ?? 0), 0)
  const callsPerRequest = totalRequests ? totalCalls / totalRequests : 0
  const tokensPerRequest = totalRequests ? totalTokens / totalRequests : 0
  const costPerRequest = totalRequests ? knownSpend / totalRequests : 0
  const coverageBase = quality.fully_priced_requests + quality.partial_requests + quality.unpriced_requests
  const coverage = coverageBase ? (quality.fully_priced_requests / coverageBase) * 100 : null
  const executionPreview = executions.slice(0, 5)
  const labels = groupLabels[groupBy]

  return (
    <div className="space-y-4">
      <div className="grid gap-4 xl:grid-cols-12">
        <section className="overflow-hidden rounded-xl border border-border/90 bg-surface/70 xl:col-span-8">
          <div className="flex flex-col gap-2 border-b border-border px-4 py-3 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <h2 className="text-sm font-semibold text-white">
                {groupBy === 'environment' || groupBy === 'release'
                  ? `Compare ${labels.plural.toLowerCase()}`
                  : `Spend by ${labels.singular}`}
              </h2>
              <p className="mt-1 text-xs text-muted">
                {contextLabel} Top five are shown; the remaining drivers are consolidated into Others.
              </p>
            </div>
            <span className="w-fit rounded-md border border-border/80 bg-background/45 px-2 py-1 text-[10px] font-semibold uppercase tracking-wider text-muted">
              {labels.singular}
            </span>
          </div>

          {driverRows.length === 0 ? (
            <div className="px-4 py-10 text-center text-sm text-muted">No attributed usage for this scope.</div>
          ) : (
            <div className="space-y-2 p-4">
              {driverRows.map((row, index) => {
                const drillable = row.key !== 'others' && canDrill(groupBy, row)
                const content = (
                  <>
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
                          <span>{formatNumber(row.runtime_requests)} requests</span>
                          <span>{formatNumber(row.llm_calls)} LLM calls</span>
                          <span>{formatKnownMoney(row.cost_per_priced_request)} / priced request</span>
                        </div>
                      </div>
                    </div>
                  </>
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
              <h2 className="text-sm font-semibold text-white">Efficiency</h2>
            </div>
            <p className="mt-1 text-xs text-muted">Unit economics for the active scope.</p>
            <div className="mt-4 grid grid-cols-2 gap-2">
              <div className="rounded-lg border border-border/60 bg-background/25 p-3">
                <p className="text-[9px] uppercase tracking-wider text-muted">Known cost / request</p>
                <p className="mt-1 text-sm font-semibold text-white">{formatMoney(costPerRequest)}</p>
              </div>
              <div className="rounded-lg border border-border/60 bg-background/25 p-3">
                <p className="text-[9px] uppercase tracking-wider text-muted">LLM calls / request</p>
                <p className="mt-1 text-sm font-semibold text-white">{callsPerRequest.toFixed(2)}</p>
              </div>
              <div className="rounded-lg border border-border/60 bg-background/25 p-3">
                <p className="text-[9px] uppercase tracking-wider text-muted">Tokens / request</p>
                <p className="mt-1 text-sm font-semibold text-white">{formatNumber(tokensPerRequest)}</p>
              </div>
              <div className="rounded-lg border border-border/60 bg-background/25 p-3">
                <p className="text-[9px] uppercase tracking-wider text-muted">Tool calls</p>
                <p className="mt-1 text-sm font-semibold text-white">{formatNumber(composition.tool_calls)}</p>
              </div>
            </div>
            <div className="mt-3 rounded-lg border border-border/60 bg-background/25 p-3 text-[10px] leading-4 text-muted">
              <Layers3 className="mr-1 inline h-3.5 w-3.5 text-primary-light" />
              {formatNumber(composition.input_tokens)} input · {formatNumber(composition.output_tokens)} output · {formatNumber(composition.embedding_tokens)} embedding tokens
            </div>
          </section>

          <section className="rounded-xl border border-border/90 bg-surface/70 p-4">
            <div className="flex items-center justify-between gap-3">
              <div className="flex items-center gap-2">
                <Database className="h-4 w-4 text-primary-light" />
                <h2 className="text-sm font-semibold text-white">Data confidence</h2>
              </div>
              <span className={cn(
                'text-xs font-semibold',
                coverage === 100 ? 'text-emerald-300' : 'text-amber-300',
              )}>
                {coverage === null ? '—' : `${coverage.toFixed(1)}%`}
              </span>
            </div>
            <div className="mt-3 h-2 overflow-hidden rounded-full bg-background/60">
              <div
                className={coverage === 100 ? 'h-full rounded-full bg-emerald-400' : 'h-full rounded-full bg-amber-300'}
                style={{ width: `${coverage ?? 0}%` }}
              />
            </div>
            <div className="mt-4 grid grid-cols-3 gap-2 text-center">
              <div className="rounded-lg border border-border/60 bg-background/25 p-2">
                <p className="text-[9px] uppercase text-muted">Priced</p>
                <p className="mt-1 text-xs font-semibold text-emerald-300">{formatNumber(quality.fully_priced_requests)}</p>
              </div>
              <div className="rounded-lg border border-border/60 bg-background/25 p-2">
                <p className="text-[9px] uppercase text-muted">Partial</p>
                <p className="mt-1 text-xs font-semibold text-amber-300">{formatNumber(quality.partial_requests)}</p>
              </div>
              <div className="rounded-lg border border-border/60 bg-background/25 p-2">
                <p className="text-[9px] uppercase text-muted">Unpriced</p>
                <p className="mt-1 text-xs font-semibold text-amber-300">{formatNumber(quality.unpriced_requests)}</p>
              </div>
            </div>
            {(quality.partial_requests > 0 || quality.unpriced_requests > 0) && (
              <div className="mt-3 flex gap-2 rounded-lg border border-amber-400/20 bg-amber-400/5 p-3 text-[10px] leading-4 text-amber-200">
                <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
                Known spend excludes incomplete pricing and must not be treated as the final invoice total.
              </div>
            )}
          </section>
        </div>
      </div>

      <section className="overflow-hidden rounded-xl border border-border/90 bg-surface/70">
        <div className="flex flex-col gap-2 border-b border-border px-4 py-3 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h2 className="text-sm font-semibold text-white">Execution evidence</h2>
            <p className="mt-1 text-xs text-muted">Five highest known-spend traces. Open Traces for the complete operational investigation.</p>
          </div>
          <Link
            to={`/organizations/${organizationId}/projects/${projectId}/traces`}
            className="inline-flex w-fit items-center gap-1 text-xs font-medium text-primary-light hover:text-white"
          >
            View all traces <ExternalLink className="h-3 w-3" />
          </Link>
        </div>

        {executionPreview.length === 0 ? (
          <div className="px-4 py-10 text-center text-sm text-muted">No terminal executions in this scope.</div>
        ) : (
          <div className="divide-y divide-border/70">
            {executionPreview.map((execution) => (
              <div key={execution.trace_id} className="grid gap-3 px-4 py-3 transition-colors hover:bg-background/25 md:grid-cols-[minmax(0,1fr)_auto_auto] md:items-center">
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <p className="truncate text-xs font-medium text-white">{execution.agent_name ?? 'Unattributed agent'}</p>
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
                    {execution.model ?? 'Unknown model'} · {execution.environment ?? 'unknown environment'}
                    {execution.release_version ? ` · release ${execution.release_version}` : ''}
                  </p>
                </div>
                <div className="flex flex-wrap gap-3 text-[10px] text-muted md:justify-end">
                  <span><Workflow className="mr-1 inline h-3 w-3" />{execution.llm_calls} calls</span>
                  <span>{formatNumber(execution.input_tokens + execution.output_tokens)} tokens</span>
                  <span>{execution.tool_calls} tools</span>
                </div>
                <div className="flex items-center justify-between gap-3 md:justify-end">
                  <span className={execution.cost_status === 'known' ? 'text-xs font-semibold text-white' : 'text-xs font-semibold text-amber-300'}>
                    {formatKnownMoney(execution.known_cost_usd)}
                  </span>
                  <Link
                    to={`/organizations/${organizationId}/projects/${projectId}/traces?trace_id=${execution.trace_id}`}
                    className="inline-flex items-center gap-1 text-[10px] font-medium text-primary-light hover:text-white"
                  >
                    Open <ExternalLink className="h-3 w-3" />
                  </Link>
                </div>
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  )
}
