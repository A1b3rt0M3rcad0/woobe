import { useMemo, useState } from 'react'
import {
  AlertTriangle,
  CheckCircle2,
  Clock3,
  Copy,
  Download,
  FileJson,
  RefreshCw,
  Search,
  TerminalSquare,
  XCircle,
} from 'lucide-react'
import { toast } from 'sonner'

import { ErrorState } from '@/components/common/ErrorState'
import { LoadingState } from '@/components/common/LoadingState'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { Dialog } from '@/components/ui/Dialog'
import { Input } from '@/components/ui/Input'
import { JsonCodeBlock } from '@/components/ui/JsonCodeBlock'
import { useEvaluationRunDiagnostics } from '@/features/evaluations/experienceHooks'
import type {
  EvaluationDiagnosticJudgeCall,
  EvaluationDiagnosticSignal,
  EvaluationDiagnosticTimelineEvent,
  EvaluationDiagnosticTrial,
} from '@/features/evaluations/experienceTypes'
import { cn } from '@/lib/utils'

type DiagnosticsTab = 'signals' | 'judge' | 'trials' | 'timeline' | 'raw'

interface Props {
  open: boolean
  projectId: string
  runId: string
  onClose: () => void
}

function label(value?: string | null) {
  if (!value) return 'Unknown'
  return value
    .split('_')
    .map((item) => item.charAt(0).toUpperCase() + item.slice(1))
    .join(' ')
}

function formatDate(value?: string | null) {
  if (!value) return '—'
  const parsed = new Date(value)
  return Number.isNaN(parsed.getTime()) ? value : parsed.toLocaleString()
}

function money(value?: number | null) {
  if (value == null) return '—'
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: value < 0.01 ? 4 : 2,
  }).format(value)
}

function signalTone(signal: EvaluationDiagnosticSignal) {
  if (signal.severity === 'error') {
    return 'border-red-500/25 bg-red-500/[0.06] text-red-200'
  }
  if (signal.severity === 'warning') {
    return 'border-amber-500/25 bg-amber-500/[0.06] text-amber-200'
  }
  return 'border-border bg-background/35 text-muted'
}

function statusIcon(status?: string | null) {
  if (status === 'completed' || status === 'passed') {
    return <CheckCircle2 className="h-4 w-4 text-emerald-300" />
  }
  if (status === 'failed' || status === 'error') {
    return <XCircle className="h-4 w-4 text-red-300" />
  }
  return <AlertTriangle className="h-4 w-4 text-amber-300" />
}

function matchesSearch(values: unknown[], search: string) {
  if (!search.trim()) return true
  const needle = search.toLowerCase()
  return values.some((value) => {
    if (value == null) return false
    if (typeof value === 'string') return value.toLowerCase().includes(needle)
    try {
      return JSON.stringify(value).toLowerCase().includes(needle)
    } catch {
      return String(value).toLowerCase().includes(needle)
    }
  })
}

function JudgeCallCard({ call }: { call: EvaluationDiagnosticJudgeCall }) {
  const attempts = Array.isArray(call.diagnostics?.attempts)
    ? call.diagnostics.attempts
    : []
  const repairAttempts = Array.isArray(call.diagnostics?.repair_attempts)
    ? call.diagnostics.repair_attempts
    : []

  return (
    <details
      open={call.status !== 'completed'}
      className="rounded-xl border border-border/80 bg-background/35"
    >
      <summary className="cursor-pointer list-none px-4 py-4">
        <div className="flex flex-wrap items-center gap-3">
          {statusIcon(call.status)}
          <div className="min-w-0 flex-1">
            <p className="truncate text-xs font-semibold text-white">
              {call.provider} / {call.model}
            </p>
            <p className="mt-1 truncate font-mono text-[10px] text-muted">
              Trial {call.trial_id} · Call {call.id}
            </p>
          </div>
          <Badge variant="outline">{label(call.status)}</Badge>
          {call.canonical_failure_code ? (
            <Badge variant="outline">{call.canonical_failure_code}</Badge>
          ) : null}
          <span className="text-[10px] text-muted">
            {attempts.length + repairAttempts.length} attempts
          </span>
          <span className="text-[10px] text-muted">{call.latency_ms ?? '—'}ms</span>
          <span className="text-[10px] text-muted">{money(call.cost_usd)}</span>
        </div>
      </summary>

      <div className="space-y-4 border-t border-border/70 p-4">
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-6">
          <div className="rounded-lg border border-border/70 p-3">
            <p className="text-[9px] uppercase text-muted">Input tokens</p>
            <p className="mt-2 text-sm font-semibold text-white">{call.input_tokens ?? '—'}</p>
          </div>
          <div className="rounded-lg border border-border/70 p-3">
            <p className="text-[9px] uppercase text-muted">Output tokens</p>
            <p className="mt-2 text-sm font-semibold text-white">{call.output_tokens ?? '—'}</p>
          </div>
          <div className="rounded-lg border border-border/70 p-3">
            <p className="text-[9px] uppercase text-muted">Gateway</p>
            <p className="mt-2 truncate text-xs text-white">
              {String(call.diagnostics?.gateway_version || 'not persisted')}
            </p>
          </div>
          <div className="rounded-lg border border-border/70 p-3">
            <p className="text-[9px] uppercase text-muted">Repair gateway</p>
            <p className="mt-2 truncate text-xs text-white">
              {String(call.diagnostics?.repair_gateway_version || 'not observed')}
            </p>
          </div>
          <div className="rounded-lg border border-border/70 p-3">
            <p className="text-[9px] uppercase text-muted">Response mode</p>
            <p className="mt-2 truncate text-xs text-white">
              {String(call.diagnostics?.final_response_mode || '—')}
            </p>
          </div>
          <div className="rounded-lg border border-border/70 p-3">
            <p className="text-[9px] uppercase text-muted">Profile</p>
            <p className="mt-2 truncate text-xs text-white">
              {String(call.diagnostics?.final_inference_profile || '—')}
            </p>
          </div>
        </div>

        {call.error ? (
          <section className="rounded-lg border border-red-500/25 bg-red-500/[0.05] p-4">
            <p className="text-[9px] font-medium uppercase tracking-wide text-red-300">
              Persisted Judge error
            </p>
            <pre className="mt-2 whitespace-pre-wrap break-words font-mono text-[11px] leading-5 text-red-100">
              {call.error}
            </pre>
            {call.error_fingerprint ? (
              <p className="mt-3 font-mono text-[9px] text-red-300/70">
                SHA-256 {call.error_fingerprint}
              </p>
            ) : null}
          </section>
        ) : null}

        {attempts.length || repairAttempts.length ? (
          <section className="space-y-2">
            <p className="text-xs font-semibold text-white">Provider attempts</p>
            {[...attempts.map((attempt: Record<string, any>) => ({ ...attempt, phase: 'adaptive' })),
              ...repairAttempts.map((attempt: Record<string, any>) => ({ ...attempt, phase: 'repair' }))]
              .map((attempt: Record<string, any>, index) => (
                <div
                  key={`${attempt.phase}-${attempt.attempt ?? index}-${index}`}
                  className="rounded-lg border border-border/70 bg-background/30 p-3"
                >
                  <div className="flex flex-wrap items-center gap-3 text-[10px]">
                    {statusIcon(attempt.status)}
                    <Badge variant="outline">{label(attempt.phase)}</Badge>
                    <span className="text-white">Attempt {attempt.attempt ?? index + 1}</span>
                    <span className="text-muted">Mode {String(attempt.response_mode || '—')}</span>
                    <span className="text-muted">Profile {String(attempt.inference_profile || '—')}</span>
                    <span className="text-muted">Max {String(attempt.max_tokens || '—')} tokens</span>
                    <span className="text-muted">{String(attempt.latency_ms ?? '—')}ms</span>
                  </div>
                  {attempt.error ? (
                    <pre className="mt-2 whitespace-pre-wrap break-words font-mono text-[10px] leading-4 text-red-200">
                      {String(attempt.error)}
                    </pre>
                  ) : null}
                  {attempt.response_content_preview ? (
                    <div className="mt-3">
                      <JsonCodeBlock
                        title="Provider response preview"
                        value={attempt.response_content_preview}
                        maxHeight={220}
                      />
                    </div>
                  ) : null}
                </div>
              ))}
          </section>
        ) : null}

        <div className="grid gap-4 xl:grid-cols-2">
          <JsonCodeBlock title="Complete Judge diagnostics" value={call.diagnostics} maxHeight={420} />
          <JsonCodeBlock title="Structured result and pricing" value={{
            structured_result: call.structured_result,
            pricing: call.pricing,
            judge_config_hash: call.judge_config_hash,
            rubric_hash: call.rubric_hash,
            cost_status: call.cost_status,
            cost_reason: call.cost_reason,
            started_at: call.started_at,
            completed_at: call.completed_at,
          }} maxHeight={420} />
        </div>
      </div>
    </details>
  )
}

function TrialCard({ trial }: { trial: EvaluationDiagnosticTrial }) {
  const judgment = trial.judgment || {}
  const runtime = trial.runtime || {}
  return (
    <details className="rounded-xl border border-border/80 bg-background/35">
      <summary className="cursor-pointer list-none px-4 py-4">
        <div className="flex flex-wrap items-center gap-3">
          {statusIcon(trial.status)}
          <div className="min-w-0 flex-1">
            <p className="truncate text-xs font-semibold text-white">
              {String(trial.case?.name || trial.pair_key)}
            </p>
            <p className="mt-1 truncate font-mono text-[10px] text-muted">
              #{trial.execution_order} · repetition {trial.repetition} · {trial.id}
            </p>
          </div>
          <Badge variant="outline">{label(trial.status)}</Badge>
          {judgment.canonical_failure_code ? (
            <Badge variant="outline">{String(judgment.canonical_failure_code)}</Badge>
          ) : null}
          <span className="text-[10px] text-muted">
            runtime {runtime.completed ? 'preserved' : 'missing'}
          </span>
          <span className="text-[10px] text-muted">
            call {judgment.model_call_present ? 'persisted' : 'missing'}
          </span>
        </div>
      </summary>
      <div className="grid gap-4 border-t border-border/70 p-4 xl:grid-cols-2">
        <JsonCodeBlock title="Failure chain and timestamps" value={{
          status: trial.status,
          attempt: trial.attempt,
          timestamps: trial.timestamps,
          judgment,
          checks: trial.checks,
        }} maxHeight={440} />
        <JsonCodeBlock title="Runtime evidence" value={{
          target: trial.target,
          case: trial.case,
          runtime,
        }} maxHeight={440} />
      </div>
    </details>
  )
}

function TimelineRow({ event }: { event: EvaluationDiagnosticTimelineEvent }) {
  return (
    <div className="grid gap-2 border-b border-border/60 px-4 py-3 last:border-b-0 md:grid-cols-[170px_150px_minmax(0,1fr)]">
      <p className="font-mono text-[10px] text-muted">{formatDate(event.at)}</p>
      <div className="flex items-center gap-2">
        {statusIcon(event.status)}
        <span className="text-[10px] font-medium text-white">{label(event.stage)}</span>
      </div>
      <div className="min-w-0">
        <p className="text-xs text-white">{event.message}</p>
        {event.trial_id ? (
          <p className="mt-1 truncate font-mono text-[9px] text-muted">Trial {event.trial_id}</p>
        ) : null}
        {Object.keys(event.details || {}).length ? (
          <details className="mt-2">
            <summary className="cursor-pointer text-[10px] text-primary-light">Details</summary>
            <div className="mt-2">
              <JsonCodeBlock value={event.details} maxHeight={220} />
            </div>
          </details>
        ) : null}
      </div>
    </div>
  )
}

export function EvaluationDiagnosticsDialog({
  open,
  projectId,
  runId,
  onClose,
}: Props) {
  const [tab, setTab] = useState<DiagnosticsTab>('signals')
  const [search, setSearch] = useState('')
  const query = useEvaluationRunDiagnostics(projectId, runId, open)
  const data = query.data

  const judgeCalls = useMemo(
    () => (data?.judge_calls || []).filter((call) => matchesSearch([
      call.id,
      call.trial_id,
      call.provider,
      call.model,
      call.status,
      call.canonical_failure_code,
      call.error,
      call.diagnostics,
    ], search)),
    [data?.judge_calls, search],
  )

  const trials = useMemo(
    () => (data?.trials || []).filter((trial) => matchesSearch([
      trial.id,
      trial.pair_key,
      trial.status,
      trial.case,
      trial.target,
      trial.judgment,
    ], search)),
    [data?.trials, search],
  )

  const timeline = useMemo(
    () => (data?.timeline || []).filter((event) => matchesSearch([
      event.stage,
      event.message,
      event.trial_id,
      event.details,
    ], search)),
    [data?.timeline, search],
  )

  const copyAll = async () => {
    if (!data) return
    await navigator.clipboard.writeText(JSON.stringify(data, null, 2))
    toast.success('Redacted Evaluation logs copied')
  }

  const downloadAll = () => {
    if (!data) return
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const anchor = document.createElement('a')
    anchor.href = url
    anchor.download = `evaluation-${runId}-diagnostics.json`
    anchor.click()
    URL.revokeObjectURL(url)
  }

  const tabs: Array<{ value: DiagnosticsTab; label: string }> = [
    { value: 'signals', label: `Diagnosis (${data?.signals.length ?? 0})` },
    { value: 'judge', label: `Judge calls (${data?.judge_calls.length ?? 0})` },
    { value: 'trials', label: `Trials (${data?.trials.length ?? 0})` },
    { value: 'timeline', label: `Timeline (${data?.timeline.length ?? 0})` },
    { value: 'raw', label: 'Raw logs' },
  ]

  return (
    <Dialog
      open={open}
      onClose={onClose}
      title="Evaluation execution logs"
      className="max-w-[1500px]"
      scrollMode="content"
    >
      {query.isLoading ? (
        <LoadingState message="Loading persisted Evaluation diagnostics" />
      ) : query.isError || !data ? (
        <ErrorState
          title="Unable to load Evaluation logs"
          description={query.error instanceof Error
            ? query.error.message
            : 'The diagnostic bundle could not be loaded.'}
        />
      ) : (
        <div className="space-y-4">
          <section className="rounded-xl border border-border/80 bg-background/35 p-4">
            <div className="flex flex-wrap items-start justify-between gap-4">
              <div>
                <div className="flex flex-wrap items-center gap-2">
                  <TerminalSquare className="h-4 w-4 text-primary-light" />
                  <Badge variant="outline">{data.schema_version}</Badge>
                  <Badge variant="outline">{label(data.summary.run_status)}</Badge>
                  <Badge variant="outline">
                    {data.security.redacted ? 'Secrets redacted' : 'Unredacted'}
                  </Badge>
                </div>
                <p className="mt-3 font-mono text-[10px] text-muted">Run {runId}</p>
                <p className="mt-2 max-w-3xl text-[10px] leading-5 text-muted">
                  {data.security.policy}
                </p>
              </div>
              <div className="flex flex-wrap gap-2">
                <Button variant="outline" onClick={() => void query.refetch()}>
                  <RefreshCw className="mr-2 h-4 w-4" />Refresh
                </Button>
                <Button variant="outline" onClick={() => void copyAll()}>
                  <Copy className="mr-2 h-4 w-4" />Copy all
                </Button>
                <Button variant="outline" onClick={downloadAll}>
                  <Download className="mr-2 h-4 w-4" />Download JSON
                </Button>
              </div>
            </div>

            <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4 xl:grid-cols-8">
              {[
                ['Runtime', `${data.summary.runtime_completed}/${data.summary.total_trials}`],
                ['Judge started', `${data.summary.judge_started}/${data.summary.total_trials}`],
                ['Model calls', String(data.summary.judge_calls)],
                ['Failed calls', String(data.summary.judge_calls_failed)],
                ['Diagnostics', `${data.summary.judge_diagnostics_present}/${data.summary.judge_calls}`],
                ['Adaptive marker', String(data.summary.adaptive_gateway_markers)],
                ['Repair marker', String(data.summary.resilient_repair_markers)],
                ['Judge + target cost', money(data.summary.measured_total_cost)],
              ].map(([title, value]) => (
                <div key={title} className="rounded-lg border border-border/70 p-3">
                  <p className="text-[8px] uppercase tracking-wide text-muted">{title}</p>
                  <p className="mt-2 truncate text-sm font-semibold text-white">{value}</p>
                </div>
              ))}
            </div>
          </section>

          <div className="flex flex-wrap items-center gap-3">
            <div className="flex flex-1 gap-1 overflow-x-auto rounded-xl border border-border bg-background/35 p-1">
              {tabs.map((item) => (
                <button
                  key={item.value}
                  type="button"
                  onClick={() => setTab(item.value)}
                  className={cn(
                    'shrink-0 rounded-lg px-3 py-2 text-xs font-medium transition-colors',
                    tab === item.value
                      ? 'bg-primary/15 text-primary-light'
                      : 'text-muted hover:text-white',
                  )}
                >
                  {item.label}
                </button>
              ))}
            </div>
            {tab !== 'signals' && tab !== 'raw' ? (
              <label className="relative min-w-64 flex-1 lg:max-w-sm">
                <Search className="pointer-events-none absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted" />
                <Input
                  value={search}
                  onChange={(event) => setSearch(event.target.value)}
                  placeholder="Filter by Trial, error, provider or code"
                  className="pl-9"
                />
              </label>
            ) : null}
          </div>

          {tab === 'signals' ? (
            <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_420px]">
              <section className="space-y-3">
                {data.signals.length ? data.signals.map((signal) => (
                  <div
                    key={`${signal.code}-${signal.message}`}
                    className={cn('rounded-xl border p-4', signalTone(signal))}
                  >
                    <div className="flex items-center gap-2">
                      {signal.severity === 'error'
                        ? <XCircle className="h-4 w-4" />
                        : signal.severity === 'warning'
                          ? <AlertTriangle className="h-4 w-4" />
                          : <CheckCircle2 className="h-4 w-4" />}
                      <p className="font-mono text-[10px] font-semibold">{signal.code}</p>
                    </div>
                    <p className="mt-2 text-xs leading-5">{signal.message}</p>
                  </div>
                )) : (
                  <div className="rounded-xl border border-border p-8 text-center text-xs text-muted">
                    No diagnostic signals were generated.
                  </div>
                )}
              </section>
              <aside className="space-y-4">
                <JsonCodeBlock title="Failure groups" value={data.failure_groups} maxHeight={260} />
                <JsonCodeBlock title="Repeated error signatures" value={data.repeated_errors} maxHeight={320} />
              </aside>
            </div>
          ) : null}

          {tab === 'judge' ? (
            <section className="space-y-3">
              {judgeCalls.length ? judgeCalls.map((call) => (
                <JudgeCallCard key={call.id} call={call} />
              )) : (
                <div className="rounded-xl border border-dashed border-border p-10 text-center">
                  <FileJson className="mx-auto h-5 w-5 text-muted" />
                  <p className="mt-3 text-xs text-muted">No persisted Judge calls match this filter.</p>
                </div>
              )}
            </section>
          ) : null}

          {tab === 'trials' ? (
            <section className="space-y-3">
              {trials.length ? trials.map((trial) => (
                <TrialCard key={trial.id} trial={trial} />
              )) : (
                <div className="rounded-xl border border-dashed border-border p-10 text-center text-xs text-muted">
                  No Trials match this filter.
                </div>
              )}
            </section>
          ) : null}

          {tab === 'timeline' ? (
            <section className="overflow-hidden rounded-xl border border-border/80 bg-background/30">
              <div className="flex items-center gap-2 border-b border-border px-4 py-3">
                <Clock3 className="h-4 w-4 text-primary-light" />
                <p className="text-xs font-semibold text-white">Persisted execution timeline</p>
              </div>
              {timeline.length ? timeline.map((event, index) => (
                <TimelineRow key={`${event.at}-${event.stage}-${event.trial_id}-${index}`} event={event} />
              )) : (
                <div className="p-10 text-center text-xs text-muted">No timeline events match this filter.</div>
              )}
            </section>
          ) : null}

          {tab === 'raw' ? (
            <JsonCodeBlock
              title="Complete redacted Evaluation diagnostic bundle"
              value={data}
              maxHeight="65vh"
              actions={['copy', 'expand']}
            />
          ) : null}
        </div>
      )}
    </Dialog>
  )
}
