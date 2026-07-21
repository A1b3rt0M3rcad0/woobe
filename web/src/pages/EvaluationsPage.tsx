import { useEffect, useMemo, useState } from 'react'
import {
  Activity,
  ArrowRight,
  BarChart3,
  Beaker,
  Bot,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  Clock3,
  Database,
  GitCompareArrows,
  Play,
  Plus,
  RefreshCw,
  ShieldAlert,
  Sparkles,
  Workflow,
  XCircle,
} from 'lucide-react'
import { useParams } from 'react-router-dom'
import { toast } from 'sonner'

import { ErrorState } from '@/components/common/ErrorState'
import { LoadingState } from '@/components/common/LoadingState'
import {
  ResourceEmptyState,
  ResourcePage,
  ResourceSearch,
  ResourceSectionHeader,
  ResourceTabs,
  ResourceToolbar,
} from '@/components/common/ResourcePage'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { Dialog } from '@/components/ui/Dialog'
import { Input } from '@/components/ui/Input'
import { JsonCodeBlock } from '@/components/ui/JsonCodeBlock'
import { Select } from '@/components/ui/Select'
import { useAgents, useReleases } from '@/features/agents/hooks'
import {
  useCancelEvaluationRun,
  useCreateEvaluationDataset,
  useCreateEvaluationDatasetVersion,
  useCreateEvaluationRun,
  useCreateEvaluationSuite,
  useCreateEvaluationSuiteVersion,
  useEvaluationDataset,
  useEvaluationDatasets,
  useEvaluationRun,
  useEvaluationRuns,
  useEvaluationSuites,
  usePreviewEvaluationRun,
} from '@/features/evaluations/hooks'
import type {
  CreateEvaluationRunInput,
  EvaluationDataset,
  EvaluationRun,
  EvaluationSourceType,
  EvaluationSuite,
  EvaluationTargetInput,
  EvaluationTargetType,
  EvaluationTrial,
} from '@/features/evaluations/types'
import { useNetworks, useNetworkVersions } from '@/features/network/hooks'
import { useProviderModels } from '@/features/provider-models/hooks'


type Tab = 'runs' | 'suites' | 'datasets'
type CaseDraft = {
  name: string
  message: string
  expected: string
  severity: 'low' | 'normal' | 'high' | 'critical'
  weight: number
  blocking: boolean
  productionFrequency: string
}

const terminalStatuses = new Set(['completed', 'partially_completed', 'failed', 'cancelled'])
const emptyCase = (name = 'Primary behavior'): CaseDraft => ({
  name,
  message: '',
  expected: '',
  severity: 'normal',
  weight: 1,
  blocking: false,
  productionFrequency: '',
})

function formatDate(value?: string | null) {
  if (!value) return '—'
  return new Intl.DateTimeFormat('en-US', {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  }).format(new Date(value))
}

function formatScore(value?: number | null) {
  return value === null || value === undefined ? '—' : value.toFixed(1)
}

function formatCost(value?: number | null) {
  if (value === null || value === undefined) return 'Unknown'
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: value < 0.01 ? 4 : 2,
  }).format(value)
}

function qualificationClasses(status?: string | null) {
  if (status === 'qualified') return 'border-emerald-500/30 bg-emerald-500/10 text-emerald-300'
  if (status === 'qualified_with_warnings') return 'border-amber-500/30 bg-amber-500/10 text-amber-300'
  if (status === 'not_qualified') return 'border-red-500/30 bg-red-500/10 text-red-300'
  return 'border-border bg-background/45 text-muted'
}

function riskClasses(risk: string) {
  if (risk === 'high') return 'border-red-500/30 bg-red-500/10 text-red-300'
  if (risk === 'medium') return 'border-amber-500/30 bg-amber-500/10 text-amber-300'
  return 'border-emerald-500/25 bg-emerald-500/10 text-emerald-300'
}

function statusLabel(status?: string | null) {
  if (!status) return 'Unknown'
  return status.split('_').map((part) => part.charAt(0).toUpperCase() + part.slice(1)).join(' ')
}

function asRecord(value: unknown): Record<string, any> {
  return value && typeof value === 'object' && !Array.isArray(value)
    ? value as Record<string, any>
    : {}
}

function casePayload(cases: CaseDraft[]) {
  return cases.map((item) => ({
    name: item.name,
    message: item.message,
    expected_contract: {
      semantic_criteria: item.expected ? [item.expected] : [],
      output_contract: { required: true },
    },
    severity: item.severity,
    weight: item.weight,
    blocking: item.blocking,
    production_frequency: item.productionFrequency === '' ? null : Number(item.productionFrequency),
  }))
}

function MetricCard({ label, value, detail, icon }: { label: string; value: string; detail?: string; icon: React.ReactNode }) {
  return (
    <div className="rounded-xl border border-border/80 bg-surface/45 p-4">
      <div className="flex items-center gap-2 text-xs text-muted">{icon}<span>{label}</span></div>
      <p className="mt-3 text-2xl font-semibold tracking-tight text-white">{value}</p>
      {detail ? <p className="mt-1 text-[11px] text-muted">{detail}</p> : null}
    </div>
  )
}

function RunCard({ run, onOpen }: { run: EvaluationRun; onOpen: () => void }) {
  const candidate = run.targets.find((target) => target.side === 'candidate' || target.side === 'single')
  const baseline = run.targets.find((target) => target.side === 'baseline')
  const active = !terminalStatuses.has(run.status)
  return (
    <button
      type="button"
      onClick={onOpen}
      className="w-full rounded-xl border border-border/80 bg-surface/45 p-4 text-left transition-colors hover:border-primary/30 hover:bg-surface/65"
    >
      <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-mono text-xs text-primary-light">{run.id.slice(0, 8)}</span>
            <Badge variant="outline" className={qualificationClasses(run.qualification_status)}>
              {run.qualification_status ? statusLabel(run.qualification_status) : statusLabel(run.status)}
            </Badge>
            {active ? <RefreshCw className="h-3.5 w-3.5 animate-spin text-primary-light" /> : null}
          </div>
          <div className="mt-3 flex flex-wrap items-center gap-2 text-sm text-white">
            <span className="font-medium">{candidate?.display_name ?? 'Target'}</span>
            <span className="rounded-md border border-border bg-background/45 px-2 py-1 text-[11px] text-muted">{candidate?.display_version ?? 'Unknown version'}</span>
            {baseline ? <><ArrowRight className="h-3.5 w-3.5 text-muted" /><span className="rounded-md border border-border bg-background/45 px-2 py-1 text-[11px] text-muted">{baseline.display_version}</span></> : null}
          </div>
          <p className="mt-2 text-xs text-muted">{run.mode === 'comparison' ? 'Paired version comparison' : 'Absolute qualification'} · {run.repetitions} repetition{run.repetitions === 1 ? '' : 's'} · {formatDate(run.created_at)}</p>
        </div>
        <div className="grid grid-cols-3 gap-5 lg:min-w-[310px]">
          <div><p className="text-[10px] uppercase tracking-wide text-muted">Score</p><p className="mt-1 text-lg font-semibold text-white">{formatScore(run.overall_score)}</p></div>
          <div><p className="text-[10px] uppercase tracking-wide text-muted">Pass rate</p><p className="mt-1 text-lg font-semibold text-white">{run.pass_rate === null ? '—' : `${run.pass_rate.toFixed(1)}%`}</p></div>
          <div><p className="text-[10px] uppercase tracking-wide text-muted">Measured</p><p className="mt-1 text-sm font-semibold text-white">{formatCost(run.measured_total_cost)}</p></div>
        </div>
      </div>
    </button>
  )
}

function CaseEditor({ cases, onChange }: { cases: CaseDraft[]; onChange: (cases: CaseDraft[]) => void }) {
  const patch = (index: number, values: Partial<CaseDraft>) => onChange(cases.map((item, position) => position === index ? { ...item, ...values } : item))
  return (
    <div>
      <ResourceSectionHeader title="Test Cases" description="Each case is frozen into an immutable Dataset version." count={cases.length} />
      <div className="space-y-3">
        {cases.map((item, index) => (
          <div key={`${index}-${item.name}`} className="rounded-xl border border-border/80 bg-background/35 p-4">
            <div className="flex items-center justify-between gap-3">
              <p className="text-xs font-semibold text-white">Case {index + 1}</p>
              {cases.length > 1 ? <Button size="sm" variant="ghost" onClick={() => onChange(cases.filter((_, position) => position !== index))}>Remove</Button> : null}
            </div>
            <div className="mt-3 grid gap-3 md:grid-cols-2">
              <Input value={item.name} onChange={(event) => patch(index, { name: event.target.value })} placeholder="Case name" />
              <Select value={item.severity} onChange={(event) => patch(index, { severity: event.target.value as CaseDraft['severity'] })} options={[{ value: 'low', label: 'Low severity' }, { value: 'normal', label: 'Normal severity' }, { value: 'high', label: 'High severity' }, { value: 'critical', label: 'Critical severity' }]} />
            </div>
            <textarea value={item.message} onChange={(event) => patch(index, { message: event.target.value })} placeholder="Input message sent to the Agent or Network" className="mt-3 min-h-24 w-full rounded-lg border border-border bg-background px-3 py-2 text-sm text-white outline-none transition-colors placeholder:text-muted focus:border-primary/50" />
            <textarea value={item.expected} onChange={(event) => patch(index, { expected: event.target.value })} placeholder="Expected behavior for the LLM judge" className="mt-3 min-h-20 w-full rounded-lg border border-border bg-background px-3 py-2 text-sm text-white outline-none transition-colors placeholder:text-muted focus:border-primary/50" />
            <div className="mt-3 grid gap-3 sm:grid-cols-3">
              <label className="space-y-2 text-xs text-muted"><span>Weight</span><Input type="number" min={0.1} max={100} step={0.1} value={item.weight} onChange={(event) => patch(index, { weight: Math.max(0.1, Number(event.target.value)) })} /></label>
              <label className="space-y-2 text-xs text-muted"><span>Production frequency</span><Input type="number" min={0} max={1} step={0.01} value={item.productionFrequency} onChange={(event) => patch(index, { productionFrequency: event.target.value })} placeholder="Optional 0–1" /></label>
              <label className="flex items-end gap-2 pb-2 text-xs text-muted"><input type="checkbox" checked={item.blocking} onChange={(event) => patch(index, { blocking: event.target.checked })} className="h-4 w-4 rounded border-border bg-background" /><span>Blocking case</span></label>
            </div>
          </div>
        ))}
      </div>
      <Button variant="outline" className="mt-3" onClick={() => onChange([...cases, emptyCase(`Case ${cases.length + 1}`)])}><Plus className="mr-2 h-4 w-4" />Add case</Button>
    </div>
  )
}

function DatasetDialog({ projectId, open, onClose }: { projectId: string; open: boolean; onClose: () => void }) {
  const createDataset = useCreateEvaluationDataset(projectId)
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [cases, setCases] = useState<CaseDraft[]>([emptyCase()])
  const submit = async () => {
    try {
      await createDataset.mutateAsync({ name, description, change_description: 'Initial Dataset version', cases: casePayload(cases) })
      toast.success('Evaluation Dataset created')
      setName(''); setDescription(''); setCases([emptyCase()]); onClose()
    } catch (error) { toast.error(error instanceof Error ? error.message : 'Failed to create Dataset') }
  }
  return (
    <Dialog open={open} onClose={onClose} title="Create Evaluation Dataset" className="max-w-4xl" scrollMode="content">
      <div className="space-y-5">
        <div className="grid gap-4 md:grid-cols-2">
          <label className="space-y-2 text-xs text-muted"><span>Name</span><Input value={name} onChange={(event) => setName(event.target.value)} placeholder="Support regression" /></label>
          <label className="space-y-2 text-xs text-muted"><span>Description</span><Input value={description} onChange={(event) => setDescription(event.target.value)} placeholder="Critical production behaviors" /></label>
        </div>
        <CaseEditor cases={cases} onChange={setCases} />
        <div className="flex justify-end gap-2 border-t border-border pt-4"><Button variant="ghost" onClick={onClose}>Cancel</Button><Button loading={createDataset.isPending} disabled={!name.trim() || cases.some((item) => !item.message.trim())} onClick={submit}>Create Dataset</Button></div>
      </div>
    </Dialog>
  )
}

function DatasetDetailsDialog({ projectId, datasetId, onClose }: { projectId: string; datasetId: string | null; onClose: () => void }) {
  const query = useEvaluationDataset(projectId, datasetId)
  const createVersion = useCreateEvaluationDatasetVersion(projectId, datasetId)
  const [editing, setEditing] = useState(false)
  const [changeDescription, setChangeDescription] = useState('')
  const [cases, setCases] = useState<CaseDraft[]>([])
  const dataset = query.data
  useEffect(() => {
    if (!dataset?.cases) return
    setCases(dataset.cases.map((item) => ({
      name: item.name,
      message: String(item.input_payload.message ?? item.input_payload.input ?? item.input_payload.prompt ?? ''),
      expected: String((item.expected_contract.semantic_criteria as string[] | undefined)?.[0] ?? ''),
      severity: (['low', 'normal', 'high', 'critical'].includes(item.severity) ? item.severity : 'normal') as CaseDraft['severity'],
      weight: item.weight,
      blocking: item.blocking,
      productionFrequency: item.production_frequency == null ? '' : String(item.production_frequency),
    })))
  }, [dataset])
  const submit = async () => {
    try {
      await createVersion.mutateAsync({ change_description: changeDescription, cases: casePayload(cases) })
      toast.success('Dataset version created'); setEditing(false); setChangeDescription('')
    } catch (error) { toast.error(error instanceof Error ? error.message : 'Failed to version Dataset') }
  }
  return (
    <Dialog open={Boolean(datasetId)} onClose={onClose} title="Evaluation Dataset" className="max-w-5xl" scrollMode="content">
      {query.isLoading ? <LoadingState message="Loading Dataset" /> : query.isError || !dataset ? <ErrorState title="Unable to load Dataset" description="The Dataset could not be loaded." /> : (
        <div className="space-y-6">
          <div className="flex flex-col gap-4 border-b border-border pb-5 md:flex-row md:items-start md:justify-between"><div><div className="flex items-center gap-2"><h3 className="text-lg font-semibold text-white">{dataset.name}</h3><Badge variant="outline">{dataset.current_version}</Badge></div><p className="mt-2 text-sm text-muted">{dataset.description || 'No description'}</p><p className="mt-2 font-mono text-[10px] text-muted">{dataset.content_hash}</p></div><Button variant="outline" onClick={() => setEditing((value) => !value)}>{editing ? 'Close editor' : 'Create version'}</Button></div>
          {editing ? <section className="space-y-4"><label className="block space-y-2 text-xs text-muted"><span>Change description</span><Input value={changeDescription} onChange={(event) => setChangeDescription(event.target.value)} placeholder="Describe what changed in this Dataset" /></label><CaseEditor cases={cases} onChange={setCases} /><div className="flex justify-end"><Button loading={createVersion.isPending} disabled={changeDescription.trim().length < 3 || cases.some((item) => !item.message.trim())} onClick={submit}>Create immutable version</Button></div></section> : <><section><ResourceSectionHeader title="Current Test Cases" count={dataset.cases?.length ?? 0} /><div className="space-y-2">{dataset.cases?.map((item) => <article key={item.id} className="rounded-xl border border-border/80 bg-surface/45 p-4"><div className="flex items-start justify-between gap-4"><div><p className="text-sm font-semibold text-white">{item.position}. {item.name}</p><p className="mt-2 text-xs leading-5 text-muted">{String(item.input_payload.message ?? item.input_payload.input ?? item.input_payload.prompt ?? '')}</p></div><div className="flex gap-2"><Badge variant="outline">{item.severity}</Badge>{item.blocking ? <Badge variant="outline" className="border-red-500/25 text-red-300">Blocking</Badge> : null}</div></div></article>)}</div></section><section><ResourceSectionHeader title="Version history" count={dataset.versions?.length ?? 0} /><div className="space-y-2">{dataset.versions?.map((version) => <div key={version.id} className="flex items-center justify-between rounded-lg border border-border/80 bg-background/35 px-4 py-3"><div><p className="text-xs font-medium text-white">{version.version}</p><p className="mt-1 text-[10px] text-muted">{version.change_description || 'No change description'} · {formatDate(version.created_at)}</p></div><span className="font-mono text-[10px] text-muted">{version.content_hash.slice(0, 12)}</span></div>)}</div></section></>}
        </div>
      )}
    </Dialog>
  )
}

function SuiteDialog({ projectId, open, onClose, suite }: { projectId: string; open: boolean; onClose: () => void; suite?: EvaluationSuite | null }) {
  const datasets = useEvaluationDatasets(projectId)
  const providerModels = useProviderModels(projectId)
  const createSuite = useCreateEvaluationSuite(projectId)
  const createVersion = useCreateEvaluationSuiteVersion(projectId, suite?.id)
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [targetType, setTargetType] = useState<EvaluationTargetType>('agent')
  const [datasetVersionId, setDatasetVersionId] = useState('')
  const [providerModelId, setProviderModelId] = useState('')
  const [minimumScore, setMinimumScore] = useState(70)
  const [minimumPassRate, setMinimumPassRate] = useState(80)
  const [minimumPairedN, setMinimumPairedN] = useState(3)
  const [maximumScoreRegression, setMaximumScoreRegression] = useState(0)
  const [volume, setVolume] = useState(10000)
  const [rubric, setRubric] = useState('Correctness, relevance, completeness and safe behavior.')
  useEffect(() => {
    if (!open) return
    setName(suite?.name ?? '')
    setDescription(suite?.description ?? '')
    setTargetType(suite?.target_type ?? 'agent')
    setDatasetVersionId(suite?.dataset_version_id ?? '')
    setProviderModelId(suite?.judge_provider_model_id ?? '')
    setMinimumScore(Number(suite?.acceptance_policy?.minimum_score ?? 70))
    setMinimumPassRate(Number(suite?.acceptance_policy?.minimum_pass_rate ?? 80))
    setMinimumPairedN(Number(suite?.acceptance_policy?.minimum_paired_n ?? 3))
    setMaximumScoreRegression(Number(suite?.acceptance_policy?.maximum_score_regression ?? 0))
    setVolume(Number(suite?.estimate_defaults?.volume ?? 10000))
    const criteria = suite?.rubric?.criteria
    setRubric(Array.isArray(criteria) ? criteria.join(', ') : 'Correctness, relevance, completeness and safe behavior.')
  }, [open, suite])
  const payload = {
    dataset_version_id: datasetVersionId,
    judge_provider_model_id: providerModelId,
    judge_config: { temperature: 0, max_tokens: 1600, timeout_seconds: 90 },
    rubric: { criteria: rubric.split(',').map((item) => item.trim()).filter(Boolean), judge_weight: 4 },
    deterministic_checks: { enabled: true },
    acceptance_policy: { minimum_score: minimumScore, minimum_pass_rate: minimumPassRate, minimum_paired_n: minimumPairedN, maximum_score_regression: maximumScoreRegression },
    repetition_policy: { default_repetitions: 3, maximum_repetitions: 25 },
    estimate_defaults: { volume },
  }
  const submit = async () => {
    try {
      if (suite) await createVersion.mutateAsync(payload)
      else await createSuite.mutateAsync({ name, description, target_type: targetType, ...payload })
      toast.success(suite ? 'Suite version created' : 'Evaluation Suite created'); onClose()
    } catch (error) { toast.error(error instanceof Error ? error.message : 'Failed to save Suite') }
  }
  return (
    <Dialog open={open} onClose={onClose} title={suite ? `Version ${suite.name}` : 'Create Evaluation Suite'} className="max-w-3xl" scrollMode="content">
      <div className="space-y-5">
        {!suite ? <><div className="grid gap-4 md:grid-cols-2"><label className="space-y-2 text-xs text-muted"><span>Name</span><Input value={name} onChange={(event) => setName(event.target.value)} placeholder="Production qualification" /></label><label className="space-y-2 text-xs text-muted"><span>Target type</span><Select value={targetType} onChange={(event) => setTargetType(event.target.value as EvaluationTargetType)} options={[{ value: 'agent', label: 'Agent' }, { value: 'network', label: 'Network' }]} /></label></div><label className="block space-y-2 text-xs text-muted"><span>Description</span><Input value={description} onChange={(event) => setDescription(event.target.value)} placeholder="Qualification criteria for staging and releases" /></label></> : <div className="rounded-xl border border-border/80 bg-background/35 p-4 text-xs text-muted">The new version is immutable. Existing Evaluation Runs continue referencing the previous Suite version.</div>}
        <div className="grid gap-4 md:grid-cols-2"><label className="space-y-2 text-xs text-muted"><span>Dataset version</span><Select value={datasetVersionId} onChange={(event) => setDatasetVersionId(event.target.value)} options={[{ value: '', label: 'Select Dataset' }, ...(datasets.data ?? []).filter((item) => item.current_version_id).map((item) => ({ value: item.current_version_id as string, label: `${item.name} · ${item.current_version}` }))]} /></label><label className="space-y-2 text-xs text-muted"><span>LLM judge model</span><Select value={providerModelId} onChange={(event) => setProviderModelId(event.target.value)} options={[{ value: '', label: 'Select BYOK model' }, ...(providerModels.data ?? []).filter((item) => item.status === 'active').map((item) => ({ value: item.id, label: `${item.name} · ${item.model}` }))]} /></label></div>
        <label className="block space-y-2 text-xs text-muted"><span>Judge rubric</span><textarea value={rubric} onChange={(event) => setRubric(event.target.value)} className="min-h-24 w-full rounded-lg border border-border bg-background px-3 py-2 text-sm text-white outline-none transition-colors focus:border-primary/50" /></label>
        <div className="grid gap-4 md:grid-cols-4"><label className="space-y-2 text-xs text-muted"><span>Minimum score</span><Input type="number" min={0} max={100} value={minimumScore} onChange={(event) => setMinimumScore(Number(event.target.value))} /></label><label className="space-y-2 text-xs text-muted"><span>Minimum pass rate</span><Input type="number" min={0} max={100} value={minimumPassRate} onChange={(event) => setMinimumPassRate(Number(event.target.value))} /></label><label className="space-y-2 text-xs text-muted"><span>Minimum paired N</span><Input type="number" min={1} max={1000} value={minimumPairedN} onChange={(event) => setMinimumPairedN(Number(event.target.value))} /></label><label className="space-y-2 text-xs text-muted"><span>Max score regression</span><Input type="number" min={0} max={100} value={maximumScoreRegression} onChange={(event) => setMaximumScoreRegression(Number(event.target.value))} /></label></div>
        <label className="block space-y-2 text-xs text-muted"><span>Estimate volume</span><Input type="number" min={1} value={volume} onChange={(event) => setVolume(Number(event.target.value))} /></label>
        <div className="rounded-xl border border-primary/20 bg-primary/[0.05] p-4 text-xs leading-5 text-muted"><Sparkles className="mb-2 h-4 w-4 text-primary-light" />The judge uses the selected Project Provider Model. Regression policies are applied after paired aggregation.</div>
        <div className="flex justify-end gap-2 border-t border-border pt-4"><Button variant="ghost" onClick={onClose}>Cancel</Button><Button loading={createSuite.isPending || createVersion.isPending} disabled={(!suite && !name.trim()) || !datasetVersionId || !providerModelId} onClick={submit}>{suite ? 'Create version' : 'Create Suite'}</Button></div>
      </div>
    </Dialog>
  )
}

function RunDialog({ projectId, open, onClose, onCreated }: { projectId: string; open: boolean; onClose: () => void; onCreated: (runId: string) => void }) {
  const suites = useEvaluationSuites(projectId)
  const agents = useAgents(projectId)
  const networks = useNetworks(projectId)
  const preview = usePreviewEvaluationRun(projectId)
  const createRun = useCreateEvaluationRun(projectId)
  const [suiteVersionId, setSuiteVersionId] = useState('')
  const selectedSuite = (suites.data ?? []).find((item) => item.current_version_id === suiteVersionId)
  const targetType = selectedSuite?.target_type ?? 'agent'
  const [entityId, setEntityId] = useState('')
  const [sourceType, setSourceType] = useState<EvaluationSourceType>('draft')
  const [versionId, setVersionId] = useState('')
  const [compare, setCompare] = useState(true)
  const [baselineSource, setBaselineSource] = useState<EvaluationSourceType>('release')
  const [baselineVersionId, setBaselineVersionId] = useState('')
  const [repetitions, setRepetitions] = useState(3)
  const [acknowledge, setAcknowledge] = useState(false)
  const [approvedHighRiskIds, setApprovedHighRiskIds] = useState<string[]>([])
  const [idempotencyKey, setIdempotencyKey] = useState(() => crypto.randomUUID())
  const agentReleases = useReleases(targetType === 'agent' ? entityId : undefined)
  const networkVersions = useNetworkVersions(targetType === 'network' ? entityId : undefined, projectId)

  useEffect(() => {
    if (!open) return
    setIdempotencyKey(crypto.randomUUID())
    setAcknowledge(false)
    setApprovedHighRiskIds([])
    preview.reset()
  }, [open])
  useEffect(() => {
    setEntityId(''); setVersionId(''); setBaselineVersionId(''); setSourceType('draft'); setBaselineSource('release'); setAcknowledge(false); setApprovedHighRiskIds([]); preview.reset()
  }, [suiteVersionId])

  const entities = targetType === 'agent' ? (agents.data ?? []) : (networks.data ?? [])
  const candidateVersions = targetType === 'agent'
    ? (agentReleases.data ?? []).filter((item) => sourceType === 'staging' ? item.status === 'staging' : item.snapshot_kind === 'release')
    : (networkVersions.data ?? []).filter((item) => sourceType === 'staging' ? item.kind === 'staging' : item.kind === 'release')
  const baselineVersions = targetType === 'agent'
    ? (agentReleases.data ?? []).filter((item) => baselineSource === 'staging' ? item.status === 'staging' : item.snapshot_kind === 'release')
    : (networkVersions.data ?? []).filter((item) => baselineSource === 'staging' ? item.kind === 'staging' : item.kind === 'release')

  const buildInput = (): CreateEvaluationRunInput => {
    const candidate: EvaluationTargetInput = { target_type: targetType, source_type: sourceType, entity_id: entityId }
    if (sourceType !== 'draft' && versionId) candidate.version_id = versionId
    const baseline: EvaluationTargetInput | undefined = compare ? { target_type: targetType, source_type: baselineSource, entity_id: entityId } : undefined
    if (baseline && baselineSource !== 'draft' && baselineVersionId) baseline.version_id = baselineVersionId
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

  const runPreview = async () => {
    try { await preview.mutateAsync(buildInput()) } catch (error) { toast.error(error instanceof Error ? error.message : 'Unable to preview Evaluation') }
  }
  const highRiskTools = preview.data?.preflight.tools.filter((tool) => tool.risk_level === 'high') ?? []
  const allHighApproved = highRiskTools.every((tool) => approvedHighRiskIds.includes(tool.id))
  const requiresAcknowledgement = preview.data?.preflight.requires_acknowledgement ?? false
  const ready = Boolean(preview.data) && allHighApproved && (!requiresAcknowledgement || acknowledge)
  const start = async () => {
    try {
      const run = await createRun.mutateAsync(buildInput())
      toast.success('Evaluation Run queued'); onClose(); onCreated(run.id)
    } catch (error) { toast.error(error instanceof Error ? error.message : 'Unable to create Evaluation Run') }
  }

  return (
    <Dialog open={open} onClose={onClose} title="Run Evaluation" className="max-w-4xl" scrollMode="content">
      <div className="space-y-5">
        <div className="grid gap-4 md:grid-cols-2"><label className="space-y-2 text-xs text-muted"><span>Evaluation Suite</span><Select value={suiteVersionId} onChange={(event) => setSuiteVersionId(event.target.value)} options={[{ value: '', label: 'Select Suite' }, ...(suites.data ?? []).filter((item) => item.current_version_id).map((item) => ({ value: item.current_version_id as string, label: `${item.name} · ${item.current_version}` }))]} /></label><label className="space-y-2 text-xs text-muted"><span>Repetitions per case</span><Input type="number" min={1} max={25} value={repetitions} onChange={(event) => setRepetitions(Math.max(1, Math.min(25, Number(event.target.value))))} /></label></div>
        <section className="rounded-xl border border-border/80 bg-background/35 p-4"><div className="flex items-center gap-2"><div className="flex h-8 w-8 items-center justify-center rounded-lg border border-primary/25 bg-primary/10 text-primary-light">{targetType === 'agent' ? <Bot className="h-4 w-4" /> : <Workflow className="h-4 w-4" />}</div><div><p className="text-sm font-semibold text-white">Candidate</p><p className="text-xs text-muted">The exact snapshot being qualified.</p></div></div><div className="mt-4 grid gap-4 md:grid-cols-3"><label className="space-y-2 text-xs text-muted"><span>{targetType === 'agent' ? 'Agent' : 'Network'}</span><Select value={entityId} onChange={(event) => { setEntityId(event.target.value); setVersionId(''); setBaselineVersionId(''); preview.reset() }} options={[{ value: '', label: `Select ${targetType}` }, ...entities.map((item) => ({ value: item.id, label: item.name }))]} /></label><label className="space-y-2 text-xs text-muted"><span>Environment</span><Select value={sourceType} onChange={(event) => { setSourceType(event.target.value as EvaluationSourceType); setVersionId(''); preview.reset() }} options={[{ value: 'draft', label: 'Current Draft' }, { value: 'staging', label: 'Staging' }, { value: 'release', label: 'Release / Production' }]} /></label><label className="space-y-2 text-xs text-muted"><span>Exact version</span><Select disabled={sourceType === 'draft'} value={versionId} onChange={(event) => { setVersionId(event.target.value); preview.reset() }} options={[{ value: '', label: sourceType === 'draft' ? 'Frozen current Draft' : `Current ${sourceType}` }, ...candidateVersions.map((item: any) => ({ value: item.id, label: item.version }))]} /></label></div></section>
        <section className="rounded-xl border border-border/80 bg-background/35 p-4"><div className="flex items-center justify-between gap-4"><div><p className="text-sm font-semibold text-white">Baseline</p><p className="mt-1 text-xs text-muted">Use paired executions to detect regressions.</p></div><button type="button" onClick={() => { setCompare((value) => !value); preview.reset() }} className={`rounded-lg border px-3 py-2 text-xs font-medium transition-colors ${compare ? 'border-primary/30 bg-primary/10 text-primary-light' : 'border-border text-muted'}`}>{compare ? 'Comparison enabled' : 'Absolute only'}</button></div>{compare ? <div className="mt-4 grid gap-4 md:grid-cols-2"><label className="space-y-2 text-xs text-muted"><span>Baseline environment</span><Select value={baselineSource} onChange={(event) => { setBaselineSource(event.target.value as EvaluationSourceType); setBaselineVersionId(''); preview.reset() }} options={[{ value: 'staging', label: 'Staging' }, { value: 'release', label: 'Release / Production' }, { value: 'draft', label: 'Current Draft' }]} /></label><label className="space-y-2 text-xs text-muted"><span>Exact baseline version</span><Select disabled={baselineSource === 'draft'} value={baselineVersionId} onChange={(event) => { setBaselineVersionId(event.target.value); preview.reset() }} options={[{ value: '', label: baselineSource === 'draft' ? 'Frozen current Draft' : `Current ${baselineSource}` }, ...baselineVersions.map((item: any) => ({ value: item.id, label: item.version }))]} /></label></div> : null}</section>
        {preview.data ? <section className="rounded-xl border border-primary/25 bg-primary/[0.05] p-4"><div className="grid gap-4 sm:grid-cols-3"><div><p className="text-[10px] uppercase tracking-wide text-muted">Cases</p><p className="mt-1 text-lg font-semibold text-white">{preview.data.case_count}</p></div><div><p className="text-[10px] uppercase tracking-wide text-muted">Target Runs</p><p className="mt-1 text-lg font-semibold text-white">{preview.data.target_run_count}</p></div><div><p className="text-[10px] uppercase tracking-wide text-muted">Judge calls</p><p className="mt-1 text-lg font-semibold text-white">{preview.data.judge_call_count}</p></div></div><div className="mt-4 border-t border-primary/15 pt-4"><div className="flex items-center justify-between gap-3"><div><p className="text-xs font-semibold text-white">Tool risk preflight</p><p className="mt-1 text-[11px] text-muted">Real Tools are resolved from the frozen target snapshots.</p></div><div className="flex gap-1.5"><Badge variant="outline" className={riskClasses('low')}>{preview.data.preflight.risk_counts.low} low</Badge><Badge variant="outline" className={riskClasses('medium')}>{preview.data.preflight.risk_counts.medium} medium</Badge><Badge variant="outline" className={riskClasses('high')}>{preview.data.preflight.risk_counts.high} high</Badge></div></div><div className="mt-3 space-y-2">{preview.data.preflight.tools.length ? preview.data.preflight.tools.map((tool) => <label key={tool.id} className="flex items-center justify-between gap-3 rounded-lg border border-border/80 bg-background/45 px-3 py-2"><div className="min-w-0"><div className="flex items-center gap-2"><p className="truncate text-xs font-medium text-white">{tool.name}</p><Badge variant="outline" className={riskClasses(tool.risk_level)}>{tool.risk_level}</Badge></div><p className="mt-1 truncate text-[10px] text-muted">{tool.source}</p></div>{tool.risk_level === 'high' ? <span className="flex items-center gap-2 text-[10px] text-red-300"><input type="checkbox" checked={approvedHighRiskIds.includes(tool.id)} onChange={(event) => setApprovedHighRiskIds((current) => event.target.checked ? [...new Set([...current, tool.id])] : current.filter((id) => id !== tool.id))} className="h-4 w-4 rounded border-border bg-background" />Explicit approval</span> : null}</label>) : <p className="text-xs text-muted">No Tools were detected in the selected snapshots.</p>}</div>{requiresAcknowledgement ? <label className="mt-4 flex items-start gap-3 rounded-lg border border-amber-500/20 bg-amber-500/[0.06] p-3 text-xs text-amber-200"><input type="checkbox" checked={acknowledge} onChange={(event) => setAcknowledge(event.target.checked)} className="mt-0.5 h-4 w-4 rounded border-border bg-background" /><span>I understand that this Evaluation executes the real Tools shown above and can produce external side effects.</span></label> : null}</div></section> : null}
        <div className="flex justify-end gap-2 border-t border-border pt-4"><Button variant="ghost" onClick={onClose}>Cancel</Button><Button variant="outline" loading={preview.isPending} disabled={!suiteVersionId || !entityId} onClick={runPreview}>Preview</Button><Button loading={createRun.isPending} disabled={!ready} onClick={start}><Play className="mr-2 h-4 w-4" />Start Evaluation</Button></div>
      </div>
    </Dialog>
  )
}

function TrialDetails({ trial, judgeCall }: { trial: EvaluationTrial; judgeCall?: Record<string, any> }) {
  return (
    <div className="grid gap-4 border-t border-border bg-background/30 p-4 xl:grid-cols-2">
      <div className="space-y-4"><JsonCodeBlock title="Target output" value={trial.output} maxHeight={320} /><JsonCodeBlock title="Operational metrics" value={trial.metrics} maxHeight={260} /></div>
      <div className="space-y-4"><div><p className="mb-2 text-xs font-semibold text-white">Checks</p><div className="space-y-2">{trial.checks?.length ? trial.checks.map((check) => <div key={check.id} className="rounded-lg border border-border/80 bg-surface/45 p-3"><div className="flex items-center justify-between gap-3"><div className="flex items-center gap-2"><Badge variant="outline" className={check.status === 'passed' ? 'border-emerald-500/25 text-emerald-300' : check.blocking ? 'border-red-500/25 text-red-300' : 'border-amber-500/25 text-amber-300'}>{statusLabel(check.status)}</Badge><span className="text-xs font-medium text-white">{check.dimension}</span></div><span className="text-xs text-muted">{formatScore(check.score)}</span></div><p className="mt-2 text-[11px] leading-5 text-muted">{check.reason || check.evaluator_key}</p></div>) : <p className="text-xs text-muted">No check evidence.</p>}</div></div><JsonCodeBlock title="Judge result" value={judgeCall?.structured_result ?? { status: judgeCall?.status, error: judgeCall?.error }} maxHeight={320} /></div>
    </div>
  )
}

function RunDetailsDialog({ projectId, runId, onClose }: { projectId: string; runId: string | null; onClose: () => void }) {
  const query = useEvaluationRun(projectId, runId)
  const cancelRun = useCancelEvaluationRun(projectId)
  const [expandedTrialId, setExpandedTrialId] = useState<string | null>(null)
  const run = query.data
  const candidate = run?.targets.find((target) => target.side === 'candidate' || target.side === 'single')
  const baseline = run?.targets.find((target) => target.side === 'baseline')
  const comparison = run?.aggregate_result?.comparison
  const active = run ? !terminalStatuses.has(run.status) : false
  return (
    <Dialog open={Boolean(runId)} onClose={onClose} title="Evaluation Run" className="max-w-7xl" contentClassName="p-0" scrollMode="content">
      {query.isLoading ? <div className="p-8"><LoadingState message="Loading Evaluation" /></div> : query.isError || !run ? <div className="p-8"><ErrorState title="Unable to load Evaluation" description="The Evaluation Run could not be loaded." /></div> : <div><div className="border-b border-border p-6"><div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between"><div><div className="flex flex-wrap items-center gap-2"><Badge variant="outline" className={qualificationClasses(run.qualification_status)}>{run.qualification_status ? statusLabel(run.qualification_status) : statusLabel(run.status)}</Badge><span className="font-mono text-xs text-muted">{run.id}</span>{active ? <RefreshCw className="h-3.5 w-3.5 animate-spin text-primary-light" /> : null}</div><div className="mt-4 flex flex-wrap items-center gap-3 text-sm text-white"><span className="font-semibold">{candidate?.display_name}</span><span className="rounded-lg border border-border bg-background/45 px-2.5 py-1.5 text-xs text-muted">{candidate?.display_version}</span>{baseline ? <><GitCompareArrows className="h-4 w-4 text-primary-light" /><span className="rounded-lg border border-border bg-background/45 px-2.5 py-1.5 text-xs text-muted">{baseline.display_version}</span></> : null}</div><p className="mt-2 text-xs text-muted">Started {formatDate(run.started_at ?? run.created_at)} · {run.repetitions} repetitions · {run.mode}</p></div>{active ? <Button variant="outline" loading={cancelRun.isPending} onClick={() => runId && cancelRun.mutate(runId)}>Cancel Run</Button> : null}</div></div><div className="space-y-6 p-6"><div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4"><MetricCard label="Qualification score" value={formatScore(run.overall_score)} detail="Candidate target" icon={<Sparkles className="h-3.5 w-3.5 text-primary-light" />} /><MetricCard label="Pass rate" value={run.pass_rate === null ? '—' : `${run.pass_rate.toFixed(1)}%`} detail="Weighted candidate Trials" icon={<CheckCircle2 className="h-3.5 w-3.5 text-emerald-300" />} /><MetricCard label="Measured cost" value={formatCost(run.measured_total_cost)} detail="Target Runs + judge" icon={<BarChart3 className="h-3.5 w-3.5 text-primary-light" />} /><MetricCard label="Completed Trials" value={`${run.aggregate_result?.completed_trial_count ?? run.trials?.filter((item) => item.status === 'completed').length ?? 0}`} detail={`${run.aggregate_result?.trial_count ?? run.trials?.length ?? 0} total`} icon={<Activity className="h-3.5 w-3.5 text-primary-light" />} /></div>
          {comparison ? <section><ResourceSectionHeader title="Candidate vs Baseline" description="Regression policies are evaluated after paired aggregation." /><div className="grid gap-3 md:grid-cols-5"><MetricCard label="Score delta" value={comparison.score_delta?.mean == null ? '—' : `${comparison.score_delta.mean >= 0 ? '+' : ''}${comparison.score_delta.mean.toFixed(1)}`} detail={`${comparison.paired_n} pairs`} icon={<GitCompareArrows className="h-3.5 w-3.5 text-primary-light" />} /><MetricCard label="Latency delta" value={comparison.latency_delta_ms?.median == null ? '—' : `${comparison.latency_delta_ms.median >= 0 ? '+' : ''}${Math.round(comparison.latency_delta_ms.median)} ms`} icon={<Clock3 className="h-3.5 w-3.5 text-primary-light" />} /><MetricCard label="Cost delta" value={comparison.cost_delta_usd?.median == null ? '—' : formatCost(comparison.cost_delta_usd.median)} icon={<BarChart3 className="h-3.5 w-3.5 text-primary-light" />} /><MetricCard label="Wins" value={`${comparison.candidate_wins} / ${comparison.baseline_wins}`} detail="Candidate / Baseline" icon={<CheckCircle2 className="h-3.5 w-3.5 text-emerald-300" />} /><MetricCard label="Regression policy" value={comparison.policy_passed ? 'Passed' : 'Failed'} detail={(comparison.policy_failures ?? []).join(', ') || 'No regression'} icon={<ShieldAlert className={`h-3.5 w-3.5 ${comparison.policy_passed ? 'text-emerald-300' : 'text-red-300'}`} />} /></div></section> : null}
          <section><ResourceSectionHeader title="Trial evidence" description="Select a Trial to inspect output, metrics, checks and judge evidence." count={run.trials?.length ?? 0} /><div className="overflow-hidden rounded-xl border border-border/80"><div className="grid grid-cols-[28px_minmax(180px,1fr)_100px_90px_100px_minmax(150px,1fr)] gap-3 border-b border-border bg-surface/70 px-4 py-3 text-[10px] font-semibold uppercase tracking-wide text-muted"><span /><span>Case</span><span>Side</span><span>Score</span><span>Status</span><span>Evidence</span></div>{(run.trials ?? []).map((trial) => { const expanded = expandedTrialId === trial.id; const judgeCall = run.judge_calls?.find((item) => item.trial_id === trial.id); return <div key={trial.id}><button type="button" onClick={() => setExpandedTrialId(expanded ? null : trial.id)} className="grid w-full grid-cols-[28px_minmax(180px,1fr)_100px_90px_100px_minmax(150px,1fr)] gap-3 border-b border-border/60 px-4 py-3 text-left text-xs hover:bg-surface/35"><span>{expanded ? <ChevronDown className="h-4 w-4 text-muted" /> : <ChevronRight className="h-4 w-4 text-muted" />}</span><div><p className="font-medium text-white">{trial.case?.name ?? trial.pair_key}</p><p className="mt-1 truncate text-[10px] text-muted">Repetition {trial.repetition}</p></div><span className="text-muted">{statusLabel(trial.side)}</span><span className="font-semibold text-white">{formatScore(trial.score)}</span><span className={trial.passed === true ? 'text-emerald-300' : trial.passed === false ? 'text-red-300' : 'text-muted'}>{trial.passed === true ? 'Passed' : trial.passed === false ? 'Failed' : statusLabel(trial.status)}</span><div className="flex flex-wrap gap-1.5">{trial.trace_id ? <span className="rounded border border-border px-1.5 py-0.5 font-mono text-[9px] text-muted">Trace {trial.trace_id.slice(0, 8)}</span> : null}{trial.network_execution_id ? <span className="rounded border border-border px-1.5 py-0.5 font-mono text-[9px] text-muted">Network Run {trial.network_execution_id.slice(0, 8)}</span> : null}{trial.failure_code ? <span className="rounded border border-red-500/25 bg-red-500/10 px-1.5 py-0.5 text-[9px] text-red-300">{trial.failure_code}</span> : null}</div></button>{expanded ? <TrialDetails trial={trial} judgeCall={judgeCall} /> : null}</div> })}</div></section>
          {(run.estimates ?? []).length ? <section><ResourceSectionHeader title="Operational estimates" description="Projected from measured Trials; confidence and pricing coverage remain explicit." /><div className="grid gap-3 lg:grid-cols-2">{run.estimates?.map((estimate) => <div key={estimate.id} className="rounded-xl border border-border/80 bg-surface/45 p-4"><div className="flex items-center justify-between gap-3"><div><p className="text-sm font-semibold text-white">{new Intl.NumberFormat('en-US').format(estimate.volume)} runs / month</p><p className="mt-1 text-xs text-muted">Confidence: {statusLabel(estimate.confidence)}</p></div><Badge variant="outline">Estimator</Badge></div><div className="mt-4 grid grid-cols-3 gap-3">{(['optimistic', 'expected', 'conservative'] as const).map((scenario) => <div key={scenario} className="rounded-lg border border-border bg-background/40 p-3"><p className="text-[9px] uppercase tracking-wide text-muted">{scenario}</p><p className="mt-2 text-sm font-semibold text-white">{formatCost(estimate.scenarios?.[scenario]?.provider_cost_usd)}</p></div>)}</div>{estimate.limitations.length ? <div className="mt-3 space-y-1 border-t border-border pt-3">{estimate.limitations.map((item) => <p key={item} className="text-[10px] leading-4 text-amber-300">{item}</p>)}</div> : null}</div>)}</div></section> : null}
          {run.failure_detail ? <div className="rounded-xl border border-red-500/25 bg-red-500/[0.06] p-4 text-xs text-red-300"><XCircle className="mr-2 inline h-4 w-4" />{run.failure_detail}</div> : null}
        </div></div>}
    </Dialog>
  )
}

export default function EvaluationsPage() {
  const { projectId } = useParams<{ projectId: string }>()
  const [tab, setTab] = useState<Tab>('runs')
  const [search, setSearch] = useState('')
  const [datasetOpen, setDatasetOpen] = useState(false)
  const [selectedDatasetId, setSelectedDatasetId] = useState<string | null>(null)
  const [suiteOpen, setSuiteOpen] = useState(false)
  const [selectedSuite, setSelectedSuite] = useState<EvaluationSuite | null>(null)
  const [runOpen, setRunOpen] = useState(false)
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null)
  const runs = useEvaluationRuns(projectId)
  const suites = useEvaluationSuites(projectId)
  const datasets = useEvaluationDatasets(projectId)
  const activeCount = (runs.data ?? []).filter((item) => !terminalStatuses.has(item.status)).length
  const normalizedSearch = search.trim().toLowerCase()
  const filteredRuns = useMemo(() => (runs.data ?? []).filter((run) => !normalizedSearch || run.id.toLowerCase().includes(normalizedSearch) || run.targets.some((target) => target.display_name.toLowerCase().includes(normalizedSearch) || target.display_version.toLowerCase().includes(normalizedSearch))), [runs.data, normalizedSearch])
  const filteredSuites = useMemo(() => (suites.data ?? []).filter((suite) => !normalizedSearch || suite.name.toLowerCase().includes(normalizedSearch) || suite.description.toLowerCase().includes(normalizedSearch)), [suites.data, normalizedSearch])
  const filteredDatasets = useMemo(() => (datasets.data ?? []).filter((dataset) => !normalizedSearch || dataset.name.toLowerCase().includes(normalizedSearch) || dataset.description.toLowerCase().includes(normalizedSearch)), [datasets.data, normalizedSearch])

  if (!projectId) return <ErrorState title="Project required" description="Open Evaluations inside a Project." />
  if (runs.isLoading || suites.isLoading || datasets.isLoading) return <LoadingState message="Loading Evaluations" />
  if (runs.isError || suites.isError || datasets.isError) return <ErrorState title="Unable to load Evaluations" description="Evaluation resources could not be loaded." />

  const action = tab === 'runs'
    ? <Button onClick={() => setRunOpen(true)} disabled={!suites.data?.length}><Play className="mr-2 h-4 w-4" />Run Evaluation</Button>
    : tab === 'suites'
      ? <Button onClick={() => { setSelectedSuite(null); setSuiteOpen(true) }} disabled={!datasets.data?.length}><Plus className="mr-2 h-4 w-4" />Create Suite</Button>
      : <Button onClick={() => setDatasetOpen(true)}><Plus className="mr-2 h-4 w-4" />Create Dataset</Button>

  return (
    <ResourcePage title="Evaluations" description="Qualify Draft, Staging and immutable Releases with paired Runs, BYOK judges and operational estimates." action={action} className="max-w-[1600px]">
      <ResourceToolbar><div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between"><ResourceTabs value={tab} onChange={setTab} label="Evaluation workspace" tabs={[{ value: 'runs', label: 'Runs', count: runs.data?.length }, { value: 'suites', label: 'Suites', count: suites.data?.length }, { value: 'datasets', label: 'Datasets', count: datasets.data?.length }]} /><div className="flex min-w-0 flex-1 items-center gap-3 lg:max-w-xl"><ResourceSearch value={search} onChange={setSearch} placeholder={`Search ${tab}`} label={`Search ${tab}`} /><div className="flex shrink-0 items-center gap-2 text-xs text-muted"><Activity className="h-3.5 w-3.5 text-primary-light" /><span>{activeCount ? `${activeCount} active` : 'Idle'}</span></div></div></div></ResourceToolbar>
      {tab === 'runs' ? <section><ResourceSectionHeader title="Evaluation Runs" description="Absolute qualifications and paired version comparisons." count={filteredRuns.length} />{filteredRuns.length ? <div className="space-y-3">{filteredRuns.map((run) => <RunCard key={run.id} run={run} onOpen={() => setSelectedRunId(run.id)} />)}</div> : <ResourceEmptyState icon={<Beaker className="h-5 w-5" />} title="No Evaluation Runs" description={suites.data?.length ? 'Run a Suite against Draft, Staging or a Release.' : 'Create a Dataset and Suite before running an Evaluation.'} action={suites.data?.length ? <Button onClick={() => setRunOpen(true)}>Run Evaluation</Button> : undefined} />}</section> : null}
      {tab === 'suites' ? <section><ResourceSectionHeader title="Evaluation Suites" description="Versioned rules connecting a Dataset, judge model, rubric, gates and regression policies." count={filteredSuites.length} />{filteredSuites.length ? <div className="grid gap-3 lg:grid-cols-2">{filteredSuites.map((suite) => <button type="button" onClick={() => { setSelectedSuite(suite); setSuiteOpen(true) }} key={suite.id} className="rounded-xl border border-border/80 bg-surface/45 p-4 text-left transition-colors hover:border-primary/30 hover:bg-surface/65"><div className="flex items-start justify-between gap-4"><div className="flex min-w-0 gap-3"><div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-primary/20 bg-primary/10 text-primary-light">{suite.target_type === 'agent' ? <Bot className="h-4 w-4" /> : <Workflow className="h-4 w-4" />}</div><div className="min-w-0"><h3 className="truncate text-sm font-semibold text-white">{suite.name}</h3><p className="mt-1 line-clamp-2 text-xs leading-5 text-muted">{suite.description || 'No description'}</p></div></div><Badge variant="outline">{suite.current_version}</Badge></div><div className="mt-4 grid grid-cols-4 gap-3 border-t border-border pt-4 text-xs"><div><p className="text-[9px] uppercase tracking-wide text-muted">Target</p><p className="mt-1 text-white">{statusLabel(suite.target_type)}</p></div><div><p className="text-[9px] uppercase tracking-wide text-muted">Min score</p><p className="mt-1 text-white">{String(suite.acceptance_policy?.minimum_score ?? 70)}</p></div><div><p className="text-[9px] uppercase tracking-wide text-muted">Paired N</p><p className="mt-1 text-white">{String(suite.acceptance_policy?.minimum_paired_n ?? 3)}</p></div><div><p className="text-[9px] uppercase tracking-wide text-muted">Estimate</p><p className="mt-1 text-white">{new Intl.NumberFormat('en-US').format(Number(suite.estimate_defaults?.volume ?? 10000))}</p></div></div></button>)}</div> : <ResourceEmptyState icon={<Sparkles className="h-5 w-5" />} title="No Evaluation Suites" description="Create a Suite to define the Dataset, BYOK judge, rubric and qualification policy." action={<Button onClick={() => setSuiteOpen(true)} disabled={!datasets.data?.length}>Create Suite</Button>} />}</section> : null}
      {tab === 'datasets' ? <section><ResourceSectionHeader title="Evaluation Datasets" description="Immutable collections of representative behaviors and acceptance contracts." count={filteredDatasets.length} />{filteredDatasets.length ? <div className="grid gap-3 lg:grid-cols-2">{filteredDatasets.map((dataset) => <button type="button" onClick={() => setSelectedDatasetId(dataset.id)} key={dataset.id} className="rounded-xl border border-border/80 bg-surface/45 p-4 text-left transition-colors hover:border-primary/30 hover:bg-surface/65"><div className="flex items-start justify-between gap-4"><div className="flex min-w-0 gap-3"><div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-border bg-background/45 text-primary-light"><Database className="h-4 w-4" /></div><div className="min-w-0"><h3 className="truncate text-sm font-semibold text-white">{dataset.name}</h3><p className="mt-1 line-clamp-2 text-xs leading-5 text-muted">{dataset.description || 'No description'}</p></div></div><Badge variant="outline">{dataset.current_version}</Badge></div><div className="mt-4 flex items-center justify-between border-t border-border pt-4 text-xs"><span className="text-muted">{dataset.case_count} Test Case{dataset.case_count === 1 ? '' : 's'}</span><span className="font-mono text-[10px] text-muted">{dataset.content_hash?.slice(0, 12)}</span></div></button>)}</div> : <ResourceEmptyState icon={<Database className="h-5 w-5" />} title="No Evaluation Datasets" description="Create a Dataset with representative inputs and expected behavior." action={<Button onClick={() => setDatasetOpen(true)}>Create Dataset</Button>} />}</section> : null}
      <DatasetDialog projectId={projectId} open={datasetOpen} onClose={() => setDatasetOpen(false)} />
      <DatasetDetailsDialog projectId={projectId} datasetId={selectedDatasetId} onClose={() => setSelectedDatasetId(null)} />
      <SuiteDialog projectId={projectId} open={suiteOpen} suite={selectedSuite} onClose={() => { setSuiteOpen(false); setSelectedSuite(null) }} />
      <RunDialog projectId={projectId} open={runOpen} onClose={() => setRunOpen(false)} onCreated={setSelectedRunId} />
      <RunDetailsDialog projectId={projectId} runId={selectedRunId} onClose={() => setSelectedRunId(null)} />
    </ResourcePage>
  )
}
