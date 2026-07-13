import { Link } from 'react-router-dom'
import { AlertTriangle, Database, ExternalLink, Layers3 } from 'lucide-react'

import type {
  ProjectUsageBreakdownRow,
  ProjectUsageComposition,
  ProjectUsageDataQuality,
  ProjectUsageExecution,
  UsageGroupBy,
} from '../types'
import { formatKnownMoney } from '@/lib/formatters/money'

function formatNumber(value: number) {
  return new Intl.NumberFormat('en-US', {
    notation: value >= 10_000 ? 'compact' : 'standard',
    maximumFractionDigits: 1,
  }).format(value)
}

export function UsageOperations({
  breakdown,
  composition,
  quality,
  executions,
  groupBy,
  organizationId,
  projectId,
}: {
  breakdown: ProjectUsageBreakdownRow[]
  composition: ProjectUsageComposition
  quality: ProjectUsageDataQuality
  executions: ProjectUsageExecution[]
  groupBy: UsageGroupBy
  organizationId: string
  projectId: string
}) {
  const groupLabel = groupBy.charAt(0).toUpperCase() + groupBy.slice(1)
  return (
    <div className="space-y-4">
      <div className="grid gap-4 xl:grid-cols-12">
        <section className="overflow-hidden rounded-xl border border-border/90 bg-surface/70 xl:col-span-8">
          <div className="flex items-center justify-between gap-4 border-b border-border px-4 py-3">
            <div>
              <h2 className="text-sm font-semibold text-white">Cost drivers</h2>
              <p className="mt-1 text-xs text-muted">Spend and consumption grouped by {groupLabel.toLowerCase()}.</p>
            </div>
            <span className="rounded-md border border-border/80 bg-background/45 px-2 py-1 text-[10px] font-semibold uppercase tracking-wider text-muted">{groupLabel}</span>
          </div>
          {breakdown.length === 0 ? (
            <div className="px-4 py-10 text-center text-sm text-muted">No attributed usage for this period.</div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[860px] text-left text-xs">
                <thead className="border-b border-border/80 bg-background/20 text-[10px] uppercase tracking-wider text-muted">
                  <tr>
                    <th className="px-4 py-3 font-medium">{groupLabel}</th>
                    <th className="px-3 py-3 text-right font-medium">Spend</th>
                    <th className="px-3 py-3 text-right font-medium">Share</th>
                    <th className="px-3 py-3 text-right font-medium">Requests</th>
                    <th className="px-3 py-3 text-right font-medium">LLM calls</th>
                    <th className="px-3 py-3 text-right font-medium">Tokens</th>
                    <th className="px-3 py-3 text-right font-medium">Coverage</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border/70">
                  {breakdown.map((row) => (
                    <tr key={row.key} className="transition-colors hover:bg-background/25">
                      <td className="max-w-[280px] truncate px-4 py-3 font-medium text-white" title={row.label}>{row.label}</td>
                      <td className="px-3 py-3 text-right text-white">{formatKnownMoney(row.known_cost_usd)}</td>
                      <td className="px-3 py-3 text-right text-muted">{row.share_percent.toFixed(1)}%</td>
                      <td className="px-3 py-3 text-right text-white">{formatNumber(row.runtime_requests)}</td>
                      <td className="px-3 py-3 text-right text-white">{formatNumber(row.llm_calls)}</td>
                      <td className="px-3 py-3 text-right text-white">{formatNumber(row.input_tokens + row.output_tokens)}</td>
                      <td className="px-3 py-3 text-right">
                        <span className={(row.cost_coverage_percent ?? 0) < 100 ? 'text-amber-300' : 'text-emerald-300'}>
                          {row.cost_coverage_percent === null ? '—' : `${row.cost_coverage_percent.toFixed(1)}%`}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>

        <div className="space-y-4 xl:col-span-4">
          <section className="rounded-xl border border-border/90 bg-surface/70 p-4">
            <div className="flex items-center gap-2">
              <Layers3 className="h-4 w-4 text-primary-light" />
              <h2 className="text-sm font-semibold text-white">Usage composition</h2>
            </div>
            <div className="mt-4 space-y-3">
              {[
                ['Input tokens', composition.input_tokens],
                ['Output tokens', composition.output_tokens],
                ['Embedding tokens', composition.embedding_tokens],
                ['Tool calls', composition.tool_calls],
                ['Vector queries', composition.vector_queries],
              ].map(([label, value]) => (
                <div key={String(label)} className="flex items-center justify-between gap-4 text-xs">
                  <span className="text-muted">{label}</span>
                  <span className="font-medium text-white">{formatNumber(Number(value))}</span>
                </div>
              ))}
            </div>
          </section>

          <section className="rounded-xl border border-border/90 bg-surface/70 p-4">
            <div className="flex items-center gap-2">
              <Database className="h-4 w-4 text-primary-light" />
              <h2 className="text-sm font-semibold text-white">Data quality</h2>
            </div>
            <div className="mt-4 space-y-3">
              <div className="flex items-center justify-between text-xs"><span className="text-muted">Fully priced</span><span className="text-emerald-300">{formatNumber(quality.fully_priced_requests)}</span></div>
              <div className="flex items-center justify-between text-xs"><span className="text-muted">Partial</span><span className="text-amber-300">{formatNumber(quality.partial_requests)}</span></div>
              <div className="flex items-center justify-between text-xs"><span className="text-muted">Unpriced</span><span className="text-amber-300">{formatNumber(quality.unpriced_requests)}</span></div>
              <div className="flex items-center justify-between text-xs"><span className="text-muted">Missing model</span><span className="text-white">{formatNumber(quality.missing_model_attribution)}</span></div>
              <div className="flex items-center justify-between text-xs"><span className="text-muted">Missing release</span><span className="text-white">{formatNumber(quality.missing_release_attribution)}</span></div>
              <div className="flex items-center justify-between text-xs"><span className="text-muted">Freshness</span><span className="text-white">{quality.aggregation_lag_seconds === null ? '—' : `${quality.aggregation_lag_seconds}s`}</span></div>
            </div>
            {(quality.partial_requests > 0 || quality.unpriced_requests > 0) && (
              <div className="mt-4 flex gap-2 rounded-lg border border-amber-400/20 bg-amber-400/5 p-3 text-xs leading-5 text-amber-200">
                <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
                Spend is partially estimated. Unknown pricing is not converted to zero.
              </div>
            )}
          </section>
        </div>
      </div>

      <section className="overflow-hidden rounded-xl border border-border/90 bg-surface/70">
        <div className="border-b border-border px-4 py-3">
          <h2 className="text-sm font-semibold text-white">Most expensive executions</h2>
          <p className="mt-1 text-xs text-muted">Trace-level drill-down ordered by known provider spend.</p>
        </div>
        {executions.length === 0 ? (
          <div className="px-4 py-10 text-center text-sm text-muted">No terminal executions in this period.</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[1080px] text-left text-xs">
              <thead className="border-b border-border/80 bg-background/20 text-[10px] uppercase tracking-wider text-muted">
                <tr>
                  <th className="px-4 py-3 font-medium">Agent</th>
                  <th className="px-3 py-3 font-medium">Environment</th>
                  <th className="px-3 py-3 font-medium">Release</th>
                  <th className="px-3 py-3 font-medium">Model</th>
                  <th className="px-3 py-3 font-medium">Status</th>
                  <th className="px-3 py-3 text-right font-medium">LLM calls</th>
                  <th className="px-3 py-3 text-right font-medium">Tokens</th>
                  <th className="px-3 py-3 text-right font-medium">Tools</th>
                  <th className="px-3 py-3 text-right font-medium">Spend</th>
                  <th className="px-4 py-3 text-right font-medium">Trace</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border/70">
                {executions.map((execution) => (
                  <tr key={execution.trace_id} className="transition-colors hover:bg-background/25">
                    <td className="px-4 py-3 font-medium text-white">{execution.agent_name ?? 'Unattributed agent'}</td>
                    <td className="px-3 py-3 capitalize text-muted">{execution.environment ?? 'unknown'}</td>
                    <td className="px-3 py-3 text-muted">{execution.release_version ?? '—'}</td>
                    <td className="max-w-[220px] truncate px-3 py-3 text-muted" title={`${execution.provider ?? ''} ${execution.model ?? ''}`}>{execution.model ?? 'Unknown'}</td>
                    <td className="px-3 py-3 capitalize text-white">{execution.status}</td>
                    <td className="px-3 py-3 text-right text-white">{execution.llm_calls}</td>
                    <td className="px-3 py-3 text-right text-white">{formatNumber(execution.input_tokens + execution.output_tokens)}</td>
                    <td className="px-3 py-3 text-right text-white">{execution.tool_calls}</td>
                    <td className={execution.cost_status === 'known' ? 'px-3 py-3 text-right text-white' : 'px-3 py-3 text-right text-amber-300'}>{formatKnownMoney(execution.known_cost_usd)}</td>
                    <td className="px-4 py-3 text-right">
                      <Link
                        to={`/organizations/${organizationId}/projects/${projectId}/traces?trace_id=${execution.trace_id}`}
                        className="inline-flex items-center gap-1 font-medium text-primary-light hover:text-white"
                      >
                        Open <ExternalLink className="h-3 w-3" />
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  )
}
