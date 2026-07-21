import { useEffect, useMemo, useState } from 'react'
import {
  AlertTriangle,
  ArrowLeft,
  Braces,
  CheckCircle2,
  FileJson,
  Loader2,
  Plus,
  RefreshCw,
  Sparkles,
  Trash2,
  WandSparkles,
  XCircle,
} from 'lucide-react'
import { toast } from 'sonner'

import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { Select } from '@/components/ui/Select'
import type { EvaluationAuthoringCall } from '@/features/evaluations/authoringTypes'
import {
  useCancelEvaluatorSuiteAuthoring,
  useCreateComposedEvaluatorSuite,
  useEvaluationAuthoringCall,
  useGenerateEvaluatorSuite,
  usePreviewSuiteAuthoringContext,
  useRetryEvaluatorSuiteAuthoring,
  useValidateEvaluatorSuite,
} from '@/features/evaluations/hooks'
import type {
  EvaluationCaseInput,
  EvaluationCaseType,
  EvaluationSourceType,
  EvaluationSuite,
  EvaluationTargetInput,
  EvaluationTargetType,
  EvaluatorSuiteDraft,
  ExpectedOutcome,
  SuiteAuthoringSource,
  SuiteValidationResult,
} from '@/features/evaluations/types'
import type { ProviderModel } from '@/features/provider-models/types'
import { cn } from '@/lib/utils'

type Step = 'method' | 'ai' | 'json' | 'progress' | 'editor'

export interface EvaluatorVersionOption {
  id: string
  version: string
  status: string
  kind?: string
  snapshot_kind?: string
}

interface Props {
  projectId: string
  targetType: EvaluationTargetType
  entityId: string
  targetName: string
  versions: EvaluatorVersionOption[]
  providerModels: ProviderModel[]
  onCancel: () => void
  onCreated: (suite: EvaluationSuite) => void
  initialSourceType?: EvaluationSourceType
  initialVersionId?: string
}

const coverageOptions = [
  ['core_behavior', 'Core behavior'],
  ['edge_cases', 'Edge cases'],
  ['tools', 'Tool usage'],
  ['knowledge', 'Knowledge grounding'],
  ['security_refusal', 'Security and refusal'],
  ['output_contract', 'Output contract'],
  ['error_handling', 'Error handling'],
] as const

const caseTypes: Array<{ value: EvaluationCaseType; label: string }> = [
  { value: 'success', label: 'Successful response' },
  { value: 'refusal', label: 'Safe refusal' },
  { value: 'handled_error', label: 'Handled error' },
  { value: 'expected_failure', label: 'Expected runtime failure' },
]

function emptyOutcome(type: EvaluationCaseType): ExpectedOutcome {
  return {
    type,
    allowed_failure_origins: [],
    allowed_failure_stages: [],
    allowed_failure_codes: [],
    required_behavior: [],
    forbidden_behavior: [],
  }
}

function emptyCase(index: number): EvaluationCaseInput {
  return {
    name: `Question ${index}`,
    case_type: 'success',
    message: '',
    expected_outcome: emptyOutcome('success'),
    expected_contract: {
      semantic_criteria: [],
      output_contract: { required: true },
      tools: { required: [], forbidden: [] },
    },
    severity: 'normal',
    weight: 1,
    blocking: false,
    tags: [],
    production_frequency: null,
  }
}

function emptyDraft(): EvaluatorSuiteDraft {
  return { schema_version: 1, suite: {}, coverage: {}, cases: [emptyCase(1)] }
}

function list(value: unknown): string {
  return Array.isArray(value) ? value.map(String).join('\n') : ''
}

function fromLines(value: string): string[] {
  return value.split('\n').map((item) => item.trim()).filter(Boolean)
}

function normalizeDraft(value: unknown): EvaluatorSuiteDraft {
  if (!value || typeof value !== 'object') throw new Error('JSON root must be an object')
  const raw = value as Record<string, any>
  if (!Array.isArray(raw.cases)) throw new Error('JSON must contain a cases array')
  return {
    schema_version: Number(raw.schema_version || 1),
    suite: raw.suite && typeof raw.suite === 'object' ? raw.suite : {},
    coverage: raw.coverage && typeof raw.coverage === 'object' ? raw.coverage : {},
    cases: raw.cases.map((source: Record<string, any>, index: number) => {
      const type = (source?.case_type || source?.expected_outcome?.type || source?.expected_contract?.expected_outcome?.type || 'success') as EvaluationCaseType
      return {
        ...emptyCase(index + 1),
        ...source,
        case_type: type,
        message: String(source?.message || source?.input_payload?.message || ''),
        expected_outcome: {
          ...emptyOutcome(type),
          ...(source?.expected_outcome || source?.expected_contract?.expected_outcome || {}),
          type,
        },
        expected_contract: {
          ...emptyCase(index + 1).expected_contract,
          ...(source?.expected_contract || {}),
        },
      }
    }),
  }
}

function MethodCard({ icon, title, description, onClick }: { icon: React.ReactNode; title: string; description: string; onClick: () => void }) {
  return <button type="button" onClick={onClick} className="rounded-xl border border-border/80 bg-background/40 p-5 text-left transition-colors hover:border-primary/35 hover:bg-primary/[0.04]">
    <div className="flex h-10 w-10 items-center justify-center rounded-xl border border-primary/20 bg-primary/10 text-primary-light">{icon}</div>
    <h4 className="mt-4 text-sm font-semibold text-white">{title}</h4>
    <p className="mt-2 text-xs leading-5 text-muted">{description}</p>
  </button>
}

function ProgressPanel({ call, onCancel, onRetry }: { call: EvaluationAuthoringCall; onCancel: () => void; onRetry: () => void }) {
  const active = ['queued', 'running', 'partial', 'cancel_requested'].includes(call.status)
  const failed = call.batches.some((batch) => batch.status === 'failed')
  return <div className="mx-auto max-w-4xl space-y-5">
    <div>
      <div className="flex items-center gap-2"><Loader2 className={cn('h-4 w-4 text-primary-light', active && 'animate-spin')} /><h3 className="text-base font-semibold text-white">Generating Evaluator Suite</h3></div>
      <p className="mt-1 text-xs text-muted">Batches are persisted independently. A failed batch can be retried without discarding completed cases.</p>
    </div>
    <section className="rounded-xl border border-primary/25 bg-primary/[0.04] p-4">
      <div className="flex items-center justify-between"><p className="text-sm font-semibold text-white">{call.completed_batch_count} / {call.total_batch_count} batches</p><Badge variant="outline">{call.status.replace('_', ' ')}</Badge></div>
      <div className="mt-3 h-2 overflow-hidden rounded-full bg-background"><div className="h-full bg-primary transition-all" style={{ width: `${call.progress_percent}%` }} /></div>
      <div className="mt-4 grid gap-3 sm:grid-cols-3"><div><p className="text-[9px] uppercase text-muted">Progress</p><p className="mt-1 text-sm text-white">{call.progress_percent.toFixed(1)}%</p></div><div><p className="text-[9px] uppercase text-muted">Tokens</p><p className="mt-1 text-sm text-white">{Number(call.generator.input_tokens || 0).toLocaleString()} in · {Number(call.generator.output_tokens || 0).toLocaleString()} out</p></div><div><p className="text-[9px] uppercase text-muted">Cost</p><p className="mt-1 text-sm text-white">{call.generator.cost_usd == null ? 'Unknown' : `$${call.generator.cost_usd.toFixed(4)}`}</p></div></div>
    </section>
    <div className="space-y-2">{call.batches.map((batch) => <div key={batch.id} className="flex items-center justify-between rounded-lg border border-border/80 bg-background/35 px-4 py-3"><div><p className="text-xs font-medium text-white">Batch {batch.batch_index} · {batch.requested_case_count} cases</p><p className="mt-1 text-[10px] text-muted">Attempt {batch.attempt} · {batch.case_count} generated{batch.error ? ` · ${batch.error}` : ''}</p></div><Badge variant="outline" className={batch.status === 'completed' ? 'border-emerald-500/25 text-emerald-300' : batch.status === 'failed' ? 'border-red-500/25 text-red-300' : 'border-border text-muted'}>{batch.status}</Badge></div>)}</div>
    <div className="flex justify-end gap-2 border-t border-border pt-4">{active && call.status !== 'cancel_requested' ? <Button variant="outline" onClick={onCancel}>Cancel generation</Button> : null}{failed ? <Button onClick={onRetry}><RefreshCw className="mr-2 h-4 w-4" />Retry failed batches</Button> : null}</div>
  </div>
}

export function EvaluatorSuiteAuthoringWizard({
  projectId,
  targetType,
  entityId,
  targetName,
  versions,
  providerModels,
  onCancel,
  onCreated,
  initialSourceType = 'draft',
  initialVersionId = '',
}: Props) {
  const preview = usePreviewSuiteAuthoringContext(projectId)
  const generate = useGenerateEvaluatorSuite(projectId)
  const validate = useValidateEvaluatorSuite(projectId)
  const create = useCreateComposedEvaluatorSuite(projectId)
  const cancelAuthoring = useCancelEvaluatorSuiteAuthoring(projectId)
  const retryAuthoring = useRetryEvaluatorSuiteAuthoring(projectId)

  const [step, setStep] = useState<Step>('method')
  const [source, setSource] = useState<SuiteAuthoringSource>('manual')
  const [draft, setDraft] = useState<EvaluatorSuiteDraft>(emptyDraft())
  const [validation, setValidation] = useState<SuiteValidationResult | null>(null)
  const [authoringCallId, setAuthoringCallId] = useState<string | null>(null)
  const authoringQuery = useEvaluationAuthoringCall(projectId, authoringCallId)
  const call = authoringQuery.data

  const [sourceType, setSourceType] = useState<EvaluationSourceType>(initialSourceType)
  const [versionId, setVersionId] = useState(initialVersionId)
  const [jsonText, setJsonText] = useState('')
  const [generatorModelId, setGeneratorModelId] = useState('')
  const [judgeModelId, setJudgeModelId] = useState('')
  const [objective, setObjective] = useState('')
  const [caseCount, setCaseCount] = useState(20)
  const [errorRatio, setErrorRatio] = useState(30)
  const [maximumCost, setMaximumCost] = useState('')
  const [suiteName, setSuiteName] = useState('')
  const [description, setDescription] = useState('')
  const [minimumScore, setMinimumScore] = useState(70)
  const [minimumPassRate, setMinimumPassRate] = useState(80)
  const [repetitions, setRepetitions] = useState(3)
  const [coverage] = useState<string[]>(coverageOptions.map(([value]) => value))

  const activeModels = providerModels.filter((model) => model.status === 'active')
  const availableVersions = useMemo(() => versions.filter((item) => sourceType === 'staging' ? item.status === 'staging' || item.kind === 'staging' : item.snapshot_kind === 'release' || item.kind === 'release' || ['released', 'production', 'rolled_back'].includes(item.status)), [versions, sourceType])
  const target: EvaluationTargetInput = {
    target_type: targetType,
    source_type: sourceType,
    entity_id: entityId,
    ...(sourceType !== 'draft' && versionId ? { version_id: versionId } : {}),
  }
  const targetReady = sourceType === 'draft' || Boolean(versionId)

  useEffect(() => {
    if (!call || call.status !== 'completed' || !call.draft || !call.validation?.valid) return
    setDraft({ ...call.draft, cases: call.validation.cases })
    setValidation(call.validation)
    setSource('ai_generated')
    setSuiteName(call.draft.suite?.suggested_name || `${targetName} qualification`)
    setDescription(call.draft.suite?.description || objective)
    if (!judgeModelId) setJudgeModelId(generatorModelId)
    setStep('editor')
  }, [call?.status])

  const allocation = () => {
    const base = Math.floor(caseCount / coverage.length)
    let remainder = caseCount - base * coverage.length
    return Object.fromEntries(coverage.map((key) => {
      const value = base + (remainder > 0 ? 1 : 0)
      remainder = Math.max(0, remainder - 1)
      return [key, value]
    }))
  }

  const validateDraft = async (value = draft) => {
    const result = await validate.mutateAsync({ draft: value, reference_target: target })
    setValidation(result)
    if (result.valid) setDraft((current) => ({ ...current, ...value, cases: result.cases }))
    return result
  }

  const importJson = async () => {
    try {
      const imported = normalizeDraft(JSON.parse(jsonText))
      const result = await validateDraft(imported)
      setDraft({ ...imported, cases: result.cases })
      setSource('json_import')
      setSuiteName(imported.suite?.suggested_name || '')
      setDescription(imported.suite?.description || '')
      setStep('editor')
    } catch (error) { toast.error(error instanceof Error ? error.message : 'Invalid JSON') }
  }

  const startGeneration = async () => {
    if (!targetReady || !generatorModelId || objective.trim().length < 10) return toast.error('Choose a target, generator model and objective')
    try {
      const queued = await generate.mutateAsync({
        target,
        generator_provider_model_id: generatorModelId,
        objective: objective.trim(),
        case_count: caseCount,
        coverage: allocation(),
        error_case_ratio: errorRatio / 100,
        language: 'pt-BR',
        maximum_input_tokens: 16000,
        maximum_cost_usd: maximumCost ? Number(maximumCost) : null,
      })
      setAuthoringCallId(queued.authoring_call_id)
      setStep('progress')
    } catch (error) { toast.error(error instanceof Error ? error.message : 'Unable to queue generation') }
  }

  const save = async () => {
    if (!suiteName.trim() || !judgeModelId) return toast.error('Suite name and Judge model are required')
    try {
      const result = await validateDraft()
      if (!result.valid) return toast.error('Fix validation errors before saving')
      const suite = await create.mutateAsync({
        name: suiteName.trim(),
        description: description.trim(),
        target_type: targetType,
        judge_provider_model_id: judgeModelId,
        draft: { ...draft, cases: result.cases },
        judge_config: { temperature: 0, max_tokens: 800, timeout_seconds: 90, maximum_input_tokens: 8000 },
        rubric: { criteria: ['Correctness', 'Relevance', 'Completeness', 'Expected behavior'], judge_weight: 4 },
        deterministic_checks: { enabled: true },
        acceptance_policy: { minimum_score: minimumScore, minimum_pass_rate: minimumPassRate, minimum_paired_n: repetitions, maximum_score_regression: 0 },
        repetition_policy: { default_repetitions: repetitions, maximum_repetitions: 25 },
        estimate_defaults: { volume: 10000 },
        authoring_source: source,
        source_snapshot_hash: call?.source_snapshot_hash || (result as any).reference?.snapshot_hash || null,
        source_context_hash: call?.source_context_hash || (result as any).reference?.context_hash || null,
        authoring_metadata: {
          ...(call ? { authoring_call_id: call.authoring_call_id, generator: call.generator, context_budget: call.context_budget } : {}),
          reference_target: target,
          objective,
        },
      })
      toast.success('Evaluator Suite created')
      onCreated(suite)
    } catch (error) { toast.error(error instanceof Error ? error.message : 'Unable to create Suite') }
  }

  if (step === 'progress' && call) return <ProgressPanel call={call} onCancel={() => void cancelAuthoring.mutateAsync(call.authoring_call_id)} onRetry={() => void retryAuthoring.mutateAsync(call.authoring_call_id)} />

  if (step === 'method') return <div className="mx-auto max-w-4xl space-y-5"><div><h3 className="text-base font-semibold text-white">Create Evaluator Suite</h3><p className="mt-1 text-xs text-muted">Every method ends in the same target-bound review editor.</p></div><div className="grid gap-4 md:grid-cols-3"><MethodCard icon={<WandSparkles className="h-5 w-5" />} title="Generate with AI" description={`Analyze an exact ${targetType} snapshot and generate persisted batches of up to 10 cases.`} onClick={() => setStep('ai')} /><MethodCard icon={<FileJson className="h-5 w-5" />} title="Import JSON" description="Validate an external or Git-versioned Suite against the selected snapshot." onClick={() => setStep('json')} /><MethodCard icon={<Plus className="h-5 w-5" />} title="Create manually" description="Start with an empty target-bound Test Case." onClick={() => { setSource('manual'); setDraft(emptyDraft()); setStep('editor') }} /></div><div className="flex justify-end border-t border-border pt-4"><Button variant="outline" onClick={onCancel}>Cancel</Button></div></div>

  if (step === 'json') return <div className="mx-auto max-w-4xl space-y-5"><div className="flex items-start gap-3"><Button size="sm" variant="ghost" onClick={() => setStep('method')}><ArrowLeft className="h-4 w-4" /></Button><div><h3 className="text-base font-semibold text-white">Import Evaluator Suite JSON</h3><p className="mt-1 text-xs text-muted">Concrete Tool references are validated against the reference snapshot.</p></div></div><textarea value={jsonText} onChange={(event) => setJsonText(event.target.value)} className="min-h-[420px] w-full rounded-xl border border-border bg-background p-4 font-mono text-xs text-white outline-none" placeholder={'{"schema_version":1,"cases":[]}'} /><div className="flex justify-end gap-2"><Button variant="outline" onClick={() => setStep('method')}>Back</Button><Button loading={validate.isPending} onClick={() => void importJson()}><Braces className="mr-2 h-4 w-4" />Validate and review</Button></div></div>

  if (step === 'ai') return <div className="mx-auto max-w-5xl space-y-5"><div className="flex items-start gap-3"><Button size="sm" variant="ghost" onClick={() => setStep('method')}><ArrowLeft className="h-4 w-4" /></Button><div><h3 className="text-base font-semibold text-white">Generate with AI</h3><p className="mt-1 text-xs text-muted">The operation is durable and split into batches of at most 10 cases.</p></div></div><section className="rounded-xl border border-border/80 bg-background/35 p-4"><div className="grid gap-4 md:grid-cols-2"><label className="space-y-2 text-xs text-muted"><span>Environment</span><Select value={sourceType} onChange={(event) => { setSourceType(event.target.value as EvaluationSourceType); setVersionId(''); preview.reset() }} options={[{ value: 'draft', label: 'Current Draft' }, { value: 'staging', label: 'Staging' }, { value: 'release', label: 'Release / Production' }]} /></label><label className="space-y-2 text-xs text-muted"><span>Exact snapshot</span><Select disabled={sourceType === 'draft'} value={versionId} onChange={(event) => setVersionId(event.target.value)} options={[{ value: '', label: sourceType === 'draft' ? 'Current Draft will be frozen' : 'Select exact snapshot' }, ...availableVersions.map((item) => ({ value: item.id, label: `${item.version} · ${item.status}` }))]} /></label><label className="space-y-2 text-xs text-muted"><span>Generator model</span><Select value={generatorModelId} onChange={(event) => setGeneratorModelId(event.target.value)} options={[{ value: '', label: 'Select BYOK model' }, ...activeModels.map((model) => ({ value: model.id, label: `${model.name} · ${model.model}` }))]} /></label><label className="space-y-2 text-xs text-muted"><span>Number of cases</span><Input type="number" min={5} max={50} value={caseCount} onChange={(event) => setCaseCount(Math.max(5, Math.min(50, Number(event.target.value))))} /></label></div><label className="mt-4 block space-y-2 text-xs text-muted"><span>Objective</span><textarea value={objective} onChange={(event) => setObjective(event.target.value)} className="min-h-28 w-full rounded-lg border border-border bg-background px-3 py-2 text-sm text-white outline-none" /></label><div className="mt-4 grid gap-4 md:grid-cols-2"><label className="space-y-2 text-xs text-muted"><span>Negative/error cases (%)</span><Input type="number" min={0} max={80} value={errorRatio} onChange={(event) => setErrorRatio(Math.max(0, Math.min(80, Number(event.target.value))))} /></label><label className="space-y-2 text-xs text-muted"><span>Maximum total cost (USD)</span><Input type="number" min={0} step={0.01} value={maximumCost} onChange={(event) => setMaximumCost(event.target.value)} placeholder="Optional" /></label></div></section>{preview.data ? <section className="rounded-xl border border-primary/25 bg-primary/[0.04] p-4"><p className="text-sm font-semibold text-white">Context preview</p><p className="mt-2 text-xs text-muted">{preview.data.context_budget.estimated_input_tokens.toLocaleString()} input tokens per batch · estimated ${preview.data.estimated_cost_usd?.toFixed(4) ?? 'unknown'} for one call</p></section> : null}<div className="flex justify-end gap-2 border-t border-border pt-4"><Button variant="outline" onClick={() => setStep('method')}>Back</Button><Button variant="outline" loading={preview.isPending} disabled={!targetReady || !generatorModelId || objective.trim().length < 10} onClick={() => void preview.mutateAsync({ target, generator_provider_model_id: generatorModelId, objective, case_count: caseCount, maximum_input_tokens: 16000 })}>Preview</Button><Button loading={generate.isPending} disabled={!targetReady || !generatorModelId || objective.trim().length < 10} onClick={() => void startGeneration()}><Sparkles className="mr-2 h-4 w-4" />Queue generation</Button></div></div>

  return <div className="mx-auto max-w-5xl space-y-5"><div className="flex items-start justify-between"><div className="flex items-start gap-3"><Button size="sm" variant="ghost" onClick={() => setStep('method')}><ArrowLeft className="h-4 w-4" /></Button><div><div className="flex items-center gap-2"><h3 className="text-base font-semibold text-white">Review Evaluator Suite</h3><Badge variant="outline">{source.replace('_', ' ')}</Badge></div><p className="mt-1 text-xs text-muted">Review is mandatory. Saving creates an immutable Dataset and Suite version transactionally.</p></div></div><Button size="sm" variant="outline" loading={validate.isPending} onClick={() => void validateDraft()}>Validate</Button></div>{validation ? <section className={cn('rounded-xl border p-4', validation.valid ? 'border-emerald-500/25 bg-emerald-500/[0.04]' : 'border-red-500/25 bg-red-500/[0.04]')}><div className="flex items-center gap-2">{validation.valid ? <CheckCircle2 className="h-4 w-4 text-emerald-300" /> : <AlertTriangle className="h-4 w-4 text-red-300" />}<p className="text-sm font-semibold text-white">{validation.valid ? `${validation.case_count} valid cases` : `${validation.errors.length} validation errors`}</p></div>{validation.errors.map((item, index) => <p key={index} className="mt-2 text-xs text-red-300">{item.path ? `${item.path}: ` : ''}{item.message}</p>)}</section> : null}<section className="grid gap-4 rounded-xl border border-border/80 bg-background/35 p-4 md:grid-cols-2"><label className="space-y-2 text-xs text-muted"><span>Name</span><Input value={suiteName} onChange={(event) => setSuiteName(event.target.value)} /></label><label className="space-y-2 text-xs text-muted"><span>Judge model</span><Select value={judgeModelId} onChange={(event) => setJudgeModelId(event.target.value)} options={[{ value: '', label: 'Select BYOK model' }, ...activeModels.map((model) => ({ value: model.id, label: `${model.name} · ${model.model}` }))]} /></label><label className="space-y-2 text-xs text-muted md:col-span-2"><span>Description</span><Input value={description} onChange={(event) => setDescription(event.target.value)} /></label></section><section className="space-y-3">{draft.cases.map((item, index) => { const type = item.case_type || 'success'; const expected = item.expected_outcome || emptyOutcome(type); const contract = item.expected_contract || {}; const tools = (contract.tools && typeof contract.tools === 'object' ? contract.tools : {}) as Record<string, unknown>; return <article key={index} className="rounded-xl border border-border/80 bg-background/35 p-4"><div className="flex gap-3"><Input value={item.name} onChange={(event) => setDraft((current) => ({ ...current, cases: current.cases.map((value, position) => position === index ? { ...value, name: event.target.value } : value) }))} className="flex-1" /><Select value={type} onChange={(event) => { const next = event.target.value as EvaluationCaseType; setDraft((current) => ({ ...current, cases: current.cases.map((value, position) => position === index ? { ...value, case_type: next, expected_outcome: emptyOutcome(next) } : value) })) }} options={caseTypes} className="w-52" /><Button size="sm" variant="ghost" disabled={draft.cases.length === 1} onClick={() => setDraft((current) => ({ ...current, cases: current.cases.filter((_, position) => position !== index) }))}><Trash2 className="h-4 w-4" /></Button></div><div className="mt-3 grid gap-3 md:grid-cols-2"><textarea value={item.message} onChange={(event) => setDraft((current) => ({ ...current, cases: current.cases.map((value, position) => position === index ? { ...value, message: event.target.value } : value) }))} placeholder="Question sent to target" className="min-h-24 rounded-lg border border-border bg-background p-3 text-sm text-white outline-none" /><textarea value={list(contract.semantic_criteria)} onChange={(event) => setDraft((current) => ({ ...current, cases: current.cases.map((value, position) => position === index ? { ...value, expected_contract: { ...(value.expected_contract || {}), semantic_criteria: fromLines(event.target.value) } } : value) }))} placeholder="Expected behavior, one criterion per line" className="min-h-24 rounded-lg border border-border bg-background p-3 text-sm text-white outline-none" /></div><div className="mt-3 grid gap-3 md:grid-cols-2"><textarea value={list(tools.required)} onChange={(event) => setDraft((current) => ({ ...current, cases: current.cases.map((value, position) => position === index ? { ...value, expected_contract: { ...(value.expected_contract || {}), tools: { ...tools, required: fromLines(event.target.value) } } } : value) }))} placeholder="Required Tools, one per line" className="min-h-16 rounded-lg border border-border bg-background p-3 text-xs text-white outline-none" /><textarea value={list(tools.forbidden)} onChange={(event) => setDraft((current) => ({ ...current, cases: current.cases.map((value, position) => position === index ? { ...value, expected_contract: { ...(value.expected_contract || {}), tools: { ...tools, forbidden: fromLines(event.target.value) } } } : value) }))} placeholder="Forbidden Tools, one per line" className="min-h-16 rounded-lg border border-border bg-background p-3 text-xs text-white outline-none" /></div>{type === 'expected_failure' ? <div className="mt-3 grid gap-3 md:grid-cols-3"><Input value={(expected.allowed_failure_origins || []).join(', ')} onChange={(event) => setDraft((current) => ({ ...current, cases: current.cases.map((value, position) => position === index ? { ...value, expected_outcome: { ...expected, allowed_failure_origins: event.target.value.split(',').map((text) => text.trim()).filter(Boolean) } } : value) }))} placeholder="Origins: tool, provider" /><Input value={(expected.allowed_failure_stages || []).join(', ')} onChange={(event) => setDraft((current) => ({ ...current, cases: current.cases.map((value, position) => position === index ? { ...value, expected_outcome: { ...expected, allowed_failure_stages: event.target.value.split(',').map((text) => text.trim()).filter(Boolean) } } : value) }))} placeholder="Stages" /><Input value={(expected.allowed_failure_codes || []).join(', ')} onChange={(event) => setDraft((current) => ({ ...current, cases: current.cases.map((value, position) => position === index ? { ...value, expected_outcome: { ...expected, allowed_failure_codes: event.target.value.split(',').map((text) => text.trim()).filter(Boolean) } } : value) }))} placeholder="Codes" /></div> : null}<div className="mt-3 flex flex-wrap items-center gap-4"><label className="flex items-center gap-2 text-xs text-muted"><input type="checkbox" checked={Boolean(item.blocking)} onChange={(event) => setDraft((current) => ({ ...current, cases: current.cases.map((value, position) => position === index ? { ...value, blocking: event.target.checked } : value) }))} />Blocking</label><Input type="number" min={0.1} max={100} step={0.1} value={item.weight || 1} onChange={(event) => setDraft((current) => ({ ...current, cases: current.cases.map((value, position) => position === index ? { ...value, weight: Number(event.target.value) } : value) }))} className="w-24" /></div></article> })}<Button size="sm" variant="outline" onClick={() => setDraft((current) => ({ ...current, cases: [...current.cases, emptyCase(current.cases.length + 1)] }))}><Plus className="mr-2 h-4 w-4" />Add case</Button></section><section className="grid gap-4 rounded-xl border border-border/80 bg-background/35 p-4 sm:grid-cols-3"><label className="space-y-2 text-xs text-muted"><span>Minimum score</span><Input type="number" min={0} max={100} value={minimumScore} onChange={(event) => setMinimumScore(Number(event.target.value))} /></label><label className="space-y-2 text-xs text-muted"><span>Minimum pass rate</span><Input type="number" min={0} max={100} value={minimumPassRate} onChange={(event) => setMinimumPassRate(Number(event.target.value))} /></label><label className="space-y-2 text-xs text-muted"><span>Runs per case</span><Input type="number" min={1} max={25} value={repetitions} onChange={(event) => setRepetitions(Math.max(1, Math.min(25, Number(event.target.value))))} /></label></section><div className="flex justify-end gap-2 border-t border-border pt-4"><Button variant="outline" onClick={onCancel}>Cancel</Button><Button loading={create.isPending} onClick={() => void save()}><Sparkles className="mr-2 h-4 w-4" />Create immutable Suite</Button></div></div>
}
