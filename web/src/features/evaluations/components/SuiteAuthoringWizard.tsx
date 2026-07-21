import { useMemo, useState } from 'react'
import {
  AlertTriangle,
  ArrowLeft,
  Braces,
  CheckCircle2,
  FileJson,
  Plus,
  Sparkles,
  Trash2,
  WandSparkles,
} from 'lucide-react'
import { toast } from 'sonner'

import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { Select } from '@/components/ui/Select'
import type { AgentRelease } from '@/features/agents/types'
import {
  useCreateComposedEvaluatorSuite,
  useGenerateEvaluatorSuite,
  usePreviewSuiteAuthoringContext,
  useValidateEvaluatorSuite,
} from '@/features/evaluations/hooks'
import type {
  EvaluationCaseInput,
  EvaluationCaseType,
  EvaluationSourceType,
  EvaluationSuite,
  EvaluationTargetInput,
  EvaluatorSuiteDraft,
  ExpectedOutcome,
  GeneratedSuiteDraft,
  SuiteAuthoringSource,
  SuiteValidationResult,
} from '@/features/evaluations/types'
import type { ProviderModel } from '@/features/provider-models/types'
import { cn } from '@/lib/utils'

type AuthoringStep = 'method' | 'ai' | 'json' | 'editor'

interface SuiteAuthoringWizardProps {
  projectId: string
  agentId: string
  releases: AgentRelease[]
  providerModels: ProviderModel[]
  onCancel: () => void
  onCreated: (suite: EvaluationSuite) => void
}

const caseTypeOptions = [
  { value: 'success', label: 'Successful response' },
  { value: 'refusal', label: 'Safe refusal' },
  { value: 'handled_error', label: 'Handled error' },
  { value: 'expected_failure', label: 'Expected runtime failure' },
]

const severityOptions = [
  { value: 'low', label: 'Low' },
  { value: 'normal', label: 'Normal' },
  { value: 'high', label: 'High' },
  { value: 'critical', label: 'Critical' },
]

const coverageOptions = [
  ['core_behavior', 'Core behavior'],
  ['edge_cases', 'Edge cases'],
  ['tools', 'Tool usage'],
  ['knowledge', 'Knowledge grounding'],
  ['security_refusal', 'Security and refusal'],
  ['output_contract', 'Output contract'],
  ['error_handling', 'Error handling'],
] as const

function emptyExpectedOutcome(type: EvaluationCaseType): ExpectedOutcome {
  return {
    type,
    allowed_failure_origins: [],
    allowed_failure_stages: [],
    allowed_failure_codes: [],
    required_behavior: [],
    forbidden_behavior: [],
  }
}

function emptyCase(index = 1): EvaluationCaseInput {
  return {
    name: `Question ${index}`,
    case_type: 'success',
    message: '',
    expected_outcome: emptyExpectedOutcome('success'),
    expected_contract: {
      semantic_criteria: [''],
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
  return { schema_version: 1, suite: {}, coverage: {}, cases: [emptyCase()] }
}

function lines(value: unknown): string {
  return Array.isArray(value) ? value.map(String).join('\n') : ''
}

function listFromLines(value: string): string[] {
  return value.split('\n').map((item) => item.trim()).filter(Boolean)
}

function targetOptions(releases: AgentRelease[], source: EvaluationSourceType) {
  if (source === 'staging') return releases.filter((release) => release.status === 'staging')
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

function normalizeImportedDraft(value: unknown): EvaluatorSuiteDraft {
  if (!value || typeof value !== 'object') throw new Error('JSON root must be an object')
  const raw = value as Record<string, unknown>
  const cases = raw.cases
  if (!Array.isArray(cases)) throw new Error('JSON must contain a cases array')
  return {
    schema_version: Number(raw.schema_version || 1),
    suite: raw.suite && typeof raw.suite === 'object' ? raw.suite as EvaluatorSuiteDraft['suite'] : {},
    coverage: raw.coverage && typeof raw.coverage === 'object' ? raw.coverage as Record<string, number> : {},
    cases: cases.map((item, index) => {
      const source = item && typeof item === 'object' ? item as Record<string, any> : {}
      const type = (source.case_type || source.expected_outcome?.type || 'success') as EvaluationCaseType
      return {
        ...emptyCase(index + 1),
        ...source,
        case_type: type,
        message: String(source.message || source.input_payload?.message || ''),
        expected_outcome: { ...emptyExpectedOutcome(type), ...(source.expected_outcome || source.expected_contract?.expected_outcome || {}), type },
        expected_contract: {
          ...emptyCase(index + 1).expected_contract,
          ...(source.expected_contract || {}),
        },
      }
    }),
  }
}

function MethodCard({ icon, title, description, onClick }: { icon: React.ReactNode; title: string; description: string; onClick: () => void }) {
  return (
    <button type="button" onClick={onClick} className="rounded-xl border border-border/80 bg-background/40 p-5 text-left transition-colors hover:border-primary/35 hover:bg-primary/[0.04]">
      <div className="flex h-10 w-10 items-center justify-center rounded-xl border border-primary/20 bg-primary/10 text-primary-light">{icon}</div>
      <h4 className="mt-4 text-sm font-semibold text-white">{title}</h4>
      <p className="mt-2 text-xs leading-5 text-muted">{description}</p>
    </button>
  )
}

export function SuiteAuthoringWizard({ projectId, agentId, releases, providerModels, onCancel, onCreated }: SuiteAuthoringWizardProps) {
  const previewContext = usePreviewSuiteAuthoringContext(projectId)
  const generateSuite = useGenerateEvaluatorSuite(projectId)
  const validateSuite = useValidateEvaluatorSuite(projectId)
  const createSuite = useCreateComposedEvaluatorSuite(projectId)

  const activeModels = providerModels.filter((model) => model.status === 'active')
  const production = releases.find((release) => release.status === 'production')
  const [step, setStep] = useState<AuthoringStep>('method')
  const [authoringSource, setAuthoringSource] = useState<SuiteAuthoringSource>('manual')
  const [draft, setDraft] = useState<EvaluatorSuiteDraft>(emptyDraft())
  const [validation, setValidation] = useState<SuiteValidationResult | null>(null)
  const [generated, setGenerated] = useState<GeneratedSuiteDraft | null>(null)
  const [jsonText, setJsonText] = useState('')

  const [suiteName, setSuiteName] = useState('')
  const [suiteDescription, setSuiteDescription] = useState('')
  const [judgeModelId, setJudgeModelId] = useState('')
  const [minimumScore, setMinimumScore] = useState(70)
  const [minimumPassRate, setMinimumPassRate] = useState(80)
  const [defaultRepetitions, setDefaultRepetitions] = useState(3)

  const [sourceType, setSourceType] = useState<EvaluationSourceType>('draft')
  const [versionId, setVersionId] = useState('')
  const [generatorModelId, setGeneratorModelId] = useState('')
  const [objective, setObjective] = useState('')
  const [caseCount, setCaseCount] = useState(20)
  const [errorRatio, setErrorRatio] = useState(30)
  const [maximumInputTokens, setMaximumInputTokens] = useState(16000)
  const [maximumCost, setMaximumCost] = useState('')
  const [coverage, setCoverage] = useState<string[]>(coverageOptions.map(([value]) => value))

  const versions = useMemo(() => targetOptions(releases, sourceType), [releases, sourceType])
  const target: EvaluationTargetInput = {
    target_type: 'agent',
    source_type: sourceType,
    entity_id: agentId,
    ...(sourceType !== 'draft' && versionId ? { version_id: versionId } : {}),
  }
  const targetReady = sourceType === 'draft' || Boolean(versionId)

  const patchCase = (index: number, values: Partial<EvaluationCaseInput>) => {
    setDraft((current) => ({
      ...current,
      cases: current.cases.map((item, position) => position === index ? { ...item, ...values } : item),
    }))
    setValidation(null)
  }

  const patchOutcome = (index: number, values: Partial<ExpectedOutcome>) => {
    const current = draft.cases[index]
    patchCase(index, { expected_outcome: { ...emptyExpectedOutcome(current.case_type || 'success'), ...(current.expected_outcome || {}), ...values } })
  }

  const patchContract = (index: number, values: Record<string, unknown>) => {
    const current = draft.cases[index]
    patchCase(index, { expected_contract: { ...(current.expected_contract || {}), ...values } })
  }

  const startManual = () => {
    setAuthoringSource('manual')
    setDraft(emptyDraft())
    setStep('editor')
  }

  const importJson = async () => {
    try {
      const imported = normalizeImportedDraft(JSON.parse(jsonText))
      const result = await validateSuite.mutateAsync(imported)
      setDraft({ ...imported, cases: result.cases })
      setValidation(result)
      setAuthoringSource('json_import')
      setSuiteName(imported.suite?.suggested_name || suiteName)
      setSuiteDescription(imported.suite?.description || suiteDescription)
      setStep('editor')
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Invalid Evaluator Suite JSON')
    }
  }

  const readJsonFile = async (file?: File) => {
    if (!file) return
    try { setJsonText(await file.text()) } catch { toast.error('Unable to read JSON file') }
  }

  const coverageAllocation = () => {
    const selected = coverage.length ? coverage : ['core_behavior']
    const base = Math.floor(caseCount / selected.length)
    let remainder = caseCount - base * selected.length
    return Object.fromEntries(selected.map((key) => {
      const value = base + (remainder > 0 ? 1 : 0)
      remainder -= remainder > 0 ? 1 : 0
      return [key, value]
    }))
  }

  const previewAiContext = async () => {
    if (!generatorModelId || !objective.trim() || !targetReady) return toast.error('Choose target, generator model and objective')
    try {
      await previewContext.mutateAsync({
        target,
        generator_provider_model_id: generatorModelId,
        objective: objective.trim(),
        case_count: caseCount,
        maximum_input_tokens: maximumInputTokens,
      })
    } catch (error) { toast.error(error instanceof Error ? error.message : 'Unable to preview generator context') }
  }

  const generateAiDraft = async () => {
    if (!generatorModelId || !objective.trim() || !targetReady) return toast.error('Choose target, generator model and objective')
    try {
      const result = await generateSuite.mutateAsync({
        target,
        generator_provider_model_id: generatorModelId,
        objective: objective.trim(),
        case_count: caseCount,
        coverage: coverageAllocation(),
        error_case_ratio: errorRatio / 100,
        language: 'pt-BR',
        maximum_input_tokens: maximumInputTokens,
        maximum_cost_usd: maximumCost ? Number(maximumCost) : null,
      })
      if (!result.validation.valid) {
        toast.error(result.generator.error || 'The generated Suite did not pass validation')
        setValidation(result.validation)
        return
      }
      setGenerated(result)
      setDraft({ ...result.draft, cases: result.validation.cases })
      setValidation(result.validation)
      setAuthoringSource('ai_generated')
      setSuiteName(result.draft.suite?.suggested_name || suiteName)
      setSuiteDescription(result.draft.suite?.description || objective.trim())
      if (!judgeModelId) setJudgeModelId(generatorModelId)
      setStep('editor')
    } catch (error) { toast.error(error instanceof Error ? error.message : 'Unable to generate Evaluator Suite') }
  }

  const validateCurrentDraft = async () => {
    try {
      const result = await validateSuite.mutateAsync(draft)
      setValidation(result)
      if (result.valid) setDraft((current) => ({ ...current, cases: result.cases }))
      return result
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Unable to validate Evaluator Suite')
      return null
    }
  }

  const save = async () => {
    if (!suiteName.trim()) return toast.error('Evaluator Suite name is required')
    if (!judgeModelId) return toast.error('Choose the LLM judge model')
    const result = await validateCurrentDraft()
    if (!result?.valid) return toast.error('Fix the validation errors before saving')
    try {
      const suite = await createSuite.mutateAsync({
        name: suiteName.trim(),
        description: suiteDescription.trim(),
        target_type: 'agent',
        judge_provider_model_id: judgeModelId,
        draft: { ...draft, cases: result.cases },
        judge_config: { temperature: 0, max_tokens: 800, timeout_seconds: 90, maximum_input_tokens: 8000 },
        rubric: { criteria: ['Correctness', 'Relevance', 'Completeness', 'Expected behavior'], judge_weight: 4 },
        deterministic_checks: { enabled: true },
        acceptance_policy: { minimum_score: minimumScore, minimum_pass_rate: minimumPassRate, minimum_paired_n: Math.max(1, defaultRepetitions), maximum_score_regression: 0 },
        repetition_policy: { default_repetitions: defaultRepetitions, maximum_repetitions: 25 },
        estimate_defaults: { volume: 10000 },
        authoring_source: authoringSource,
        source_snapshot_hash: generated?.source_snapshot_hash || null,
        source_context_hash: generated?.source_context_hash || null,
        authoring_metadata: generated ? {
          authoring_call_id: generated.authoring_call_id,
          generator: generated.generator,
          context_budget: generated.context_budget,
          objective,
        } : {},
      })
      toast.success('Evaluator Suite created')
      onCreated(suite)
    } catch (error) { toast.error(error instanceof Error ? error.message : 'Failed to create Evaluator Suite') }
  }

  if (step === 'method') {
    return <div className="mx-auto max-w-4xl space-y-5">
      <div><h3 className="text-base font-semibold text-white">Create Evaluator Suite</h3><p className="mt-1 text-xs leading-5 text-muted">Choose how to create the question set. Every method ends in the same reviewable editor.</p></div>
      <div className="grid gap-4 md:grid-cols-3">
        <MethodCard icon={<WandSparkles className="h-5 w-5" />} title="Generate with AI" description="Analyze an exact Agent snapshot and propose a balanced battery of success, refusal and error cases." onClick={() => setStep('ai')} />
        <MethodCard icon={<FileJson className="h-5 w-5" />} title="Import JSON" description="Paste or upload a versionable Suite definition produced externally or stored in Git." onClick={() => setStep('json')} />
        <MethodCard icon={<Plus className="h-5 w-5" />} title="Create manually" description="Start with an empty Test Case and define every criterion yourself." onClick={startManual} />
      </div>
      <div className="flex justify-end border-t border-border pt-4"><Button variant="outline" onClick={onCancel}>Cancel</Button></div>
    </div>
  }

  if (step === 'json') {
    return <div className="mx-auto max-w-4xl space-y-5">
      <div className="flex items-start gap-3"><Button size="sm" variant="ghost" onClick={() => setStep('method')}><ArrowLeft className="h-4 w-4" /></Button><div><h3 className="text-base font-semibold text-white">Import Evaluator Suite JSON</h3><p className="mt-1 text-xs text-muted">The JSON is validated by the same backend contract used by AI generation and manual authoring.</p></div></div>
      <textarea value={jsonText} onChange={(event) => setJsonText(event.target.value)} placeholder={'{"schema_version":1,"cases":[]}'} className="min-h-[420px] w-full rounded-xl border border-border bg-background p-4 font-mono text-xs leading-5 text-white outline-none focus:border-primary/50" />
      <div className="flex items-center justify-between gap-3"><label className="text-xs text-muted">Upload .json <input type="file" accept="application/json,.json" className="ml-3 text-xs" onChange={(event) => void readJsonFile(event.target.files?.[0])} /></label><div className="flex gap-2"><Button variant="outline" onClick={() => setStep('method')}>Back</Button><Button loading={validateSuite.isPending} disabled={!jsonText.trim()} onClick={() => void importJson()}><Braces className="mr-2 h-4 w-4" />Validate and review</Button></div></div>
    </div>
  }

  if (step === 'ai') {
    const context = previewContext.data
    return <div className="mx-auto max-w-5xl space-y-5">
      <div className="flex items-start gap-3"><Button size="sm" variant="ghost" onClick={() => setStep('method')}><ArrowLeft className="h-4 w-4" /></Button><div><h3 className="text-base font-semibold text-white">Generate Evaluator Suite with AI</h3><p className="mt-1 text-xs leading-5 text-muted">The generator receives a sanitized, token-budgeted digest of the selected snapshot. Secrets are never included.</p></div></div>
      <section className="rounded-xl border border-border/80 bg-background/35 p-4"><p className="text-sm font-semibold text-white">Reference snapshot</p><div className="mt-3 grid gap-4 md:grid-cols-2"><label className="space-y-2 text-xs text-muted"><span>Environment</span><Select value={sourceType} onChange={(event) => { setSourceType(event.target.value as EvaluationSourceType); setVersionId(''); previewContext.reset() }} options={[{ value: 'draft', label: 'Current Draft' }, { value: 'staging', label: 'Staging' }, { value: 'release', label: 'Release / Production' }]} /></label><label className="space-y-2 text-xs text-muted"><span>Exact snapshot</span><Select disabled={sourceType === 'draft'} value={versionId} onChange={(event) => { setVersionId(event.target.value); previewContext.reset() }} options={[{ value: '', label: sourceType === 'draft' ? 'Current Draft will be frozen' : 'Select exact snapshot' }, ...versions.map((release) => ({ value: release.id, label: `${release.version} · ${release.status}` }))]} /></label></div>{production && sourceType === 'release' ? <p className="mt-3 text-[11px] text-muted">Current Production: <span className="font-mono text-white">{production.version}</span></p> : null}</section>
      <section className="rounded-xl border border-border/80 bg-background/35 p-4"><div className="grid gap-4 md:grid-cols-2"><label className="space-y-2 text-xs text-muted"><span>Generator model</span><Select value={generatorModelId} onChange={(event) => setGeneratorModelId(event.target.value)} options={[{ value: '', label: 'Select a BYOK model' }, ...activeModels.map((model) => ({ value: model.id, label: `${model.name} · ${model.model}` }))]} /></label><label className="space-y-2 text-xs text-muted"><span>Number of Test Cases</span><Input type="number" min={5} max={50} value={caseCount} onChange={(event) => { setCaseCount(Math.max(5, Math.min(50, Number(event.target.value)))); previewContext.reset() }} /></label></div><label className="mt-4 block space-y-2 text-xs text-muted"><span>Test objective</span><textarea value={objective} onChange={(event) => { setObjective(event.target.value); previewContext.reset() }} className="min-h-28 w-full rounded-lg border border-border bg-background px-3 py-2 text-sm text-white outline-none focus:border-primary/50" placeholder="Validate customer support behavior, Tool selection, grounded answers and safe refusals before Production." /></label><div className="mt-4 grid gap-4 md:grid-cols-3"><label className="space-y-2 text-xs text-muted"><span>Negative/error cases (%)</span><Input type="number" min={0} max={80} value={errorRatio} onChange={(event) => setErrorRatio(Math.max(0, Math.min(80, Number(event.target.value))))} /></label><label className="space-y-2 text-xs text-muted"><span>Maximum input tokens</span><Input type="number" min={2000} max={64000} step={1000} value={maximumInputTokens} onChange={(event) => { setMaximumInputTokens(Math.max(2000, Math.min(64000, Number(event.target.value)))); previewContext.reset() }} /></label><label className="space-y-2 text-xs text-muted"><span>Maximum generation cost (USD)</span><Input type="number" min={0} step={0.01} value={maximumCost} onChange={(event) => setMaximumCost(event.target.value)} placeholder="Optional" /></label></div></section>
      <section className="rounded-xl border border-border/80 bg-background/35 p-4"><p className="text-sm font-semibold text-white">Coverage</p><div className="mt-3 grid gap-2 sm:grid-cols-2 lg:grid-cols-4">{coverageOptions.map(([value, label]) => <label key={value} className={cn('flex items-center gap-2 rounded-lg border px-3 py-2 text-xs', coverage.includes(value) ? 'border-primary/30 bg-primary/[0.06] text-white' : 'border-border text-muted')}><input type="checkbox" checked={coverage.includes(value)} onChange={(event) => setCoverage((current) => event.target.checked ? [...current, value] : current.filter((item) => item !== value))} />{label}</label>)}</div></section>
      {context ? <section className="rounded-xl border border-primary/25 bg-primary/[0.04] p-4"><div className="flex items-center gap-2"><CheckCircle2 className="h-4 w-4 text-primary-light" /><p className="text-sm font-semibold text-white">Context budget</p></div><div className="mt-3 grid gap-3 sm:grid-cols-4"><div><p className="text-[9px] uppercase text-muted">Input estimate</p><p className="mt-1 text-sm text-white">{context.context_budget.estimated_input_tokens.toLocaleString()} tokens</p></div><div><p className="text-[9px] uppercase text-muted">Output reserve</p><p className="mt-1 text-sm text-white">{context.reserved_output_tokens.toLocaleString()} tokens</p></div><div><p className="text-[9px] uppercase text-muted">Context window</p><p className="mt-1 text-sm text-white">{context.context_window.toLocaleString()}</p></div><div><p className="text-[9px] uppercase text-muted">Estimated cost</p><p className="mt-1 text-sm text-white">{context.estimated_cost_usd == null ? 'Unknown' : `$${context.estimated_cost_usd.toFixed(4)}`}</p></div></div>{context.context_budget.truncation_applied ? <p className="mt-3 text-xs text-amber-300">Compacted sections: {context.context_budget.truncated_sections.join(', ')}</p> : <p className="mt-3 text-xs text-emerald-300">The selected context fits without truncation.</p>}</section> : null}
      <div className="flex justify-end gap-2 border-t border-border pt-4"><Button variant="outline" onClick={() => setStep('method')}>Back</Button><Button variant="outline" loading={previewContext.isPending} disabled={!targetReady || !generatorModelId || objective.trim().length < 10} onClick={() => void previewAiContext()}>Preview context</Button><Button loading={generateSuite.isPending} disabled={!targetReady || !generatorModelId || objective.trim().length < 10} onClick={() => void generateAiDraft()}><Sparkles className="mr-2 h-4 w-4" />Generate cases</Button></div>
    </div>
  }

  return <div className="mx-auto max-w-5xl space-y-5">
    <div className="flex items-start justify-between gap-4"><div className="flex items-start gap-3"><Button size="sm" variant="ghost" onClick={() => setStep('method')}><ArrowLeft className="h-4 w-4" /></Button><div><div className="flex items-center gap-2"><h3 className="text-base font-semibold text-white">Review Evaluator Suite</h3><Badge variant="outline">{authoringSource.replace('_', ' ')}</Badge></div><p className="mt-1 text-xs text-muted">Review is mandatory before the immutable Suite version is created.</p></div></div><Button size="sm" variant="outline" loading={validateSuite.isPending} onClick={() => void validateCurrentDraft()}>Validate</Button></div>
    {generated ? <section className="rounded-xl border border-primary/25 bg-primary/[0.04] p-4"><div className="grid gap-3 sm:grid-cols-4"><div><p className="text-[9px] uppercase text-muted">Generator</p><p className="mt-1 text-xs text-white">{generated.generator.provider}/{generated.generator.model}</p></div><div><p className="text-[9px] uppercase text-muted">Input</p><p className="mt-1 text-xs text-white">{generated.generator.input_tokens?.toLocaleString() ?? 'Unknown'} tokens</p></div><div><p className="text-[9px] uppercase text-muted">Output</p><p className="mt-1 text-xs text-white">{generated.generator.output_tokens?.toLocaleString() ?? 'Unknown'} tokens</p></div><div><p className="text-[9px] uppercase text-muted">Cost</p><p className="mt-1 text-xs text-white">{generated.generator.cost_usd == null ? 'Unknown' : `$${generated.generator.cost_usd.toFixed(4)}`}</p></div></div></section> : null}
    {validation ? <section className={cn('rounded-xl border p-4', validation.valid ? 'border-emerald-500/25 bg-emerald-500/[0.04]' : 'border-red-500/25 bg-red-500/[0.04]')}><div className="flex items-center gap-2">{validation.valid ? <CheckCircle2 className="h-4 w-4 text-emerald-300" /> : <AlertTriangle className="h-4 w-4 text-red-300" />}<p className="text-sm font-semibold text-white">{validation.valid ? `${validation.case_count} cases are valid` : `${validation.errors.length} validation errors`}</p></div>{validation.errors.length ? <div className="mt-3 space-y-1">{validation.errors.map((item, index) => <p key={index} className="text-xs text-red-300">{item.path ? `${item.path}: ` : ''}{item.message}</p>)}</div> : null}{validation.warnings.length ? <div className="mt-3 space-y-1">{validation.warnings.map((item, index) => <p key={index} className="text-xs text-amber-300">{item.message}</p>)}</div> : null}</section> : null}
    <section className="grid gap-4 rounded-xl border border-border/80 bg-background/35 p-4 md:grid-cols-2"><label className="space-y-2 text-xs text-muted"><span>Name</span><Input value={suiteName} onChange={(event) => setSuiteName(event.target.value)} /></label><label className="space-y-2 text-xs text-muted"><span>LLM judge</span><Select value={judgeModelId} onChange={(event) => setJudgeModelId(event.target.value)} options={[{ value: '', label: 'Select a BYOK model' }, ...activeModels.map((model) => ({ value: model.id, label: `${model.name} · ${model.model}` }))]} /></label><label className="space-y-2 text-xs text-muted md:col-span-2"><span>Description</span><Input value={suiteDescription} onChange={(event) => setSuiteDescription(event.target.value)} /></label></section>
    <section><div className="mb-3 flex items-center justify-between"><div><p className="text-sm font-semibold text-white">Test Cases</p><p className="mt-1 text-[11px] text-muted">The Judge receives the expected outcome, relevant Run evidence and a compact target digest.</p></div><Button size="sm" variant="outline" onClick={() => setDraft((current) => ({ ...current, cases: [...current.cases, emptyCase(current.cases.length + 1)] }))}><Plus className="mr-1 h-3.5 w-3.5" />Add case</Button></div><div className="space-y-3">{draft.cases.map((item, index) => {
      const type = item.case_type || 'success'
      const expected = item.expected_outcome || emptyExpectedOutcome(type)
      const contract = item.expected_contract || {}
      const tools = contract.tools && typeof contract.tools === 'object' ? contract.tools as Record<string, unknown> : {}
      return <article key={index} className="rounded-xl border border-border/80 bg-background/35 p-4"><div className="flex items-center gap-3"><Input value={item.name} onChange={(event) => patchCase(index, { name: event.target.value })} className="min-w-0 flex-1" /><Select value={type} onChange={(event) => { const next = event.target.value as EvaluationCaseType; patchCase(index, { case_type: next, expected_outcome: emptyExpectedOutcome(next), expected_contract: { ...contract, output_contract: { ...(contract.output_contract as Record<string, unknown> || {}), required: next !== 'expected_failure' } } }) }} options={caseTypeOptions} className="w-52" /><Button size="sm" variant="ghost" disabled={draft.cases.length === 1} onClick={() => setDraft((current) => ({ ...current, cases: current.cases.filter((_, position) => position !== index) }))}><Trash2 className="h-4 w-4" /></Button></div><div className="mt-3 grid gap-3 md:grid-cols-2"><label className="space-y-2 text-xs text-muted"><span>Question sent to Agent</span><textarea value={item.message} onChange={(event) => patchCase(index, { message: event.target.value })} className="min-h-28 w-full rounded-lg border border-border bg-background px-3 py-2 text-sm text-white outline-none focus:border-primary/50" /></label><label className="space-y-2 text-xs text-muted"><span>Semantic grading criteria, one per line</span><textarea value={lines(contract.semantic_criteria)} onChange={(event) => patchContract(index, { semantic_criteria: listFromLines(event.target.value) })} className="min-h-28 w-full rounded-lg border border-border bg-background px-3 py-2 text-sm text-white outline-none focus:border-primary/50" /></label></div><div className="mt-3 grid gap-3 md:grid-cols-2"><label className="space-y-2 text-xs text-muted"><span>Required behavior, one per line</span><textarea value={lines(expected.required_behavior)} onChange={(event) => patchOutcome(index, { required_behavior: listFromLines(event.target.value) })} className="min-h-20 w-full rounded-lg border border-border bg-background px-3 py-2 text-xs text-white outline-none focus:border-primary/50" /></label><label className="space-y-2 text-xs text-muted"><span>Forbidden behavior, one per line</span><textarea value={lines(expected.forbidden_behavior)} onChange={(event) => patchOutcome(index, { forbidden_behavior: listFromLines(event.target.value) })} className="min-h-20 w-full rounded-lg border border-border bg-background px-3 py-2 text-xs text-white outline-none focus:border-primary/50" /></label></div>{type === 'expected_failure' ? <div className="mt-3 grid gap-3 md:grid-cols-3"><label className="space-y-2 text-xs text-muted"><span>Allowed origins</span><Input value={(expected.allowed_failure_origins || []).join(', ')} onChange={(event) => patchOutcome(index, { allowed_failure_origins: event.target.value.split(',').map((value) => value.trim()).filter(Boolean) })} placeholder="tool, provider" /></label><label className="space-y-2 text-xs text-muted"><span>Allowed stages</span><Input value={(expected.allowed_failure_stages || []).join(', ')} onChange={(event) => patchOutcome(index, { allowed_failure_stages: event.target.value.split(',').map((value) => value.trim()).filter(Boolean) })} placeholder="tool_execution" /></label><label className="space-y-2 text-xs text-muted"><span>Allowed codes</span><Input value={(expected.allowed_failure_codes || []).join(', ')} onChange={(event) => patchOutcome(index, { allowed_failure_codes: event.target.value.split(',').map((value) => value.trim()).filter(Boolean) })} placeholder="tool_timeout" /></label></div> : null}<div className="mt-3 grid gap-3 md:grid-cols-2"><label className="space-y-2 text-xs text-muted"><span>Required Tools, one per line</span><textarea value={lines(tools.required)} onChange={(event) => patchContract(index, { tools: { ...tools, required: listFromLines(event.target.value) } })} className="min-h-16 w-full rounded-lg border border-border bg-background px-3 py-2 text-xs text-white outline-none" /></label><label className="space-y-2 text-xs text-muted"><span>Forbidden Tools, one per line</span><textarea value={lines(tools.forbidden)} onChange={(event) => patchContract(index, { tools: { ...tools, forbidden: listFromLines(event.target.value) } })} className="min-h-16 w-full rounded-lg border border-border bg-background px-3 py-2 text-xs text-white outline-none" /></label></div><div className="mt-3 flex flex-wrap items-end gap-4"><label className="space-y-2 text-xs text-muted"><span>Severity</span><Select value={item.severity || 'normal'} onChange={(event) => patchCase(index, { severity: event.target.value as EvaluationCaseInput['severity'] })} options={severityOptions} className="w-32" /></label><label className="space-y-2 text-xs text-muted"><span>Weight</span><Input type="number" min={0.1} max={100} step={0.1} value={item.weight || 1} onChange={(event) => patchCase(index, { weight: Math.max(0.1, Number(event.target.value)) })} className="w-24" /></label><label className="space-y-2 text-xs text-muted"><span>Production frequency</span><Input type="number" min={0} max={1} step={0.01} value={item.production_frequency ?? ''} onChange={(event) => patchCase(index, { production_frequency: event.target.value ? Number(event.target.value) : null })} className="w-32" /></label><label className="flex items-center gap-2 pb-2 text-xs text-muted"><input type="checkbox" checked={Boolean(item.blocking)} onChange={(event) => patchCase(index, { blocking: event.target.checked })} />Blocking case</label></div></article>
    })}</div></section>
    <section className="rounded-xl border border-border/80 bg-background/35 p-4"><p className="text-sm font-semibold text-white">Acceptance policy</p><div className="mt-3 grid gap-4 sm:grid-cols-3"><label className="space-y-2 text-xs text-muted"><span>Minimum score</span><Input type="number" min={0} max={100} value={minimumScore} onChange={(event) => setMinimumScore(Number(event.target.value))} /></label><label className="space-y-2 text-xs text-muted"><span>Minimum pass rate</span><Input type="number" min={0} max={100} value={minimumPassRate} onChange={(event) => setMinimumPassRate(Number(event.target.value))} /></label><label className="space-y-2 text-xs text-muted"><span>Default Runs per case</span><Input type="number" min={1} max={25} value={defaultRepetitions} onChange={(event) => setDefaultRepetitions(Math.max(1, Math.min(25, Number(event.target.value))))} /></label></div></section>
    <div className="flex justify-end gap-2 border-t border-border pt-4"><Button variant="outline" onClick={onCancel}>Cancel</Button><Button variant="outline" loading={validateSuite.isPending} onClick={() => void validateCurrentDraft()}>Validate draft</Button><Button loading={createSuite.isPending} onClick={() => void save()}><Sparkles className="mr-2 h-4 w-4" />Create immutable Suite</Button></div>
  </div>
}
