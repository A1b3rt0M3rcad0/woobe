import { useEffect, useMemo, useRef, useState } from 'react'
import type { ReactNode } from 'react'
import {
  AlertTriangle,
  Beaker,
  Check,
  ChevronDown,
  GitCompareArrows,
  Play,
  Settings2,
  Sparkles,
} from 'lucide-react'
import { toast } from 'sonner'

import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { Select } from '@/components/ui/Select'
import type { AgentRelease } from '@/features/agents/types'
import {
  useEvaluationRunProgress,
  useRetryEvaluationJudgments,
} from '@/features/evaluations/experienceHooks'
import type {
  EvaluationExperienceRunInput,
  EvaluationTargetWithVariant,
} from '@/features/evaluations/experienceTypes'
import {
  useCreateEvaluationRun,
  useEvaluationRun,
  usePreviewEvaluationRun,
} from '@/features/evaluations/hooks'
import type {
  EvaluationPreview,
  EvaluationSourceType,
  EvaluationSuite,
} from '@/features/evaluations/types'
import type { ProviderModel } from '@/features/provider-models/types'
import { cn } from '@/lib/utils'
import { EvaluationResultsView } from './EvaluationResultsView'
import { EvaluationRunProgressView } from './EvaluationRunProgressView'

type SetupMode = 'quick' | 'compare' | 'advanced'
type ComparisonType = 'models' | 'snapshots'

interface Props {
  projectId: string
  agentId: string
  suites: EvaluationSuite[]
  releases: AgentRelease[]
  providerModels: ProviderModel[]
  initialRunId?: string | null
  initialSuiteVersionId?: string | null
  onRunCreated?: (runId: string) => void
  onCreateSuite?: () => void
}

const terminalStatuses = new Set([
  'completed',
  'partially_completed',
  'failed',
  'cancelled',
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

function modelLabel(model: ProviderModel) {
  return `${model.name} · ${model.model}`
}

function ModeButton({
  active,
  icon,
  title,
  description,
  onClick,
}: {
  active: boolean
  icon: ReactNode
  title: string
  description: string
  onClick: () => void
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        'rounded-xl border p-4 text-left transition-colors',
        active
          ? 'border-primary/35 bg-primary/[0.07]'
          : 'border-border/80 bg-background/30 hover:border-primary/25',
      )}
    >
      <div className="flex items-start gap-3">
        <div className={cn(
          'flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border',
          active
            ? 'border-primary/30 bg-primary/10 text-primary-light'
            : 'border-border text-muted',
        )}>
          {icon}
        </div>
        <div>
          <p className="text-sm font-semibold text-white">{title}</p>
          <p className="mt-1 text-[11px] leading-4 text-muted">{description}</p>
        </div>
      </div>
    </button>
  )
}

export function AgentEvaluationExperience({
  projectId,
  agentId,
  suites,
  releases,
  providerModels,
  initialRunId,
  initialSuiteVersionId,
  onRunCreated,
  onCreateSuite,
}: Props) {
  const preview = usePreviewEvaluationRun(projectId)
  const createRun = useCreateEvaluationRun(projectId)
  const [runId, setRunId] = useState<string | null>(initialRunId || null)
  const progressQuery = useEvaluationRunProgress(projectId, runId)
  const retryJudgments = useRetryEvaluationJudgments(projectId, runId)

  const [mode, setMode] = useState<SetupMode>('quick')
  const [comparisonType, setComparisonType] = useState<ComparisonType>('models')
  const [suiteVersionId, setSuiteVersionId] = useState(initialSuiteVersionId || '')
  const [repetitions, setRepetitions] = useState(3)
  const [candidateSource, setCandidateSource] = useState<EvaluationSourceType>('draft')
  const [candidateVersionId, setCandidateVersionId] = useState('')
  const [baselineSource, setBaselineSource] = useState<EvaluationSourceType>('release')
  const [baselineVersionId, setBaselineVersionId] = useState('')
  const [modelAId, setModelAId] = useState('')
  const [modelBId, setModelBId] = useState('')
  const [acknowledge, setAcknowledge] = useState(false)
  const [approvedHighRiskIds, setApprovedHighRiskIds] = useState<string[]>([])
  const [advancedOpen, setAdvancedOpen] = useState(false)
  const [detailsOpen, setDetailsOpen] = useState(false)
  const [idempotencyKey, setIdempotencyKey] = useState(() => crypto.randomUUID())
  const lastPreviewKey = useRef('')

  const activeModels = providerModels.filter((item) => item.status === 'active')
  const draft = releases.find(
    (item) => item.status === 'draft' || item.snapshot_kind === 'draft',
  )
  const production = releases.find((item) => item.status === 'production')
  const selectedSuite = suites.find(
    (item) => item.current_version_id === suiteVersionId,
  )
  const progress = progressQuery.data
  const progressTerminal = Boolean(
    progress && terminalStatuses.has(progress.status),
  )
  const shouldLoadDetails = Boolean(runId && (detailsOpen || progressTerminal))
  const runQuery = useEvaluationRun(
    projectId,
    shouldLoadDetails ? runId : null,
  )

  useEffect(() => {
    if (initialRunId) setRunId(initialRunId)
  }, [initialRunId])

  useEffect(() => {
    if (initialSuiteVersionId) setSuiteVersionId(initialSuiteVersionId)
  }, [initialSuiteVersionId])

  useEffect(() => {
    if (!suiteVersionId && suites[0]?.current_version_id) {
      setSuiteVersionId(suites[0].current_version_id)
      setRepetitions(
        Number(suites[0].repetition_policy?.default_repetitions ?? 3),
      )
    }
  }, [suites, suiteVersionId])

  useEffect(() => {
    if (!modelAId) {
      setModelAId(draft?.provider_model_id || activeModels[0]?.id || '')
    }
    if (!modelBId) {
      const first = draft?.provider_model_id || activeModels[0]?.id
      setModelBId(activeModels.find((item) => item.id !== first)?.id || '')
    }
    if (!baselineVersionId && production?.id) {
      setBaselineVersionId(production.id)
    }
  }, [activeModels, draft?.provider_model_id, production?.id])

  const candidateVersions = versionsFor(releases, candidateSource)
  const baselineVersions = versionsFor(releases, baselineSource)

  const buildInput = (): EvaluationExperienceRunInput | null => {
    if (!suiteVersionId) return null
    if (candidateSource !== 'draft' && !candidateVersionId) return null

    const candidate: EvaluationTargetWithVariant = {
      target_type: 'agent',
      source_type: candidateSource,
      entity_id: agentId,
      ...(candidateSource !== 'draft' && candidateVersionId
        ? { version_id: candidateVersionId }
        : {}),
    }
    let baseline: EvaluationTargetWithVariant | undefined

    if (mode === 'compare' && comparisonType === 'models') {
      if (!modelAId || !modelBId || modelAId === modelBId) return null
      candidate.variant = {
        type: 'model_override',
        provider_model_id: modelAId,
      }
      baseline = {
        target_type: 'agent',
        source_type: candidateSource,
        entity_id: agentId,
        ...(candidateSource !== 'draft' && candidateVersionId
          ? { version_id: candidateVersionId }
          : {}),
        variant: {
          type: 'model_override',
          provider_model_id: modelBId,
        },
      }
    } else if (mode === 'compare' && comparisonType === 'snapshots') {
      if (baselineSource !== 'draft' && !baselineVersionId) return null
      baseline = {
        target_type: 'agent',
        source_type: baselineSource,
        entity_id: agentId,
        ...(baselineSource !== 'draft' && baselineVersionId
          ? { version_id: baselineVersionId }
          : {}),
      }
    }

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
    comparisonType,
    suiteVersionId,
    repetitions,
    candidateSource,
    candidateVersionId,
    baselineSource,
    baselineVersionId,
    modelAId,
    modelBId,
  ])

  useEffect(() => {
    if (!input || runId || previewKey === lastPreviewKey.current) return
    const timer = window.setTimeout(() => {
      lastPreviewKey.current = previewKey
      preview.mutate(input as any, { onError: () => undefined })
    }, 450)
    return () => window.clearTimeout(timer)
  }, [previewKey, runId])

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
  const judgeMatchesComparedModel = Boolean(
    mode === 'compare'
    && comparisonType === 'models'
    && selectedSuite?.judge_provider_model_id
    && [modelAId, modelBId].includes(selectedSuite.judge_provider_model_id),
  )

  const start = async () => {
    const payload = buildInput()
    if (!payload) {
      toast.error('Complete the Evaluation setup')
      return
    }
    try {
      const run = await createRun.mutateAsync(payload as any)
      setRunId(run.id)
      onRunCreated?.(run.id)
      setIdempotencyKey(crypto.randomUUID())
      toast.success(
        run.mode === 'comparison' ? 'Comparison queued' : 'Evaluation queued',
      )
    } catch (error) {
      toast.error(
        error instanceof Error ? error.message : 'Unable to start Evaluation',
      )
    }
  }

  const retry = async () => {
    try {
      await retryJudgments.mutateAsync({
        failure_codes: [
          'judge_failed',
          'judge_output_length_limit',
          'judge_invalid_json',
        ],
      })
      setDetailsOpen(false)
      toast.success('Judgments queued without re-running the Agent')
    } catch (error) {
      toast.error(
        error instanceof Error ? error.message : 'Unable to retry judgments',
      )
    }
  }

  if (runId) {
    const active = Boolean(progress && !progressTerminal)
    if (!detailsOpen && progress && (active || !runQuery.data?.trials?.length)) {
      return (
        <EvaluationRunProgressView
          progress={progress}
          retrying={retryJudgments.isPending}
          onRetryJudgments={
            !active && progress.inconclusive_trials + progress.failed_trials > 0
              ? () => void retry()
              : undefined
          }
          onOpenDetails={!active ? () => setDetailsOpen(true) : undefined}
        />
      )
    }
    if (runQuery.data) {
      return (
        <EvaluationResultsView
          run={runQuery.data}
          retrying={retryJudgments.isPending}
          onRetryJudgments={() => void retry()}
        />
      )
    }
    return (
      <div className="flex min-h-72 items-center justify-center text-sm text-muted">
        Loading Evaluation…
      </div>
    )
  }

  if (!suites.length) {
    return (
      <div className="mx-auto max-w-2xl rounded-2xl border border-dashed border-border p-12 text-center">
        <Beaker className="mx-auto h-8 w-8 text-muted" />
        <h3 className="mt-4 text-base font-semibold text-white">
          Create an Evaluator Suite first
        </h3>
        <p className="mx-auto mt-2 max-w-lg text-xs leading-5 text-muted">
          A Suite is the reusable, versioned set of Test Cases used by Quick
          tests and comparisons.
        </p>
        {onCreateSuite ? (
          <Button className="mt-5" onClick={onCreateSuite}>
            Create Evaluator Suite
          </Button>
        ) : null}
      </div>
    )
  }

  return (
    <div className="mx-auto max-w-4xl space-y-5">
      <section>
        <p className="text-[10px] font-medium uppercase tracking-[0.18em] text-muted">
          What do you want to do?
        </p>
        <div className="mt-3 grid gap-3 md:grid-cols-3">
          <ModeButton
            active={mode === 'quick'}
            icon={<Sparkles className="h-4 w-4" />}
            title="Quick test"
            description="Test the current Agent with recommended settings."
            onClick={() => setMode('quick')}
          />
          <ModeButton
            active={mode === 'compare'}
            icon={<GitCompareArrows className="h-4 w-4" />}
            title="Compare two"
            description="Compare two models or two immutable snapshots."
            onClick={() => setMode('compare')}
          />
          <ModeButton
            active={mode === 'advanced'}
            icon={<Settings2 className="h-4 w-4" />}
            title="Advanced"
            description="Control exact snapshots, repetitions and Tool approvals."
            onClick={() => setMode('advanced')}
          />
        </div>
      </section>

      <section className="rounded-2xl border border-border/80 bg-background/35 p-5">
        <div className="grid gap-4 md:grid-cols-[minmax(0,1fr)_180px]">
          <label className="space-y-2 text-xs text-muted">
            <span>Evaluator Suite</span>
            <Select
              value={suiteVersionId}
              onChange={(event) => setSuiteVersionId(event.target.value)}
              options={suites.map((suite) => ({
                value: suite.current_version_id || '',
                label: `${suite.name} · ${suite.current_version}`,
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
            {selectedSuite.description
              || `${selectedSuite.case_count || 0} versioned Test Cases.`}
          </p>
        ) : null}
      </section>

      {mode === 'compare' ? (
        <section className="rounded-2xl border border-border/80 bg-background/35 p-5">
          <div className="flex gap-1 rounded-lg border border-border bg-background/45 p-1">
            <button
              type="button"
              onClick={() => setComparisonType('models')}
              className={cn(
                'flex-1 rounded-md px-3 py-2 text-xs font-medium',
                comparisonType === 'models'
                  ? 'bg-primary/15 text-primary-light'
                  : 'text-muted',
              )}
            >
              Compare models
            </button>
            <button
              type="button"
              onClick={() => setComparisonType('snapshots')}
              className={cn(
                'flex-1 rounded-md px-3 py-2 text-xs font-medium',
                comparisonType === 'snapshots'
                  ? 'bg-primary/15 text-primary-light'
                  : 'text-muted',
              )}
            >
              Compare snapshots
            </button>
          </div>

          {comparisonType === 'models' ? (
            <div className="mt-4 grid gap-4 md:grid-cols-2">
              <label className="space-y-2 text-xs text-muted">
                <span>Model A</span>
                <Select
                  value={modelAId}
                  onChange={(event) => setModelAId(event.target.value)}
                  options={[
                    { value: '', label: 'Select Model A' },
                    ...activeModels.map((item) => ({
                      value: item.id,
                      label: modelLabel(item),
                    })),
                  ]}
                />
              </label>
              <label className="space-y-2 text-xs text-muted">
                <span>Model B</span>
                <Select
                  value={modelBId}
                  onChange={(event) => setModelBId(event.target.value)}
                  options={[
                    { value: '', label: 'Select Model B' },
                    ...activeModels.map((item) => ({
                      value: item.id,
                      label: modelLabel(item),
                    })),
                  ]}
                />
              </label>
              <p className="md:col-span-2 text-[11px] leading-5 text-muted">
                Both models receive the same frozen prompt, Tools, Knowledge,
                output contract and runtime configuration. The Agent Draft is
                not changed.
              </p>
              {judgeMatchesComparedModel ? (
                <div className="md:col-span-2 flex items-start gap-2 rounded-lg border border-amber-500/20 bg-amber-500/[0.05] p-3 text-xs text-amber-200">
                  <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
                  The selected Suite uses one of the compared models as Judge.
                  This is allowed, but can introduce evaluation bias.
                </div>
              ) : null}
            </div>
          ) : (
            <div className="mt-4 grid gap-4 md:grid-cols-2">
              <label className="space-y-2 text-xs text-muted">
                <span>Candidate snapshot</span>
                <Select
                  value={candidateSource}
                  onChange={(event) => {
                    setCandidateSource(event.target.value as EvaluationSourceType)
                    setCandidateVersionId('')
                  }}
                  options={[
                    { value: 'draft', label: 'Current Draft' },
                    { value: 'staging', label: 'Staging' },
                    { value: 'release', label: 'Release / Production' },
                  ]}
                />
              </label>
              <label className="space-y-2 text-xs text-muted">
                <span>Baseline snapshot</span>
                <Select
                  value={baselineSource}
                  onChange={(event) => {
                    setBaselineSource(event.target.value as EvaluationSourceType)
                    setBaselineVersionId('')
                  }}
                  options={[
                    { value: 'release', label: 'Release / Production' },
                    { value: 'staging', label: 'Staging' },
                    { value: 'draft', label: 'Current Draft' },
                  ]}
                />
              </label>
              {candidateSource !== 'draft' ? (
                <Select
                  value={candidateVersionId}
                  onChange={(event) => setCandidateVersionId(event.target.value)}
                  options={[
                    { value: '', label: 'Select candidate version' },
                    ...candidateVersions.map((item) => ({
                      value: item.id,
                      label: `${item.version} · ${item.status}`,
                    })),
                  ]}
                />
              ) : (
                <div className="rounded-lg border border-border px-3 py-2 text-xs text-muted">
                  Current Draft will be frozen
                </div>
              )}
              {baselineSource !== 'draft' ? (
                <Select
                  value={baselineVersionId}
                  onChange={(event) => setBaselineVersionId(event.target.value)}
                  options={[
                    { value: '', label: 'Select baseline version' },
                    ...baselineVersions.map((item) => ({
                      value: item.id,
                      label: `${item.version} · ${item.status}`,
                    })),
                  ]}
                />
              ) : (
                <div className="rounded-lg border border-border px-3 py-2 text-xs text-muted">
                  Current Draft will be frozen
                </div>
              )}
            </div>
          )}
        </section>
      ) : null}

      {mode === 'advanced'
      || (mode === 'compare' && comparisonType === 'models') ? (
        <section className="rounded-2xl border border-border/80 bg-background/35 p-5">
          <button
            type="button"
            onClick={() => setAdvancedOpen((value) => !value)}
            className="flex w-full items-center justify-between text-left"
          >
            <div>
              <p className="text-sm font-semibold text-white">Advanced settings</p>
              <p className="mt-1 text-[11px] text-muted">
                Exact base snapshot and execution details.
              </p>
            </div>
            <ChevronDown className={cn(
              'h-4 w-4 text-muted transition-transform',
              advancedOpen && 'rotate-180',
            )} />
          </button>
          {advancedOpen || mode === 'advanced' ? (
            <div className="mt-4 grid gap-4 md:grid-cols-2">
              <label className="space-y-2 text-xs text-muted">
                <span>Base environment</span>
                <Select
                  value={candidateSource}
                  onChange={(event) => {
                    setCandidateSource(event.target.value as EvaluationSourceType)
                    setCandidateVersionId('')
                  }}
                  options={[
                    { value: 'draft', label: 'Current Draft' },
                    { value: 'staging', label: 'Staging' },
                    { value: 'release', label: 'Release / Production' },
                  ]}
                />
              </label>
              <label className="space-y-2 text-xs text-muted">
                <span>Exact base snapshot</span>
                <Select
                  disabled={candidateSource === 'draft'}
                  value={candidateVersionId}
                  onChange={(event) => setCandidateVersionId(event.target.value)}
                  options={[
                    {
                      value: '',
                      label: candidateSource === 'draft'
                        ? 'Current Draft will be frozen'
                        : 'Select exact snapshot',
                    },
                    ...candidateVersions.map((item) => ({
                      value: item.id,
                      label: `${item.version} · ${item.status}`,
                    })),
                  ]}
                />
              </label>
              <label className="space-y-2 text-xs text-muted">
                <span>Custom repetitions</span>
                <Input
                  type="number"
                  min={1}
                  max={25}
                  value={repetitions}
                  onChange={(event) => setRepetitions(
                    Math.max(1, Math.min(25, Number(event.target.value))),
                  )}
                />
              </label>
              <div className="rounded-lg border border-border/70 bg-surface/20 p-3 text-[11px] text-muted">
                Judge output budget is automatic and adapts to reasoning models.
                Agent output limits remain unchanged because they are part of the
                tested snapshot.
              </div>
            </div>
          ) : null}
        </section>
      ) : null}

      <section className="rounded-2xl border border-primary/20 bg-primary/[0.035] p-5">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <div className="flex items-center gap-2">
              <Check className="h-4 w-4 text-primary-light" />
              <p className="text-sm font-semibold text-white">Workload preview</p>
            </div>
            <p className="mt-1 text-[11px] text-muted">
              Calculated automatically. The backend repeats the authoritative
              preflight when you start.
            </p>
          </div>
          {preview.isPending ? (
            <Badge variant="outline">Calculating…</Badge>
          ) : previewData ? (
            <Badge variant="outline">Ready</Badge>
          ) : preview.isError ? (
            <Badge variant="outline">Preflight failed</Badge>
          ) : (
            <Badge variant="outline">Complete the setup</Badge>
          )}
        </div>

        {preview.isError ? (
          <div className="mt-4 flex items-start gap-2 rounded-lg border border-red-500/20 bg-red-500/[0.05] p-3 text-xs text-red-300">
            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
            {preview.error instanceof Error
              ? preview.error.message
              : 'Unable to validate this Evaluation setup.'}
          </div>
        ) : null}

        {previewData ? (
          <div className="mt-4 grid gap-3 sm:grid-cols-3">
            <div>
              <p className="text-[9px] uppercase text-muted">Test Cases</p>
              <p className="mt-1 text-xl font-semibold text-white">
                {previewData.case_count}
              </p>
            </div>
            <div>
              <p className="text-[9px] uppercase text-muted">Agent Runs</p>
              <p className="mt-1 text-xl font-semibold text-white">
                {previewData.target_run_count}
              </p>
            </div>
            <div>
              <p className="text-[9px] uppercase text-muted">Judge calls</p>
              <p className="mt-1 text-xl font-semibold text-white">
                {previewData.judge_call_count}
              </p>
            </div>
          </div>
        ) : null}

        {previewData?.preflight.tools.length ? (
          <div className="mt-4 border-t border-primary/15 pt-4">
            <p className="text-xs font-medium text-white">Real Tools detected</p>
            <div className="mt-2 space-y-2">
              {previewData.preflight.tools.map((tool) => (
                <label
                  key={tool.id}
                  className="flex items-center justify-between gap-3 rounded-lg border border-border/70 bg-background/35 px-3 py-2"
                >
                  <div>
                    <p className="text-xs text-white">{tool.name}</p>
                    <p className="text-[10px] text-muted">{tool.risk_level} risk</p>
                  </div>
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
                      />
                      Approve
                    </span>
                  ) : null}
                </label>
              ))}
            </div>
            {needsAcknowledgement ? (
              <label className="mt-3 flex items-start gap-3 rounded-lg border border-amber-500/20 bg-amber-500/[0.05] p-3 text-xs text-amber-200">
                <input
                  type="checkbox"
                  checked={acknowledge}
                  onChange={(event) => setAcknowledge(event.target.checked)}
                  className="mt-0.5"
                />
                <span>
                  I understand that this Evaluation executes the real Tools shown
                  above and may produce external side effects.
                </span>
              </label>
            ) : null}
          </div>
        ) : null}
      </section>

      <div className="flex items-center justify-between border-t border-border pt-4">
        <p className="text-[11px] text-muted">
          {mode === 'compare'
            ? 'Paired execution keeps both configurations under comparable conditions.'
            : `${sourceLabel(candidateSource)} will be frozen before execution.`}
        </p>
        <Button
          loading={createRun.isPending}
          disabled={!readyToRun}
          onClick={() => void start()}
        >
          <Play className="mr-2 h-4 w-4" />
          {mode === 'compare' ? 'Run Comparison' : 'Run Evaluation'}
        </Button>
      </div>
    </div>
  )
}
