import { useEffect, useMemo, useState } from 'react'
import {
  Activity,
  ArrowRight,
  BarChart3,
  Beaker,
  Bot,
  CheckCircle2,
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
  ResourceSectionHeader,
  ResourceTabs,
  ResourceToolbar,
} from '@/components/common/ResourcePage'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { Dialog } from '@/components/ui/Dialog'
import { Input } from '@/components/ui/Input'
import { Select } from '@/components/ui/Select'
import { useAgents, useReleases } from '@/features/agents/hooks'
import {
  useCancelEvaluationRun,
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
  EvaluationTargetType,
} from '@/features/evaluations/types'
import { useNetworks, useNetworkVersions } from '@/features/network/hooks'
import { useProviderModels } from '@/features/provider-models/hooks'


type Tab = 'runs' | 'suites' | 'datasets'

const terminalStatuses = new Set(['completed', 'partially_completed', 'failed', 'cancelled'])

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

function statusLabel(status: string) {
  return status.split('_').map((part) => part.charAt(0).toUpperCase() + part.slice(1)).join(' ')
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
            {baseline ? (
              <>
                <ArrowRight className="h-3.5 w-3.5 text-muted" />
                <span className="rounded-md border border-border bg-background/45 px-2 py-1 text-[11px] text-muted">{baseline.display_version}</span>
              </>
            ) : null}
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

function DatasetDialog({ projectId, open, onClose }: { projectId: string; open: boolean; onClose: () => void }) {
  const createDataset = useCreateEvaluationDataset(projectId)
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [cases, setCases] = useState([{ name: 'Primary behavior', message: '', expected: '' }])

  const submit = async () => {
    try {
      await createDataset.mutateAsync({
        name,
        description,
        change_description: 'Initial Dataset version',
        cases: cases.map((item) => ({
          name: item.name,
          message: item.message,
          expected_contract: {
            semantic_criteria: item.expected ? [item.expected] : [],
            output_contract: { required: true },
          },
        })),
      })
      toast.success('Evaluation Dataset created')
      setName('')
      setDescription('')
      setCases([{ name: 'Primary behavior', message: '', expected: '' }])
      onClose()
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Failed to create Dataset')
    }
  }

  return (
    <Dialog open={open} onClose={onClose} title="Create Evaluation Dataset" className="max-w-3xl" scrollMode="content">
      <div className="space-y-5">
        <div className="grid gap-4 md:grid-cols-2">
          <label className="space-y-2 text-xs text-muted"><span>Name</span><Input value={name} onChange={(event) => setName(event.target.value)} placeholder="Support regression" /></label>
          <label className="space-y-2 text-xs text-muted"><span>Description</span><Input value={description} onChange={(event) => setDescription(event.target.value)} placeholder="Critical production behaviors" /></label>
        </div>
        <div>
          <ResourceSectionHeader title="Test Cases" description="Each case becomes an immutable input in the Dataset version." count={cases.length} />
          <div className="space-y-3">
            {cases.map((item, index) => (
              <div key={index} className="rounded-xl border border-border/80 bg-background/35 p-4">
                <div className="flex items-center justify-between gap-3">
                  <p className="text-xs font-semibold text-white">Case {index + 1}</p>
                  {cases.length > 1 ? <Button size="sm" variant="ghost" onClick={() => setCases((current) => current.filter((_, position) => position !== index))}>Remove</Button> : null}
                </div>
                <div className="mt-3 space-y-3">
                  <Input value={item.name} onChange={(event) => setCases((current) => current.map((entry, position) => position === index ? { ...entry, name: event.target.value } : entry))} placeholder="Case name" />
                  <textarea value={item.message} onChange={(event) => setCases((current) => current.map((entry, position) => position === index ? { ...entry, message: event.target.value } : entry))} placeholder="Input message sent to the Agent or Network" className="min-h-24 w-full rounded-lg border border-border bg-background px-3 py-2 text-sm text-white outline-none transition-colors placeholder:text-muted focus:border-primary/50" />
                  <textarea value={item.expected} onChange={(event) => setCases((current) => current.map((entry, position) => position === index ? { ...entry, expected: event.target.value } : entry))} placeholder="Expected behavior for the LLM judge" className="min-h-20 w-full rounded-lg border border-border bg-background px-3 py-2 text-sm text-white outline-none transition-colors placeholder:text-muted focus:border-primary/50" />
                </div>
              </div>
            ))}
          </div>
          <Button variant="outline" className="mt-3" onClick={() => setCases((current) => [...current, { name: `Case ${current.length + 1}`, message: '', expected: '' }])}><Plus className="mr-2 h-4 w-4" />Add case</Button>
        </div>
        <div className="flex justify-end gap-2 border-t border-border pt-4"><Button variant="ghost" onClick={onClose}>Cancel</Button><Button loading={createDataset.isPending} disabled={!name.trim() || cases.some((item) => !item.message.trim())} onClick={submit}>Create Dataset</Button></div>
      </div>
    </Dialog>
  )
}

function SuiteDialog({ projectId, open, onClose }: { projectId: string; open: boolean; onClose: () => void }) {
  const datasets = useEvaluationDatasets(projectId)
  const providerModels = useProviderModels(projectId)
  const createSuite = useCreateEvaluationSuite(projectId)
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [targetType, setTargetType] = useState<EvaluationTargetType>('agent')
  const [datasetVersionId, setDatasetVersionId] = useState('')
  const [providerModelId, setProviderModelId] = useState('')
  const [minimumScore, setMinimumScore] = useState(70)
  const [minimumPassRate, setMinimumPassRate] = useState(80)
  const [volume, setVolume] = useState(10000)
  const [rubric, setRubric] = useState('Correctness, relevance, completeness and safe behavior.')

  const submit = async () => {
    try {
      await createSuite.mutateAsync({
        name,
        description,
        target_type: targetType,
        dataset_version_id: datasetVersionId,
        judge_provider_model_id: providerModelId,
        judge_config: { temperature: 0, max_tokens: 1600 },
        rubric: { criteria: rubric.split(',').map((item) => item.trim()).filter(Boolean) },
        deterministic_checks: { enabled: true },
        acceptance_policy: { minimum_score: minimumScore, minimum_pass_rate: minimumPassRate },
        repetition_policy: { default_repetitions: 3, maximum_repetitions: 25 },
        estimate_defaults: { volume },
      })
      toast.success('Evaluation Suite created')
      onClose()
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Failed to create Suite')
    }
  }

  return (
    <Dialog open={open} onClose={onClose} title="Create Evaluation Suite" className="max-w-2xl" scrollMode="content">
      <div className="space-y-5">
        <div className="grid gap-4 md:grid-cols-2">
          <label className="space-y-2 text-xs text-muted"><span>Name</span><Input value={name} onChange={(event) => setName(event.target.value)} placeholder="Production qualification" /></label>
          <label className="space-y-2 text-xs text-muted"><span>Target type</span><Select value={targetType} onChange={(event) => setTargetType(event.target.value as EvaluationTargetType)} options={[{ value: 'agent', label: 'Agent' }, { value: 'network', label: 'Network' }]} /></label>
        </div>
        <label className="block space-y-2 text-xs text-muted"><span>Description</span><Input value={description} onChange={(event) => setDescription(event.target.value)} placeholder="Qualification criteria for staging and releases" /></label>
        <div className="grid gap-4 md:grid-cols-2">
          <label className="space-y-2 text-xs text-muted"><span>Dataset version</span><Select value={datasetVersionId} onChange={(event) => setDatasetVersionId(event.target.value)} options={[{ value: '', label: 'Select Dataset' }, ...(datasets.data ?? []).filter((item) => item.current_version_id).map((item) => ({ value: item.current_version_id as string, label: `${item.name} · ${item.current_version}` }))]} /></label>
          <label className="space-y-2 text-xs text-muted"><span>LLM judge model</span><Select value={providerModelId} onChange={(event) => setProviderModelId(event.target.value)} options={[{ value: '', label: 'Select BYOK model' }, ...(providerModels.data ?? []).filter((item) => item.status === 'active').map((item) => ({ value: item.id, label: `${item.name} · ${item.model}` }))]} /></label>
        </div>
        <label className="block space-y-2 text-xs text-muted"><span>Judge rubric</span><textarea value={rubric} onChange={(event) => setRubric(event.target.value)} className="min-h-24 w-full rounded-lg border border-border bg-background px-3 py-2 text-sm text-white outline-none transition-colors focus:border-primary/50" /></label>
        <div className="grid gap-4 md:grid-cols-3">
          <label className="space-y-2 text-xs text-muted"><span>Minimum score</span><Input type="number" min={0} max={100} value={minimumScore} onChange={(event) => setMinimumScore(Number(event.target.value))} /></label>
          <label className="space-y-2 text-xs text-muted"><span>Minimum pass rate</span><Input type="number" min={0} max={100} value={minimumPassRate} onChange={(event) => setMinimumPassRate(Number(event.target.value))} /></label>
          <label className="space-y-2 text-xs text-muted"><span>Estimate volume</span><Input type="number" min={1} value={volume} onChange={(event) => setVolume(Number(event.target.value))} /></label>
        </div>
        <div className="rounded-xl border border-primary/20 bg-primary/[0.05] p-4 text-xs leading-5 text-muted"><Sparkles className="mb-2 h-4 w-4 text-primary-light" />The judge uses the selected Provider Model and its Project Credential. Target Runs and judge calls are measured separately.</div>
        <div className="flex justify-end gap-2 border-t border-border pt-4"><Button variant="ghost" onClick={onClose}>Cancel</Button><Button loading={createSuite.isPending} disabled={!name.trim() || !datasetVersionId || !providerModelId} onClick={submit}>Create Suite</Button></div>
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
  const agentReleases = useReleases(targetType === 'agent' ? entityId : undefined)
  const networkVersions = useNetworkVersions(targetType === 'network' ? entityId : undefined, projectId)

  useEffect(() => {
    setEntityId('')
    setVersionId('')
    setBaselineVersionId('')
    setSourceType('draft')
    setBaselineSource('release')
    preview.reset()
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
    if (sourceType === 'release' && versionId) candidate.version_id = versionId
    if (sourceType === 'staging' && versionId) candidate.version_id = versionId
    const baseline: EvaluationTargetInput | undefined = compare ? { target_type: targetType, source_type: baselineSource, entity_id: entityId } : undefined
    if (baseline && baselineVersionId) baseline.version_id = baselineVersionId
    return { suite_version_id: suiteVersionId, repetitions, candidate, baseline }
  }

  const runPreview = async () => {
    try { await preview.mutateAsync(buildInput()) } catch (error) { toast.error(error instanceof Error ? error.message : 'Unable to preview Evaluation') }
  }
  const start = async () => {
    try {
      const run = await createRun.mutateAsync(buildInput())
      toast.success('Evaluation Run queued')
      onClose()
      onCreated(run.id)
    } catch (error) { toast.error(error instanceof Error ? error.message : 'Unable to create Evaluation Run') }
  }

  return (
    <Dialog open={open} onClose={onClose} title="Run Evaluation" className="max-w-3xl" scrollMode="content">
      <div className="space-y-5">
        <div className="grid gap-4 md:grid-cols-2">
          <label className="space-y-2 text-xs text-muted"><span>Evaluation Suite</span><Select value={suiteVersionId} onChange={(event) => setSuiteVersionId(event.target.value)} options={[{ value: '', label: 'Select Suite' }, ...(suites.data ?? []).filter((item) => item.current_version_id).map((item) => ({ value: item.current_version_id as string, label: `${item.name} · ${item.current_version}` }))]} /></label>
          <label className="space-y-2 text-xs text-muted"><span>Repetitions per case</span><Input type="number" min={1} max={25} value={repetitions} onChange={(event) => setRepetitions(Math.max(1, Math.min(25, Number(event.target.value))))} /></label>
        </div>
        <section className="rounded-xl border border-border/80 bg-background/35 p-4">
          <div className="flex items-center gap-2"><div className="flex h-8 w-8 items-center justify-center rounded-lg border border-primary/25 bg-primary/10 text-primary-light">{targetType === 'agent' ? <Bot className="h-4 w-4" /> : <Workflow className="h-4 w-4" />}</div><div><p className="text-sm font-semibold text-white">Candidate</p><p className="text-xs text-muted">The version being qualified.</p></div></div>
          <div className="mt-4 grid gap-4 md:grid-cols-3">
            <label className="space-y-2 text-xs text-muted"><span>{targetType === 'agent' ? 'Agent' : 'Network'}</span><Select value={entityId} onChange={(event) => { setEntityId(event.target.value); setVersionId(''); setBaselineVersionId(''); preview.reset() }} options={[{ value: '', label: `Select ${targetType}` }, ...entities.map((item) => ({ value: item.id, label: item.name }))]} /></label>
            <label className="space-y-2 text-xs text-muted"><span>Environment</span><Select value={sourceType} onChange={(event) => { setSourceType(event.target.value as EvaluationSourceType); setVersionId(''); preview.reset() }} options={[{ value: 'draft', label: 'Current Draft' }, { value: 'staging', label: 'Current Staging' }, { value: 'release', label: 'Release / Production' }]} /></label>
            <label className="space-y-2 text-xs text-muted"><span>Exact version</span><Select disabled={sourceType === 'draft'} value={versionId} onChange={(event) => { setVersionId(event.target.value); preview.reset() }} options={[{ value: '', label: sourceType === 'draft' ? 'Frozen current Draft' : `Current ${sourceType}` }, ...candidateVersions.map((item: any) => ({ value: item.id, label: item.version }))]} /></label>
          </div>
        </section>
        <section className="rounded-xl border border-border/80 bg-background/35 p-4">
          <div className="flex items-center justify-between gap-4"><div><p className="text-sm font-semibold text-white">Baseline</p><p className="mt-1 text-xs text-muted">Use paired runs to measure regressions and trade-offs.</p></div><button type="button" onClick={() => { setCompare((value) => !value); preview.reset() }} className={`rounded-lg border px-3 py-2 text-xs font-medium transition-colors ${compare ? 'border-primary/30 bg-primary/10 text-primary-light' : 'border-border text-muted'}`}>{compare ? 'Comparison enabled' : 'Absolute only'}</button></div>
          {compare ? <div className="mt-4 grid gap-4 md:grid-cols-2"><label className="space-y-2 text-xs text-muted"><span>Baseline environment</span><Select value={baselineSource} onChange={(event) => { setBaselineSource(event.target.value as EvaluationSourceType); setBaselineVersionId(''); preview.reset() }} options={[{ value: 'staging', label: 'Current Staging' }, { value: 'release', label: 'Release / Production' }, { value: 'draft', label: 'Current Draft' }]} /></label><label className="space-y-2 text-xs text-muted"><span>Exact baseline version</span><Select disabled={baselineSource === 'draft'} value={baselineVersionId} onChange={(event) => { setBaselineVersionId(event.target.value); preview.reset() }} options={[{ value: '', label: baselineSource === 'draft' ? 'Frozen current Draft' : `Current ${baselineSource}` }, ...baselineVersions.map((item: any) => ({ value: item.id, label: item.version }))]} /></label></div> : null}
        </section>
        {preview.data ? <div className="rounded-xl border border-primary/25 bg-primary/[0.05] p-4"><div className="grid gap-4 sm:grid-cols-3"><div><p className="text-[10px] uppercase tracking-wide text-muted">Cases</p><p className="mt-1 text-lg font-semibold text-white">{preview.data.case_count}</p></div><div><p className="text-[10px] uppercase tracking-wide text-muted">Target Runs</p><p className="mt-1 text-lg font-semibold text-white">{preview.data.target_run_count}</p></div><div><p className="text-[10px] uppercase tracking-wide text-muted">Judge calls</p><p className="mt-1 text-lg font-semibold text-white">{preview.data.judge_call_count}</p></div></div><p className="mt-3 border-t border-primary/15 pt-3 text-xs leading-5 text-amber-300"><ShieldAlert className="mr-1 inline h-3.5 w-3.5" />{preview.data.tool_execution_warning}</p></div> : null}
        <div className="flex justify-end gap-2 border-t border-border pt-4"><Button variant="ghost" onClick={onClose}>Cancel</Button><Button variant="outline" loading={preview.isPending} disabled={!suiteVersionId || !entityId} onClick={runPreview}>Preview</Button><Button loading={createRun.isPending} disabled={!preview.data} onClick={start}><Play className="mr-2 h-4 w-4" />Start Evaluation</Button></div>
      </div>
    </Dialog>
  )
}

function RunDetailsDialog({ projectId, runId, onClose }: { projectId: string; runId: string | null; onClose: () => void }) {
  const query = useEvaluationRun(projectId, runId)
  const cancelRun = useCancelEvaluationRun(projectId)
  const run = query.data
  const candidate = run?.targets.find((target) => target.side === 'candidate' || target.side === 'single')
  const baseline = run?.targets.find((target) => target.side === 'baseline')
  const comparison = run?.aggregate_result?.comparison
  const active = run ? !terminalStatuses.has(run.status) : false

  return (
    <Dialog open={Boolean(runId)} onClose={onClose} title="Evaluation Run" className="max-w-6xl" contentClassName="p-0" scrollMode="content">
      {query.isLoading ? <div className="p-8"><LoadingState message="Loading Evaluation" /></div> : query.isError || !run ? <div className="p-8"><ErrorState title="Unable to load Evaluation" description="The Evaluation Run could not be loaded." /></div> : (
        <div>
          <div className="border-b border-border p-6">
            <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between"><div><div className="flex flex-wrap items-center gap-2"><Badge variant="outline" className={qualificationClasses(run.qualification_status)}>{run.qualification_status ? statusLabel(run.qualification_status) : statusLabel(run.status)}</Badge><span className="font-mono text-xs text-muted">{run.id}</span>{active ? <RefreshCw className="h-3.5 w-3.5 animate-spin text-primary-light" /> : null}</div><div className="mt-4 flex flex-wrap items-center gap-3 text-sm text-white"><span className="font-semibold">{candidate?.display_name}</span><span className="rounded-lg border border-border bg-background/45 px-2.5 py-1.5 text-xs text-muted">{candidate?.display_version}</span>{baseline ? <><GitCompareArrows className="h-4 w-4 text-primary-light" /><span className="rounded-lg border border-border bg-background/45 px-2.5 py-1.5 text-xs text-muted">{baseline.display_version}</span></> : null}</div><p className="mt-2 text-xs text-muted">Started {formatDate(run.started_at ?? run.created_at)} · {run.repetitions} repetitions · {run.mode}</p></div>{active ? <Button variant="outline" loading={cancelRun.isPending} onClick={() => runId && cancelRun.mutate(runId)}>Cancel Run</Button> : null}</div>
          </div>
          <div className="space-y-6 p-6">
            <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4"><MetricCard label="Qualification score" value={formatScore(run.overall_score)} detail="Candidate target" icon={<Sparkles className="h-3.5 w-3.5 text-primary-light" />} /><MetricCard label="Pass rate" value={run.pass_rate === null ? '—' : `${run.pass_rate.toFixed(1)}%`} detail="Across candidate Trials" icon={<CheckCircle2 className="h-3.5 w-3.5 text-emerald-300" />} /><MetricCard label="Measured cost" value={formatCost(run.measured_total_cost)} detail="Target Runs + judge" icon={<BarChart3 className="h-3.5 w-3.5 text-primary-light" />} /><MetricCard label="Completed Trials" value={`${run.aggregate_result?.completed_trial_count ?? run.trials?.filter((item) => item.status === 'completed').length ?? 0}`} detail={`${run.aggregate_result?.trial_count ?? run.trials?.length ?? 0} total`} icon={<Activity className="h-3.5 w-3.5 text-primary-light" />} /></div>
            {comparison ? <section><ResourceSectionHeader title="Candidate vs Baseline" description="Paired deltas are calculated per case and repetition before aggregation." /><div className="grid gap-3 md:grid-cols-4"><MetricCard label="Score delta" value={comparison.score_delta?.mean === null ? '—' : `${comparison.score_delta.mean >= 0 ? '+' : ''}${comparison.score_delta.mean.toFixed(1)}`} detail={`${comparison.paired_n} paired observations`} icon={<GitCompareArrows className="h-3.5 w-3.5 text-primary-light" />} /><MetricCard label="Latency delta" value={comparison.latency_delta_ms?.median === null ? '—' : `${comparison.latency_delta_ms.median >= 0 ? '+' : ''}${Math.round(comparison.latency_delta_ms.median)} ms`} icon={<Clock3 className="h-3.5 w-3.5 text-primary-light" />} /><MetricCard label="Cost delta" value={comparison.cost_delta_usd?.median === null ? '—' : formatCost(comparison.cost_delta_usd.median)} icon={<BarChart3 className="h-3.5 w-3.5 text-primary-light" />} /><MetricCard label="Wins" value={`${comparison.candidate_wins} / ${comparison.baseline_wins}`} detail="Candidate / Baseline" icon={<CheckCircle2 className="h-3.5 w-3.5 text-emerald-300" />} /></div></section> : null}
            <section><ResourceSectionHeader title="Trial evidence" description="Every result remains linked to the exact target snapshot and operational evidence." count={run.trials?.length ?? 0} />
              <div className="overflow-hidden rounded-xl border border-border/80"><div className="grid grid-cols-[minmax(180px,1fr)_100px_90px_90px_minmax(160px,1fr)] gap-3 border-b border-border bg-surface/70 px-4 py-3 text-[10px] font-semibold uppercase tracking-wide text-muted"><span>Case</span><span>Side</span><span>Score</span><span>Status</span><span>Evidence</span></div>{(run.trials ?? []).map((trial) => <div key={trial.id} className="grid grid-cols-[minmax(180px,1fr)_100px_90px_90px_minmax(160px,1fr)] gap-3 border-b border-border/60 px-4 py-3 text-xs last:border-b-0"><div><p className="font-medium text-white">{trial.case?.name ?? trial.pair_key}</p><p className="mt-1 truncate text-[10px] text-muted">Repetition {trial.repetition}</p></div><span className="text-muted">{statusLabel(trial.side)}</span><span className="font-semibold text-white">{formatScore(trial.score)}</span><span className={trial.passed === true ? 'text-emerald-300' : trial.passed === false ? 'text-red-300' : 'text-muted'}>{trial.passed === true ? 'Passed' : trial.passed === false ? 'Failed' : statusLabel(trial.status)}</span><div className="flex flex-wrap gap-1.5">{trial.trace_id ? <span className="rounded border border-border px-1.5 py-0.5 font-mono text-[9px] text-muted">Trace {trial.trace_id.slice(0, 8)}</span> : null}{trial.network_execution_id ? <span className="rounded border border-border px-1.5 py-0.5 font-mono text-[9px] text-muted">Network Run {trial.network_execution_id.slice(0, 8)}</span> : null}{trial.failure_code ? <span className="rounded border border-red-500/25 bg-red-500/10 px-1.5 py-0.5 text-[9px] text-red-300">{trial.failure_code}</span> : null}</div></div>)}</div>
            </section>
            {(run.estimates ?? []).length ? <section><ResourceSectionHeader title="Operational estimates" description="Projected from observed Trials; measured and unknown costs remain distinct." /><div className="grid gap-3 lg:grid-cols-2">{run.estimates?.map((estimate) => <div key={estimate.id} className="rounded-xl border border-border/80 bg-surface/45 p-4"><div className="flex items-center justify-between gap-3"><div><p className="text-sm font-semibold text-white">{new Intl.NumberFormat('en-US').format(estimate.volume)} runs / month</p><p className="mt-1 text-xs text-muted">Confidence: {statusLabel(estimate.confidence)}</p></div><Badge variant="outline">Estimator</Badge></div><div className="mt-4 grid grid-cols-3 gap-3">{(['optimistic', 'expected', 'conservative'] as const).map((scenario) => <div key={scenario} className="rounded-lg border border-border bg-background/40 p-3"><p className="text-[9px] uppercase tracking-wide text-muted">{scenario}</p><p className="mt-2 text-sm font-semibold text-white">{formatCost(estimate.scenarios?.[scenario]?.provider_cost_usd)}</p></div>)}</div>{estimate.limitations.length ? <div className="mt-3 space-y-1 border-t border-border pt-3">{estimate.limitations.map((item) => <p key={item} className="text-[10px] leading-4 text-amber-300">{item}</p>)}</div> : null}</div>)}</div></section> : null}
            {run.failure_detail ? <div className="rounded-xl border border-red-500/25 bg-red-500/[0.06] p-4 text-xs text-red-300"><XCircle className="mr-2 inline h-4 w-4" />{run.failure_detail}</div> : null}
          </div>
        </div>
      )}
    </Dialog>
  )
}

export default function EvaluationsPage() {
  const { projectId } = useParams<{ projectId: string }>()
  const [tab, setTab] = useState<Tab>('runs')
  const [datasetOpen, setDatasetOpen] = useState(false)
  const [suiteOpen, setSuiteOpen] = useState(false)
  const [runOpen, setRunOpen] = useState(false)
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null)
  const runs = useEvaluationRuns(projectId)
  const suites = useEvaluationSuites(projectId)
  const datasets = useEvaluationDatasets(projectId)
  const activeCount = (runs.data ?? []).filter((item) => !terminalStatuses.has(item.status)).length

  if (!projectId) return <ErrorState title="Project required" description="Open Evaluations inside a Project." />
  if (runs.isLoading || suites.isLoading || datasets.isLoading) return <LoadingState message="Loading Evaluations" />
  if (runs.isError || suites.isError || datasets.isError) return <ErrorState title="Unable to load Evaluations" description="Evaluation resources could not be loaded." />

  const action = tab === 'runs'
    ? <Button onClick={() => setRunOpen(true)} disabled={!suites.data?.length}><Play className="mr-2 h-4 w-4" />Run Evaluation</Button>
    : tab === 'suites'
      ? <Button onClick={() => setSuiteOpen(true)} disabled={!datasets.data?.length}><Plus className="mr-2 h-4 w-4" />Create Suite</Button>
      : <Button onClick={() => setDatasetOpen(true)}><Plus className="mr-2 h-4 w-4" />Create Dataset</Button>

  return (
    <ResourcePage title="Evaluations" description="Qualify Draft, Staging and immutable Releases with paired Runs, BYOK judges and operational estimates." action={action} className="max-w-[1600px]">
      <ResourceToolbar><div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between"><ResourceTabs value={tab} onChange={setTab} label="Evaluation workspace" tabs={[{ value: 'runs', label: 'Runs', count: runs.data?.length }, { value: 'suites', label: 'Suites', count: suites.data?.length }, { value: 'datasets', label: 'Datasets', count: datasets.data?.length }]} /><div className="flex items-center gap-2 text-xs text-muted"><Activity className="h-3.5 w-3.5 text-primary-light" /><span>{activeCount ? `${activeCount} Evaluation Run${activeCount === 1 ? '' : 's'} active` : 'No active Evaluation Runs'}</span></div></div></ResourceToolbar>
      {tab === 'runs' ? <section><ResourceSectionHeader title="Evaluation Runs" description="Absolute qualifications and paired version comparisons." count={runs.data?.length ?? 0} />{runs.data?.length ? <div className="space-y-3">{runs.data.map((run) => <RunCard key={run.id} run={run} onOpen={() => setSelectedRunId(run.id)} />)}</div> : <ResourceEmptyState icon={<Beaker className="h-5 w-5" />} title="No Evaluation Runs" description={suites.data?.length ? 'Run a Suite against Draft, Staging or a Release.' : 'Create a Dataset and Suite before running an Evaluation.'} action={suites.data?.length ? <Button onClick={() => setRunOpen(true)}>Run Evaluation</Button> : undefined} />}</section> : null}
      {tab === 'suites' ? <section><ResourceSectionHeader title="Evaluation Suites" description="Versioned rules connecting a Dataset, judge model, rubric, gates and estimate defaults." count={suites.data?.length ?? 0} />{suites.data?.length ? <div className="grid gap-3 lg:grid-cols-2">{suites.data.map((suite) => <article key={suite.id} className="rounded-xl border border-border/80 bg-surface/45 p-4"><div className="flex items-start justify-between gap-4"><div className="flex min-w-0 gap-3"><div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-primary/20 bg-primary/10 text-primary-light">{suite.target_type === 'agent' ? <Bot className="h-4 w-4" /> : <Workflow className="h-4 w-4" />}</div><div className="min-w-0"><h3 className="truncate text-sm font-semibold text-white">{suite.name}</h3><p className="mt-1 line-clamp-2 text-xs leading-5 text-muted">{suite.description || 'No description'}</p></div></div><Badge variant="outline">{suite.current_version}</Badge></div><div className="mt-4 grid grid-cols-3 gap-3 border-t border-border pt-4 text-xs"><div><p className="text-[9px] uppercase tracking-wide text-muted">Target</p><p className="mt-1 text-white">{statusLabel(suite.target_type)}</p></div><div><p className="text-[9px] uppercase tracking-wide text-muted">Min score</p><p className="mt-1 text-white">{String(suite.acceptance_policy?.minimum_score ?? 70)}</p></div><div><p className="text-[9px] uppercase tracking-wide text-muted">Estimate</p><p className="mt-1 text-white">{new Intl.NumberFormat('en-US').format(Number(suite.estimate_defaults?.volume ?? 10000))}</p></div></div></article>)}</div> : <ResourceEmptyState icon={<Sparkles className="h-5 w-5" />} title="No Evaluation Suites" description="Create a Suite to define the Dataset, BYOK judge, rubric and qualification policy." action={<Button onClick={() => setSuiteOpen(true)} disabled={!datasets.data?.length}>Create Suite</Button>} />}</section> : null}
      {tab === 'datasets' ? <section><ResourceSectionHeader title="Evaluation Datasets" description="Immutable collections of production behaviors and acceptance contracts." count={datasets.data?.length ?? 0} />{datasets.data?.length ? <div className="grid gap-3 lg:grid-cols-2">{datasets.data.map((dataset) => <article key={dataset.id} className="rounded-xl border border-border/80 bg-surface/45 p-4"><div className="flex items-start justify-between gap-4"><div className="flex min-w-0 gap-3"><div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-border bg-background/45 text-primary-light"><Database className="h-4 w-4" /></div><div className="min-w-0"><h3 className="truncate text-sm font-semibold text-white">{dataset.name}</h3><p className="mt-1 line-clamp-2 text-xs leading-5 text-muted">{dataset.description || 'No description'}</p></div></div><Badge variant="outline">{dataset.current_version}</Badge></div><div className="mt-4 flex items-center justify-between border-t border-border pt-4 text-xs"><span className="text-muted">{dataset.case_count} Test Case{dataset.case_count === 1 ? '' : 's'}</span><span className="font-mono text-[10px] text-muted">{dataset.content_hash?.slice(0, 12)}</span></div></article>)}</div> : <ResourceEmptyState icon={<Database className="h-5 w-5" />} title="No Evaluation Datasets" description="Create a Dataset with representative inputs and expected behavior." action={<Button onClick={() => setDatasetOpen(true)}>Create Dataset</Button>} />}</section> : null}
      <DatasetDialog projectId={projectId} open={datasetOpen} onClose={() => setDatasetOpen(false)} />
      <SuiteDialog projectId={projectId} open={suiteOpen} onClose={() => setSuiteOpen(false)} />
      <RunDialog projectId={projectId} open={runOpen} onClose={() => setRunOpen(false)} onCreated={setSelectedRunId} />
      <RunDetailsDialog projectId={projectId} runId={selectedRunId} onClose={() => setSelectedRunId(null)} />
    </ResourcePage>
  )
}
