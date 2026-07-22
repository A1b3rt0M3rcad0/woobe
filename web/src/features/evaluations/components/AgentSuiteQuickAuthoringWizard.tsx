import { useEffect, useMemo, useRef, useState } from 'react'
import {
  ArrowLeft,
  Braces,
  ChevronDown,
  FileJson,
  Loader2,
  Plus,
  Sparkles,
  Upload,
  WandSparkles,
} from 'lucide-react'
import { toast } from 'sonner'

import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { Select } from '@/components/ui/Select'
import type { AgentRelease } from '@/features/agents/types'
import {
  useCancelEvaluatorSuiteAuthoring,
  useCreateComposedEvaluatorSuite,
  useEvaluationAuthoringCall,
  useGenerateEvaluatorSuite,
  usePreviewSuiteAuthoringContext,
  useRetryEvaluatorSuiteAuthoring,
  useValidateEvaluatorSuite,
} from '@/features/evaluations/hooks'
import { evaluatorSuiteJsonExample } from '@/features/evaluations/jsonExample'
import type {
  EvaluationCaseInput,
  EvaluationCaseType,
  EvaluationSourceType,
  EvaluationSuite,
  EvaluationTargetInput,
  EvaluatorSuiteDraft,
  SuiteAuthoringSource,
  SuiteValidationResult,
} from '@/features/evaluations/types'
import type { ProviderModel } from '@/features/provider-models/types'
import { cn } from '@/lib/utils'
import { SuiteCaseWorkspace, emptyCase, emptyOutcome } from './SuiteCaseWorkspace'
import { SuiteGenerationProgress } from './SuiteGenerationProgress'

type Step = 'method' | 'generate' | 'json' | 'manual' | 'progress' | 'review'
type Depth = 'quick' | 'standard' | 'thorough'
type Focus = 'general' | 'tools' | 'knowledge' | 'safety' | 'regression'

interface Props {
  projectId: string
  agentId: string
  releases: AgentRelease[]
  providerModels: ProviderModel[]
  onCancel: () => void
  onCreated: (suite: EvaluationSuite) => void
}

const coverageLabels: Record<string, string> = {
  core_behavior: 'Core behavior',
  edge_cases: 'Edge cases',
  tools: 'Tool usage',
  knowledge: 'Knowledge grounding',
  security_refusal: 'Security and refusal',
  output_contract: 'Output contract',
  error_handling: 'Error handling',
}

const focusCoverage: Record<Focus, string[]> = {
  general: ['core_behavior', 'edge_cases', 'output_contract', 'security_refusal'],
  tools: ['core_behavior', 'tools', 'error_handling', 'output_contract'],
  knowledge: ['core_behavior', 'knowledge', 'edge_cases', 'security_refusal'],
  safety: ['security_refusal', 'error_handling', 'edge_cases'],
  regression: Object.keys(coverageLabels),
}

const depthCases: Record<Depth, number> = {
  quick: 10,
  standard: 20,
  thorough: 40,
}

const negativeCoverage = new Set(['security_refusal', 'error_handling'])

function emptyDraft(): EvaluatorSuiteDraft {
  return { schema_version: 1, suite: {}, coverage: {}, cases: [emptyCase(1)] }
}

function listValue(value: unknown): string[] {
  if (Array.isArray(value)) return value.map(String).map((item) => item.trim()).filter(Boolean)
  if (typeof value === 'string' && value.trim()) return [value.trim()]
  return []
}

function normalizeDraft(value: unknown): EvaluatorSuiteDraft {
  if (!value || typeof value !== 'object') throw new Error('JSON root must be an object')
  const raw = value as Record<string, any>
  if (!Array.isArray(raw.cases) || !raw.cases.length) throw new Error('JSON must contain at least one Test Case')
  return {
    schema_version: Number(raw.schema_version || 1),
    suite: raw.suite && typeof raw.suite === 'object' ? raw.suite : {},
    coverage: raw.coverage && typeof raw.coverage === 'object' ? raw.coverage : {},
    cases: raw.cases.map((source: Record<string, any>, index: number) => {
      const type = (source.case_type || source.expected_outcome?.type || source.expected_contract?.expected_outcome?.type || 'success') as EvaluationCaseType
      const expected = source.expected_outcome || source.expected_contract?.expected_outcome || {}
      const contract = source.expected_contract || {}
      const tools = contract.tools || {}
      return {
        ...emptyCase(index + 1, type),
        ...source,
        case_type: type,
        message: String(source.message || source.input_payload?.message || ''),
        expected_outcome: {
          ...emptyOutcome(type),
          ...expected,
          type,
          required_behavior: listValue(expected.required_behavior ?? source.expected_behavior),
          forbidden_behavior: listValue(expected.forbidden_behavior),
          allowed_failure_origins: listValue(expected.allowed_failure_origins),
          allowed_failure_stages: listValue(expected.allowed_failure_stages),
          allowed_failure_codes: listValue(expected.allowed_failure_codes),
        },
        expected_contract: {
          ...emptyCase(index + 1, type).expected_contract,
          ...contract,
          semantic_criteria: listValue(contract.semantic_criteria ?? source.expected_result),
          tools: {
            required: listValue(tools.required),
            forbidden: listValue(tools.forbidden),
          },
        },
        tags: listValue(source.tags),
      }
    }),
  }
}

function distribute(keys: string[], count: number, result: Record<string, number>) {
  if (!keys.length) return
  for (let index = 0; index < count; index += 1) {
    const key = keys[index % keys.length]
    result[key] = (result[key] || 0) + 1
  }
}

export function AgentSuiteQuickAuthoringWizard({
  projectId,
  agentId,
  releases,
  providerModels,
  onCancel,
  onCreated,
}: Props) {
  const preview = usePreviewSuiteAuthoringContext(projectId)
  const generate = useGenerateEvaluatorSuite(projectId)
  const validate = useValidateEvaluatorSuite(projectId)
  const create = useCreateComposedEvaluatorSuite(projectId)
  const cancelAuthoring = useCancelEvaluatorSuiteAuthoring(projectId)
  const retryAuthoring = useRetryEvaluatorSuiteAuthoring(projectId)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const [step, setStep] = useState<Step>('method')
  const [source, setSource] = useState<SuiteAuthoringSource>('manual')
  const [draft, setDraft] = useState<EvaluatorSuiteDraft>(emptyDraft())
  const [validation, setValidation] = useState<SuiteValidationResult | null>(null)
  const [authoringCallId, setAuthoringCallId] = useState<string | null>(null)
  const callQuery = useEvaluationAuthoringCall(projectId, authoringCallId)
  const call = callQuery.data

  const [objective, setObjective] = useState('')
  const [depth, setDepth] = useState<Depth>('standard')
  const [focus, setFocus] = useState<Focus>('general')
  const [advancedOpen, setAdvancedOpen] = useState(false)
  const [sourceType, setSourceType] = useState<EvaluationSourceType>('draft')
  const [versionId, setVersionId] = useState('')
  const [generatorModelId, setGeneratorModelId] = useState('')
  const [judgeModelId, setJudgeModelId] = useState('')
  const [selectedCoverage, setSelectedCoverage] = useState<string[]>(focusCoverage.general)
  const [errorRatio, setErrorRatio] = useState(20)
  const [maximumCost, setMaximumCost] = useState('')
  const [jsonText, setJsonText] = useState('')
  const [suiteName, setSuiteName] = useState('')
  const [description, setDescription] = useState('')
  const [minimumScore, setMinimumScore] = useState(70)
  const [minimumPassRate, setMinimumPassRate] = useState(80)
  const [repetitions, setRepetitions] = useState(3)
  const [reviewAdvancedOpen, setReviewAdvancedOpen] = useState(false)

  const activeModels = providerModels.filter((model) => model.status === 'active')
  const caseCount = depthCases[depth]
  const availableVersions = useMemo(() => releases.filter((item) => (
    sourceType === 'staging'
      ? item.status === 'staging'
      : item.snapshot_kind === 'release' || ['released', 'production', 'rolled_back'].includes(item.status)
  )), [releases, sourceType])
  const target: EvaluationTargetInput = {
    target_type: 'agent',
    source_type: sourceType,
    entity_id: agentId,
    ...(sourceType !== 'draft' && versionId ? { version_id: versionId } : {}),
  }
  const targetReady = sourceType === 'draft' || Boolean(versionId)

  useEffect(() => {
    if (!generatorModelId && activeModels[0]) setGeneratorModelId(activeModels[0].id)
    if (!judgeModelId && activeModels[0]) setJudgeModelId(activeModels[0].id)
  }, [activeModels])

  useEffect(() => {
    setSelectedCoverage(focusCoverage[focus])
    setErrorRatio(focus === 'safety' ? 50 : focus === 'tools' ? 30 : 20)
  }, [focus])

  const allocation = useMemo(() => {
    const positive = selectedCoverage.filter((key) => !negativeCoverage.has(key))
    const negative = selectedCoverage.filter((key) => negativeCoverage.has(key))
    let negativeCount = negative.length ? Math.round(caseCount * errorRatio / 100) : 0
    if (!positive.length) negativeCount = caseCount
    const result: Record<string, number> = {}
    distribute(positive, caseCount - negativeCount, result)
    distribute(negative, negativeCount, result)
    return result
  }, [selectedCoverage, caseCount, errorRatio])

  useEffect(() => {
    if (step !== 'generate' || !targetReady || !generatorModelId || objective.trim().length < 10) return
    const timer = window.setTimeout(() => {
      preview.mutate({
        target,
        generator_provider_model_id: generatorModelId,
        objective: objective.trim(),
        case_count: caseCount,
        maximum_input_tokens: 16000,
      })
    }, 500)
    return () => window.clearTimeout(timer)
  }, [step, sourceType, versionId, generatorModelId, objective, caseCount])

  useEffect(() => {
    if (!call || call.status !== 'completed' || !call.draft || !call.validation?.valid) return
    setDraft({ ...call.draft, cases: call.validation.cases })
    setValidation(call.validation)
    setSource('ai_generated')
    setSuiteName(call.draft.suite?.suggested_name || 'Agent qualification')
    setDescription(call.draft.suite?.description || objective)
    if (!judgeModelId) setJudgeModelId(generatorModelId)
    setStep('review')
  }, [call?.status])

  const validateDraft = async (value = draft) => {
    const result = await validate.mutateAsync({ draft: value, reference_target: target })
    setValidation(result)
    if (result.valid) setDraft((current) => ({ ...current, ...value, cases: result.cases }))
    return result
  }

  const startGeneration = async () => {
    if (!targetReady || !generatorModelId || objective.trim().length < 10) {
      toast.error('Describe the objective and choose a valid target')
      return
    }
    try {
      const queued = await generate.mutateAsync({
        target,
        generator_provider_model_id: generatorModelId,
        objective: objective.trim(),
        case_count: caseCount,
        coverage: allocation,
        error_case_ratio: errorRatio / 100,
        language: 'pt-BR',
        maximum_input_tokens: 16000,
        maximum_cost_usd: maximumCost ? Number(maximumCost) : null,
      })
      setAuthoringCallId(queued.authoring_call_id)
      setStep('progress')
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Unable to queue generation')
    }
  }

  const importJson = async () => {
    try {
      const imported = normalizeDraft(JSON.parse(jsonText))
      const result = await validateDraft(imported)
      setDraft(result.valid ? { ...imported, cases: result.cases } : imported)
      setSource('json_import')
      setSuiteName(imported.suite?.suggested_name || '')
      setDescription(imported.suite?.description || '')
      setStep('review')
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Invalid JSON')
    }
  }

  const save = async () => {
    if (!suiteName.trim() || !judgeModelId) {
      toast.error('Suite name and Judge model are required')
      return
    }
    try {
      const result = await validateDraft()
      if (!result.valid) {
        toast.error('Fix validation errors before saving')
        return
      }
      const suite = await create.mutateAsync({
        name: suiteName.trim(),
        description: description.trim(),
        target_type: 'agent',
        judge_provider_model_id: judgeModelId,
        draft: { ...draft, cases: result.cases },
        judge_config: {
          temperature: 0,
          output_budget_policy: 'auto',
          max_tokens: 1200,
          maximum_retry_tokens: 8192,
          timeout_seconds: 90,
          maximum_input_tokens: 8000,
        },
        rubric: {
          criteria: ['Correctness', 'Relevance', 'Completeness', 'Expected behavior'],
          judge_weight: 4,
        },
        deterministic_checks: { enabled: true },
        acceptance_policy: {
          minimum_score: minimumScore,
          minimum_pass_rate: minimumPassRate,
          minimum_paired_n: repetitions,
          maximum_score_regression: 0,
        },
        repetition_policy: {
          default_repetitions: repetitions,
          maximum_repetitions: 25,
        },
        estimate_defaults: { volume: 10000 },
        authoring_source: source,
        source_snapshot_hash: call?.source_snapshot_hash || result.reference?.snapshot_hash || null,
        source_context_hash: call?.source_context_hash || result.reference?.context_hash || null,
        authoring_metadata: {
          ...(call ? { authoring_call_id: call.authoring_call_id, generator: call.generator, context_budget: call.context_budget } : {}),
          reference_target: target,
          objective,
          depth,
          focus,
        },
      })
      toast.success('Evaluator Suite created')
      onCreated(suite)
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Unable to save Evaluator Suite')
    }
  }

  if (step === 'progress') {
    if (!call) return <div className="flex min-h-64 items-center justify-center"><Loader2 className="h-5 w-5 animate-spin text-primary-light" /></div>
    return <SuiteGenerationProgress call={call} cancelling={cancelAuthoring.isPending} retrying={retryAuthoring.isPending} onCancel={() => void cancelAuthoring.mutateAsync(call.authoring_call_id)} onRetry={() => void retryAuthoring.mutateAsync(call.authoring_call_id)} onChangeSettings={() => setStep('generate')} />
  }

  if (step === 'method') {
    return (
      <div className="mx-auto max-w-4xl space-y-5">
        <div><h3 className="text-base font-semibold text-white">Create Evaluator Suite</h3><p className="mt-1 text-xs text-muted">Choose the fastest authoring method. Every option ends in the same review editor.</p></div>
        <div className="grid gap-4 md:grid-cols-3">
          {[
            { title: 'Generate with AI', description: 'Describe the goal and choose a test depth.', icon: <WandSparkles className="h-5 w-5" />, action: () => setStep('generate') },
            { title: 'Import JSON', description: 'Paste a valid example or upload a versioned file.', icon: <FileJson className="h-5 w-5" />, action: () => setStep('json') },
            { title: 'Create manually', description: 'Start with one case in the compact navigator.', icon: <Plus className="h-5 w-5" />, action: () => { setSource('manual'); setDraft(emptyDraft()); setValidation(null); setStep('review') } },
          ].map((item) => <button key={item.title} type="button" onClick={item.action} className="rounded-xl border border-border/80 bg-background/40 p-5 text-left hover:border-primary/35"><div className="flex h-10 w-10 items-center justify-center rounded-xl border border-primary/20 bg-primary/10 text-primary-light">{item.icon}</div><h4 className="mt-4 text-sm font-semibold text-white">{item.title}</h4><p className="mt-2 text-xs leading-5 text-muted">{item.description}</p></button>)}
        </div>
        <div className="flex justify-end border-t border-border pt-4"><Button variant="outline" onClick={onCancel}>Cancel</Button></div>
      </div>
    )
  }

  if (step === 'generate') {
    const previewData = preview.data
    return (
      <div className="mx-auto max-w-4xl space-y-5">
        <div className="flex items-start gap-3"><Button size="sm" variant="ghost" onClick={() => setStep('method')}><ArrowLeft className="h-4 w-4" /></Button><div><h3 className="text-base font-semibold text-white">Generate Test Cases</h3><p className="mt-1 text-xs text-muted">Simple defaults first. Advanced controls stay out of the way.</p></div></div>
        <section className="rounded-2xl border border-border/80 bg-background/35 p-5">
          <label className="block space-y-2 text-xs text-muted"><span>What should this Agent be tested for?</span><textarea value={objective} onChange={(event) => setObjective(event.target.value)} placeholder="Validate billing support accuracy, safe refusal, correct Tool usage and behavior when required data is missing." className="min-h-28 w-full rounded-xl border border-border bg-background p-3 text-sm text-white outline-none focus:border-primary/40" /></label>
          <div className="mt-5"><p className="text-xs text-muted">Test depth</p><div className="mt-2 grid gap-2 sm:grid-cols-3">{(['quick', 'standard', 'thorough'] as Depth[]).map((value) => <button key={value} type="button" onClick={() => setDepth(value)} className={cn('rounded-lg border px-3 py-3 text-left', depth === value ? 'border-primary/35 bg-primary/[0.07]' : 'border-border bg-background')}><p className="text-xs font-medium text-white">{value.charAt(0).toUpperCase() + value.slice(1)}</p><p className="mt-1 text-[10px] text-muted">{depthCases[value]} cases</p></button>)}</div></div>
          <label className="mt-5 block space-y-2 text-xs text-muted"><span>Primary focus</span><Select value={focus} onChange={(event) => setFocus(event.target.value as Focus)} options={[{ value: 'general', label: 'General quality' }, { value: 'tools', label: 'Tool usage' }, { value: 'knowledge', label: 'Knowledge / RAG' }, { value: 'safety', label: 'Safety and refusal' }, { value: 'regression', label: 'Deep regression' }]} /></label>
          <button type="button" onClick={() => setAdvancedOpen((value) => !value)} className="mt-5 flex w-full items-center justify-between border-t border-border pt-4 text-left"><div><p className="text-xs font-medium text-white">Advanced generation settings</p><p className="mt-1 text-[10px] text-muted">Snapshot, generator model, coverage, negative ratio and cost.</p></div><ChevronDown className={cn('h-4 w-4 text-muted transition-transform', advancedOpen && 'rotate-180')} /></button>
          {advancedOpen ? <div className="mt-4 space-y-4"><div className="grid gap-4 md:grid-cols-2"><label className="space-y-2 text-xs text-muted"><span>Reference environment</span><Select value={sourceType} onChange={(event) => { setSourceType(event.target.value as EvaluationSourceType); setVersionId('') }} options={[{ value: 'draft', label: 'Current Draft' }, { value: 'staging', label: 'Staging' }, { value: 'release', label: 'Release / Production' }]} /></label><label className="space-y-2 text-xs text-muted"><span>Exact snapshot</span><Select disabled={sourceType === 'draft'} value={versionId} onChange={(event) => setVersionId(event.target.value)} options={[{ value: '', label: sourceType === 'draft' ? 'Current Draft will be frozen' : 'Select snapshot' }, ...availableVersions.map((item) => ({ value: item.id, label: `${item.version} · ${item.status}` }))]} /></label><label className="space-y-2 text-xs text-muted"><span>Generator model</span><Select value={generatorModelId} onChange={(event) => setGeneratorModelId(event.target.value)} options={activeModels.map((model) => ({ value: model.id, label: `${model.name} · ${model.model}` }))} /></label><label className="space-y-2 text-xs text-muted"><span>Maximum total cost</span><Input type="number" step={0.01} value={maximumCost} onChange={(event) => setMaximumCost(event.target.value)} placeholder="Optional" /></label></div><div><p className="text-xs text-muted">Coverage</p><div className="mt-2 grid gap-2 sm:grid-cols-2">{Object.entries(coverageLabels).map(([key, text]) => <label key={key} className="flex items-center gap-2 rounded-lg border border-border px-3 py-2 text-xs text-muted"><input type="checkbox" checked={selectedCoverage.includes(key)} onChange={(event) => setSelectedCoverage((current) => event.target.checked ? [...current, key] : current.filter((item) => item !== key))} />{text}</label>)}</div></div><label className="block space-y-2 text-xs text-muted"><span>Negative/error cases: {errorRatio}%</span><input type="range" min={0} max={80} value={errorRatio} onChange={(event) => setErrorRatio(Number(event.target.value))} className="w-full" /></label></div> : null}
        </section>
        <section className="rounded-xl border border-primary/20 bg-primary/[0.04] p-4"><div className="flex flex-wrap items-center justify-between gap-3"><div><p className="text-sm font-semibold text-white">Automatic preview</p><p className="mt-1 text-xs text-muted">{caseCount} cases · {Math.ceil(caseCount / 10)} batches · {Object.entries(allocation).map(([key, count]) => `${coverageLabels[key]} ${count}`).join(' · ')}</p></div>{preview.isPending ? <Badge variant="outline">Calculating…</Badge> : previewData ? <Badge variant="outline">{previewData.estimated_cost_usd == null ? 'Cost unknown' : `~$${(previewData.estimated_cost_usd * Math.ceil(caseCount / 10)).toFixed(4)}`}</Badge> : null}</div></section>
        <div className="flex justify-end gap-2 border-t border-border pt-4"><Button variant="outline" onClick={() => setStep('method')}>Back</Button><Button loading={generate.isPending} disabled={!targetReady || !generatorModelId || objective.trim().length < 10 || !selectedCoverage.length} onClick={() => void startGeneration()}><Sparkles className="mr-2 h-4 w-4" />Generate Test Cases</Button></div>
      </div>
    )
  }

  if (step === 'json') {
    return <div className="mx-auto max-w-5xl space-y-5"><div className="flex items-start gap-3"><Button size="sm" variant="ghost" onClick={() => setStep('method')}><ArrowLeft className="h-4 w-4" /></Button><div><h3 className="text-base font-semibold text-white">Import Evaluator Suite JSON</h3><p className="mt-1 text-xs text-muted">Use the concrete example or upload a Git-versioned Suite.</p></div></div><div className="flex flex-wrap gap-2"><Button size="sm" variant="outline" onClick={() => setJsonText(evaluatorSuiteJsonExample)}>Insert valid example</Button><Button size="sm" variant="outline" disabled={!jsonText.trim()} onClick={() => { try { setJsonText(JSON.stringify(JSON.parse(jsonText), null, 2)) } catch (error) { toast.error(error instanceof Error ? error.message : 'Invalid JSON') } }}><Braces className="mr-2 h-4 w-4" />Format JSON</Button><Button size="sm" variant="outline" onClick={() => fileInputRef.current?.click()}><Upload className="mr-2 h-4 w-4" />Upload .json</Button><input ref={fileInputRef} type="file" accept="application/json,.json" className="hidden" onChange={(event) => { const file = event.target.files?.[0]; if (file) void file.text().then(setJsonText); event.target.value = '' }} /></div><textarea value={jsonText} onChange={(event) => setJsonText(event.target.value)} className="min-h-[440px] w-full rounded-xl border border-border bg-background p-4 font-mono text-xs leading-5 text-white outline-none focus:border-primary/40" placeholder={evaluatorSuiteJsonExample} spellCheck={false} /><div className="flex justify-end gap-2 border-t border-border pt-4"><Button variant="outline" onClick={() => setStep('method')}>Back</Button><Button loading={validate.isPending} disabled={!jsonText.trim()} onClick={() => void importJson()}><Braces className="mr-2 h-4 w-4" />Validate and review</Button></div></div>
  }

  return <div className="mx-auto max-w-6xl space-y-5"><div className="flex flex-wrap items-start justify-between gap-4"><div className="flex items-start gap-3"><Button size="sm" variant="ghost" onClick={() => setStep('method')}><ArrowLeft className="h-4 w-4" /></Button><div><div className="flex items-center gap-2"><h3 className="text-base font-semibold text-white">Review Evaluator Suite</h3><Badge variant="outline">{source.replaceAll('_', ' ')}</Badge></div><p className="mt-1 text-xs text-muted">Review is mandatory before the immutable version is created.</p></div></div><Button size="sm" variant="outline" loading={validate.isPending} onClick={() => void validateDraft()}>Validate all</Button></div>{validation ? <section className={cn('rounded-xl border p-4', validation.valid ? 'border-emerald-500/25 bg-emerald-500/[0.04]' : 'border-red-500/25 bg-red-500/[0.04]')}><p className="text-sm font-semibold text-white">{validation.valid ? `${validation.case_count} valid cases` : `${validation.errors.length} validation errors`}</p>{!validation.valid ? <p className="mt-1 text-xs text-muted">Cases with errors are marked in the navigator.</p> : null}</section> : null}<section className="grid gap-4 rounded-xl border border-border/80 bg-background/35 p-4 md:grid-cols-2"><label className="space-y-2 text-xs text-muted"><span>Suite name</span><Input value={suiteName} onChange={(event) => setSuiteName(event.target.value)} /></label><label className="space-y-2 text-xs text-muted"><span>Judge model</span><Select value={judgeModelId} onChange={(event) => setJudgeModelId(event.target.value)} options={activeModels.map((model) => ({ value: model.id, label: `${model.name} · ${model.model}` }))} /></label><label className="space-y-2 text-xs text-muted md:col-span-2"><span>Description</span><Input value={description} onChange={(event) => setDescription(event.target.value)} /></label><button type="button" onClick={() => setReviewAdvancedOpen((value) => !value)} className="md:col-span-2 flex items-center justify-between border-t border-border pt-3 text-left"><div><p className="text-xs font-medium text-white">Acceptance settings</p><p className="text-[10px] text-muted">Recommended defaults are already applied.</p></div><ChevronDown className={cn('h-4 w-4 text-muted transition-transform', reviewAdvancedOpen && 'rotate-180')} /></button>{reviewAdvancedOpen ? <><label className="space-y-2 text-xs text-muted"><span>Minimum score</span><Input type="number" min={0} max={100} value={minimumScore} onChange={(event) => setMinimumScore(Number(event.target.value))} /></label><label className="space-y-2 text-xs text-muted"><span>Minimum pass rate</span><Input type="number" min={0} max={100} value={minimumPassRate} onChange={(event) => setMinimumPassRate(Number(event.target.value))} /></label><label className="space-y-2 text-xs text-muted"><span>Default Runs per case</span><Input type="number" min={1} max={25} value={repetitions} onChange={(event) => setRepetitions(Number(event.target.value))} /></label><div className="rounded-lg border border-border/70 bg-surface/20 p-3 text-[11px] text-muted">Judge token budget is automatic and retries reasoning-model truncation without re-running the Agent.</div></> : null}</section><SuiteCaseWorkspace cases={draft.cases} validation={validation} onChange={(cases: EvaluationCaseInput[]) => { setDraft((current) => ({ ...current, cases })); setValidation(null) }} /><div className="flex justify-end gap-2 border-t border-border pt-4"><Button variant="outline" onClick={onCancel}>Cancel</Button><Button loading={create.isPending} onClick={() => void save()}>Create immutable Suite</Button></div></div>
}
