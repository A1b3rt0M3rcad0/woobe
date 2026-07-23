import { useEffect, useMemo, useRef, useState } from 'react'
import type { ReactNode } from 'react'
import {
  AlertTriangle,
  ArrowLeft,
  Braces,
  CheckCircle2,
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
import {
  SuiteCaseWorkspace,
  emptyCase,
  emptyOutcome,
} from '@/features/evaluations/components/SuiteCaseWorkspace'
import { SuiteGenerationProgress } from '@/features/evaluations/components/SuiteGenerationProgress'
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
  EvaluationInteractionMode,
  EvaluationSessionTurnInput,
  EvaluationSourceType,
  EvaluationSuite,
  EvaluationTargetInput,
  EvaluationTargetType,
  EvaluationTestStructure,
  EvaluatorSuiteDraft,
  SuiteAuthoringSource,
  SuiteContextPreview,
  SuiteValidationResult,
} from '@/features/evaluations/types'
import { useCreateComposedEvaluationSuiteVersion } from '@/features/evaluations/versionHooks'
import type { ProviderModel } from '@/features/provider-models/types'
import { cn } from '@/lib/utils'

type Step = 'method' | 'ai' | 'json' | 'progress' | 'editor'

type PreviewData = SuiteContextPreview & {
  estimated_batch_count?: number
  estimated_total_cost_usd?: number | null
  estimated_maximum_provider_calls?: number
}

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
  existingSuite?: EvaluationSuite | null
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

const negativeCoverage = new Set(['security_refusal', 'error_handling'])

function emptyDraft(): EvaluatorSuiteDraft {
  return { schema_version: 1, suite: {}, coverage: {}, cases: [emptyCase(1)] }
}

function listValue(value: unknown): string[] {
  if (Array.isArray(value)) return value.map(String).map((item) => item.trim()).filter(Boolean)
  if (typeof value === 'string' && value.trim()) return [value.trim()]
  return []
}

function normalizedTurns(source: Record<string, any>): EvaluationSessionTurnInput[] {
  const raw = Array.isArray(source.turns)
    ? source.turns
    : Array.isArray(source.session_turns)
      ? source.session_turns
      : []
  return raw
    .filter((item): item is Record<string, any> => Boolean(item && typeof item === 'object'))
    .map((turn, index) => ({
      position: index + 1,
      message: String(
        turn.message
        || turn.input_payload?.message
        || turn.input
        || '',
      ),
      expected_behavior: listValue(turn.expected_behavior ?? turn.required_behavior),
      forbidden_behavior: listValue(turn.forbidden_behavior),
    }))
}

function normalizeDraft(value: unknown): EvaluatorSuiteDraft {
  if (!value || typeof value !== 'object') throw new Error('JSON root must be an object')
  const raw = value as Record<string, any>
  if (!Array.isArray(raw.cases)) throw new Error('JSON must contain a cases array')
  if (!raw.cases.length) throw new Error('JSON must contain at least one Test Case')

  return {
    schema_version: Number(raw.schema_version || 1),
    suite: raw.suite && typeof raw.suite === 'object' ? raw.suite : {},
    coverage: raw.coverage && typeof raw.coverage === 'object' ? raw.coverage : {},
    cases: raw.cases.map((source: Record<string, any>, index: number) => {
      const type = (
        source.case_type
        || source.expected_outcome?.type
        || source.expected_contract?.expected_outcome?.type
        || 'success'
      ) as EvaluationCaseType
      const turns = normalizedTurns(source)
      const interactionMode = (
        source.interaction_mode
        || (turns.length ? 'session' : 'single_turn')
      ) as EvaluationInteractionMode
      const expectedSource = source.expected_outcome || source.expected_contract?.expected_outcome || {}
      const contractSource = source.expected_contract || {}
      const semanticSource = contractSource.semantic_criteria
        ?? source.semantic_criteria
        ?? source.expected_result
        ?? source.expected
      const toolsSource = contractSource.tools || {}
      return {
        ...emptyCase(index + 1, type),
        ...source,
        case_type: type,
        interaction_mode: interactionMode,
        message: String(
          source.message
          || source.input_payload?.message
          || turns[0]?.message
          || '',
        ),
        turns: interactionMode === 'session' ? turns : [],
        expected_outcome: {
          ...emptyOutcome(type),
          ...expectedSource,
          type,
          required_behavior: listValue(
            expectedSource.required_behavior
            ?? source.expected_behavior
            ?? source.required_behavior,
          ),
          forbidden_behavior: listValue(
            expectedSource.forbidden_behavior
            ?? source.forbidden_behavior,
          ),
          allowed_failure_origins: listValue(expectedSource.allowed_failure_origins),
          allowed_failure_stages: listValue(expectedSource.allowed_failure_stages),
          allowed_failure_codes: listValue(expectedSource.allowed_failure_codes),
        },
        expected_contract: {
          ...emptyCase(index + 1, type).expected_contract,
          ...contractSource,
          semantic_criteria: listValue(semanticSource),
          tools: {
            required: listValue(toolsSource.required),
            forbidden: listValue(toolsSource.forbidden),
          },
          output_contract: {
            required: type !== 'expected_failure',
            ...(contractSource.output_contract || {}),
          },
        },
        tags: listValue(source.tags),
      }
    }),
  }
}

function MethodCard({
  icon,
  title,
  description,
  onClick,
}: {
  icon: ReactNode
  title: string
  description: string
  onClick: () => void
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="rounded-xl border border-border/80 bg-background/40 p-5 text-left transition-colors hover:border-primary/35 hover:bg-primary/[0.04]"
    >
      <div className="flex h-10 w-10 items-center justify-center rounded-xl border border-primary/20 bg-primary/10 text-primary-light">
        {icon}
      </div>
      <h4 className="mt-4 text-sm font-semibold text-white">{title}</h4>
      <p className="mt-2 text-xs leading-5 text-muted">{description}</p>
    </button>
  )
}

function distribute(keys: string[], count: number, result: Record<string, number>) {
  if (!keys.length || count <= 0) return
  for (let index = 0; index < count; index += 1) {
    const key = keys[index % keys.length]
    result[key] = (result[key] || 0) + 1
  }
}

export function EvaluatorSuiteAuthoringWizard({
  projectId,
  targetType,
  entityId,
  targetName,
  versions,
  providerModels,
  existingSuite,
  onCancel,
  onCreated,
  initialSourceType = 'draft',
  initialVersionId = '',
}: Props) {
  const preview = usePreviewSuiteAuthoringContext(projectId)
  const generate = useGenerateEvaluatorSuite(projectId)
  const validate = useValidateEvaluatorSuite(projectId)
  const create = useCreateComposedEvaluatorSuite(projectId)
  const createVersion = useCreateComposedEvaluationSuiteVersion(projectId, existingSuite?.id)
  const cancelAuthoring = useCancelEvaluatorSuiteAuthoring(projectId)
  const retryAuthoring = useRetryEvaluatorSuiteAuthoring(projectId)
  const fileInputRef = useRef<HTMLInputElement>(null)

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
  const [judgeModelId, setJudgeModelId] = useState(existingSuite?.judge_provider_model_id || '')
  const [objective, setObjective] = useState('')
  const [caseCount, setCaseCount] = useState(existingSuite?.case_count || 20)
  const [errorRatio, setErrorRatio] = useState(30)
  const [maximumCost, setMaximumCost] = useState('')
  const [testStructure, setTestStructure] = useState<EvaluationTestStructure>('single_turn')
  const [minimumSessionTurns, setMinimumSessionTurns] = useState(2)
  const [maximumSessionTurns, setMaximumSessionTurns] = useState(5)
  const [selectedCoverage, setSelectedCoverage] = useState<string[]>(
    coverageOptions.map(([value]) => value),
  )
  const [suiteName, setSuiteName] = useState(existingSuite?.name || '')
  const [description, setDescription] = useState(existingSuite?.description || '')
  const [changeDescription, setChangeDescription] = useState('')
  const [minimumScore, setMinimumScore] = useState(
    Number(existingSuite?.acceptance_policy?.minimum_score ?? 70),
  )
  const [minimumPassRate, setMinimumPassRate] = useState(
    Number(existingSuite?.acceptance_policy?.minimum_pass_rate ?? 80),
  )
  const [repetitions, setRepetitions] = useState(
    Number(existingSuite?.repetition_policy?.default_repetitions ?? 3),
  )

  const activeModels = providerModels.filter((model) => model.status === 'active')
  const availableVersions = useMemo(
    () => versions.filter((item) => sourceType === 'staging'
      ? item.status === 'staging' || item.kind === 'staging'
      : item.snapshot_kind === 'release'
        || item.kind === 'release'
        || ['released', 'production', 'rolled_back'].includes(item.status)),
    [versions, sourceType],
  )
  const target: EvaluationTargetInput = {
    target_type: targetType,
    source_type: sourceType,
    entity_id: entityId,
    ...(sourceType !== 'draft' && versionId ? { version_id: versionId } : {}),
  }
  const targetReady = sourceType === 'draft' || Boolean(versionId)

  useEffect(() => {
    setSourceType(initialSourceType)
    setVersionId(initialVersionId)
  }, [initialSourceType, initialVersionId])

  useEffect(() => {
    if (!call || call.status !== 'completed' || !call.draft || !call.validation?.valid) return
    setDraft({ ...call.draft, cases: call.validation.cases })
    setValidation(call.validation)
    setSource('ai_generated')
    if (!existingSuite) {
      setSuiteName(call.draft.suite?.suggested_name || `${targetName} qualification`)
      setDescription(call.draft.suite?.description || objective)
    }
    if (!judgeModelId) setJudgeModelId(generatorModelId)
    setStep('editor')
  }, [call?.status])

  const allocation = useMemo(() => {
    const positiveKeys = selectedCoverage.filter((key) => !negativeCoverage.has(key))
    const negativeKeys = selectedCoverage.filter((key) => negativeCoverage.has(key))
    let negativeCount = negativeKeys.length ? Math.round(caseCount * errorRatio / 100) : 0
    if (!positiveKeys.length) negativeCount = caseCount
    if (!negativeKeys.length) negativeCount = 0
    const positiveCount = caseCount - negativeCount
    const result: Record<string, number> = {}
    distribute(positiveKeys, positiveCount, result)
    distribute(negativeKeys, negativeCount, result)
    return result
  }, [caseCount, errorRatio, selectedCoverage])

  const previewData = preview.data as PreviewData | undefined
  const estimatedBatchCount = previewData?.estimated_batch_count ?? Math.ceil(caseCount / 10)
  const estimatedTotalCost = previewData?.estimated_total_cost_usd
    ?? (previewData?.estimated_cost_usd == null
      ? null
      : previewData.estimated_cost_usd * estimatedBatchCount)

  const validateDraft = async (value = draft) => {
    const result = await validate.mutateAsync({ draft: value, reference_target: target })
    setValidation(result)
    if (result.valid) {
      setDraft((current) => ({ ...current, ...value, cases: result.cases }))
    }
    return result
  }

  const importJson = async () => {
    try {
      const imported = normalizeDraft(JSON.parse(jsonText))
      const result = await validateDraft(imported)
      setDraft(result.valid ? { ...imported, cases: result.cases } : imported)
      setSource('json_import')
      if (!existingSuite) {
        setSuiteName(imported.suite?.suggested_name || '')
        setDescription(imported.suite?.description || '')
      }
      setObjective(imported.suite?.objective || objective)
      setStep('editor')
      if (!result.valid) toast.error('JSON imported with validation errors. Review the marked cases.')
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Invalid JSON')
    }
  }

  const formatJson = () => {
    try {
      setJsonText(JSON.stringify(JSON.parse(jsonText), null, 2))
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Invalid JSON')
    }
  }

  const uploadJson = async (file?: File) => {
    if (!file) return
    try {
      setJsonText(await file.text())
      toast.success(`${file.name} loaded`)
    } catch {
      toast.error('Unable to read JSON file')
    }
  }

  const startGeneration = async () => {
    if (!targetReady || !generatorModelId || objective.trim().length < 10) {
      toast.error('Choose a target, generator model and objective')
      return
    }
    if (!selectedCoverage.length) {
      toast.error('Select at least one coverage category')
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
        test_structure: testStructure,
        minimum_session_turns: minimumSessionTurns,
        maximum_session_turns: maximumSessionTurns,
      })
      setAuthoringCallId(queued.authoring_call_id)
      setStep('progress')
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Unable to queue generation')
    }
  }

  const save = async () => {
    if (!suiteName.trim() || !judgeModelId) {
      toast.error('Suite name and Judge model are required')
      return
    }
    if (existingSuite && changeDescription.trim().length < 3) {
      toast.error('Describe what changed in this Suite version')
      return
    }
    try {
      const result = await validateDraft()
      if (!result.valid) {
        toast.error('Fix validation errors before saving')
        return
      }
      const common = {
        judge_provider_model_id: judgeModelId,
        draft: { ...draft, cases: result.cases },
        judge_config: {
          temperature: 0,
          max_tokens: 800,
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
          ...(call
            ? {
                authoring_call_id: call.authoring_call_id,
                generator: call.generator,
                context_budget: call.context_budget,
              }
            : {}),
          reference_target: target,
          objective,
        },
      } as const
      const suite = existingSuite
        ? await createVersion.mutateAsync({
            ...common,
            change_description: changeDescription.trim(),
          })
        : await create.mutateAsync({
            ...common,
            name: suiteName.trim(),
            description: description.trim(),
            target_type: targetType,
          })
      toast.success(existingSuite ? 'Evaluator Suite version created' : 'Evaluator Suite created')
      onCreated(suite)
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Unable to save Evaluator Suite')
    }
  }

  if (step === 'progress') {
    if (!call) {
      return (
        <div className="flex min-h-64 items-center justify-center">
          <Loader2 className="h-5 w-5 animate-spin text-primary-light" />
        </div>
      )
    }
    return (
      <SuiteGenerationProgress
        call={call}
        cancelling={cancelAuthoring.isPending}
        retrying={retryAuthoring.isPending}
        onCancel={() => {
          void cancelAuthoring.mutateAsync(call.authoring_call_id).catch((error) => {
            toast.error(error instanceof Error ? error.message : 'Unable to cancel generation')
          })
        }}
        onRetry={() => {
          void retryAuthoring.mutateAsync(call.authoring_call_id).then(() => {
            toast.success('Eligible batches queued for repair')
          }).catch((error) => {
            toast.error(error instanceof Error ? error.message : 'Unable to retry generation')
          })
        }}
        onChangeSettings={() => setStep('ai')}
      />
    )
  }

  if (step === 'method') {
    return (
      <div className="mx-auto max-w-4xl space-y-5">
        <div>
          <h3 className="text-base font-semibold text-white">
            {existingSuite
              ? `Create a new version of ${existingSuite.name}`
              : 'Create Evaluator Suite'}
          </h3>
          <p className="mt-1 text-xs text-muted">
            Every method ends in the same target-bound review editor.
          </p>
        </div>
        <div className="grid gap-4 md:grid-cols-3">
          <MethodCard
            icon={<WandSparkles className="h-5 w-5" />}
            title="Generate with AI"
            description={`Analyze an exact ${targetType} snapshot and generate single-turn, Session or mixed validated Test Cases.`}
            onClick={() => setStep('ai')}
          />
          <MethodCard
            icon={<FileJson className="h-5 w-5" />}
            title="Import JSON"
            description="Insert an example, upload a file or validate a Git-versioned Suite against the snapshot. Session turns are part of the same schema."
            onClick={() => setStep('json')}
          />
          <MethodCard
            icon={<Plus className="h-5 w-5" />}
            title="Create manually"
            description="Create single-turn or multi-turn Session Tests in the same compact case navigator."
            onClick={() => {
              setSource('manual')
              setDraft(emptyDraft())
              setValidation(null)
              setStep('editor')
            }}
          />
        </div>
        <div className="flex justify-end border-t border-border pt-4">
          <Button variant="outline" onClick={onCancel}>Cancel</Button>
        </div>
      </div>
    )
  }

  if (step === 'json') {
    return (
      <div className="mx-auto max-w-5xl space-y-5">
        <div className="flex items-start gap-3">
          <Button size="sm" variant="ghost" onClick={() => setStep('method')}>
            <ArrowLeft className="h-4 w-4" />
          </Button>
          <div>
            <h3 className="text-base font-semibold text-white">Import Evaluator Suite JSON</h3>
            <p className="mt-1 text-xs text-muted">
              Lists, Session turns, expected outcomes and concrete Tool references are normalized and validated against the reference snapshot.
            </p>
          </div>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button size="sm" variant="outline" onClick={() => setJsonText(evaluatorSuiteJsonExample)}>
            Insert valid example
          </Button>
          <Button size="sm" variant="outline" disabled={!jsonText.trim()} onClick={formatJson}>
            <Braces className="mr-2 h-4 w-4" />Format JSON
          </Button>
          <Button size="sm" variant="outline" onClick={() => fileInputRef.current?.click()}>
            <Upload className="mr-2 h-4 w-4" />Upload .json
          </Button>
          <input
            ref={fileInputRef}
            type="file"
            accept="application/json,.json"
            className="hidden"
            onChange={(event) => {
              void uploadJson(event.target.files?.[0])
              event.target.value = ''
            }}
          />
        </div>
        <textarea
          value={jsonText}
          onChange={(event) => setJsonText(event.target.value)}
          className="min-h-[440px] w-full rounded-xl border border-border bg-background p-4 font-mono text-xs leading-5 text-white outline-none focus:border-primary/40"
          placeholder={evaluatorSuiteJsonExample}
          spellCheck={false}
        />
        <div className="flex justify-end gap-2 border-t border-border pt-4">
          <Button variant="outline" onClick={() => setStep('method')}>Back</Button>
          <Button
            loading={validate.isPending}
            disabled={!jsonText.trim()}
            onClick={() => void importJson()}
          >
            <Braces className="mr-2 h-4 w-4" />Validate and review
          </Button>
        </div>
      </div>
    )
  }

  if (step === 'ai') {
    return (
      <div className="mx-auto max-w-5xl space-y-5">
        <div className="flex items-start gap-3">
          <Button size="sm" variant="ghost" onClick={() => setStep('method')}>
            <ArrowLeft className="h-4 w-4" />
          </Button>
          <div>
            <h3 className="text-base font-semibold text-white">Generate with AI</h3>
            <p className="mt-1 text-xs text-muted">
              The model receives the exact sanitized snapshot and must satisfy the canonical single-turn / Session Test schema.
            </p>
          </div>
        </div>

        <section className="rounded-xl border border-border/80 bg-background/35 p-4">
          <div className="grid gap-4 md:grid-cols-2">
            <label className="space-y-2 text-xs text-muted">
              <span>Environment</span>
              <Select
                value={sourceType}
                onChange={(event) => {
                  setSourceType(event.target.value as EvaluationSourceType)
                  setVersionId('')
                  preview.reset()
                }}
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
                disabled={sourceType === 'draft'}
                value={versionId}
                onChange={(event) => setVersionId(event.target.value)}
                options={[
                  {
                    value: '',
                    label: sourceType === 'draft'
                      ? 'Current Draft will be frozen'
                      : 'Select exact snapshot',
                  },
                  ...availableVersions.map((item) => ({
                    value: item.id,
                    label: `${item.version} · ${item.status}`,
                  })),
                ]}
              />
            </label>
            <label className="space-y-2 text-xs text-muted">
              <span>Generator model</span>
              <Select
                value={generatorModelId}
                onChange={(event) => setGeneratorModelId(event.target.value)}
                options={[
                  { value: '', label: 'Select BYOK model' },
                  ...activeModels.map((model) => ({
                    value: model.id,
                    label: `${model.name} · ${model.model}`,
                  })),
                ]}
              />
            </label>
            <label className="space-y-2 text-xs text-muted">
              <span>Number of cases</span>
              <Input
                type="number"
                min={5}
                max={50}
                value={caseCount}
                onChange={(event) => setCaseCount(
                  Math.max(5, Math.min(50, Number(event.target.value))),
                )}
              />
            </label>
          </div>

          <div className="mt-4 grid gap-4 md:grid-cols-3">
            <label className="space-y-2 text-xs text-muted">
              <span>Test structure</span>
              <Select
                value={testStructure}
                onChange={(event) => setTestStructure(event.target.value as EvaluationTestStructure)}
                options={[
                  { value: 'single_turn', label: 'Single-turn only' },
                  { value: 'session', label: 'Session only' },
                  { value: 'mixed', label: 'Mixed · single-turn + Session' },
                ]}
              />
            </label>
            <label className="space-y-2 text-xs text-muted">
              <span>Minimum turns / Session</span>
              <Input
                type="number"
                min={2}
                max={10}
                disabled={testStructure === 'single_turn'}
                value={minimumSessionTurns}
                onChange={(event) => {
                  const value = Math.max(2, Math.min(10, Number(event.target.value)))
                  setMinimumSessionTurns(value)
                  setMaximumSessionTurns((current) => Math.max(current, value))
                }}
              />
            </label>
            <label className="space-y-2 text-xs text-muted">
              <span>Maximum turns / Session</span>
              <Input
                type="number"
                min={2}
                max={20}
                disabled={testStructure === 'single_turn'}
                value={maximumSessionTurns}
                onChange={(event) => setMaximumSessionTurns(
                  Math.max(minimumSessionTurns, Math.min(20, Number(event.target.value))),
                )}
              />
            </label>
          </div>
          {testStructure !== 'single_turn' ? (
            <p className="mt-3 text-[10px] leading-4 text-muted">
              One Session Test is one Trial containing an ordered conversation. Every repetition starts a new isolated Agent or Network session and one Judge evaluates the complete transcript.
            </p>
          ) : null}

          <label className="mt-4 block space-y-2 text-xs text-muted">
            <span>Test objective</span>
            <textarea
              value={objective}
              onChange={(event) => setObjective(event.target.value)}
              placeholder="Example: Validate billing support accuracy, safe refusal, context retention, correct Tool usage and behavior when required data is missing."
              className="min-h-28 w-full rounded-lg border border-border bg-background px-3 py-2 text-sm text-white outline-none focus:border-primary/40"
            />
          </label>

          <div className="mt-4">
            <p className="text-xs text-muted">Coverage categories</p>
            <div className="mt-2 grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
              {coverageOptions.map(([value, label]) => {
                const checked = selectedCoverage.includes(value)
                return (
                  <label
                    key={value}
                    className={cn(
                      'flex items-center gap-2 rounded-lg border px-3 py-2 text-xs',
                      checked
                        ? 'border-primary/30 bg-primary/[0.06] text-white'
                        : 'border-border bg-background text-muted',
                    )}
                  >
                    <input
                      type="checkbox"
                      checked={checked}
                      onChange={(event) => setSelectedCoverage((current) => (
                        event.target.checked
                          ? [...current, value]
                          : current.filter((item) => item !== value)
                      ))}
                    />
                    {label}
                  </label>
                )
              })}
            </div>
          </div>

          <div className="mt-4 grid gap-4 md:grid-cols-2">
            <label className="space-y-2 text-xs text-muted">
              <span>Negative/error cases (%)</span>
              <Input
                type="number"
                min={0}
                max={80}
                value={errorRatio}
                disabled={!selectedCoverage.some((key) => negativeCoverage.has(key))}
                onChange={(event) => setErrorRatio(
                  Math.max(0, Math.min(80, Number(event.target.value))),
                )}
              />
            </label>
            <label className="space-y-2 text-xs text-muted">
              <span>Maximum total cost (USD)</span>
              <Input
                type="number"
                min={0}
                step={0.01}
                value={maximumCost}
                onChange={(event) => setMaximumCost(event.target.value)}
                placeholder="Optional"
              />
            </label>
          </div>

          <div className="mt-4 rounded-lg border border-border/70 bg-surface/25 p-3">
            <p className="text-[10px] font-medium uppercase text-muted">Effective distribution</p>
            <div className="mt-2 flex flex-wrap gap-2">
              {Object.entries(allocation).map(([key, count]) => (
                <Badge key={key} variant="outline">
                  {coverageOptions.find(([value]) => value === key)?.[1] || key}: {count}
                </Badge>
              ))}
              <Badge variant="outline">Structure: {testStructure.replaceAll('_', ' ')}</Badge>
            </div>
          </div>
        </section>

        {previewData ? (
          <section className="rounded-xl border border-primary/25 bg-primary/[0.04] p-4">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <p className="text-sm font-semibold text-white">Generation preview</p>
                <p className="mt-1 text-xs text-muted">
                  {estimatedBatchCount} batches · up to {previewData.estimated_maximum_provider_calls || estimatedBatchCount * 2} provider calls including repair
                </p>
              </div>
              <Badge variant="outline">
                {previewData.context_budget.truncation_applied ? 'context compacted' : 'full selected context'}
              </Badge>
            </div>
            <div className="mt-4 grid gap-3 sm:grid-cols-3">
              <div>
                <p className="text-[9px] uppercase text-muted">Input per batch</p>
                <p className="mt-1 text-sm text-white">
                  {previewData.context_budget.estimated_input_tokens.toLocaleString()} tokens
                </p>
              </div>
              <div>
                <p className="text-[9px] uppercase text-muted">Estimated total</p>
                <p className="mt-1 text-sm text-white">
                  {estimatedTotalCost == null ? 'Unknown cost' : `$${estimatedTotalCost.toFixed(4)}`}
                </p>
              </div>
              <div>
                <p className="text-[9px] uppercase text-muted">Context window</p>
                <p className="mt-1 text-sm text-white">
                  {previewData.context_window.toLocaleString()} tokens
                </p>
              </div>
            </div>
            {previewData.context_budget.truncated_sections.length ? (
              <p className="mt-3 text-[10px] text-amber-300/80">
                Compacted sections: {previewData.context_budget.truncated_sections.join(', ')}
              </p>
            ) : null}
          </section>
        ) : null}

        <div className="flex justify-end gap-2 border-t border-border pt-4">
          <Button variant="outline" onClick={() => setStep('method')}>Back</Button>
          <Button
            variant="outline"
            loading={preview.isPending}
            disabled={!targetReady || !generatorModelId || objective.trim().length < 10 || !selectedCoverage.length}
            onClick={() => void preview.mutateAsync({
              target,
              generator_provider_model_id: generatorModelId,
              objective,
              case_count: caseCount,
              maximum_input_tokens: 16000,
            }).catch((error) => {
              toast.error(error instanceof Error ? error.message : 'Unable to preview generation')
            })}
          >
            Preview
          </Button>
          <Button
            loading={generate.isPending}
            disabled={!targetReady || !generatorModelId || objective.trim().length < 10 || !selectedCoverage.length}
            onClick={() => void startGeneration()}
          >
            <Sparkles className="mr-2 h-4 w-4" />Generate cases
          </Button>
        </div>
      </div>
    )
  }

  return (
    <div className="mx-auto max-w-6xl space-y-5">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="flex items-start gap-3">
          <Button size="sm" variant="ghost" onClick={() => setStep('method')}>
            <ArrowLeft className="h-4 w-4" />
          </Button>
          <div>
            <div className="flex items-center gap-2">
              <h3 className="text-base font-semibold text-white">Review Evaluator Suite</h3>
              <Badge variant="outline">{source.replaceAll('_', ' ')}</Badge>
            </div>
            <p className="mt-1 text-xs text-muted">
              Review is mandatory before an immutable version is created.
            </p>
          </div>
        </div>
        <Button
          size="sm"
          variant="outline"
          loading={validate.isPending}
          onClick={() => void validateDraft()}
        >
          Validate all
        </Button>
      </div>

      {validation ? (
        <section className={cn(
          'rounded-xl border p-4',
          validation.valid
            ? 'border-emerald-500/25 bg-emerald-500/[0.04]'
            : 'border-red-500/25 bg-red-500/[0.04]',
        )}>
          <div className="flex flex-wrap items-center gap-2">
            {validation.valid ? (
              <CheckCircle2 className="h-4 w-4 text-emerald-300" />
            ) : (
              <AlertTriangle className="h-4 w-4 text-red-300" />
            )}
            <p className="text-sm font-semibold text-white">
              {validation.valid
                ? `${validation.case_count} valid cases`
                : `${validation.errors.length} validation errors`}
            </p>
            {validation.interaction_coverage ? (
              <>
                <Badge variant="outline">{validation.interaction_coverage.single_turn || 0} single-turn</Badge>
                <Badge variant="outline">{validation.interaction_coverage.session || 0} Session</Badge>
              </>
            ) : null}
          </div>
          {!validation.valid ? (
            <p className="mt-2 text-xs text-muted">
              Cases with errors are marked in the navigator. Select one to edit it.
            </p>
          ) : null}
          {validation.warnings.length ? (
            <details className="mt-3 text-xs text-amber-300/80">
              <summary className="cursor-pointer">
                {validation.warnings.length} normalization or coverage warnings
              </summary>
              <div className="mt-2 space-y-1">
                {validation.warnings.map((item, index) => (
                  <p key={index}>{item.path ? `${item.path}: ` : ''}{item.message}</p>
                ))}
              </div>
            </details>
          ) : null}
        </section>
      ) : null}

      <section className="grid gap-4 rounded-xl border border-border/80 bg-background/35 p-4 md:grid-cols-2">
        <label className="space-y-2 text-xs text-muted">
          <span>Suite name</span>
          <Input
            value={suiteName}
            disabled={Boolean(existingSuite)}
            onChange={(event) => setSuiteName(event.target.value)}
          />
        </label>
        <label className="space-y-2 text-xs text-muted">
          <span>Judge model</span>
          <Select
            value={judgeModelId}
            onChange={(event) => setJudgeModelId(event.target.value)}
            options={[
              { value: '', label: 'Select BYOK model' },
              ...activeModels.map((model) => ({
                value: model.id,
                label: `${model.name} · ${model.model}`,
              })),
            ]}
          />
        </label>
        <label className="space-y-2 text-xs text-muted md:col-span-2">
          <span>Description</span>
          <Input
            value={description}
            disabled={Boolean(existingSuite)}
            onChange={(event) => setDescription(event.target.value)}
          />
        </label>
        {existingSuite ? (
          <label className="space-y-2 text-xs text-muted md:col-span-2">
            <span>What changed in this Suite version</span>
            <Input
              value={changeDescription}
              onChange={(event) => setChangeDescription(event.target.value)}
              placeholder="Regenerate cases for the current Agent snapshot"
            />
          </label>
        ) : null}
      </section>

      <SuiteCaseWorkspace
        cases={draft.cases}
        validation={validation}
        onChange={(cases: EvaluationCaseInput[]) => {
          setDraft((current) => ({ ...current, cases }))
          setValidation(null)
        }}
      />

      <details className="rounded-xl border border-border/80 bg-background/35 p-4">
        <summary className="cursor-pointer text-sm font-medium text-white">
          Evaluation acceptance and repetition policy
        </summary>
        <div className="mt-4 grid gap-4 sm:grid-cols-3">
          <label className="space-y-2 text-xs text-muted">
            <span>Minimum score</span>
            <Input
              type="number"
              min={0}
              max={100}
              value={minimumScore}
              onChange={(event) => setMinimumScore(Number(event.target.value))}
            />
          </label>
          <label className="space-y-2 text-xs text-muted">
            <span>Minimum pass rate</span>
            <Input
              type="number"
              min={0}
              max={100}
              value={minimumPassRate}
              onChange={(event) => setMinimumPassRate(Number(event.target.value))}
            />
          </label>
          <label className="space-y-2 text-xs text-muted">
            <span>Repetitions per Test Case</span>
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
        </div>
        <p className="mt-3 text-[10px] text-muted">
          For Session Tests, one repetition means one complete isolated conversation, not one individual turn.
        </p>
      </details>

      <div className="sticky bottom-0 flex flex-wrap items-center justify-between gap-3 border-t border-border bg-surface/95 py-4 backdrop-blur">
        <p className="text-xs text-muted">
          {draft.cases.length} cases
          {validation ? ` · ${validation.case_count} valid · ${validation.errors.length} errors` : ' · not validated'}
        </p>
        <div className="flex gap-2">
          <Button variant="outline" onClick={onCancel}>Cancel</Button>
          <Button
            loading={create.isPending || createVersion.isPending}
            onClick={() => void save()}
          >
            <Sparkles className="mr-2 h-4 w-4" />
            {existingSuite ? 'Create immutable version' : 'Create immutable Suite'}
          </Button>
        </div>
      </div>
    </div>
  )
}
