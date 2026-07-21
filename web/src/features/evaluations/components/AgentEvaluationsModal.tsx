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
  useCreateEvaluationRun,
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
  EvaluationTrial,
} from '@/features/evaluations/types'
import { useProviderModels } from '@/features/provider-models/hooks'
import { cn } from '@/lib/utils'
import { SuiteAuthoringWizard } from './SuiteAuthoringWizard'

type Screen = 'run' | 'suites' | 'results' | 'create-suite' | 'result-detail'

interface AgentEvaluationsModalProps {
  open: boolean
  onClose: () => void
  projectId: string
  agentId: string
  agentName: string
}

const terminalStatuses = new Set(['completed', 'partially_completed', 'failed', 'cancelled'])

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
  if (status === 'qualified' || status === 'completed' || status === 'passed') return 'border-emerald-500/30 bg-emerald-500/10 text-emerald-300'
  if (status === 'not_qualified' || status === 'failed') return 'border-red-500/30 bg-red-500/10 text-red-300'
  if (status === 'qualified_with_warnings' || status === 'partially_completed') return 'border-amber-500/30 bg-amber-500/10 text-amber-300'
  if (status === 'inconclusive') return 'border-slate-500/30 bg-slate-500/10 text-slate-300'
  return 'border-border bg-background/50 text-muted'
}

function versionOptions(releases: AgentRelease[], source: EvaluationSourceType) {
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

function runBelongsToAgent(run: EvaluationRun, agentId: string) {
  return run.targets.some((target) => target.target_type === 'agent' && target.entity_id === agentId)
}

function observedOutcome(trial: EvaluationTrial): Record<string, any> | null {
  const value = trial.observed_outcome || trial.metrics?.observed_outcome || trial.output?.observed_outcome
  return value && typeof value === 'object' ? value : null
}

function expectedOutcome(trial: EvaluationTrial): Record<string, any> | null {
  const value = trial.case?.expected_contract?.expected_outcome
  return value && typeof value === 'object' ? value : null
}

function TrialResult({ trial, judgeCall }: { trial: EvaluationTrial; judgeCall?: Record<string, any> }) {
  const observed = observedOutcome(trial)
  const expected = expectedOutcome(trial)
  const contextBudget = judgeCall?.structured_result?.context_budget
  return <article className="rounded-xl border border-border/80 bg-background/35 p-4">
    <div className="flex items-start justify-between gap-4">
      <div className="min-w-0">
        <div className="flex flex-wrap items-center gap-2">
          {trial.passed === true ? <CheckCircle2 className="h-4 w-4 text-emerald-300" /> : trial.passed === false ? <XCircle className="h-4 w-4 text-red-300" /> : <RefreshCw className="h-4 w-4 text-muted" />}
          <p className="text-sm font-semibold text-white">{trial.case?.name ?? trial.pair_key}</p>
          <Badge variant="outline">Run {trial.repetition}</Badge>
          <Badge variant="outline" className={statusClass(trial.status)}>{formatStatus(trial.status)}</Badge>
        </div>
        <p className="mt-2 text-xs leading-5 text-muted">{String(trial.case?.input_payload?.message ?? '')}</p>
      </div>
      <div className="text-right"><p className="text-lg font-semibold text-white">{formatScore(trial.score)}</p><p className="text-[10px] text-muted">score</p></div>
    </div>
    <div className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
      <div className="rounded-lg border border-border/70 bg-surface/30 p-3"><p className="text-[9px] uppercase tracking-wide text-muted">Expected outcome</p><p className="mt-1 text-xs text-white">{formatStatus(expected?.type || trial.case?.case_type || 'success')}</p></div>
      <div className="rounded-lg border border-border/70 bg-surface/30 p-3"><p className="text-[9px] uppercase tracking-wide text-muted">Observed outcome</p><p className="mt-1 text-xs text-white">{formatStatus(observed?.type || 'response')}</p>{observed?.failure_code ? <p className="mt-1 font-mono text-[10px] text-muted">{observed.failure_code}</p> : null}</div>
      <div className="rounded-lg border border-border/70 bg-surface/30 p-3"><p className="text-[9px] uppercase tracking-wide text-muted">Target tokens</p><p className="mt-1 text-xs text-white">{Number(trial.metrics?.input_tokens || 0).toLocaleString()} in · {Number(trial.metrics?.output_tokens || 0).toLocaleString()} out</p></div>
      <div className="rounded-lg border border-border/70 bg-surface/30 p-3"><p className="text-[9px] uppercase tracking-wide text-muted">Judge tokens</p><p className="mt-1 text-xs text-white">{judgeCall?.input_tokens?.toLocaleString?.() ?? '—'} in · {judgeCall?.output_tokens?.toLocaleString?.() ?? '—'} out</p></div>
    </div>
    {contextBudget ? <p className="mt-3 text-[10px] text-muted">Judge context: {Number(contextBudget.estimated_input_tokens || 0).toLocaleString()} / {Number(contextBudget.maximum_input_tokens || 0).toLocaleString()} tokens{contextBudget.truncation_applied ? ` · compacted ${contextBudget.truncated_sections?.join(', ')}` : ' · no truncation'}</p> : null}
    {trial.failure_detail ? <p className="mt-3 rounded-lg border border-red-500/20 bg-red-500/[0.05] p-3 text-xs text-red-300">{trial.failure_detail}</p> : null}
    {trial.checks?.length ? <details className="mt-3 rounded-lg border border-border/70 bg-surface/20 p-3"><summary className="cursor-pointer text-xs font-medium text-white">Checks and Judge evidence</summary><div className="mt-3 space-y-2">{trial.checks.map((check) => <div key={check.id} className="flex items-start justify-between gap-3 text-xs"><div><p className="text-white">{check.evaluator_key}</p><p className="mt-1 text-muted">{check.reason || check.dimension}</p></div><Badge variant="outline" className={statusClass(check.status)}>{formatScore(check.score)}</Badge></div>)}</div></details> : null}
  </article>
}

export function AgentEvaluationsModal({ open, onClose, projectId, agentId, agentName }: AgentEvaluationsModalProps) {
  const suitesQuery = useEvaluationSuites(projectId)
  const runsQuery = useEvaluationRuns(projectId)
  const modelsQuery = useProviderModels(projectId)
  const releasesQuery = useReleases(agentId)
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

  const suites = useMemo(() => (suitesQuery.data ?? []).filter((suite) => suite.target_type === 'agent' && suite.current_version_id), [suitesQuery.data])
  const releases = releasesQuery.data ?? []
  const recentRuns = useMemo(() => (runsQuery.data ?? []).filter((run) => runBelongsToAgent(run, agentId)), [agentId, runsQuery.data])
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
    const candidate: EvaluationTargetInput = { target_type: 'agent', source_type: sourceType, entity_id: agentId }
    if (sourceType !== 'draft' && versionId) candidate.version_id = versionId
    let baseline: EvaluationTargetInput | undefined
    if (compare) {
      baseline = { target_type: 'agent', source_type: baselineSource, entity_id: agentId }
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
    try { await preview.mutateAsync(buildRunInput()) } catch (error) { toast.error(error instanceof Error ? error.message : 'Unable to preview Evaluation') }
  }

  const startRun = async () => {
    try {
      const run = await createRun.mutateAsync(buildRunInput())
      toast.success('Evaluation Run queued')
      setSelectedRunId(run.id)
      setScreen('result-detail')
      setIdempotencyKey(crypto.randomUUID())
    } catch (error) { toast.error(error instanceof Error ? error.message : 'Unable to start Evaluation') }
  }

  const highRiskTools = preview.data?.preflight.tools.filter((tool) => tool.risk_level === 'high') ?? []
  const highRiskApproved = highRiskTools.every((tool) => approvedHighRiskIds.includes(tool.id))
  const needsAcknowledgement = preview.data?.preflight.requires_acknowledgement ?? false
  const readyToStart = Boolean(preview.data) && highRiskApproved && (!needsAcknowledgement || acknowledge)
  const targetReady = sourceType === 'draft' || Boolean(versionId)
  const baselineReady = !compare || baselineSource === 'draft' || Boolean(baselineVersionId)
  const selectedRun = selectedRunQuery.data
  const loading = suitesQuery.isLoading || runsQuery.isLoading || releasesQuery.isLoading || modelsQuery.isLoading
  const failed = suitesQuery.isError || runsQuery.isError || releasesQuery.isError || modelsQuery.isError

  return <Dialog open={open} onClose={onClose} title="Evaluate Agent" className="max-w-6xl overflow-hidden bg-surface/95">
    <div className="-m-6 flex max-h-[82vh] min-h-[640px] flex-col overflow-hidden">
      <div className="flex shrink-0 items-center justify-between gap-4 border-b border-border/80 px-5 py-4">
        <div className="flex min-w-0 items-center gap-3">
          {(screen === 'create-suite' || screen === 'result-detail') ? <button type="button" onClick={() => setScreen(screen === 'create-suite' ? 'suites' : 'results')} className="flex h-8 w-8 items-center justify-center rounded-lg border border-border text-muted hover:text-white"><ArrowLeft className="h-4 w-4" /></button> : null}
          <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl border border-primary/20 bg-primary/10 text-primary-light"><Bot className="h-4 w-4" /></div>
          <div className="min-w-0"><p className="truncate text-sm font-semibold text-white">{agentName}</p><p className="text-[11px] text-muted">Create, run and inspect Evaluator Suites without leaving the Playground.</p></div>
        </div>
        {(screen === 'run' || screen === 'suites' || screen === 'results') ? <div className="flex rounded-lg border border-border bg-background/45 p-1">{([['run', 'Run'], ['suites', 'Evaluator Suites'], ['results', 'Results']] as const).map(([value, label]) => <button key={value} type="button" onClick={() => setScreen(value)} className={cn('rounded-md px-3 py-1.5 text-xs font-medium transition-colors', screen === value ? 'bg-primary/15 text-primary-light' : 'text-muted hover:text-white')}>{label}</button>)}</div> : null}
      </div>
      <div className="scrollbar-thin min-h-0 flex-1 overflow-y-auto p-5">
        {loading ? <LoadingState message="Loading Evaluations" /> : failed ? <ErrorState message="Unable to load Agent Evaluations" /> : screen === 'create-suite' ? <SuiteAuthoringWizard projectId={projectId} agentId={agentId} releases={releases} providerModels={modelsQuery.data ?? []} onCancel={() => setScreen('suites')} onCreated={(suite) => { setSuiteVersionId(suite.current_version_id || ''); setScreen('run') }} /> : screen === 'run' ? <div className="mx-auto max-w-4xl space-y-5">
          {!suites.length ? <div className="rounded-xl border border-dashed border-border p-10 text-center"><Beaker className="mx-auto h-8 w-8 text-muted" /><h3 className="mt-3 text-sm font-semibold text-white">Create your first Evaluator Suite</h3><p className="mx-auto mt-2 max-w-lg text-xs leading-5 text-muted">Generate it from the Agent snapshot, import JSON or create cases manually.</p><Button className="mt-4" onClick={() => setScreen('create-suite')}><Plus className="mr-2 h-4 w-4" />Create Evaluator Suite</Button></div> : <>
            <section className="rounded-xl border border-border/80 bg-background/35 p-4"><div className="grid gap-4 md:grid-cols-[minmax(0,1fr)_180px]"><label className="space-y-2 text-xs text-muted"><span>Evaluator Suite</span><Select value={suiteVersionId} onChange={(event) => { setSuiteVersionId(event.target.value); resetPreview() }} options={[{ value: '', label: 'Select a Suite' }, ...suites.map((suite) => ({ value: suite.current_version_id as string, label: `${suite.name} · ${suite.current_version}` }))]} /></label><label className="space-y-2 text-xs text-muted"><span>Runs per Test Case</span><Input type="number" min={1} max={25} value={repetitions} onChange={(event) => { setRepetitions(Math.max(1, Math.min(25, Number(event.target.value)))); resetPreview() }} /></label></div>{selectedSuite ? <p className="mt-3 text-[11px] leading-5 text-muted">{selectedSuite.description || 'Versioned Test Cases and acceptance criteria.'}</p> : null}</section>
            <section className="rounded-xl border border-border/80 bg-background/35 p-4"><div className="flex items-center gap-2"><Sparkles className="h-4 w-4 text-primary-light" /><div><p className="text-sm font-semibold text-white">Candidate snapshot</p><p className="text-[11px] text-muted">The exact Agent version that answers every Test Case.</p></div></div><div className="mt-4 grid gap-4 md:grid-cols-2"><label className="space-y-2 text-xs text-muted"><span>Environment</span><Select value={sourceType} onChange={(event) => { setSourceType(event.target.value as EvaluationSourceType); setVersionId(''); resetPreview() }} options={[{ value: 'draft', label: 'Current Draft' }, { value: 'staging', label: 'Staging' }, { value: 'release', label: 'Release / Production' }]} /></label><label className="space-y-2 text-xs text-muted"><span>Exact snapshot</span><Select disabled={sourceType === 'draft'} value={versionId} onChange={(event) => { setVersionId(event.target.value); resetPreview() }} options={[{ value: '', label: sourceType === 'draft' ? 'Current Draft will be frozen' : 'Select exact snapshot' }, ...candidateVersions.map((release) => ({ value: release.id, label: `${release.version} · ${formatStatus(release.status)}` }))]} /></label></div></section>
            <section className="rounded-xl border border-border/80 bg-background/35 p-4"><div className="flex items-center justify-between gap-4"><div><div className="flex items-center gap-2"><GitCompareArrows className="h-4 w-4 text-primary-light" /><p className="text-sm font-semibold text-white">Compare with a Baseline</p></div><p className="mt-1 text-[11px] text-muted">Optional paired execution against another exact snapshot.</p></div><button type="button" onClick={() => { setCompare((value) => !value); resetPreview() }} className={cn('rounded-lg border px-3 py-2 text-xs font-medium', compare ? 'border-primary/30 bg-primary/10 text-primary-light' : 'border-border text-muted')}>{compare ? 'Enabled' : 'Disabled'}</button></div>{compare ? <div className="mt-4 grid gap-4 md:grid-cols-2"><label className="space-y-2 text-xs text-muted"><span>Baseline environment</span><Select value={baselineSource} onChange={(event) => { setBaselineSource(event.target.value as EvaluationSourceType); setBaselineVersionId(''); resetPreview() }} options={[{ value: 'release', label: 'Release / Production' }, { value: 'staging', label: 'Staging' }, { value: 'draft', label: 'Current Draft' }]} /></label><label className="space-y-2 text-xs text-muted"><span>Exact baseline</span><Select disabled={baselineSource === 'draft'} value={baselineVersionId} onChange={(event) => { setBaselineVersionId(event.target.value); resetPreview() }} options={[{ value: '', label: baselineSource === 'draft' ? 'Current Draft will be frozen' : 'Select exact snapshot' }, ...baselineVersions.map((release) => ({ value: release.id, label: `${release.version} · ${formatStatus(release.status)}` }))]} /></label></div> : null}</section>
            {preview.data ? <section className="rounded-xl border border-primary/25 bg-primary/[0.05] p-4"><div className="grid gap-3 sm:grid-cols-3"><div><p className="text-[10px] uppercase tracking-wide text-muted">Test Cases</p><p className="mt-1 text-xl font-semibold text-white">{preview.data.case_count}</p></div><div><p className="text-[10px] uppercase tracking-wide text-muted">Agent Runs</p><p className="mt-1 text-xl font-semibold text-white">{preview.data.target_run_count}</p></div><div><p className="text-[10px] uppercase tracking-wide text-muted">Judge calls</p><p className="mt-1 text-xl font-semibold text-white">{preview.data.judge_call_count}</p></div></div><div className="mt-4 border-t border-primary/15 pt-4"><div className="flex items-center gap-2"><ShieldAlert className="h-4 w-4 text-amber-300" /><p className="text-xs font-semibold text-white">Tool execution preflight</p></div><div className="mt-3 space-y-2">{preview.data.preflight.tools.length ? preview.data.preflight.tools.map((tool) => <label key={tool.id} className="flex items-center justify-between gap-3 rounded-lg border border-border/80 bg-background/45 px-3 py-2"><div><p className="text-xs font-medium text-white">{tool.name}</p><p className="mt-1 text-[10px] text-muted">{tool.source} · {tool.risk_level} risk</p></div>{tool.risk_level === 'high' ? <span className="flex items-center gap-2 text-[10px] text-red-300"><input type="checkbox" checked={approvedHighRiskIds.includes(tool.id)} onChange={(event) => setApprovedHighRiskIds((current) => event.target.checked ? [...new Set([...current, tool.id])] : current.filter((id) => id !== tool.id))} />Explicit approval</span> : null}</label>) : <p className="text-xs text-muted">No Tools detected in the selected snapshots.</p>}</div>{needsAcknowledgement ? <label className="mt-4 flex items-start gap-3 rounded-lg border border-amber-500/20 bg-amber-500/[0.06] p-3 text-xs text-amber-200"><input type="checkbox" checked={acknowledge} onChange={(event) => setAcknowledge(event.target.checked)} className="mt-0.5" /><span>I understand that this Evaluation executes the real Tools shown above and can produce external side effects.</span></label> : null}</div></section> : null}
            <div className="flex justify-end gap-2 border-t border-border pt-4"><Button variant="outline" onClick={() => setScreen('create-suite')}><Plus className="mr-2 h-4 w-4" />New Suite</Button><Button variant="outline" loading={preview.isPending} disabled={!suiteVersionId || !targetReady || !baselineReady} onClick={() => void previewRun()}>Preview workload</Button><Button loading={createRun.isPending} disabled={!readyToStart} onClick={() => void startRun()}><Play className="mr-2 h-4 w-4" />Start Evaluation</Button></div>
          </>}
        </div> : screen === 'suites' ? <div className="mx-auto max-w-5xl"><div className="mb-4 flex items-center justify-between gap-4"><div><h3 className="text-sm font-semibold text-white">Evaluator Suites</h3><p className="mt-1 text-xs text-muted">Reusable, versioned Test Cases and grading policies.</p></div><Button onClick={() => setScreen('create-suite')}><Plus className="mr-2 h-4 w-4" />New Suite</Button></div>{suites.length ? <div className="grid gap-3 md:grid-cols-2">{suites.map((suite) => <article key={suite.id} className="rounded-xl border border-border/80 bg-background/40 p-4"><div className="flex items-start justify-between gap-4"><div><div className="flex flex-wrap items-center gap-2"><h4 className="text-sm font-semibold text-white">{suite.name}</h4>{suite.authoring_source ? <Badge variant="outline">{suite.authoring_source.replace('_', ' ')}</Badge> : null}</div><p className="mt-1 text-xs leading-5 text-muted">{suite.description || 'No description'}</p></div><Badge variant="outline">{suite.current_version}</Badge></div><div className="mt-4 grid grid-cols-3 gap-3 border-t border-border pt-3 text-xs"><div><p className="text-[9px] uppercase tracking-wide text-muted">Test Cases</p><p className="mt-1 text-white">{suite.case_count ?? '—'}</p></div><div><p className="text-[9px] uppercase tracking-wide text-muted">Minimum score</p><p className="mt-1 text-white">{String(suite.acceptance_policy?.minimum_score ?? 70)}</p></div><div><p className="text-[9px] uppercase tracking-wide text-muted">Default Runs</p><p className="mt-1 text-white">{String(suite.repetition_policy?.default_repetitions ?? 3)}</p></div></div>{suite.source_snapshot_hash ? <p className="mt-3 truncate font-mono text-[9px] text-muted">Generated from {suite.source_snapshot_hash}</p> : null}<div className="mt-4 flex justify-end"><Button size="sm" onClick={() => { setSuiteVersionId(suite.current_version_id as string); setScreen('run') }}>Use Suite</Button></div></article>)}</div> : <div className="rounded-xl border border-dashed border-border p-10 text-center text-sm text-muted">No Evaluator Suites configured for Agents.</div>}</div> : screen === 'results' ? <div className="mx-auto max-w-5xl"><div className="mb-4"><h3 className="text-sm font-semibold text-white">Agent Evaluation Results</h3><p className="mt-1 text-xs text-muted">Runs remain associated with the exact evaluated snapshot.</p></div>{recentRuns.length ? <div className="space-y-2">{recentRuns.map((run) => { const targetItem = run.targets.find((item) => item.side === 'candidate' || item.side === 'single'); const active = !terminalStatuses.has(run.status); return <button key={run.id} type="button" onClick={() => { setSelectedRunId(run.id); setScreen('result-detail') }} className="flex w-full items-center gap-4 rounded-xl border border-border/80 bg-background/40 p-4 text-left hover:border-primary/30"><div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-border bg-surface"><Beaker className="h-4 w-4 text-primary-light" /></div><div className="min-w-0 flex-1"><div className="flex flex-wrap items-center gap-2"><p className="text-sm font-semibold text-white">{targetItem?.display_version ?? 'Agent snapshot'}</p><Badge variant="outline" className={statusClass(run.qualification_status ?? run.status)}>{formatStatus(run.qualification_status ?? run.status)}</Badge>{active ? <RefreshCw className="h-3.5 w-3.5 animate-spin text-primary-light" /> : null}</div><p className="mt-1 text-[11px] text-muted">{run.repetitions} Runs per Test Case · {run.mode}</p></div><div className="grid grid-cols-2 gap-5 text-right"><div><p className="text-[9px] uppercase tracking-wide text-muted">Score</p><p className="mt-1 text-sm font-semibold text-white">{formatScore(run.overall_score)}</p></div><div><p className="text-[9px] uppercase tracking-wide text-muted">Cost</p><p className="mt-1 text-sm font-semibold text-white">{formatCost(run.measured_total_cost)}</p></div></div><ChevronRight className="h-4 w-4 text-muted" /></button> })}</div> : <div className="rounded-xl border border-dashed border-border p-10 text-center text-sm text-muted">No Evaluations have been run for this Agent.</div>}</div> : <div className="mx-auto max-w-5xl">{selectedRunQuery.isLoading ? <LoadingState message="Loading Evaluation Result" /> : selectedRunQuery.isError || !selectedRun ? <ErrorState message="Unable to load Evaluation Result" /> : <div className="space-y-5"><section className="rounded-xl border border-border/80 bg-background/40 p-5"><div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between"><div><div className="flex flex-wrap items-center gap-2"><Badge variant="outline" className={statusClass(selectedRun.qualification_status ?? selectedRun.status)}>{formatStatus(selectedRun.qualification_status ?? selectedRun.status)}</Badge>{!terminalStatuses.has(selectedRun.status) ? <RefreshCw className="h-3.5 w-3.5 animate-spin text-primary-light" /> : null}</div><h3 className="mt-3 text-base font-semibold text-white">{selectedRun.targets.find((targetItem) => targetItem.side === 'candidate' || targetItem.side === 'single')?.display_version ?? 'Agent Evaluation'}</h3><p className="mt-1 text-xs text-muted">{selectedRun.repetitions} Runs per Test Case · {selectedRun.mode}</p></div><div className="grid grid-cols-3 gap-5"><div><p className="text-[9px] uppercase tracking-wide text-muted">Score</p><p className="mt-1 text-lg font-semibold text-white">{formatScore(selectedRun.overall_score)}</p></div><div><p className="text-[9px] uppercase tracking-wide text-muted">Pass rate</p><p className="mt-1 text-lg font-semibold text-white">{selectedRun.pass_rate == null ? '—' : `${selectedRun.pass_rate.toFixed(1)}%`}</p></div><div><p className="text-[9px] uppercase tracking-wide text-muted">Cost</p><p className="mt-1 text-sm font-semibold text-white">{formatCost(selectedRun.measured_total_cost)}</p></div></div></div></section><section><div className="mb-3"><p className="text-sm font-semibold text-white">Test Case results</p><p className="mt-1 text-[11px] text-muted">Each row is one Agent Run judged against its explicit expected outcome.</p></div><div className="space-y-2">{(selectedRun.trials ?? []).map((trial) => <TrialResult key={trial.id} trial={trial} judgeCall={(selectedRun.judge_calls ?? []).find((call) => call.trial_id === trial.id)} />)}</div></section></div>}</div>}
      </div>
    </div>
  </Dialog>
}
