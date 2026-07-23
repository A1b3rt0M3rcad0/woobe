import { useEffect, useMemo, useRef, useState } from 'react'
import {
  AlertTriangle,
  Bot,
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
import {
  useCreateCatalogEvaluationRun,
  useCreatePairedEvaluationComparison,
  usePreviewCatalogEvaluation,
  usePreviewPairedEvaluationComparison,
} from '@/features/evaluations/catalogHooks'
import type {
  CreateCatalogEvaluationInput,
  CreatePairedComparisonInput,
} from '@/features/evaluations/catalogTypes'
import { useEvaluationJudgeModels } from '@/features/evaluations/experienceHooks'
import type {
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
  onComparisonCreated?: (comparisonId: string) => void
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
  if (source === 'staging') return releases.filter((item) => item.status === 'staging')
  if (source === 'release') {
    return releases.filter((item) => (
      item.snapshot_kind === 'release'
      || ['released', 'production', 'rolled_back'].includes(item.status)
    ))
  }
  return []
}

function label(value?: string | null) {
  if (!value) return 'Unknown'
  return value.split('_').map((item) => item.charAt(0).toUpperCase() + item.slice(1)).join(' ')
}

function price(value?: number | null) {
  if (value == null) return 'pricing unknown'
  return `$${value.toFixed(value < 1 ? 4 : 2)}/1M`
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
      <div className="mt-3 flex items-center justify-between rounded-lg border border-border/70 px-3 py-2">
        <div>
          <p className="text-[9px] uppercase text-muted">Exact target</p>
          <p className="mt-1 text-xs font-medium text-white">
            {source === 'draft'
              ? 'Current Draft'
              : selected
                ? `${selected.version} · ${selected.status}`
                : 'Select a snapshot'}
          </p>
        </div>
        {selected ? (
          <span className="text-[10px] text-muted">
            {[selected.provider, selected.model].filter(Boolean).join(' · ')}
          </span>
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
  onComparisonCreated,
  onOpenResult,
  onCreateSuite,
}: Props) {
  const production = releases.find((item) => item.status === 'production')
  const judgeModelsQuery = useEvaluationJudgeModels(projectId)
  const previewSingle = usePreviewCatalogEvaluation(projectId)
  const previewComparison = usePreviewPairedEvaluationComparison(projectId)
  const createRun = useCreateCatalogEvaluationRun(projectId)
  const createComparison = useCreatePairedEvaluationComparison(projectId)
  const [mode, setMode] = useState<SetupMode>('single')
  const [suiteVersionId, setSuiteVersionId] = useState(initialSuiteVersionId || '')
  const [judgeModelId, setJudgeModelId] = useState('')
  const [repetitions, setRepetitions] = useState(1)
  const [candidateSource, setCandidateSource] = useState<EvaluationSourceType>(
    production ? 'release' : 'draft',
  )
  const [candidateVersionId, setCandidateVersionId] = useState(production?.id || '')
  const [referenceSource, setReferenceSource] = useState<EvaluationSourceType>('draft')
  const [referenceVersionId, setReferenceVersionId] = useState('')
  const [acknowledge, setAcknowledge] = useState(false)
  const [approvedHighRiskIds, setApprovedHighRiskIds] = useState<string[]>([])
  const [idempotencyKey, setIdempotencyKey] = useState(() => crypto.randomUUID())
  const lastPreviewKey = useRef('')

  const selectedSuite = suites.find((item) => item.current_version_id === suiteVersionId)
  const eligibleJudgeModels = useMemo(
    () => (judgeModelsQuery.data ?? []).filter((item) => item.eligible),
    [judgeModelsQuery.data],
  )
  const selectedJudge = eligibleJudgeModels.find((item) => item.provider_model_id === judgeModelId)
  const suiteDefaultJudge = eligibleJudgeModels.find(
    (item) => item.provider_model_id === selectedSuite?.judge_provider_model_id,
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

  useEffect(() => {
    if (!selectedSuite || !eligibleJudgeModels.length) {
      setJudgeModelId('')
      return
    }
    const preferred = eligibleJudgeModels.some(
      (item) => item.provider_model_id === selectedSuite.judge_provider_model_id,
    )
      ? selectedSuite.judge_provider_model_id || ''
      : eligibleJudgeModels[0].provider_model_id
    setJudgeModelId(preferred)
  }, [suiteVersionId, selectedSuite?.judge_provider_model_id, eligibleJudgeModels])

  const target = (source: EvaluationSourceType, versionId: string): EvaluationTargetInput => ({
    target_type: 'agent',
    source_type: source,
    entity_id: agentId,
    ...(source !== 'draft' ? { version_id: versionId } : {}),
  })

  const input = useMemo<CreateCatalogEvaluationInput | CreatePairedComparisonInput | null>(() => {
    if (!suiteVersionId || !judgeModelId) return null
    if (candidateSource !== 'draft' && !candidateVersionId) return null
    const candidate = target(candidateSource, candidateVersionId)
    if (mode === 'single') {
      return {
        suite_version_id: suiteVersionId,
        repetitions,
        target: candidate,
        judge_provider_model_id: judgeModelId,
        acknowledge_tool_side_effects: acknowledge,
        approved_high_risk_tool_ids: approvedHighRiskIds,
        idempotency_key: idempotencyKey,
      }
    }
    if (referenceSource !== 'draft' && !referenceVersionId) return null
    return {
      suite_version_id: suiteVersionId,
      repetitions,
      candidate,
      reference: target(referenceSource, referenceVersionId),
      judge_provider_model_id: judgeModelId,
      acknowledge_tool_side_effects: acknowledge,
      approved_high_risk_tool_ids: approvedHighRiskIds,
      idempotency_key: idempotencyKey,
    }
  }, [
    suiteVersionId,
    judgeModelId,
    repetitions,
    candidateSource,
    candidateVersionId,
    referenceSource,
    referenceVersionId,
    mode,
    acknowledge,
    approvedHighRiskIds,
    idempotencyKey,
  ])

  const previewKey = input ? JSON.stringify({ ...input, idempotency_key: undefined }) : ''
  useEffect(() => {
    setAcknowledge(false)
    setApprovedHighRiskIds([])
    lastPreviewKey.current = ''
    previewSingle.reset()
    previewComparison.reset()
  }, [mode, suiteVersionId, judgeModelId, repetitions, candidateSource, candidateVersionId, referenceSource, referenceVersionId])

  useEffect(() => {
    if (!input || previewKey === lastPreviewKey.current) return
    const timer = window.setTimeout(() => {
      lastPreviewKey.current = previewKey
      if (mode === 'single') {
        const { idempotency_key: _ignored, ...payload } = input as CreateCatalogEvaluationInput
        previewSingle.mutate(payload, { onError: () => undefined })
      } else {
        previewComparison.mutate(input as CreatePairedComparisonInput, { onError: () => undefined })
      }
    }, 450)
    return () => window.clearTimeout(timer)
  }, [previewKey, mode])

  const preview = mode === 'single' ? previewSingle : previewComparison
  const previewData = preview.data as any
  const highRiskTools = (previewData?.preflight?.tools || []).filter(
    (tool: any) => tool.risk_level === 'high',
  )
  const highRiskApproved = highRiskTools.every(
    (tool: any) => approvedHighRiskIds.includes(tool.id),
  )
  const needsAcknowledgement = Boolean(previewData?.preflight?.requires_acknowledgement)
  const readyToRun = Boolean(
    input
    && previewData
    && previewData.can_execute !== false
    && highRiskApproved
    && (!needsAcknowledgement || acknowledge),
  )

  const start = async () => {
    if (!input) {
      toast.error('Select an exact target and an eligible Judge Model')
      return
    }
    try {
      if (mode === 'single') {
        const run = await createRun.mutateAsync(input as CreateCatalogEvaluationInput)
        onRunCreated?.(run.id)
        toast.success('Evaluation Run queued with the selected Judge Model.')
      } else {
        const comparison = await createComparison.mutateAsync(input as CreatePairedComparisonInput)
        onComparisonCreated?.(comparison.id)
        toast.success('Two Evaluations were queued with the selected Judge Model.')
      }
      setIdempotencyKey(crypto.randomUUID())
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
          A Suite is the reusable, versioned protocol used to evaluate exact snapshots.
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
            <h3 className="text-base font-semibold text-white">New Evaluation operation</h3>
            <p className="mt-1 text-xs text-muted">
              Evaluate one exact snapshot or create two independent Evaluations and compare them.
            </p>
          </div>
          <div className="flex rounded-lg border border-border bg-background/45 p-1">
            <button
              type="button"
              onClick={() => setMode('single')}
              className={cn('rounded-md px-3 py-2 text-xs font-medium', mode === 'single' ? 'bg-primary/15 text-primary-light' : 'text-muted')}
            >
              Evaluate snapshot
            </button>
            <button
              type="button"
              onClick={() => setMode('compare')}
              className={cn('rounded-md px-3 py-2 text-xs font-medium', mode === 'compare' ? 'bg-primary/15 text-primary-light' : 'text-muted')}
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
            <span>Repetitions per Test Case</span>
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
            {selectedSuite.case_count || 0} Test Cases · Policy score ≥ {String(selectedSuite.acceptance_policy?.minimum_score ?? 70)} · immutable Suite {selectedSuite.current_version}
          </p>
        ) : null}

        <div className="mt-4 rounded-xl border border-primary/20 bg-primary/[0.025] p-4">
          <div className="grid gap-4 md:grid-cols-[minmax(0,1fr)_minmax(0,1.35fr)]">
            <label className="space-y-2 text-xs text-muted">
              <span className="flex items-center gap-2">
                <Bot className="h-3.5 w-3.5 text-primary-light" />
                Judge Model for this Run
              </span>
              <Select
                value={judgeModelId}
                disabled={judgeModelsQuery.isLoading || !eligibleJudgeModels.length}
                onChange={(event) => setJudgeModelId(event.target.value)}
                options={eligibleJudgeModels.map((model) => ({
                  value: model.provider_model_id,
                  label: `${model.display_name} · ${model.provider}`,
                }))}
              />
              {!eligibleJudgeModels.length && !judgeModelsQuery.isLoading ? (
                <p className="text-[10px] text-red-300">No eligible Judge Model is available in this Project.</p>
              ) : null}
            </label>

            {selectedJudge ? (
              <div className="rounded-lg border border-border/70 bg-background/35 px-3 py-3">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p className="truncate text-xs font-semibold text-white">{selectedJudge.display_name}</p>
                    <p className="mt-1 truncate font-mono text-[10px] text-muted">
                      {selectedJudge.provider} · {selectedJudge.model}
                    </p>
                  </div>
                  <Badge variant="outline" className={judgeModelId === selectedSuite?.judge_provider_model_id ? '' : 'border-primary/30 text-primary-light'}>
                    {judgeModelId === selectedSuite?.judge_provider_model_id ? 'Suite default' : 'Run override'}
                  </Badge>
                </div>
                <div className="mt-3 flex flex-wrap gap-2">
                  <Badge variant="outline">{selectedJudge.capabilities.response_strategy}</Badge>
                  <Badge variant="outline">
                    {selectedJudge.budget.effective_initial_tokens.toLocaleString()} → {selectedJudge.budget.effective_retry_tokens.toLocaleString()} tokens
                  </Badge>
                  <Badge variant="outline">Credential: {selectedJudge.credential_name}</Badge>
                </div>
                <p className="mt-3 text-[10px] leading-4 text-muted">
                  Input {price(selectedJudge.pricing.input_cost_per_1m_tokens)} · Output {price(selectedJudge.pricing.output_cost_per_1m_tokens)}. The exact Judge snapshot is frozen into this Run and recorded in Evaluation history.
                </p>
                {suiteDefaultJudge && judgeModelId !== selectedSuite?.judge_provider_model_id ? (
                  <p className="mt-2 text-[10px] text-primary-light">
                    Suite default: {suiteDefaultJudge.display_name}. This override does not mutate the Suite Version.
                  </p>
                ) : null}
              </div>
            ) : (
              <div className="flex min-h-24 items-center justify-center rounded-lg border border-dashed border-border/70 text-xs text-muted">
                Select an eligible Judge Model.
              </div>
            )}
          </div>
        </div>
      </section>

      <div className={cn('grid gap-4', mode === 'compare' && 'lg:grid-cols-2')}>
        <SnapshotSelector
          title={mode === 'compare' ? 'Candidate Evaluation' : 'Target Evaluation'}
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
            title="Reference Evaluation"
            source={referenceSource}
            versionId={referenceVersionId}
            releases={releases}
            onSourceChange={(value) => {
              setReferenceSource(value)
              setReferenceVersionId('')
            }}
            onVersionChange={setReferenceVersionId}
          />
        ) : null}
      </div>

      <section className="rounded-2xl border border-primary/20 bg-primary/[0.035] p-5">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <div className="flex items-center gap-2">
              <Check className="h-4 w-4 text-primary-light" />
              <p className="text-sm font-semibold text-white">Authoritative preflight</p>
            </div>
            <p className="mt-1 text-[11px] text-muted">
              {mode === 'compare'
                ? 'Candidate and Reference become separate Evaluation Runs using the same selected Judge protocol.'
                : 'The exact snapshot, Suite Version and selected Judge identify the durable Evaluation evidence.'}
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            {selectedJudge ? <Badge variant="outline">Judge: {selectedJudge.display_name}</Badge> : null}
            {preview.isPending ? <Badge variant="outline">Calculating…</Badge>
              : previewData ? <Badge variant="outline">Ready</Badge>
                : preview.isError ? <Badge variant="outline">Preflight failed</Badge>
                  : <Badge variant="outline">Complete the setup</Badge>}
          </div>
        </div>
        {preview.isError ? (
          <div className="mt-4 flex items-start gap-2 rounded-lg border border-red-500/20 bg-red-500/[0.05] p-3 text-xs text-red-300">
            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
            {preview.error instanceof Error ? preview.error.message : 'Unable to validate this operation.'}
          </div>
        ) : null}
        {previewData ? (
          <div className="mt-4 grid gap-3 sm:grid-cols-5">
            <div><p className="text-[9px] uppercase text-muted">Evaluations</p><p className="mt-1 text-xl font-semibold text-white">{previewData.operations?.evaluation_runs ?? (mode === 'compare' ? 2 : 1)}</p></div>
            <div><p className="text-[9px] uppercase text-muted">Comparisons</p><p className="mt-1 text-xl font-semibold text-white">{previewData.operations?.comparisons ?? 0}</p></div>
            <div><p className="text-[9px] uppercase text-muted">Test Cases</p><p className="mt-1 text-xl font-semibold text-white">{previewData.case_count}</p></div>
            <div><p className="text-[9px] uppercase text-muted">Target Runs</p><p className="mt-1 text-xl font-semibold text-white">{previewData.target_run_count}</p></div>
            <div><p className="text-[9px] uppercase text-muted">Judge Calls</p><p className="mt-1 text-xl font-semibold text-white">{previewData.judge_call_count}</p></div>
          </div>
        ) : null}
        {highRiskTools.length ? (
          <div className="mt-4 border-t border-primary/15 pt-4">
            <p className="text-xs font-medium text-white">High-risk Tools require explicit approval</p>
            <div className="mt-2 space-y-2">
              {highRiskTools.map((tool: any) => (
                <label key={tool.id} className="flex items-center justify-between gap-3 rounded-lg border border-border/70 bg-background/35 px-3 py-2">
                  <div><p className="text-xs text-white">{tool.name}</p><p className="text-[10px] text-muted">{tool.risk_level} risk</p></div>
                  <input
                    type="checkbox"
                    checked={approvedHighRiskIds.includes(tool.id)}
                    onChange={(event) => setApprovedHighRiskIds((current) => (
                      event.target.checked ? [...new Set([...current, tool.id])] : current.filter((id) => id !== tool.id)
                    ))}
                  />
                </label>
              ))}
            </div>
          </div>
        ) : null}
        {needsAcknowledgement ? (
          <label className="mt-3 flex items-start gap-3 rounded-lg border border-amber-500/20 bg-amber-500/[0.05] p-3 text-xs text-amber-200">
            <input type="checkbox" checked={acknowledge} onChange={(event) => setAcknowledge(event.target.checked)} className="mt-0.5" />
            <span>I understand that these Evaluations execute the real Tools from the selected snapshots.</span>
          </label>
        ) : null}
      </section>

      <div className="flex items-center justify-end border-t border-border pt-4">
        <Button loading={createRun.isPending || createComparison.isPending} disabled={!readyToRun} onClick={() => void start()}>
          <Play className="mr-2 h-4 w-4" />
          {mode === 'compare' ? 'Run paired Comparison' : 'Run Evaluation'}
        </Button>
      </div>

      {activeRuns.length ? (
        <section className="rounded-2xl border border-border/80 bg-background/25 p-4">
          <div className="flex items-center justify-between">
            <div>
              <h4 className="text-sm font-semibold text-white">Active Evaluation Runs</h4>
              <p className="mt-1 text-[11px] text-muted">Runs continue independently while this launcher remains available.</p>
            </div>
            <Badge variant="outline">{activeRuns.length}</Badge>
          </div>
          <div className="mt-3 space-y-2">
            {activeRuns.slice(0, 5).map((run) => {
              const exactTarget = run.targets.find((item) => item.side === 'single') || run.targets[0]
              return (
                <button
                  key={run.id}
                  type="button"
                  onClick={() => onOpenResult?.(run.id)}
                  className="flex w-full items-center gap-3 rounded-xl border border-border/70 bg-surface/20 px-3 py-3 text-left hover:border-primary/30"
                >
                  <Loader2 className="h-4 w-4 animate-spin text-primary-light" />
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-xs font-medium text-white">{exactTarget?.display_name} · {exactTarget?.display_version}</p>
                    <p className="mt-1 text-[10px] text-muted">{label(run.status)} · {run.repetitions} repetitions/case</p>
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
