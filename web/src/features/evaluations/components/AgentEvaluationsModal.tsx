import { useEffect, useMemo, useState } from 'react'
import {
  ArrowLeft,
  Beaker,
  Bot,
  CheckCircle2,
  ChevronRight,
  GitCompareArrows,
  Play,
  Plus,
  RefreshCw,
  ShieldAlert,
  Sparkles,
  XCircle,
} from 'lucide-react'
import { toast } from 'sonner'

import { ErrorState } from '@/components/common/ErrorState'
import { LoadingState } from '@/components/common/LoadingState'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { Dialog } from '@/components/ui/Dialog'
import { Input } from '@/components/ui/Input'
import { Select } from '@/components/ui/Select'
import { useReleases } from '@/features/agents/hooks'
import type { AgentRelease } from '@/features/agents/types'
import {
  useCreateEvaluationDataset,
  useCreateEvaluationRun,
  useCreateEvaluationSuite,
  useEvaluationDatasets,
  useEvaluationRun,
  useEvaluationRuns,
  useEvaluationSuites,
  usePreviewEvaluationRun,
} from '@/features/evaluations/hooks'
import type {
  CreateEvaluationRunInput,
  EvaluationRun,
  EvaluationSourceType,
  EvaluationTargetInput,
} from '@/features/evaluations/types'
import { useProviderModels } from '@/features/provider-models/hooks'
import { cn } from '@/lib/utils'

type Screen = 'run' | 'suites' | 'results' | 'create-suite' | 'result-detail'

type QuestionDraft = {
  name: string
  message: string
  expected: string
  blocking: boolean
  weight: number
}

interface AgentEvaluationsModalProps {
  open: boolean
  onClose: () => void
  projectId: string
  agentId: string
  agentName: string
}

const terminalStatuses = new Set(['completed', 'partially_completed', 'failed', 'cancelled'])

function emptyQuestion(index = 1): QuestionDraft {
  return {
    name: `Question ${index}`,
    message: '',
    expected: '',
    blocking: false,
    weight: 1,
  }
}

function formatStatus(value?: string | null) {
  if (!value) return 'Unknown'
  return value.split('_').map((part) => part.charAt(0).toUpperCase() + part.slice(1)).join(' ')
}

function formatScore(value?: number | null) {
  return value == null ? '—' : value.toFixed(1)
}

function formatCost(value?: number | null) {
  if (value == null) return 'Unknown'
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: value < 0.01 ? 4 : 2,
  }).format(value)
}

function statusClass(status?: string | null) {
  if (status === 'qualified' || status === 'completed') return 'border-emerald-500/30 bg-emerald-500/10 text-emerald-300'
  if (status === 'not_qualified' || status === 'failed') return 'border-red-500/30 bg-red-500/10 text-red-300'
  if (status === 'qualified_with_warnings' || status === 'partially_completed') return 'border-amber-500/30 bg-amber-500/10 text-amber-300'
  return 'border-border bg-background/50 text-muted'
}

function versionOptions(releases: AgentRelease[], source: EvaluationSourceType) {
  if (source === 'staging') {
    return releases.filter((release) => release.status === 'staging')
  }
  if (source === 'release') {
    return releases.filter((release) => (
      release.snapshot_kind === 'release'
      || release.status === 'released'
      || release.status === 'production'
      || release.status === 'rolled_back'
    ))
  }
  return []
}

function runBelongsToAgent(run: EvaluationRun, agentId: string) {
  return run.targets.some((target) => target.target_type === 'agent' && target.entity_id === agentId)
}

export function AgentEvaluationsModal({ open, onClose, projectId, agentId, agentName }: AgentEvaluationsModalProps) {
  const suitesQuery = useEvaluationSuites(projectId)
  const datasetsQuery = useEvaluationDatasets(projectId)
  const runsQuery = useEvaluationRuns(projectId)
  const modelsQuery = useProviderModels(projectId)
  const releasesQuery = useReleases(agentId)
  const createDataset = useCreateEvaluationDataset(projectId)
  const createSuite = useCreateEvaluationSuite(projectId)
  const preview = usePreviewEvaluationRun(projectId)
  const createRun = useCreateEvaluationRun(projectId)

  const [screen, setScreen] = useState<Screen>('run')
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null)
  const selectedRunQuery = useEvaluationRun(projectId, selectedRunId)

  const [suiteVersionId, setSuiteVersionId] = useState('')
  const [sourceType, setSourceType] = useState<EvaluationSourceType>('draft')
  const [versionId, setVersionId] = useState('')
  const [repetitions, setRepetitions] = useState(3)
  const [compare, setCompare] = useState(false)
  const [baselineSource, setBaselineSource] = useState<EvaluationSourceType>('release')
  const [baselineVersionId, setBaselineVersionId] = useState('')
  const [acknowledge, setAcknowledge] = useState(false)
  const [approvedHighRiskIds, setApprovedHighRiskIds] = useState<string[]>([])
  const [idempotencyKey, setIdempotencyKey] = useState(() => crypto.randomUUID())

  const [suiteName, setSuiteName] = useState('')
  const [suiteDescription, setSuiteDescription] = useState('')
  const [judgeModelId, setJudgeModelId] = useState('')
  const [minimumScore, setMinimumScore] = useState(70)
  const [minimumPassRate, setMinimumPassRate] = useState(80)
  const [defaultRepetitions, setDefaultRepetitions] = useState(3)
  const [questions, setQuestions] = useState<QuestionDraft[]>([emptyQuestion()])

  const suites = useMemo(
    () => (suitesQuery.data ?? []).filter((suite) => suite.target_type === 'agent' && suite.current_version_id),
    [suitesQuery.data],
  )
  const datasets = datasetsQuery.data ?? []
  const releases = releasesQuery.data ?? []
  const recentRuns = useMemo(
    () => (runsQuery.data ?? []).filter((run) => runBelongsToAgent(run, agentId)),
    [agentId, runsQuery.data],
  )
  const candidateVersions = versionOptions(releases, sourceType)
  const baselineVersions = versionOptions(releases, baselineSource)
  const selectedSuite = suites.find((suite) => suite.current_version_id === suiteVersionId)

  useEffect(() => {
    if (!open) return
    setScreen('run')
    setSelectedRunId(null)
    setSourceType('draft')
    setVersionId('')
    setCompare(false)
    setBaselineSource('release')
    setBaselineVersionId(releases.find((release) => release.status === 'production')?.id ?? '')
    setAcknowledge(false)
    setApprovedHighRiskIds([])
    setIdempotencyKey(crypto.randomUUID())
    preview.reset()
  }, [open])

  useEffect(() => {
    if (!selectedSuite) return
    setRepetitions(Number(selectedSuite.repetition_policy?.default_repetitions ?? 3))
  }, [selectedSuite?.id])

  const resetPreview = () => {
    preview.reset()
    setAcknowledge(false)
    setApprovedHighRiskIds([])
  }

  const buildRunInput = (): CreateEvaluationRunInput => {
    const candidate: EvaluationTargetInput = {
      target_type: 'agent',
      source_type: sourceType,
      entity_id: agentId,
    }
    if (sourceType !== 'draft' && versionId) candidate.version_id = versionId

    let baseline: EvaluationTargetInput | undefined
    if (compare) {
      baseline = {
        target_type: 'agent',
        source_type: baselineSource,
        entity_id: agentId,
      }
      if (baselineSource !== 'draft' && baselineVersionId) baseline.version_id = baselineVersionId
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

  const previewRun = async () => {
    try {
      await preview.mutateAsync(buildRunInput())
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Unable to preview Evaluation')
    }
  }

  const startRun = async () => {
    try {
      const run = await createRun.mutateAsync(buildRunInput())
      toast.success('Evaluation Run queued')
      setSelectedRunId(run.id)
      setScreen('result-detail')
      setIdempotencyKey(crypto.randomUUID())
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Unable to start Evaluation')
    }
  }

  const saveSuite = async () => {
    if (!suiteName.trim()) return toast.error('Evaluator Suite name is required')
    if (!judgeModelId) return toast.error('Choose the LLM judge model')
    if (questions.some((question) => !question.message.trim() || !question.expected.trim())) {
      return toast.error('Every question needs an input and expected result')
    }

    try {
      const dataset = await createDataset.mutateAsync({
        name: `${suiteName.trim()} · Questions`,
        description: suiteDescription.trim() || `Question set managed by ${suiteName.trim()}`,
        change_description: 'Initial Evaluator Suite question set',
        cases: questions.map((question) => ({
          name: question.name.trim() || 'Question',
          message: question.message.trim(),
          expected_contract: {
            semantic_criteria: [question.expected.trim()],
            output_contract: { required: true },
          },
          severity: question.blocking ? 'critical' : 'normal',
          weight: question.weight,
          blocking: question.blocking,
        })),
      })
      if (!dataset.current_version_id) throw new Error('Question set version was not created')

      const suite = await createSuite.mutateAsync({
        name: suiteName.trim(),
        description: suiteDescription.trim(),
        target_type: 'agent',
        dataset_version_id: dataset.current_version_id,
        judge_provider_model_id: judgeModelId,
        judge_config: { temperature: 0, max_tokens: 1600, timeout_seconds: 90 },
        rubric: {
          criteria: ['Correctness', 'Relevance', 'Completeness', 'Expected behavior'],
          judge_weight: 4,
        },
        deterministic_checks: { enabled: true },
        acceptance_policy: {
          minimum_score: minimumScore,
          minimum_pass_rate: minimumPassRate,
          minimum_paired_n: Math.max(1, defaultRepetitions),
          maximum_score_regression: 0,
        },
        repetition_policy: {
          default_repetitions: defaultRepetitions,
          maximum_repetitions: 25,
        },
        estimate_defaults: { volume: 10000 },
      })

      setSuiteVersionId(suite.current_version_id ?? '')
      setRepetitions(defaultRepetitions)
      setSuiteName('')
      setSuiteDescription('')
      setQuestions([emptyQuestion()])
      toast.success('Evaluator Suite created')
      setScreen('run')
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Failed to create Evaluator Suite')
    }
  }

  const highRiskTools = preview.data?.preflight.tools.filter((tool) => tool.risk_level === 'high') ?? []
  const highRiskApproved = highRiskTools.every((tool) => approvedHighRiskIds.includes(tool.id))
  const needsAcknowledgement = preview.data?.preflight.requires_acknowledgement ?? false
  const readyToStart = Boolean(preview.data)
    && highRiskApproved
    && (!needsAcknowledgement || acknowledge)
  const targetReady = sourceType === 'draft' || Boolean(versionId)
  const baselineReady = !compare || baselineSource === 'draft' || Boolean(baselineVersionId)

  const patchQuestion = (index: number, values: Partial<QuestionDraft>) => {
    setQuestions((current) => current.map((question, position) => (
      position === index ? { ...question, ...values } : question
    )))
  }

  const selectedRun = selectedRunQuery.data
  const loading = suitesQuery.isLoading || datasetsQuery.isLoading || runsQuery.isLoading || releasesQuery.isLoading
  const failed = suitesQuery.isError || datasetsQuery.isError || runsQuery.isError || releasesQuery.isError

  return (
    <Dialog open={open} onClose={onClose} title="Evaluate Agent" className="max-w-6xl overflow-hidden bg-surface/95">
      <div className="-m-6 flex max-h-[82vh] min-h-[640px] flex-col overflow-hidden">
        <div className="flex shrink-0 items-center justify-between gap-4 border-b border-border/80 px-5 py-4">
          <div className="flex min-w-0 items-center gap-3">
            {(screen === 'create-suite' || screen === 'result-detail') ? (
              <button
                type="button"
                onClick={() => setScreen(screen === 'create-suite' ? 'suites' : 'results')}
                className="flex h-8 w-8 items-center justify-center rounded-lg border border-border text-muted hover:text-white"
              >
                <ArrowLeft className="h-4 w-4" />
              </button>
            ) : null}
            <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl border border-primary/20 bg-primary/10 text-primary-light">
              <Bot className="h-4 w-4" />
            </div>
            <div className="min-w-0">
              <p className="truncate text-sm font-semibold text-white">{agentName}</p>
              <p className="text-[11px] text-muted">Evaluate Draft, Staging or an immutable Release without leaving the Playground.</p>
            </div>
          </div>
          {(screen === 'run' || screen === 'suites' || screen === 'results') ? (
            <div className="flex rounded-lg border border-border bg-background/45 p-1">
              {([
                ['run', 'Run'],
                ['suites', 'Evaluator Suites'],
                ['results', 'Results'],
              ] as const).map(([value, label]) => (
                <button
                  key={value}
                  type="button"
                  onClick={() => setScreen(value)}
                  className={cn(
                    'rounded-md px-3 py-1.5 text-xs font-medium transition-colors',
                    screen === value ? 'bg-primary/15 text-primary-light' : 'text-muted hover:text-white',
                  )}
                >
                  {label}
                </button>
              ))}
            </div>
          ) : null}
        </div>

        <div className="scrollbar-thin min-h-0 flex-1 overflow-y-auto p-5">
          {loading ? <LoadingState message="Loading Evaluations" /> : failed ? (
            <ErrorState message="Unable to load Agent Evaluations" />
          ) : screen === 'run' ? (
            <div className="mx-auto max-w-4xl space-y-5">
              {!suites.length ? (
                <div className="rounded-xl border border-dashed border-border p-10 text-center">
                  <Beaker className="mx-auto h-8 w-8 text-muted" />
                  <h3 className="mt-3 text-sm font-semibold text-white">Create your first Evaluator Suite</h3>
                  <p className="mx-auto mt-2 max-w-lg text-xs leading-5 text-muted">A Suite contains the questions, expected results, LLM judge and acceptance policy used to grade this Agent.</p>
                  <Button className="mt-4" onClick={() => setScreen('create-suite')}><Plus className="mr-2 h-4 w-4" />Create Evaluator Suite</Button>
                </div>
              ) : (
                <>
                  <section className="rounded-xl border border-border/80 bg-background/35 p-4">
                    <div className="grid gap-4 md:grid-cols-[minmax(0,1fr)_180px]">
                      <label className="space-y-2 text-xs text-muted">
                        <span>Evaluator Suite</span>
                        <Select
                          value={suiteVersionId}
                          onChange={(event) => { setSuiteVersionId(event.target.value); resetPreview() }}
                          options={[
                            { value: '', label: 'Select a Suite' },
                            ...suites.map((suite) => ({ value: suite.current_version_id as string, label: `${suite.name} · ${suite.current_version}` })),
                          ]}
                        />
                      </label>
                      <label className="space-y-2 text-xs text-muted">
                        <span>Runs per question</span>
                        <Input
                          type="number"
                          min={1}
                          max={25}
                          value={repetitions}
                          onChange={(event) => { setRepetitions(Math.max(1, Math.min(25, Number(event.target.value)))); resetPreview() }}
                        />
                      </label>
                    </div>
                    {selectedSuite ? <p className="mt-3 text-[11px] leading-5 text-muted">{selectedSuite.description || 'Versioned questions and acceptance criteria.'}</p> : null}
                  </section>

                  <section className="rounded-xl border border-border/80 bg-background/35 p-4">
                    <div className="flex items-center gap-2"><Sparkles className="h-4 w-4 text-primary-light" /><div><p className="text-sm font-semibold text-white">Candidate snapshot</p><p className="text-[11px] text-muted">The Agent version that will answer every question.</p></div></div>
                    <div className="mt-4 grid gap-4 md:grid-cols-2">
                      <label className="space-y-2 text-xs text-muted"><span>Environment</span><Select value={sourceType} onChange={(event) => { setSourceType(event.target.value as EvaluationSourceType); setVersionId(''); resetPreview() }} options={[{ value: 'draft', label: 'Current Draft' }, { value: 'staging', label: 'Staging' }, { value: 'release', label: 'Release / Production' }]} /></label>
                      <label className="space-y-2 text-xs text-muted"><span>Exact snapshot</span><Select disabled={sourceType === 'draft'} value={versionId} onChange={(event) => { setVersionId(event.target.value); resetPreview() }} options={[{ value: '', label: sourceType === 'draft' ? 'Current Draft will be frozen' : 'Select exact snapshot' }, ...candidateVersions.map((release) => ({ value: release.id, label: `${release.version} · ${formatStatus(release.status)}` }))]} /></label>
                    </div>
                  </section>

                  <section className="rounded-xl border border-border/80 bg-background/35 p-4">
                    <div className="flex items-center justify-between gap-4"><div><div className="flex items-center gap-2"><GitCompareArrows className="h-4 w-4 text-primary-light" /><p className="text-sm font-semibold text-white">Compare with a Baseline</p></div><p className="mt-1 text-[11px] text-muted">Optional paired execution against another snapshot.</p></div><button type="button" onClick={() => { setCompare((value) => !value); resetPreview() }} className={cn('rounded-lg border px-3 py-2 text-xs font-medium', compare ? 'border-primary/30 bg-primary/10 text-primary-light' : 'border-border text-muted')}>{compare ? 'Enabled' : 'Disabled'}</button></div>
                    {compare ? <div className="mt-4 grid gap-4 md:grid-cols-2"><label className="space-y-2 text-xs text-muted"><span>Baseline environment</span><Select value={baselineSource} onChange={(event) => { setBaselineSource(event.target.value as EvaluationSourceType); setBaselineVersionId(''); resetPreview() }} options={[{ value: 'release', label: 'Release / Production' }, { value: 'staging', label: 'Staging' }, { value: 'draft', label: 'Current Draft' }]} /></label><label className="space-y-2 text-xs text-muted"><span>Exact baseline</span><Select disabled={baselineSource === 'draft'} value={baselineVersionId} onChange={(event) => { setBaselineVersionId(event.target.value); resetPreview() }} options={[{ value: '', label: baselineSource === 'draft' ? 'Current Draft will be frozen' : 'Select exact snapshot' }, ...baselineVersions.map((release) => ({ value: release.id, label: `${release.version} · ${formatStatus(release.status)}` }))]} /></label></div> : null}
                  </section>

                  {preview.data ? (
                    <section className="rounded-xl border border-primary/25 bg-primary/[0.05] p-4">
                      <div className="grid gap-3 sm:grid-cols-3">
                        <div><p className="text-[10px] uppercase tracking-wide text-muted">Questions</p><p className="mt-1 text-xl font-semibold text-white">{preview.data.case_count}</p></div>
                        <div><p className="text-[10px] uppercase tracking-wide text-muted">Agent Runs</p><p className="mt-1 text-xl font-semibold text-white">{preview.data.target_run_count}</p></div>
                        <div><p className="text-[10px] uppercase tracking-wide text-muted">Judge calls</p><p className="mt-1 text-xl font-semibold text-white">{preview.data.judge_call_count}</p></div>
                      </div>
                      <div className="mt-4 border-t border-primary/15 pt-4">
                        <div className="flex items-center gap-2"><ShieldAlert className="h-4 w-4 text-amber-300" /><p className="text-xs font-semibold text-white">Tool execution preflight</p></div>
                        <div className="mt-3 space-y-2">
                          {preview.data.preflight.tools.length ? preview.data.preflight.tools.map((tool) => (
                            <label key={tool.id} className="flex items-center justify-between gap-3 rounded-lg border border-border/80 bg-background/45 px-3 py-2">
                              <div><p className="text-xs font-medium text-white">{tool.name}</p><p className="mt-1 text-[10px] text-muted">{tool.source} · {tool.risk_level} risk</p></div>
                              {tool.risk_level === 'high' ? <span className="flex items-center gap-2 text-[10px] text-red-300"><input type="checkbox" checked={approvedHighRiskIds.includes(tool.id)} onChange={(event) => setApprovedHighRiskIds((current) => event.target.checked ? [...new Set([...current, tool.id])] : current.filter((id) => id !== tool.id))} />Explicit approval</span> : null}
                            </label>
                          )) : <p className="text-xs text-muted">No Tools detected in the selected snapshots.</p>}
                        </div>
                        {needsAcknowledgement ? <label className="mt-4 flex items-start gap-3 rounded-lg border border-amber-500/20 bg-amber-500/[0.06] p-3 text-xs text-amber-200"><input type="checkbox" checked={acknowledge} onChange={(event) => setAcknowledge(event.target.checked)} className="mt-0.5" /><span>I understand that this Evaluation executes the real Tools shown above and can produce external side effects.</span></label> : null}
                      </div>
                    </section>
                  ) : null}

                  <div className="flex justify-end gap-2 border-t border-border pt-4">
                    <Button variant="outline" loading={preview.isPending} disabled={!suiteVersionId || !targetReady || !baselineReady} onClick={() => void previewRun()}>Preview workload</Button>
                    <Button loading={createRun.isPending} disabled={!readyToStart} onClick={() => void startRun()}><Play className="mr-2 h-4 w-4" />Start Evaluation</Button>
                  </div>
                </>
              )}
            </div>
          ) : screen === 'suites' ? (
            <div className="mx-auto max-w-5xl">
              <div className="mb-4 flex items-center justify-between gap-4"><div><h3 className="text-sm font-semibold text-white">Evaluator Suites</h3><p className="mt-1 text-xs text-muted">Reusable, versioned question sets and grading policies.</p></div><Button onClick={() => setScreen('create-suite')}><Plus className="mr-2 h-4 w-4" />New Suite</Button></div>
              {suites.length ? <div className="grid gap-3 md:grid-cols-2">{suites.map((suite) => { const dataset = datasets.find((item) => item.current_version_id === suite.dataset_version_id); return <article key={suite.id} className="rounded-xl border border-border/80 bg-background/40 p-4"><div className="flex items-start justify-between gap-4"><div><h4 className="text-sm font-semibold text-white">{suite.name}</h4><p className="mt-1 text-xs leading-5 text-muted">{suite.description || 'No description'}</p></div><Badge variant="outline">{suite.current_version}</Badge></div><div className="mt-4 grid grid-cols-3 gap-3 border-t border-border pt-3 text-xs"><div><p className="text-[9px] uppercase tracking-wide text-muted">Questions</p><p className="mt-1 text-white">{dataset?.case_count ?? '—'}</p></div><div><p className="text-[9px] uppercase tracking-wide text-muted">Minimum score</p><p className="mt-1 text-white">{String(suite.acceptance_policy?.minimum_score ?? 70)}</p></div><div><p className="text-[9px] uppercase tracking-wide text-muted">Default runs</p><p className="mt-1 text-white">{String(suite.repetition_policy?.default_repetitions ?? 3)}</p></div></div><div className="mt-4 flex justify-end"><Button size="sm" onClick={() => { setSuiteVersionId(suite.current_version_id as string); setScreen('run') }}>Use Suite</Button></div></article> })}</div> : <div className="rounded-xl border border-dashed border-border p-10 text-center text-sm text-muted">No Evaluator Suites configured for Agents.</div>}
            </div>
          ) : screen === 'create-suite' ? (
            <div className="mx-auto max-w-4xl space-y-5">
              <div><h3 className="text-base font-semibold text-white">Create Evaluator Suite</h3><p className="mt-1 text-xs leading-5 text-muted">Define the questions, expected results, judge model and acceptance threshold in one workflow.</p></div>
              <div className="grid gap-4 md:grid-cols-2"><label className="space-y-2 text-xs text-muted"><span>Name</span><Input value={suiteName} onChange={(event) => setSuiteName(event.target.value)} placeholder="Customer support quality" /></label><label className="space-y-2 text-xs text-muted"><span>LLM judge</span><Select value={judgeModelId} onChange={(event) => setJudgeModelId(event.target.value)} options={[{ value: '', label: 'Select a BYOK model' }, ...(modelsQuery.data ?? []).filter((model) => model.status === 'active').map((model) => ({ value: model.id, label: `${model.name} · ${model.model}` }))]} /></label></div>
              <label className="block space-y-2 text-xs text-muted"><span>Description</span><Input value={suiteDescription} onChange={(event) => setSuiteDescription(event.target.value)} placeholder="Critical behaviors that must remain stable before promotion" /></label>
              <section><div className="mb-3 flex items-center justify-between"><div><p className="text-sm font-semibold text-white">Questions and expected results</p><p className="mt-1 text-[11px] text-muted">Each question is executed independently and graded by the selected LLM.</p></div><Button size="sm" variant="outline" onClick={() => setQuestions((current) => [...current, emptyQuestion(current.length + 1)])}><Plus className="mr-1 h-3.5 w-3.5" />Add question</Button></div><div className="space-y-3">{questions.map((question, index) => <article key={index} className="rounded-xl border border-border/80 bg-background/35 p-4"><div className="flex items-center justify-between gap-3"><Input value={question.name} onChange={(event) => patchQuestion(index, { name: event.target.value })} className="max-w-sm" /><Button size="sm" variant="ghost" disabled={questions.length === 1} onClick={() => setQuestions((current) => current.filter((_, position) => position !== index))}>Remove</Button></div><div className="mt-3 grid gap-3 md:grid-cols-2"><label className="space-y-2 text-xs text-muted"><span>Question sent to the Agent</span><textarea value={question.message} onChange={(event) => patchQuestion(index, { message: event.target.value })} className="min-h-28 w-full rounded-lg border border-border bg-background px-3 py-2 text-sm text-white outline-none focus:border-primary/50" /></label><label className="space-y-2 text-xs text-muted"><span>Expected result / grading criteria</span><textarea value={question.expected} onChange={(event) => patchQuestion(index, { expected: event.target.value })} className="min-h-28 w-full rounded-lg border border-border bg-background px-3 py-2 text-sm text-white outline-none focus:border-primary/50" /></label></div><div className="mt-3 flex flex-wrap items-center gap-4"><label className="flex items-center gap-2 text-xs text-muted"><input type="checkbox" checked={question.blocking} onChange={(event) => patchQuestion(index, { blocking: event.target.checked })} />Blocking question</label><label className="flex items-center gap-2 text-xs text-muted"><span>Weight</span><Input type="number" min={0.1} max={100} step={0.1} value={question.weight} onChange={(event) => patchQuestion(index, { weight: Math.max(0.1, Number(event.target.value)) })} className="w-24" /></label></div></article>)}</div></section>
              <section className="rounded-xl border border-border/80 bg-background/35 p-4"><p className="text-sm font-semibold text-white">Acceptance policy</p><div className="mt-3 grid gap-4 sm:grid-cols-3"><label className="space-y-2 text-xs text-muted"><span>Minimum score</span><Input type="number" min={0} max={100} value={minimumScore} onChange={(event) => setMinimumScore(Number(event.target.value))} /></label><label className="space-y-2 text-xs text-muted"><span>Minimum pass rate</span><Input type="number" min={0} max={100} value={minimumPassRate} onChange={(event) => setMinimumPassRate(Number(event.target.value))} /></label><label className="space-y-2 text-xs text-muted"><span>Default runs / question</span><Input type="number" min={1} max={25} value={defaultRepetitions} onChange={(event) => setDefaultRepetitions(Math.max(1, Math.min(25, Number(event.target.value))))} /></label></div></section>
              <div className="flex justify-end gap-2 border-t border-border pt-4"><Button variant="outline" onClick={() => setScreen('suites')}>Cancel</Button><Button loading={createDataset.isPending || createSuite.isPending} onClick={() => void saveSuite()}><Sparkles className="mr-2 h-4 w-4" />Create Evaluator Suite</Button></div>
            </div>
          ) : screen === 'results' ? (
            <div className="mx-auto max-w-5xl"><div className="mb-4"><h3 className="text-sm font-semibold text-white">Agent Evaluation Results</h3><p className="mt-1 text-xs text-muted">Runs remain associated with the exact evaluated snapshot.</p></div>{recentRuns.length ? <div className="space-y-2">{recentRuns.map((run) => { const target = run.targets.find((item) => item.side === 'candidate' || item.side === 'single'); const active = !terminalStatuses.has(run.status); return <button key={run.id} type="button" onClick={() => { setSelectedRunId(run.id); setScreen('result-detail') }} className="flex w-full items-center gap-4 rounded-xl border border-border/80 bg-background/40 p-4 text-left hover:border-primary/30"><div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-border bg-surface"><Beaker className="h-4 w-4 text-primary-light" /></div><div className="min-w-0 flex-1"><div className="flex flex-wrap items-center gap-2"><p className="text-sm font-semibold text-white">{target?.display_version ?? 'Agent snapshot'}</p><Badge variant="outline" className={statusClass(run.qualification_status ?? run.status)}>{formatStatus(run.qualification_status ?? run.status)}</Badge>{active ? <RefreshCw className="h-3.5 w-3.5 animate-spin text-primary-light" /> : null}</div><p className="mt-1 text-[11px] text-muted">{run.repetitions} runs per question · {run.mode}</p></div><div className="grid grid-cols-2 gap-5 text-right"><div><p className="text-[9px] uppercase tracking-wide text-muted">Score</p><p className="mt-1 text-sm font-semibold text-white">{formatScore(run.overall_score)}</p></div><div><p className="text-[9px] uppercase tracking-wide text-muted">Cost</p><p className="mt-1 text-sm font-semibold text-white">{formatCost(run.measured_total_cost)}</p></div></div><ChevronRight className="h-4 w-4 text-muted" /></button> })}</div> : <div className="rounded-xl border border-dashed border-border p-10 text-center text-sm text-muted">No Evaluations have been run for this Agent.</div>}</div>
          ) : (
            <div className="mx-auto max-w-5xl">
              {selectedRunQuery.isLoading ? <LoadingState message="Loading Evaluation Result" /> : selectedRunQuery.isError || !selectedRun ? <ErrorState message="Unable to load Evaluation Result" /> : <div className="space-y-5"><section className="rounded-xl border border-border/80 bg-background/40 p-5"><div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between"><div><div className="flex flex-wrap items-center gap-2"><Badge variant="outline" className={statusClass(selectedRun.qualification_status ?? selectedRun.status)}>{formatStatus(selectedRun.qualification_status ?? selectedRun.status)}</Badge>{!terminalStatuses.has(selectedRun.status) ? <RefreshCw className="h-3.5 w-3.5 animate-spin text-primary-light" /> : null}</div><h3 className="mt-3 text-base font-semibold text-white">{selectedRun.targets.find((target) => target.side === 'candidate' || target.side === 'single')?.display_version ?? 'Agent Evaluation'}</h3><p className="mt-1 text-xs text-muted">{selectedRun.repetitions} runs per question · {selectedRun.mode}</p></div><div className="grid grid-cols-3 gap-5"><div><p className="text-[9px] uppercase tracking-wide text-muted">Score</p><p className="mt-1 text-lg font-semibold text-white">{formatScore(selectedRun.overall_score)}</p></div><div><p className="text-[9px] uppercase tracking-wide text-muted">Pass rate</p><p className="mt-1 text-lg font-semibold text-white">{selectedRun.pass_rate == null ? '—' : `${selectedRun.pass_rate.toFixed(1)}%`}</p></div><div><p className="text-[9px] uppercase tracking-wide text-muted">Cost</p><p className="mt-1 text-sm font-semibold text-white">{formatCost(selectedRun.measured_total_cost)}</p></div></div></div></section><section><div className="mb-3"><p className="text-sm font-semibold text-white">Question results</p><p className="mt-1 text-[11px] text-muted">Each row is one Agent Run judged against its expected result.</p></div><div className="space-y-2">{(selectedRun.trials ?? []).map((trial) => <article key={trial.id} className="rounded-xl border border-border/80 bg-background/35 p-4"><div className="flex items-start justify-between gap-4"><div className="min-w-0"><div className="flex items-center gap-2">{trial.passed === true ? <CheckCircle2 className="h-4 w-4 text-emerald-300" /> : trial.passed === false ? <XCircle className="h-4 w-4 text-red-300" /> : <RefreshCw className="h-4 w-4 text-muted" />}<p className="text-sm font-semibold text-white">{trial.case?.name ?? trial.pair_key}</p><Badge variant="outline">Run {trial.repetition}</Badge></div><p className="mt-2 text-xs leading-5 text-muted">{String(trial.case?.input_payload?.message ?? '')}</p></div><div className="text-right"><p className="text-lg font-semibold text-white">{formatScore(trial.score)}</p><p className="text-[10px] text-muted">{formatStatus(trial.status)}</p></div></div>{trial.failure_detail ? <p className="mt-3 rounded-lg border border-red-500/20 bg-red-500/[0.05] p-3 text-xs text-red-300">{trial.failure_detail}</p> : null}</article>)}</div></section></div>}
            </div>
          )}
        </div>
      </div>
    </Dialog>
  )
}
