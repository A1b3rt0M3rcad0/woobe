import { useMemo, useState } from 'react'
import { BadgeCheck, CircleHelp, MessageSquareText, Sparkles, TriangleAlert } from 'lucide-react'

import type { ProjectUsageBreakdownRow, ProjectUsageSummary, UsageGroupBy } from '../types'
import { formatKnownMoney, formatMoney } from '@/lib/formatters/money'
import { cn } from '@/lib/utils'

type StoryIntent = 'change' | 'driver' | 'efficiency' | 'quality'

const intentLabels: Array<{ value: StoryIntent; label: string }> = [
  { value: 'change', label: 'Why did spend change?' },
  { value: 'driver', label: 'What drives usage?' },
  { value: 'efficiency', label: 'Is usage efficient?' },
  { value: 'quality', label: 'Can I trust the total?' },
]

const dimensionLabels: Record<UsageGroupBy, string> = {
  agent: 'agent',
  model: 'model',
  provider: 'provider',
  environment: 'environment',
  release: 'release',
}

function formatPercent(value: number | null) {
  if (value === null) return 'No previous baseline'
  const sign = value > 0 ? '+' : ''
  return `${sign}${value.toFixed(1)}%`
}

function movement(value: number | null, noun: string) {
  if (value === null) return `${noun} has no previous-period baseline`
  if (value === 0) return `${noun} was flat`
  return `${noun} ${value > 0 ? 'increased' : 'decreased'} ${Math.abs(value).toFixed(1)}%`
}

function buildAnswer(
  intent: StoryIntent,
  summary: ProjectUsageSummary,
  topDriver: ProjectUsageBreakdownRow | undefined,
  groupBy: UsageGroupBy,
) {
  const requests = summary.runtime_requests
  const successRate = requests ? (summary.successful_requests / requests) * 100 : 0
  const callsPerRequest = requests ? summary.llm_calls / requests : 0
  const tokensPerRequest = requests ? (summary.input_tokens + summary.output_tokens) / requests : 0
  const coverage = summary.cost_coverage_percent

  if (intent === 'change') {
    const costChange = summary.cost_change_percent
    const requestChange = summary.request_change_percent
    let interpretation = 'There is not enough previous-period data to separate volume from unit-cost movement.'
    if (costChange !== null && requestChange !== null) {
      const gap = costChange - requestChange
      interpretation = Math.abs(gap) < 3
        ? 'Spend and request volume moved at a similar rate, so volume is the dominant explanation.'
        : gap > 0
          ? 'Spend grew faster than request volume, which indicates higher unit cost or more model work per request.'
          : 'Request volume grew faster than spend, which indicates improving unit economics.'
    }
    return `${movement(costChange, 'Known spend')}, while ${movement(requestChange, 'request volume').toLowerCase()}. ${interpretation}`
  }

  if (intent === 'driver') {
    if (!topDriver) return 'No attributed driver is available for the selected scope.'
    return `${topDriver.label} is the leading ${dimensionLabels[groupBy]} with ${topDriver.share_percent.toFixed(1)}% of known spend, ${topDriver.runtime_requests.toLocaleString('en-US')} requests and ${topDriver.llm_calls.toLocaleString('en-US')} LLM calls.`
  }

  if (intent === 'efficiency') {
    return `The selected scope averages ${formatKnownMoney(summary.cost_per_priced_request)} per priced request, ${callsPerRequest.toFixed(2)} LLM calls and ${tokensPerRequest.toFixed(0)} generation tokens per request. The runtime success rate is ${successRate.toFixed(1)}%, with ${formatMoney(summary.failed_spend_usd)} of known spend attached to failed or cancelled executions.`
  }

  if (coverage === null) {
    return 'No runtime requests are available to calculate pricing coverage for this scope.'
  }
  return `${coverage.toFixed(1)}% of requests are fully priced. ${summary.partial_cost_requests.toLocaleString('en-US')} are partially priced and ${summary.unpriced_requests.toLocaleString('en-US')} are unpriced, so known spend must not be interpreted as a complete invoice total.`
}

export function UsageStory({
  summary,
  breakdown,
  groupBy,
  contextLabel,
}: {
  summary: ProjectUsageSummary
  breakdown: ProjectUsageBreakdownRow[]
  groupBy: UsageGroupBy
  contextLabel: string
}) {
  const [intent, setIntent] = useState<StoryIntent>('change')
  const topDriver = breakdown[0]
  const successRate = summary.runtime_requests
    ? (summary.successful_requests / summary.runtime_requests) * 100
    : 0
  const partial = summary.partial_cost_requests > 0 || summary.unpriced_requests > 0
  const answer = useMemo(
    () => buildAnswer(intent, summary, topDriver, groupBy),
    [groupBy, intent, summary, topDriver],
  )

  const headline = [
    `${movement(summary.cost_change_percent, 'Known spend')} to ${formatKnownMoney(summary.known_cost_usd)}.`,
    `${movement(summary.request_change_percent, 'Request volume')}.`,
    topDriver
      ? `${topDriver.label} leads ${dimensionLabels[groupBy]} attribution at ${topDriver.share_percent.toFixed(1)}%.`
      : 'No attributed cost driver is available.',
  ].join(' ')

  return (
    <section className="overflow-hidden rounded-xl border border-primary/25 bg-gradient-to-br from-primary/10 via-surface/80 to-surface/70">
      <div className="grid gap-5 p-5 xl:grid-cols-[minmax(0,1.35fr)_minmax(320px,0.65fr)]">
        <div>
          <div className="flex items-center gap-2">
            <Sparkles className="h-4 w-4 text-primary-light" />
            <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-primary-light">Usage story</p>
          </div>
          <h2 className="mt-3 max-w-4xl text-lg font-semibold leading-7 text-white">{headline}</h2>
          <p className="mt-2 text-xs leading-5 text-muted">{contextLabel}</p>

          <div className="mt-5 grid gap-3 sm:grid-cols-3">
            <div className="rounded-lg border border-border/70 bg-background/25 p-3">
              <p className="text-[10px] font-semibold uppercase tracking-wider text-muted">Spend movement</p>
              <p className="mt-1 text-sm font-semibold text-white">{formatPercent(summary.cost_change_percent)}</p>
            </div>
            <div className="rounded-lg border border-border/70 bg-background/25 p-3">
              <p className="text-[10px] font-semibold uppercase tracking-wider text-muted">Success rate</p>
              <p className="mt-1 text-sm font-semibold text-white">{successRate.toFixed(1)}%</p>
            </div>
            <div className="rounded-lg border border-border/70 bg-background/25 p-3">
              <p className="text-[10px] font-semibold uppercase tracking-wider text-muted">Data confidence</p>
              <p className={cn('mt-1 text-sm font-semibold', partial ? 'text-amber-300' : 'text-emerald-300')}>
                {summary.cost_coverage_percent === null ? 'No baseline' : `${summary.cost_coverage_percent.toFixed(1)}% priced`}
              </p>
            </div>
          </div>
        </div>

        <div className="rounded-xl border border-border/80 bg-background/30 p-4">
          <div className="flex items-center gap-2">
            <MessageSquareText className="h-4 w-4 text-primary-light" />
            <h3 className="text-sm font-semibold text-white">Ask this story</h3>
          </div>
          <div className="mt-3 flex flex-wrap gap-2">
            {intentLabels.map((item) => (
              <button
                key={item.value}
                type="button"
                onClick={() => setIntent(item.value)}
                className={cn(
                  'rounded-lg border px-2.5 py-1.5 text-[11px] font-medium transition-colors',
                  intent === item.value
                    ? 'border-primary/40 bg-primary/15 text-primary-light'
                    : 'border-border/80 bg-surface/40 text-muted hover:text-white',
                )}
              >
                {item.label}
              </button>
            ))}
          </div>
          <div className="mt-4 rounded-lg border border-border/70 bg-surface/55 p-3">
            <div className="flex gap-2">
              {partial && intent === 'quality'
                ? <TriangleAlert className="mt-0.5 h-4 w-4 shrink-0 text-amber-300" />
                : intent === 'quality'
                  ? <BadgeCheck className="mt-0.5 h-4 w-4 shrink-0 text-emerald-300" />
                  : <CircleHelp className="mt-0.5 h-4 w-4 shrink-0 text-primary-light" />}
              <p className="text-xs leading-5 text-white/90">{answer}</p>
            </div>
          </div>
          <p className="mt-3 text-[10px] leading-4 text-muted">
            Answers are generated from the active filters and deterministic Usage metrics.
          </p>
        </div>
      </div>
    </section>
  )
}
