import { useEffect, useMemo, useState } from 'react'
import {
  Archive,
  BarChart3,
  Beaker,
  Bot,
  ChevronRight,
  Database,
  ExternalLink,
  Play,
  Plus,
  RefreshCw,
  Sparkles,
  Workflow,
} from 'lucide-react'
import { useNavigate, useParams, useSearchParams } from 'react-router-dom'
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
import { EvaluatorSuiteAuthoringWizard } from '@/features/evaluations/components/EvaluatorSuiteAuthoringWizard'
import {
  useArchiveEvaluationDataset,
  useArchiveEvaluationSuite,
  useCancelEvaluationRun,
  useCreateEvaluationEstimate,
  useCreateEvaluationRun,
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
  EvaluationSuite,
  EvaluationTargetInput,
  EvaluationTargetType,
} from '@/features/evaluations/types'
import { useNetworks, useNetworkVersions } from '@/features/network/hooks'
import { useProviderModels } from '@/features/provider-models/hooks'

type Tab = 'runs' | 'suites' | 'datasets'

interface TargetPrefill {
  targetType: EvaluationTargetType
  entityId: string
  sourceType: EvaluationSourceType
  versionId: string
}

interface RunPrefill extends TargetPrefill {
  suiteVersionId: string
}

const terminalStatuses = new Set(['completed', 'partially_completed', 'failed', 'cancelled'])

function titleCase(value?: string | null) {
  if (!value) return 'Unknown'
  return value.split('_').map((part) => part.charAt(0).toUpperCase() + part.slice(1)).join(' ')
}

function formatDate(value?: string | null) {
  if (!value) return '—'
  return new Intl.DateTimeFormat('en-US', {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  }).format(new Date(value))
}

function formatCost(value?: number | null) {
  if (value == null) return 'Unknown'
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: value < 0.01 ? 4 : 2,
  }).format(value)
}

function statusClass(value?: string | null) {
  if (['qualified', 'completed', 'passed', 'current'].includes(value || '')) return 'border-emerald-500/30 bg-emerald-500/10 text-emerald-300'
  if (['not_qualified', 'failed'].includes(value || '')) return 'border-red-500/30 bg-red-500/10 text-red-300'
  if (['qualified_with_warnings', 'partially_completed', 'stale'].includes(value || '')) return 'border-amber-500/30 bg-amber-500/10 text-amber-300'
  return 'border-border bg-background/40 text-muted'
}

function RunCard({ run, onOpen }: { run: EvaluationRun; onOpen: () => void }) {
  const candidate = run.targets.find((target) => target.side === 'candidate' || target.side === 'single')
  const active = !terminalStatuses.has(run.status)
  return (
    <button type="button" onClick={onOpen} className="flex w-full items-center gap-4 rounded-xl border border-border/80 bg-surface/45 p-4 text-left hover:border-primary/30">
      <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-primary/20 bg-primary/10 text-primary-light"><Beaker className="h-4 w-4" /></div>
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-2">
          <p className="truncate text-sm font-semibold text-white">{candidate?.display_name ?? 'Evaluation target'}</p>
          <Badge variant="outline" className={statusClass(run.qualification_status ?? run.status)}>{titleCase(run.qualification_status ?? run.status)}</Badge>
          {active ? <RefreshCw className="h-3.5 w-3.5 animate-spin text-primary-light" /> : null}
        </div>
        <p className="mt-1 text-xs text-muted">{candidate?.display_version} · {run.repetitions} Runs per case · {formatDate(run.created_at)}</p>
      </div>
      <div className="hidden grid-cols-2 gap-6 text-right sm:grid">
        <div><p className="text-[9px] uppercase text-muted">Score</p><p className="mt-1 text-sm font-semibold text-white">{run.overall_score == null ? '—' : run.overall_score.toFixed(1)}</p></div>
        <div><p className="text-[9px] uppercase text-muted">Cost</p><p className="mt-1 text-sm font-semibold text-white">{formatCost(run.measured_total_cost)}</p></div>
      </div>
      <ChevronRight className="h-4 w-4 text-muted" />
    </button>
  )
}

function AuthoringDialog({
  projectId,
  open,
  onClose,
  prefill,
  existingSuite,
  onCreated,
}: {
  projectId: string
  open: boolean
  onClose: () => void
  prefill: TargetPrefill
  existingSuite?: EvaluationSuite | null
  onCreated: (suite: EvaluationSuite, target: TargetPrefill) => void
}) {
  const agents = useAgents(projectId)
  const networks = useNetworks(projectId)
  const models = useProviderModels(projectId)
  const [targetType, setTargetType] = useState<EvaluationTargetType>(prefill.targetType)
  const [entityId, setEntityId] = useState(prefill.entityId)
  const agentReleases = useReleases(targetType === 'agent' ? entityId : undefined)
  const networkVersions = useNetworkVersions(targetType === 'network' ? entityId : undefined, projectId)

  useEffect(() => {
    if (!open) return
    setTargetType(prefill.targetType)
    setEntityId(prefill.entityId)
  }, [open, prefill.targetType, prefill.entityId])

  const entities = targetType === 'agent' ? agents.data ?? [] : networks.data ?? []
  const selected = entities.find((item) => item.id === entityId)
  const versions = targetType === 'agent'
    ? (agentReleases.data ?? []).map((item) => ({ id: item.id, version: item.version, status: item.status, snapshot_kind: item.snapshot_kind }))
    : (networkVersions.data ?? []).map((item) => ({ id: item.id, version: item.version, status: item.kind, kind: item.kind }))

  const targetPrefill: TargetPrefill = {
    targetType,
    entityId,
    sourceType: prefill.sourceType,
    versionId: prefill.versionId,
  }

  return (
    <Dialog open={open} onClose={onClose} title={existingSuite ? `Version ${existingSuite.name}` : 'Create Evaluator Suite'} className="max-w-6xl overflow-hidden" scrollMode="content">
      {!entityId ? (
        <div className="space-y-5">
          <div><h3 className="text-base font-semibold text-white">Reference target</h3><p className="mt-1 text-xs text-muted">Manual, JSON and AI authoring use the same snapshot-aware contract.</p></div>
          <div className="grid gap-4 md:grid-cols-2">
            <label className="space-y-2 text-xs text-muted"><span>Target type</span><Select value={targetType} onChange={(event) => { setTargetType(event.target.value as EvaluationTargetType); setEntityId('') }} options={[{ value: 'agent', label: 'Agent' }, { value: 'network', label: 'Network' }]} /></label>
            <label className="space-y-2 text-xs text-muted"><span>{targetType === 'agent' ? 'Agent' : 'Network'}</span><Select value={entityId} onChange={(event) => setEntityId(event.target.value)} options={[{ value: '', label: `Select ${targetType}` }, ...entities.map((item) => ({ value: item.id, label: item.name }))]} /></label>
          </div>
          <div className="flex justify-end"><Button variant="outline" onClick={onClose}>Cancel</Button></div>
        </div>
      ) : (
        <EvaluatorSuiteAuthoringWizard
          projectId={projectId}
          targetType={targetType}
          entityId={entityId}
          targetName={selected?.name ?? targetType}
          versions={versions}
          providerModels={models.data ?? []}
          existingSuite={existingSuite}
          initialSourceType={prefill.sourceType}
          initialVersionId={prefill.versionId}
          onCancel={onClose}
          onCreated={(suite) => onCreated(suite, targetPrefill)}
        />
      )}
    </Dialog>
  )
}

function RunDialog({
  projectId,
  open,
  onClose,
  prefill,
  onCreated,
}: {
  projectId: string
  open: boolean
  onClose: () => void
  prefill: RunPrefill | null
  onCreated: (id: string) => void
}) {
  const suites = useEvaluationSuites(projectId)
  const agents = useAgents(projectId)
  const networks = useNetworks(projectId)
  const preview = usePreviewEvaluationRun(projectId)
  const create = useCreateEvaluationRun(projectId)
  const [suiteVersionId, setSuiteVersionId] = useState('')
  const suite = (suites.data ?? []).find((item) => item.current_version_id === suiteVersionId)
  const targetType = suite?.target_type ?? prefill?.targetType ?? 'agent'
  const [entityId, setEntityId] = useState('')
  const [sourceType, setSourceType] = useState<EvaluationSourceType>('draft')
  const [versionId, setVersionId] = useState('')
  const [baselineEnabled, setBaselineEnabled] = useState(false)
  const [baselineSource, setBaselineSource] = useState<EvaluationSourceType>('release')
  const [baselineVersionId, setBaselineVersionId] = useState('')
  const [repetitions, setRepetitions] = useState(3)
  const [acknowledge, setAcknowledge] = useState(false)
  const [approved, setApproved] = useState<string[]>([])
  const [idempotencyKey, setIdempotencyKey] = useState(() => crypto.randomUUID())
  const agentVersions = useReleases(targetType === 'agent' ? entityId : undefined)
  const networkVersions = useNetworkVersions(targetType === 'network' ? entityId : undefined, projectId)
  const entities = targetType === 'agent' ? agents.data ?? [] : networks.data ?? []
  const versions = targetType === 'agent'
    ? (agentVersions.data ?? []).map((item) => ({ id: item.id, version: item.version, status: item.status, kind: item.snapshot_kind }))
    : (networkVersions.data ?? []).map((item) => ({ id: item.id, version: item.version, status: item.kind, kind: item.kind }))
  const candidates = versions.filter((item) => sourceType === 'staging' ? item.status === 'staging' || item.kind === 'staging' : item.status === 'released' || item.status === 'production' || item.kind === 'release')
  const baselines = versions.filter((item) => baselineSource === 'staging' ? item.status === 'staging' || item.kind === 'staging' : item.status === 'released' || item.status === 'production' || item.kind === 'release')

  useEffect(() => {
    if (!open) return
    setSuiteVersionId(prefill?.suiteVersionId ?? '')
    setEntityId(prefill?.entityId ?? '')
    setSourceType(prefill?.sourceType ?? 'draft')
    setVersionId(prefill?.versionId ?? '')
    setBaselineEnabled(false)
    setBaselineSource('release')
    setBaselineVersionId('')
    setAcknowledge(false)
    setApproved([])
    setIdempotencyKey(crypto.randomUUID())
    preview.reset()
  }, [open, prefill?.suiteVersionId, prefill?.entityId, prefill?.sourceType, prefill?.versionId])

  useEffect(() => {
    if (!suite) return
    setRepetitions(Number(suite.repetition_policy?.default_repetitions ?? 3))
  }, [suite?.id])

  const build = (): CreateEvaluationRunInput => {
    const candidate: EvaluationTargetInput = {
      target_type: targetType,
      source_type: sourceType,
      entity_id: entityId,
      ...(sourceType !== 'draft' && versionId ? { version_id: versionId } : {}),
    }
    const baseline: EvaluationTargetInput | undefined = baselineEnabled
      ? {
          target_type: targetType,
          source_type: baselineSource,
          entity_id: entityId,
          ...(baselineSource !== 'draft' && baselineVersionId ? { version_id: baselineVersionId } : {}),
        }
      : undefined
    return {
      suite_version_id: suiteVersionId,
      repetitions,
      candidate,
      baseline,
      acknowledge_tool_side_effects: acknowledge,
      approved_high_risk_tool_ids: approved,
      idempotency_key: idempotencyKey,
    }
  }

  const highRiskTools = preview.data?.preflight.tools.filter((tool) => tool.risk_level === 'high') ?? []
  const ready = Boolean(preview.data)
    && highRiskTools.every((tool) => approved.includes(tool.id))
    && (!preview.data?.preflight.requires_acknowledgement || acknowledge)

  return (
    <Dialog open={open} onClose={onClose} title="Configure Evaluation Run" className="max-w-4xl" scrollMode="content">
      <div className="space-y-5">
        <div className="grid gap-4 md:grid-cols-2">
          <label className="space-y-2 text-xs text-muted"><span>Evaluator Suite</span><Select value={suiteVersionId} onChange={(event) => { setSuiteVersionId(event.target.value); preview.reset() }} options={[{ value: '', label: 'Select Suite' }, ...(suites.data ?? []).filter((item) => item.current_version_id).map((item) => ({ value: item.current_version_id as string, label: `${item.name} · ${item.current_version}` }))]} /></label>
          <label className="space-y-2 text-xs text-muted"><span>Runs per case</span><Input type="number" min={1} max={25} value={repetitions} onChange={(event) => { setRepetitions(Math.max(1, Math.min(25, Number(event.target.value)))); preview.reset() }} /></label>
        </div>
        <section className="rounded-xl border border-border/80 bg-background/35 p-4">
          <div className="grid gap-4 md:grid-cols-3">
            <label className="space-y-2 text-xs text-muted"><span>{targetType === 'agent' ? 'Agent' : 'Network'}</span><Select value={entityId} onChange={(event) => { setEntityId(event.target.value); setVersionId(''); setBaselineVersionId(''); preview.reset() }} options={[{ value: '', label: `Select ${targetType}` }, ...entities.map((item) => ({ value: item.id, label: item.name }))]} /></label>
            <label className="space-y-2 text-xs text-muted"><span>Candidate environment</span><Select value={sourceType} onChange={(event) => { setSourceType(event.target.value as EvaluationSourceType); setVersionId(''); preview.reset() }} options={[{ value: 'draft', label: 'Current Draft' }, { value: 'staging', label: 'Staging' }, { value: 'release', label: 'Release / Production' }]} /></label>
            <label className="space-y-2 text-xs text-muted"><span>Candidate snapshot</span><Select disabled={sourceType === 'draft'} value={versionId} onChange={(event) => { setVersionId(event.target.value); preview.reset() }} options={[{ value: '', label: sourceType === 'draft' ? 'Current Draft' : 'Select version' }, ...candidates.map((item) => ({ value: item.id, label: item.version }))]} /></label>
          </div>
        </section>
        <section className="rounded-xl border border-border/80 bg-background/35 p-4">
          <div className="flex items-center justify-between gap-4"><div><p className="text-sm font-semibold text-white">Candidate vs Baseline</p><p className="mt-1 text-xs text-muted">Candidate and Baseline remain serial inside each pair.</p></div><Button size="sm" variant="outline" onClick={() => { setBaselineEnabled((value) => !value); preview.reset() }}>{baselineEnabled ? 'Enabled' : 'Disabled'}</Button></div>
          {baselineEnabled ? <div className="mt-4 grid gap-4 md:grid-cols-2"><label className="space-y-2 text-xs text-muted"><span>Baseline environment</span><Select value={baselineSource} onChange={(event) => { setBaselineSource(event.target.value as EvaluationSourceType); setBaselineVersionId(''); preview.reset() }} options={[{ value: 'release', label: 'Release / Production' }, { value: 'staging', label: 'Staging' }, { value: 'draft', label: 'Current Draft' }]} /></label><label className="space-y-2 text-xs text-muted"><span>Baseline snapshot</span><Select disabled={baselineSource === 'draft'} value={baselineVersionId} onChange={(event) => { setBaselineVersionId(event.target.value); preview.reset() }} options={[{ value: '', label: baselineSource === 'draft' ? 'Current Draft' : 'Select version' }, ...baselines.map((item) => ({ value: item.id, label: item.version }))]} /></label></div> : null}
        </section>
        {preview.data ? <section className="rounded-xl border border-primary/25 bg-primary/[0.05] p-4"><div className="grid gap-3 sm:grid-cols-3"><div><p className="text-[9px] uppercase text-muted">Cases</p><p className="mt-1 text-lg text-white">{preview.data.case_count}</p></div><div><p className="text-[9px] uppercase text-muted">Target Runs</p><p className="mt-1 text-lg text-white">{preview.data.target_run_count}</p></div><div><p className="text-[9px] uppercase text-muted">Judge calls</p><p className="mt-1 text-lg text-white">{preview.data.judge_call_count}</p></div></div>{highRiskTools.map((tool) => <label key={tool.id} className="mt-3 flex items-center justify-between rounded-lg border border-red-500/20 p-3 text-xs text-red-300"><span>{tool.name} · high risk</span><input type="checkbox" checked={approved.includes(tool.id)} onChange={(event) => setApproved((current) => event.target.checked ? [...new Set([...current, tool.id])] : current.filter((id) => id !== tool.id))} /></label>)}{preview.data.preflight.requires_acknowledgement ? <label className="mt-3 flex items-start gap-2 text-xs text-amber-300"><input type="checkbox" checked={acknowledge} onChange={(event) => setAcknowledge(event.target.checked)} /><span>I understand that real Tools may cause external side effects. Calls already accepted by external systems cannot be reversed.</span></label> : null}</section> : null}
        <div className="flex justify-end gap-2 border-t border-border pt-4"><Button variant="outline" onClick={onClose}>Cancel</Button><Button variant="outline" loading={preview.isPending} disabled={!suiteVersionId || !entityId || (sourceType !== 'draft' && !versionId) || (baselineEnabled && baselineSource !== 'draft' && !baselineVersionId)} onClick={() => void preview.mutateAsync(build())}>Preview</Button><Button loading={create.isPending} disabled={!ready} onClick={async () => { try { const run = await create.mutateAsync(build()); setIdempotencyKey(crypto.randomUUID()); onCreated(run.id); onClose() } catch (error) { toast.error(error instanceof Error ? error.message : 'Unable to start Evaluation') } }}><Play className="mr-2 h-4 w-4" />Start Evaluation</Button></div>
      </div>
    </Dialog>
  )
}

function RunDetailsDialog({ projectId, organizationId, runId, onClose }: { projectId: string; organizationId: string; runId: string | null; onClose: () => void }) {
  const navigate = useNavigate()
  const query = useEvaluationRun(projectId, runId)
  const cancel = useCancelEvaluationRun(projectId)
  const estimate = useCreateEvaluationEstimate(projectId, runId)
  const [volume, setVolume] = useState(100000)
  const run = query.data
  return (
    <Dialog open={Boolean(runId)} onClose={onClose} title="Evaluation Run" className="max-w-6xl" scrollMode="content">
      {query.isLoading ? <LoadingState message="Loading Evaluation" /> : query.isError || !run ? <ErrorState message="Unable to load Evaluation" /> : (
        <div className="space-y-5">
          <section className="rounded-xl border border-border/80 bg-background/35 p-5">
            <div className="flex items-start justify-between gap-4"><div><div className="flex items-center gap-2"><Badge variant="outline" className={statusClass(run.qualification_status ?? run.status)}>{titleCase(run.qualification_status ?? run.status)}</Badge><span className="font-mono text-[10px] text-muted">{run.id}</span></div><p className="mt-3 text-sm font-semibold text-white">{run.targets.map((item) => item.display_version).join(' vs ')}</p><p className="mt-1 text-xs text-muted">{run.repetitions} Runs per case · {run.mode}</p></div>{!terminalStatuses.has(run.status) ? <Button variant="outline" loading={cancel.isPending} onClick={() => cancel.mutate(run.id)}>Cancel Run</Button> : null}</div>
            <div className="mt-4 grid gap-3 sm:grid-cols-4"><div><p className="text-[9px] uppercase text-muted">Score</p><p className="mt-1 text-xl text-white">{run.overall_score == null ? '—' : run.overall_score.toFixed(1)}</p></div><div><p className="text-[9px] uppercase text-muted">Pass rate</p><p className="mt-1 text-xl text-white">{run.pass_rate == null ? '—' : `${run.pass_rate.toFixed(1)}%`}</p></div><div><p className="text-[9px] uppercase text-muted">Cost</p><p className="mt-1 text-xl text-white">{formatCost(run.measured_total_cost)}</p></div><div><p className="text-[9px] uppercase text-muted">Parallel pairs</p><p className="mt-1 text-xl text-white">{run.execution_policy?.effective_parallel_pairs ?? '—'}</p></div></div>
          </section>
          <section>
            <ResourceSectionHeader title="Trial evidence" count={run.trials?.length ?? 0} />
            <div className="space-y-2">{run.trials?.map((trial) => <details key={trial.id} className="rounded-xl border border-border/80 bg-background/35 p-4"><summary className="cursor-pointer text-sm text-white"><span className="font-medium">{trial.case?.name ?? trial.pair_key}</span><Badge variant="outline" className="ml-2">{titleCase(trial.status)}</Badge></summary><div className="mt-4 grid gap-4 lg:grid-cols-2"><JsonCodeBlock title="Target output" value={trial.output} maxHeight={300} /><JsonCodeBlock title="Metrics and execution reference" value={{ metrics: trial.metrics, execution_reference: trial.execution_reference }} maxHeight={300} /></div>{trial.execution_reference?.trace_id ? <div className="mt-3 flex justify-end"><Button size="sm" variant="outline" onClick={() => navigate(`/organizations/${organizationId}/projects/${projectId}/traces?trace_id=${trial.execution_reference?.trace_id}`)}><ExternalLink className="mr-2 h-3.5 w-3.5" />Open Trace</Button></div> : null}</details>)}</div>
          </section>
          <section className="rounded-xl border border-border/80 bg-background/35 p-4"><div className="flex items-end gap-3"><label className="flex-1 space-y-2 text-xs text-muted"><span>Create another operational estimate without rerunning Trials</span><Input type="number" min={1} value={volume} onChange={(event) => setVolume(Math.max(1, Number(event.target.value)))} /></label><Button loading={estimate.isPending} onClick={() => estimate.mutate({ volume })}><BarChart3 className="mr-2 h-4 w-4" />Estimate</Button></div></section>
        </div>
      )}
    </Dialog>
  )
}

function prefillFromParams(params: URLSearchParams): TargetPrefill {
  const requestedType = params.get('target_type') || params.get('target')
  const source = params.get('source_type')
  return {
    targetType: requestedType === 'network' ? 'network' : 'agent',
    entityId: params.get('entity_id') || params.get('network_id') || params.get('agent_id') || '',
    sourceType: source === 'staging' || source === 'release' ? source : 'draft',
    versionId: params.get('version_id') || '',
  }
}

export default function EvaluationsPage() {
  const { organizationId, projectId } = useParams<{ organizationId: string; projectId: string }>()
  const [params, setParams] = useSearchParams()
  const [initialPrefill] = useState<TargetPrefill>(() => prefillFromParams(params))
  const [tab, setTab] = useState<Tab>('runs')
  const [search, setSearch] = useState('')
  const [authoringOpen, setAuthoringOpen] = useState(false)
  const [authoringPrefill, setAuthoringPrefill] = useState<TargetPrefill>(initialPrefill)
  const [editingSuite, setEditingSuite] = useState<EvaluationSuite | null>(null)
  const [runOpen, setRunOpen] = useState(false)
  const [runPrefill, setRunPrefill] = useState<RunPrefill | null>(null)
  const [runId, setRunId] = useState<string | null>(null)
  const runs = useEvaluationRuns(projectId)
  const suites = useEvaluationSuites(projectId)
  const datasets = useEvaluationDatasets(projectId)
  const archiveSuite = useArchiveEvaluationSuite(projectId)
  const archiveDataset = useArchiveEvaluationDataset(projectId)

  useEffect(() => {
    if (!initialPrefill.entityId) return
    setAuthoringOpen(true)
    const next = new URLSearchParams(params)
    for (const key of ['target_type', 'target', 'entity_id', 'network_id', 'agent_id', 'source_type', 'version_id']) next.delete(key)
    setParams(next, { replace: true })
  }, [initialPrefill.entityId])

  if (!projectId || !organizationId) return <ErrorState title="Project required" description="Open Evaluations inside a Project." />
  if (runs.isLoading || suites.isLoading || datasets.isLoading) return <LoadingState message="Loading Evaluations" />
  if (runs.isError || suites.isError || datasets.isError) return <ErrorState title="Unable to load Evaluations" description="Evaluation resources could not be loaded." />

  const normalizedSearch = search.trim().toLowerCase()
  const filteredRuns = (runs.data ?? []).filter((run) => !normalizedSearch || run.id.toLowerCase().includes(normalizedSearch) || run.targets.some((target) => target.display_name.toLowerCase().includes(normalizedSearch)))
  const filteredSuites = (suites.data ?? []).filter((suite) => !normalizedSearch || suite.name.toLowerCase().includes(normalizedSearch) || suite.description.toLowerCase().includes(normalizedSearch))
  const filteredDatasets = (datasets.data ?? []).filter((dataset) => !normalizedSearch || dataset.name.toLowerCase().includes(normalizedSearch) || dataset.description.toLowerCase().includes(normalizedSearch))

  const openNewSuite = () => {
    setEditingSuite(null)
    setAuthoringPrefill({ targetType: 'agent', entityId: '', sourceType: 'draft', versionId: '' })
    setAuthoringOpen(true)
  }

  const regenerateSuite = (suite: EvaluationSuite) => {
    const reference = suite.authoring_metadata?.reference_target as Partial<EvaluationTargetInput> | undefined
    const entityId = suite.staleness?.entity_id || reference?.entity_id || ''
    if (!entityId) {
      toast.error('This Suite does not preserve a target reference and cannot be regenerated automatically.')
      return
    }
    setEditingSuite(suite)
    setAuthoringPrefill({
      targetType: suite.target_type,
      entityId,
      sourceType: suite.staleness?.source_type || reference?.source_type || 'draft',
      versionId: '',
    })
    setAuthoringOpen(true)
  }

  const action = tab === 'runs'
    ? <Button onClick={() => { setRunPrefill(null); setRunOpen(true) }} disabled={!suites.data?.length}><Play className="mr-2 h-4 w-4" />Run Evaluation</Button>
    : tab === 'suites'
      ? <Button onClick={openNewSuite}><Plus className="mr-2 h-4 w-4" />Create Evaluator Suite</Button>
      : undefined

  return (
    <ResourcePage title="Evaluations" description="Author, run, compare and audit quality contracts for exact Agent and Network snapshots." action={action} className="max-w-[1600px]">
      <ResourceToolbar><div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between"><ResourceTabs value={tab} onChange={setTab} label="Evaluation workspace" tabs={[{ value: 'runs', label: 'Runs', count: runs.data?.length }, { value: 'suites', label: 'Suites', count: suites.data?.length }, { value: 'datasets', label: 'Datasets', count: datasets.data?.length }]} /><ResourceSearch value={search} onChange={setSearch} placeholder={`Search ${tab}`} label={`Search ${tab}`} /></div></ResourceToolbar>

      {tab === 'runs' ? <section><ResourceSectionHeader title="Evaluation Runs" description="Absolute qualifications and paired comparisons with resumable Trial evidence." count={filteredRuns.length} />{filteredRuns.length ? <div className="space-y-3">{filteredRuns.map((run) => <RunCard key={run.id} run={run} onOpen={() => setRunId(run.id)} />)}{runs.hasNextPage ? <div className="flex justify-center pt-2"><Button variant="outline" loading={runs.isFetchingNextPage} onClick={() => void runs.fetchNextPage()}>Load more Runs</Button></div> : null}</div> : <ResourceEmptyState icon={<Beaker className="h-5 w-5" />} title="No Evaluation Runs" description="Create a Suite, preview the workload and run it against an exact snapshot." />}</section> : null}

      {tab === 'suites' ? <section><ResourceSectionHeader title="Evaluator Suites" description="Immutable Test Cases, Judge policy, provenance and snapshot staleness." count={filteredSuites.length} />{filteredSuites.length ? <div className="grid gap-3 lg:grid-cols-2">{filteredSuites.map((suite) => <article key={suite.id} className="rounded-xl border border-border/80 bg-surface/45 p-4"><div className="flex items-start justify-between gap-4"><div className="flex min-w-0 gap-3"><div className="flex h-10 w-10 items-center justify-center rounded-xl border border-primary/20 bg-primary/10 text-primary-light">{suite.target_type === 'agent' ? <Bot className="h-4 w-4" /> : <Workflow className="h-4 w-4" />}</div><div><div className="flex flex-wrap items-center gap-2"><h3 className="text-sm font-semibold text-white">{suite.name}</h3><Badge variant="outline">{suite.current_version}</Badge>{suite.staleness?.status ? <Badge variant="outline" className={statusClass(suite.staleness.status)}>{titleCase(suite.staleness.status)}</Badge> : null}</div><p className="mt-2 text-xs leading-5 text-muted">{suite.description || 'No description'}</p></div></div><Button size="sm" variant="ghost" loading={archiveSuite.isPending} onClick={() => archiveSuite.mutate(suite.id)}><Archive className="h-4 w-4" /></Button></div><div className="mt-4 grid grid-cols-3 gap-3 border-t border-border pt-3 text-xs"><div><p className="text-[9px] uppercase text-muted">Cases</p><p className="mt-1 text-white">{suite.case_count ?? '—'}</p></div><div><p className="text-[9px] uppercase text-muted">Source</p><p className="mt-1 text-white">{titleCase(suite.authoring_source)}</p></div><div><p className="text-[9px] uppercase text-muted">Target</p><p className="mt-1 text-white">{titleCase(suite.target_type)}</p></div></div>{suite.staleness?.status === 'stale' ? <div className="mt-4 flex justify-end"><Button size="sm" variant="outline" onClick={() => regenerateSuite(suite)}><RefreshCw className="mr-2 h-3.5 w-3.5" />Regenerate as new version</Button></div> : null}</article>)}{suites.hasNextPage ? <div className="flex items-center justify-center lg:col-span-2"><Button variant="outline" loading={suites.isFetchingNextPage} onClick={() => void suites.fetchNextPage()}>Load more Suites</Button></div> : null}</div> : <ResourceEmptyState icon={<Sparkles className="h-5 w-5" />} title="No Evaluator Suites" description="Generate with AI, import JSON or create a target-bound Suite manually." action={<Button onClick={openNewSuite}>Create Evaluator Suite</Button>} />}</section> : null}

      {tab === 'datasets' ? <section><ResourceSectionHeader title="Evaluation Datasets" description="Advanced view of immutable question-set versions managed by Evaluator Suites." count={filteredDatasets.length} />{filteredDatasets.length ? <div className="grid gap-3 lg:grid-cols-2">{filteredDatasets.map((dataset) => <article key={dataset.id} className="rounded-xl border border-border/80 bg-surface/45 p-4"><div className="flex items-start justify-between"><div className="flex gap-3"><div className="flex h-10 w-10 items-center justify-center rounded-xl border border-border bg-background"><Database className="h-4 w-4 text-primary-light" /></div><div><h3 className="text-sm font-semibold text-white">{dataset.name}</h3><p className="mt-1 text-xs text-muted">{dataset.case_count} Test Cases · {dataset.current_version}</p></div></div><Button size="sm" variant="ghost" loading={archiveDataset.isPending} onClick={() => archiveDataset.mutate(dataset.id)}><Archive className="h-4 w-4" /></Button></div></article>)}{datasets.hasNextPage ? <div className="flex items-center justify-center lg:col-span-2"><Button variant="outline" loading={datasets.isFetchingNextPage} onClick={() => void datasets.fetchNextPage()}>Load more Datasets</Button></div> : null}</div> : <ResourceEmptyState icon={<Database className="h-5 w-5" />} title="No Datasets" description="Datasets are created transactionally with Evaluator Suites." />}</section> : null}

      <AuthoringDialog
        projectId={projectId}
        open={authoringOpen}
        onClose={() => { setAuthoringOpen(false); setEditingSuite(null) }}
        prefill={authoringPrefill}
        existingSuite={editingSuite}
        onCreated={(suite, target) => {
          setAuthoringOpen(false)
          setEditingSuite(null)
          if (suite.current_version_id) {
            setRunPrefill({ ...target, suiteVersionId: suite.current_version_id })
            setRunOpen(true)
          }
        }}
      />
      <RunDialog projectId={projectId} open={runOpen} onClose={() => setRunOpen(false)} prefill={runPrefill} onCreated={(id) => setRunId(id)} />
      <RunDetailsDialog projectId={projectId} organizationId={organizationId} runId={runId} onClose={() => setRunId(null)} />
    </ResourcePage>
  )
}
