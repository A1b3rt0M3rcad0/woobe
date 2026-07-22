import { useEffect, useRef, useState } from 'react'
import {
  AlertTriangle,
  Check,
  ChevronRight,
  GitCompareArrows,
  Loader2,
  Play,
  ScanSearch,
} from 'lucide-react'
import { toast } from 'sonner'

import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { Select } from '@/components/ui/Select'
import type { AgentRelease } from '@/features/agents/types'
import type { EvaluationExperienceRunInput } from '@/features/evaluations/experienceTypes'
import {
  useCreateEvaluationRun,
  usePreviewEvaluationRun,
} from '@/features/evaluations/hooks'
import type {
  EvaluationPreview,
  EvaluationRun,
  EvaluationSourceType,
  EvaluationSuite,
  EvaluationTargetInput,
} from '@/features/evaluations/types'
import { cn } from '@/lib/utils'

type SetupMode = 'single' | 'compare'

interface Props {
  projectId: string
  agentId: string
  suites: EvaluationSuite[]
  releases: AgentRelease[]
  runs: EvaluationRun[]
  initialSuiteVersionId?: string | null
  onRunCreated?: (runId: string) => void
  onOpenResult?: (runId: string) => void
  onCreateSuite?: () => void
}

const activeStatuses = new Set([
  'queued',
  'snapshotting',
  'executing',
  'judging',
  'aggregating',
  'cancel_requested',
])

function versionsFor(releases: AgentRelease[], source: EvaluationSourceType) {
  if (source === 'staging') {
    return releases.filter((item) => item.status === 'staging')
  }
  if (source === 'release') {
    return releases.filter((item) => (
      item.snapshot_kind === 'release'
      || ['released', 'production', 'rolled_back'].includes(item.status)
    ))
  }
  return []
}

function sourceLabel(source: EvaluationSourceType) {
  if (source === 'draft') return 'Current Draft'
  if (source === 'staging') return 'Staging'
  return 'Release / Production'
}

function label(value?: string | null) {
  if (!value) return 'Unknown'
  return value
    .split('_')
    .map((item) => item.charAt(0).toUpperCase() + item.slice(1))
    .join(' ')
}

function SnapshotSelector({
  title,
  source,
  versionId,
  releases,
  onSourceChange,
  onVersionChange,
}: {
  title: string
  source: EvaluationSourceType
  versionId: string
  releases: AgentRelease[]
  onSourceChange: (value: EvaluationSourceType) => void
  onVersionChange: (value: string) => void
}) {
  const versions = versionsFor(releases, source)
  const selected = releases.find((item) => item.id === versionId)
  return (
    <section className="rounded-xl border border-border/80 bg-background/35 p-4">
      <div className="flex items-center gap-2">
        <ScanSearch className="h-4 w-4 text-primary-light" />
        <p className="text-xs font-semibold text-white">{title}</p>
      </div>
      <div className="mt-4 grid gap-3 sm:grid-cols-2">
        <label className="space-y-2 text-xs text-muted">
          <span>Environment</span>
          <Select
            value={source}
            onChange={(event) => onSourceChange(event.target.value as EvaluationSourceType)}
            options={[
              { value: 'draft', label: 'Current Draft' },
              { value: 'staging', label: 'Staging' },
              { value: 'release', label: 'Release / Production' },
            ]}
          />
        </label>
        <label className="space-y-2 text-xs text-muted">
          <span>Exact snapshot</span>
          <Select
            disabled={source === 'draft'}
            value={versionId}
            onChange={(event) => onVersionChange(event.target.value)}
            options={[
              {
                value: '',
                label: source === 'draft'
                  ? 'Current Draft will be frozen'
                  : 'Select exact snapshot',
              },
              ...versions.map((item) => ({
                value: item.id,
                label: `${item.version} · ${item.status}`,
              })),
            ]}
          />
        </label>
      </div>
      <div className="mt-3 rounded-lg border border-border/70 p-3">
        <p className="text-[9px] uppercase text-muted">Will be tested</p>
        <p className="mt-1 text-xs font-medium text-white">
          {source === 'draft'
            ? 'Current Draft'
            : selected
              ? `${selected.version} · ${selected.status}`
              : 'Select a snapshot'}
        </p>
        {selected ? (
          <p className="mt-1 text-[10px] text-muted">
            {[selected.provider, selected.model].filter(Boolean).join(' · ') || 'Configured model'}
          </p>
        ) : null}
      </div>
    </section>
  )
}

export function AgentEvaluationExperience({
  projectId,
  agentId,
  suites,
  releases,
  runs,
  initialSuiteVersionId,
  onRunCreated,
  onOpenResult,
  onCreateSuite,
}: Props) {
  const production = releases.find((item) => item.status === 'production')
  const preview = usePreviewEvaluationRun(projectId)
  const createRun = useCreateEvaluationRun(projectId)
  const [mode, setMode] = useState<SetupMode>('single')
  const [suiteVersionId, setSuiteVersionId] = useState(initialSuiteVersionId || '')
  const [repetitions, setRepetitions] = useState(1)
  const [candidateSource, setCandidateSource] = useState<EvaluationSourceType>(
    production ? 'release' : 'draft',
  )
  const [candidateVersionId, setCandidateVersionId] = useState(production?.id || '')
  const [baselineSource, setBaselineSource] = useState<EvaluationSourceType>('draft')
  const [baselineVersionId, setBaselineVersionId] = useState('')
  const [acknowledge, setAcknowledge] = useState(false)
  const [approvedHighRiskIds, setApprovedHighRiskIds] = useState<string[]>([])
  const [idempotencyKey, setIdempotencyKey] = useState(() => crypto.randomUUID())
  const lastPreviewKey = useRef('')

  const selectedSuite = suites.find(
    (item) => item.current_version_id === suiteVersionId,
  )
  const activeRuns = runs.filter((item) => activeStatuses.has(item.status))

  useEffect(() => {
    if (initialSuiteVersionId) setSuiteVersionId(initialSuiteVersionId)
  }, [initialSuiteVersionId])

  useEffect(() => {
    if (!suiteVersionId && suites[0]?.current_version_id) {
      setSuiteVersionId(suites[0].current_version_id)
      setRepetitions(Number(suites[0].repetition_policy?.default_repetitions ?? 1))
    }
  }, [suites, suiteVersionId])

  const buildInput = (): EvaluationExperienceRunInput | null => {
    if (!suiteVersionId) return null
    if (candidateSource !== 'draft' && !candidateVersionId) return null
    if (mode === 'compare' && baselineSource !== 'draft' && !baselineVersionId) return null

    const candidate: EvaluationTargetInput = {
      target_type: 'agent',
      source_type: candidateSource,
      entity_id: agentId,
      ...(candidateSource !== 'draft' ? { version_id: candidateVersionId } : {}),
    }
    const baseline: EvaluationTargetInput | undefined = mode === 'compare'
      ? {
          target_type: 'agent',
          source_type: baselineSource,
          entity_id: agentId,
          ...(baselineSource !== 'draft' ? { version_id: baselineVersionId } : {}),
        }
      : undefined

    return {
      suite_version_id: suiteVersionId,
      repetitions,
      candidate,
      baseline,
      acknowledge_tool_side_effects: acknowledge,
      approved_high_risk_tool_ids: approvedHighRiskIds,
      idempotency_key: idempotencyKey,
    }
  }

  const input = buildInput()
  const previewKey = input
    ? JSON.stringify({ ...input, idempotency_key: undefined })
    : ''

  useEffect(() => {
    setAcknowledge(false)
    setApprovedHighRiskIds([])
    lastPreviewKey.current = ''
    preview.reset()
  }, [
    mode,
    suiteVersionId,
    repetitions,
    candidateSource,
    candidateVersionId,
    baselineSource,
    baselineVersionId,
  ])

  useEffect(() => {
    if (!input || previewKey === lastPreviewKey.current) return
    const timer = window.setTimeout(() => {
      lastPreviewKey.current = previewKey
      preview.mutate(input as any, { onError: () => undefined })
    }, 450)
    return () => window.clearTimeout(timer)
  }, [previewKey])

  const previewData = preview.data as EvaluationPreview | undefined
  const highRiskTools = previewData?.preflight.tools.filter(
    (tool) => tool.risk_level === 'high',
  ) || []
  const highRiskApproved = highRiskTools.every(
    (tool) => approvedHighRiskIds.includes(tool.id),
  )
  const needsAcknowledgement = (
    previewData?.preflight.requires_acknowledgement ?? false
  )
  const readyToRun = Boolean(
    input
    && previewData
    && highRiskApproved
    && (!needsAcknowledgement || acknowledge),
  )

  const start = async () => {
    const payload = buildInput()
    if (!payload) {
      toast.error('Select the exact snapshot to test')
      return
    }
    try {
      const run = await createRun.mutateAsync(payload as any)
      onRunCreated?.(run.id)
      setIdempotencyKey(crypto.randomUUID())
      toast.success(
        mode === 'compare'
          ? 'Snapshot comparison queued. The Run form remains available.'
          : 'Snapshot Evaluation queued. The Run form remains available.',
      )
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Unable to start Evaluation')
    }
  }

  if (!suites.length) {
    return (
      <div className="mx-auto max-w-2xl rounded-2xl border border-dashed border-border p-12 text-center">
        <ScanSearch className="mx-auto h-8 w-8 text-muted" />
        <h3 className="mt-4 text-base font-semibold text-white">Create an Evaluator Suite first</h3>
        <p className="mx-auto mt-2 max-w-lg text-xs leading-5 text-muted">
          A Suite is the reusable, versioned set of Test Cases used to assess real Agent snapshots.
        </p>
        {onCreateSuite ? <Button className="mt-5" onClick={onCreateSuite}>Create Evaluator Suite</Button> : null}
      </div>
    )
  }

  return (
    <div className="mx-auto max-w-5xl space-y-5">
      <section className="rounded-2xl border border-border/80 bg-background/30 p-5">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <h3 className="text-base font-semibold text-white">New Evaluation</h3>
            <p className="mt-1 text-xs text-muted">
              Configure and queue a Run. Existing Runs continue independently in Results.
            </p>
          </div>
          <div className="flex rounded-lg border border-border bg-background/45 p-1">
            <button
              type="button"
              onClick={() => setMode('single')}
              className={cn(
                'rounded-md px-3 py-2 text-xs font-medium',
                mode === 'single' ? 'bg-primary/15 text-primary-light' : 'text-muted',
              )}
            >
              Test one snapshot
            </button>
            <button
              type="button"
              onClick={() => setMode('compare')}
              className={cn(
                'rounded-md px-3 py-2 text-xs font-medium',
                mode === 'compare' ? 'bg-primary/15 text-primary-light' : 'text-muted',
              )}
            >
              <GitCompareArrows className="mr-1.5 inline h-3.5 w-3.5" />Compare snapshots
            </button>
          </div>
        </div>

        <div className="mt-5 grid gap-4 md:grid-cols-[minmax(0,1fr)_180px]">
          <label className="space-y-2 text-xs text-muted">
            <span>Evaluator Suite</span>
            <Select
              value={suiteVersionId}
              onChange={(event) => setSuiteVersionId(event.target.value)}
              options={suites.map((suite) => ({
                value: suite.current_version_id || '',
                label: `${suite.name} · Current ${suite.current_version}`,
              }))}
            />
          </label>
          <label className="space-y-2 text-xs text-muted">
            <span>Runs per Test Case</span>
            <Select
              value={String(repetitions)}
              onChange={(event) => setRepetitions(Number(event.target.value))}
              options={[
                { value: '1', label: 'Quick · 1' },
                { value: '3', label: 'Standard · 3' },
                { value: '5', label: 'Thorough · 5' },
              ]}
            />
          </label>
        </div>
        {selectedSuite ? (
          <p className="mt-3 text-[11px] leading-5 text-muted">
            {selectedSuite.case_count || 0} Test Cases · Policy score ≥ {String(selectedSuite.acceptance_policy?.minimum_score ?? 70)} · {selectedSuite.description}
          </p>
        ) : null}
      </section>

      <div className={cn('grid gap-4', mode === 'compare' && 'lg:grid-cols-2')}>
        <SnapshotSelector
          title={mode === 'compare' ? 'Candidate snapshot' : 'Target snapshot'}
          source={candidateSource}
          versionId={candidateVersionId}
          releases={releases}
          onSourceChange={(value) => {
            setCandidateSource(value)
            setCandidateVersionId(value === 'release' ? production?.id || '' : '')
          }}
          onVersionChange={setCandidateVersionId}
        />
        {mode === 'compare' ? (
          <SnapshotSelector
            title="Baseline snapshot"
            source={baselineSource}
            versionId={baselineVersionId}
            releases={releases}
            onSourceChange={(value) => {
              setBaselineSource(value)
              setBaselineVersionId('')
            }}
            onVersionChange={setBaselineVersionId}
          />
        ) : null}
      </div>

      <section className="rounded-2xl border border-primary/20 bg-primary/[0.035] p-5">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <div className="flex items-center gap-2">
              <Check className="h-4 w-4 text-primary-light" />
              <p className="text-sm font-semibold text-white">Authoritative preview</p>
            </div>
            <p className="mt-1 text-[11px] text-muted">
              The backend resolves and freezes exactly the snapshots shown above.
            </p>
          </div>
          {preview.isPending ? (
            <Badge variant="outline">Calculating…</Badge>
          ) : previewData ? (
            <Badge variant="outline">Ready · {previewData.mode === 'comparison' ? '2 targets' : '1 target'}</Badge>
          ) : preview.isError ? (
            <Badge variant="outline">Preflight failed</Badge>
          ) : (
            <Badge variant="outline">Complete the setup</Badge>
          )}
        </div>
        {preview.isError ? (
          <div className="mt-4 flex items-start gap-2 rounded-lg border border-red-500/20 bg-red-500/[0.05] p-3 text-xs text-red-300">
            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
            {preview.error instanceof Error ? preview.error.message : 'Unable to validate this Evaluation setup.'}
          </div>
        ) : null}
        {previewData ? (
          <div className="mt-4 grid gap-3 sm:grid-cols-3">
            <div><p className="text-[9px] uppercase text-muted">Test Cases</p><p className="mt-1 text-xl font-semibold text-white">{previewData.case_count}</p></div>
            <div><p className="text-[9px] uppercase text-muted">Target executions</p><p className="mt-1 text-xl font-semibold text-white">{previewData.target_run_count}</p></div>
            <div><p className="text-[9px] uppercase text-muted">Judge calls</p><p className="mt-1 text-xl font-semibold text-white">{previewData.judge_call_count}</p></div>
          </div>
        ) : null}
        {previewData?.preflight.tools.length ? (
          <div className="mt-4 border-t border-primary/15 pt-4">
            <p className="text-xs font-medium text-white">Real Tools detected</p>
            <div className="mt-2 space-y-2">
              {previewData.preflight.tools.map((tool) => (
                <label key={tool.id} className="flex items-center justify-between gap-3 rounded-lg border border-border/70 bg-background/35 px-3 py-2">
                  <div><p className="text-xs text-white">{tool.name}</p><p className="text-[10px] text-muted">{tool.risk_level} risk</p></div>
                  {tool.risk_level === 'high' ? (
                    <span className="flex items-center gap-2 text-[10px] text-amber-200">
                      <input
                        type="checkbox"
                        checked={approvedHighRiskIds.includes(tool.id)}
                        onChange={(event) => setApprovedHighRiskIds((current) => (
                          event.target.checked
                            ? [...new Set([...current, tool.id])]
                            : current.filter((id) => id !== tool.id)
                        ))}
                      />Approve
                    </span>
                  ) : null}
                </label>
              ))}
            </div>
            {needsAcknowledgement ? (
              <label className="mt-3 flex items-start gap-3 rounded-lg border border-amber-500/20 bg-amber-500/[0.05] p-3 text-xs text-amber-200">
                <input type="checkbox" checked={acknowledge} onChange={(event) => setAcknowledge(event.target.checked)} className="mt-0.5" />
                <span>I understand that this Evaluation executes the real Tools shown above and may produce external side effects.</span>
              </label>
            ) : null}
          </div>
        ) : null}
      </section>

      <div className="flex items-center justify-between border-t border-border pt-4">
        <p className="text-[11px] text-muted">
          {mode === 'compare'
            ? 'Candidate and Baseline use their exact persisted snapshots.'
            : `${sourceLabel(candidateSource)} is the only target that will be tested.`}
        </p>
        <Button loading={createRun.isPending} disabled={!readyToRun} onClick={() => void start()}>
          <Play className="mr-2 h-4 w-4" />
          {mode === 'compare' ? 'Run Snapshot Comparison' : 'Run Evaluation'}
        </Button>
      </div>

      {activeRuns.length ? (
        <section className="rounded-2xl border border-border/80 bg-background/25 p-4">
          <div className="flex items-center justify-between">
            <div>
              <h4 className="text-sm font-semibold text-white">Active Runs</h4>
              <p className="mt-1 text-[11px] text-muted">They continue independently while this form remains available.</p>
            </div>
            <Badge variant="outline">{activeRuns.length}</Badge>
          </div>
          <div className="mt-3 space-y-2">
            {activeRuns.slice(0, 5).map((run) => {
              const target = run.targets.find((item) => item.side === 'single') || run.targets[0]
              return (
                <button
                  key={run.id}
                  type="button"
                  onClick={() => onOpenResult?.(run.id)}
                  className="flex w-full items-center gap-3 rounded-xl border border-border/70 bg-surface/20 px-3 py-3 text-left hover:border-primary/30"
                >
                  <Loader2 className="h-4 w-4 animate-spin text-primary-light" />
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-xs font-medium text-white">
                      {target?.display_name} · {target?.display_version}
                    </p>
                    <p className="mt-1 text-[10px] text-muted">{label(run.status)} · {run.repetitions} runs/case</p>
                  </div>
                  <ChevronRight className="h-4 w-4 text-muted" />
                </button>
              )
            })}
          </div>
        </section>
      ) : null}
    </div>
  )
}
