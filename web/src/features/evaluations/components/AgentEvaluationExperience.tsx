import { useEffect, useRef, useState } from 'react'
import type { ReactNode } from 'react'
import {
  AlertTriangle,
  Beaker,
  Check,
  ChevronDown,
  FlaskConical,
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
type ComparisonType = 'model_experiment' | 'snapshots'

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

function releaseModelLabel(release: AgentRelease | undefined, models: ProviderModel[]) {
  if (!release) return 'Model unavailable'
  const configured = models.find((model) => model.id === release.provider_model_id)
  if (configured) return modelLabel(configured)
  if (release.provider || release.model) {
    return [release.provider, release.model].filter(Boolean).join(' · ')
  }
  return 'Configured model'
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
  const [comparisonType, setComparisonType] = useState<ComparisonType>('model_experiment')
  const [suiteVersionId, setSuiteVersionId] = useState(initialSuiteVersionId || '')
  const [repetitions, setRepetitions] = useState(3)
  const [candidateSource, setCandidateSource] = useState<EvaluationSourceType>('draft')
  const [candidateVersionId, setCandidateVersionId] = useState('')
  const [baselineSource, setBaselineSource] = useState<EvaluationSourceType>('release')
  const [baselineVersionId, setBaselineVersionId] = useState('')
  const [experimentalModelId, setExperimentalModelId] = useState('')
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
  const candidateVersions = versionsFor(releases, candidateSource)
  const baselineVersions = versionsFor(releases, baselineSource)
  const referenceRelease = candidateSource === 'draft'
    ? draft
    : releases.find((item) => item.id === candidateVersionId)
  const referenceProviderModelId = referenceRelease?.provider_model_id || ''
  const experimentalModels = activeModels.filter(
    (item) => item.id !== referenceProviderModelId,
  )
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
    if (!baselineVersionId && production?.id) {
      setBaselineVersionId(production.id)
    }
  }, [baselineVersionId, production?.id])

  useEffect(() => {
    if (
      !experimentalModelId
      || experimentalModelId === referenceProviderModelId
      || !experimentalModels.some((model) => model.id === experimentalModelId)
    ) {
      setExperimentalModelId(experimentalModels[0]?.id || '')
    }
  }, [experimentalModelId, referenceProviderModelId, experimentalModels])

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

    if (mode === 'compare' && comparisonType === 'model_experiment') {
      if (!experimentalModelId || experimentalModelId === referenceProviderModelId) {
        return null
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
          provider_model_id: experimentalModelId,
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
    experimentalModelId,
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
  const isModelExperiment = (
    mode === 'compare' && comparisonType === 'model_experiment'
  )
  const judgeMatchesExperiment = Boolean(
    isModelExperiment
    && selectedSuite?.judge_provider_model_id
    && [referenceProviderModelId, experimentalModelId].includes(
      selectedSuite.judge_provider_model_id,
    )
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
        run.mode === 'model_experiment'
          ? 'Model experiment queued'
          : run.mode === 'comparison'
            ? 'Comparison queued'
            : 'Evaluation queued',
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
          A Suite is the reusable, versioned set of Test Cases used by Evaluations
          and model experiments.
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
            description="Evaluate the exact current Agent configuration."
            onClick={() => setMode('quick')}
          />
          <ModeButton
            active={mode === 'compare'}
            icon={<GitCompareArrows className="h-4 w-4" />}
            title="Compare"
            description="Compare real snapshots or run a clearly marked model experiment."
            onClick={() => setMode('compare')}
          />
          <ModeButton
            active={mode === 'advanced'}
            icon={<Settings2 className="h-4 w-4" />}
            title="Advanced"
            description="Evaluate an exact Draft, Staging or Release snapshot."
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
              onClick={() => setComparisonType('model_experiment')}
              className={cn(
                'flex-1 rounded-md px-3 py-2 text-xs font-medium',
                comparisonType === 'model_experiment'
                  ? 'bg-primary/15 text-primary-light'
                  : 'text-muted',
              )}
            >
              Model experiment
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
              Snapshot comparison
            </button>
          </div>

          {comparisonType === 'model_experiment' ? (
            <div className="mt-4 space-y-4">
              <div className="grid gap-3 md:grid-cols-2">
                <div className="rounded-xl border border-emerald-500/20 bg-emerald-500/[0.04] p-4">
                  <div className="flex items-center gap-2">
                    <Check className="h-4 w-4 text-emerald-300" />
                    <p className="text-xs font-semibold text-white">Current Agent</p>
                  </div>
                  <p className="mt-2 text-sm text-white">
                    {releaseModelLabel(referenceRelease, activeModels)}
                  </p>
                  <p className="mt-1 text-[10px] text-muted">
                    Exact {sourceLabel(candidateSource)} snapshot · no override
                  </p>
                </div>
                <label className="rounded-xl border border-primary/20 bg-primary/[0.04] p-4 text-xs text-muted">
                  <span className="flex items-center gap-2 font-semibold text-white">
                    <FlaskConical className="h-4 w-4 text-primary-light" />
                    Experimental model
                  </span>
                  <Select
                    className="mt-3"
                    value={experimentalModelId}
                    onChange={(event) => setExperimentalModelId(event.target.value)}
                    options={[
                      { value: '', label: 'Select an alternative model' },
                      ...experimentalModels.map((item) => ({
                        value: item.id,
                        label: modelLabel(item),
                      })),
                    ]}
                  />
                </label>
              </div>

              <div className="flex items-start gap-2 rounded-lg border border-amber-500/25 bg-amber-500/[0.06] p-3 text-xs text-amber-200">
                <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
                <span>
                  This changes only the model on the experimental side. It does not
                  represent the deployed Agent and cannot qualify Draft, Staging or
                  any Release. The real Agent side always uses its configured model.
                </span>
              </div>

              {judgeMatchesExperiment ? (
                <div className="flex items-start gap-2 rounded-lg border border-amber-500/20 bg-amber-500/[0.04] p-3 text-xs text-amber-200">
                  <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
                  The Suite Judge uses the reference or experimental model. This is
                  allowed, but can introduce evaluation bias.
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

      {mode === 'advanced' || isModelExperiment ? (
        <section className="rounded-2xl border border-border/80 bg-background/35 p-5">
          <button
            type="button"
            onClick={() => setAdvancedOpen((value) => !value)}
            className="flex w-full items-center justify-between text-left"
          >
            <div>
              <p className="text-sm font-semibold text-white">Advanced settings</p>
              <p className="mt-1 text-[11px] text-muted">
                Select the exact real Agent snapshot used as the reference.
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
                <span>Reference environment</span>
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
                <span>Exact reference snapshot</span>
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
                Agent output limits remain unchanged because they belong to the
                reference snapshot. Only the experimental target changes model.
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
            <Badge variant="outline">
              {previewData.mode === 'model_experiment'
                ? 'Experiment · no qualification'
                : 'Ready'}
            </Badge>
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
                  I understand that this operation executes the real Tools shown
                  above and may produce external side effects.
                </span>
              </label>
            ) : null}
          </div>
        ) : null}
      </section>

      <div className="flex items-center justify-between border-t border-border pt-4">
        <p className="text-[11px] text-muted">
          {isModelExperiment
            ? 'Current Agent remains exact; only the experimental side changes model.'
            : mode === 'compare'
              ? 'Both immutable snapshots remain qualification-eligible evidence.'
              : `${sourceLabel(candidateSource)} will be frozen before execution.`}
        </p>
        <Button
          loading={createRun.isPending}
          disabled={!readyToRun}
          onClick={() => void start()}
        >
          <Play className="mr-2 h-4 w-4" />
          {isModelExperiment
            ? 'Run Model Experiment'
            : mode === 'compare'
              ? 'Run Comparison'
              : 'Run Evaluation'}
        </Button>
      </div>
    </div>
  )
}
