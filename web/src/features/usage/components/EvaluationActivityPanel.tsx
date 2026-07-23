import { Beaker, Bot, Calculator, Sparkles } from 'lucide-react'

import type { ProjectEvaluationUsage } from '../types'
import { formatKnownMoney } from '@/lib/formatters/money'

function formatNumber(value: number) {
  return new Intl.NumberFormat('en-US', {
    notation: value >= 10_000 ? 'compact' : 'standard',
    maximumFractionDigits: 1,
  }).format(value)
}

function CostBlock({
  label,
  value,
  detail,
  warning,
}: {
  label: string
  value: number
  detail: string
  warning?: string
}) {
  return (
    <div className="rounded-lg border border-border/70 bg-background/25 p-3">
      <p className="text-[9px] font-semibold uppercase tracking-wider text-muted">{label}</p>
      <p className="mt-1 text-base font-semibold text-white">{formatKnownMoney(value)}</p>
      <p className="mt-1 text-[10px] leading-4 text-muted">{detail}</p>
      {warning && <p className="mt-1 text-[10px] text-amber-300">{warning}</p>}
    </div>
  )
}

export function EvaluationActivityPanel({
  activity,
}: {
  activity: ProjectEvaluationUsage
}) {
  return (
    <section className="rounded-xl border border-sky-400/20 bg-sky-400/[0.035]">
      <div className="flex flex-col gap-2 border-b border-sky-400/15 px-4 py-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <div className="flex items-center gap-2">
            <Beaker className="h-4 w-4 text-sky-300" />
            <h2 className="text-sm font-semibold text-white">Evaluation activity</h2>
          </div>
          <p className="mt-1 text-xs text-muted">
            Target Runs, Judge calls and AI Suite generation are measured separately from operational use.
          </p>
        </div>
        <div className="text-left sm:text-right">
          <p className="text-[9px] font-semibold uppercase tracking-wider text-muted">Total known Evaluation cost</p>
          <p className="mt-1 text-lg font-semibold text-white">{formatKnownMoney(activity.total_known_cost_usd)}</p>
        </div>
      </div>

      <div className="grid gap-3 p-4 lg:grid-cols-3">
        <CostBlock
          label="Target runtime"
          value={activity.target_runtime_cost_usd}
          detail={`${formatNumber(activity.target_agent_runs)} Agent Runs · ${formatNumber(activity.target_network_runs)} Network Runs`}
        />
        <CostBlock
          label="Judgment"
          value={activity.judge_cost_usd}
          detail={`${formatNumber(activity.judge_invocations)} Judge invocations · ${formatNumber(activity.judge_input_tokens + activity.judge_output_tokens)} tokens`}
          warning={activity.judge_unpriced_invocations > 0
            ? `${formatNumber(activity.judge_unpriced_invocations)} unpriced invocations`
            : undefined}
        />
        <CostBlock
          label="AI Suite generation"
          value={activity.suite_generation_cost_usd}
          detail={`${formatNumber(activity.suite_generation_invocations)} generations · ${formatNumber(activity.suite_generation_input_tokens + activity.suite_generation_output_tokens)} tokens`}
          warning={activity.suite_generation_unpriced_invocations > 0
            ? `${formatNumber(activity.suite_generation_unpriced_invocations)} unpriced generations`
            : undefined}
        />
      </div>

      <div className="grid gap-2 border-t border-sky-400/15 px-4 py-3 sm:grid-cols-4">
        {[
          { icon: Calculator, label: 'Evaluations', value: activity.evaluations },
          { icon: Bot, label: 'Trials', value: activity.trials },
          { icon: Sparkles, label: 'Session Trials', value: activity.session_trials },
          { icon: Beaker, label: 'Session Turns', value: activity.session_turns },
        ].map(({ icon: Icon, label, value }) => (
          <div key={label} className="flex items-center gap-2 text-xs">
            <Icon className="h-3.5 w-3.5 text-sky-300" />
            <span className="text-muted">{label}</span>
            <span className="ml-auto font-semibold text-white">{formatNumber(value)}</span>
          </div>
        ))}
      </div>
    </section>
  )
}
