import { useMemo, useState, type ReactNode } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { toast } from 'sonner'
import {
  Activity,
  AlertTriangle,
  ArrowRight,
  Bot,
  Bug,
  Check,
  CheckCircle2,
  ChevronLeft,
  CircleDot,
  Clock3,
  Coins,
  Eye,
  GitBranch,
  History,
  ListChecks,
  Maximize2,
  Play,
  Plus,
  Rocket,
  RotateCcw,
  Search,
  Settings2,
  ShieldCheck,
  Workflow,
  X,
  ZoomIn,
  ZoomOut,
  type LucideIcon,
} from 'lucide-react'

import { useAgents } from '@/features/agents/hooks'
import type { Agent } from '@/features/agents/types'
import { useWorkspace } from '@/features/workspace/WorkspaceProvider'
import { cn } from '@/lib/utils'

type Environment = 'draft' | 'staging' | 'production'
type PanelTab = 'runs' | 'trace' | 'debug' | 'validation'
type InspectorTab = 'inspector' | 'versions'
type NodeId = 'entry' | 'coordinator' | 'billing' | 'technical' | 'end'
type ReleaseAction = 'stage' | 'publish' | 'rollback' | null

type Run = {
  id: string
  status: 'success' | 'error' | 'running'
  environment: Environment
  title: string
  duration: string
  cost: string
  time: string
  path: NodeId[]
}

const fallbackAgents: Agent[] = [
  { id: 'mock-coordinator', project_id: 'mock', name: 'Coordinator', description: 'Classifies requests and selects the correct specialist.', provider: 'openai', model: 'gpt-5.2', status: 'active' },
  { id: 'mock-billing', project_id: 'mock', name: 'Billing Specialist', description: 'Handles invoices, payments and subscriptions.', provider: 'openai', model: 'gpt-5.2-mini', status: 'active' },
  { id: 'mock-technical', project_id: 'mock', name: 'Technical Support', description: 'Investigates incidents and technical questions.', provider: 'anthropic', model: 'claude-sonnet-4.5', status: 'active' },
]

const runs: Run[] = [
  { id: 'run-1', status: 'success', environment: 'production', title: 'Invoice status request', duration: '1.84s', cost: '$0.012', time: '2 min ago', path: ['entry', 'coordinator', 'billing', 'end'] },
  { id: 'run-2', status: 'success', environment: 'staging', title: 'Password reset guidance', duration: '2.21s', cost: '$0.017', time: '18 min ago', path: ['entry', 'coordinator', 'technical', 'end'] },
  { id: 'run-3', status: 'error', environment: 'staging', title: 'API timeout investigation', duration: '0.73s', cost: '$0.004', time: '41 min ago', path: ['entry', 'coordinator', 'technical'] },
  { id: 'run-4', status: 'running', environment: 'draft', title: 'Refund eligibility check', duration: 'Running', cost: '$0.006', time: 'Now', path: ['entry', 'coordinator', 'billing'] },
]

const panelItems: Array<{ id: PanelTab; label: string; icon: LucideIcon; count?: number }> = [
  { id: 'runs', label: 'Runs', icon: Activity, count: 4 },
  { id: 'trace', label: 'Trace', icon: GitBranch },
  { id: 'debug', label: 'Debug', icon: Bug },
  { id: 'validation', label: 'Validation', icon: ListChecks, count: 2 },
]

function Badge({ children, tone = 'default' }: { children: ReactNode; tone?: 'default' | 'staging' | 'production' | 'warning' }) {
  const tones = {
    default: 'border-border/80 bg-background/45 text-muted',
    staging: 'border-indigo-500/30 bg-indigo-500/10 text-indigo-300',
    production: 'border-emerald-500/30 bg-emerald-500/10 text-emerald-300',
    warning: 'border-amber-500/30 bg-amber-500/10 text-amber-300',
  }
  return <span className={cn('rounded-md border px-1.5 py-0.5 text-[9px] font-semibold uppercase tracking-wide', tones[tone])}>{children}</span>
}

function PanelHeader({ eyebrow, title, description }: { eyebrow: string; title: string; description: string }) {
  return (
    <div className="border-b border-border/80 px-4 py-3.5">
      <p className="text-[9px] font-semibold uppercase tracking-[0.18em] text-muted/80">{eyebrow}</p>
      <h2 className="mt-1 text-sm font-semibold text-white">{title}</h2>
      <p className="mt-1 text-[11px] leading-4 text-muted">{description}</p>
    </div>
  )
}

function StatusDot({ status }: { status: Run['status'] }) {
  return <span className={cn('mt-1 h-2 w-2 shrink-0 rounded-full', status === 'success' && 'bg-emerald-400', status === 'error' && 'bg-red-400', status === 'running' && 'animate-pulse bg-blue-400')} />
}

function RunsPanel({ selectedRunId, onSelect }: { selectedRunId: string; onSelect: (id: string) => void }) {
  return (
    <div className="flex h-full min-h-0 flex-col">
      <PanelHeader eyebrow="Network operations" title="Executions" description="Inspect path, cost and release used by each run." />
      <div className="flex items-center gap-2 border-b border-border/70 px-3 py-2">
        <button type="button" className="rounded-md border border-primary/30 bg-primary/10 px-2 py-1 text-[10px] font-medium text-primary-light">All runs</button>
        <button type="button" className="rounded-md px-2 py-1 text-[10px] font-medium text-muted hover:text-white">Errors</button>
        <Search className="ml-auto h-3.5 w-3.5 text-muted" />
      </div>
      <div className="min-h-0 flex-1 space-y-1.5 overflow-y-auto p-2.5 scrollbar-thin">
        {runs.map((run) => (
          <button key={run.id} type="button" onClick={() => onSelect(run.id)} className={cn('w-full rounded-xl border p-3 text-left transition', selectedRunId === run.id ? 'border-primary/35 bg-primary/[0.08]' : 'border-border/70 bg-background/30 hover:border-border hover:bg-background/50')}>
            <div className="flex gap-2.5">
              <StatusDot status={run.status} />
              <div className="min-w-0 flex-1">
                <div className="flex items-start justify-between gap-2">
                  <p className="truncate text-xs font-medium text-white">{run.title}</p>
                  <span className="shrink-0 text-[9px] text-muted">{run.time}</span>
                </div>
                <div className="mt-2 flex items-center gap-2">
                  <Badge tone={run.environment === 'production' ? 'production' : run.environment === 'staging' ? 'staging' : 'default'}>{run.environment}</Badge>
                  <span className="text-[10px] text-muted">{Math.max(run.path.length - 2, 1)} hops</span>
                </div>
                <div className="mt-2.5 flex gap-3 text-[10px] text-muted">
                  <span className="inline-flex items-center gap-1"><Clock3 className="h-3 w-3" />{run.duration}</span>
                  <span className="inline-flex items-center gap-1"><Coins className="h-3 w-3" />{run.cost}</span>
                </div>
              </div>
            </div>
          </button>
        ))}
      </div>
    </div>
  )
}

function TracePanel({ run }: { run: Run }) {
  const labels: Record<NodeId, string> = { entry: 'Request received', coordinator: 'Coordinator classified request', billing: 'Billing Specialist completed', technical: run.status === 'error' ? 'Technical Support failed' : 'Technical Support completed', end: 'Response returned' }
  return (
    <div className="flex h-full min-h-0 flex-col">
      <PanelHeader eyebrow="Selected execution" title="Trace path" description={`${run.title} · ${run.duration}`} />
      <div className="min-h-0 flex-1 overflow-y-auto p-4 scrollbar-thin">
        {run.path.map((node, index) => {
          const failed = run.status === 'error' && index === run.path.length - 1
          return (
            <div key={node} className="relative flex gap-3 pb-5 last:pb-0">
              {index < run.path.length - 1 && <div className="absolute left-[7px] top-4 h-[calc(100%-4px)] w-px bg-border" />}
              <span className={cn('relative z-10 mt-1 h-3.5 w-3.5 rounded-full border-2', failed ? 'border-red-400 bg-red-500/20' : 'border-emerald-400 bg-emerald-500/20')} />
              <div className="min-w-0 flex-1 rounded-lg border border-border/70 bg-background/30 p-2.5">
                <p className="text-[11px] font-medium text-white">{labels[node]}</p>
                <p className="mt-1 text-[10px] text-muted">+{index * 420}ms · release pinned</p>
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}

function DebugPanel({ run }: { run: Run }) {
  const events = [
    ['network.started', `environment=${run.environment}`],
    ['node.entered', 'node=coordinator'],
    ['agent.release.resolved', 'version=v0.4.20260713.00'],
    ['handoff.selected', run.path.includes('billing') ? 'key=billing_support' : 'key=technical_support'],
    [run.status === 'error' ? 'node.failed' : 'network.completed', run.status === 'error' ? 'timeout_after_ms=700' : 'status=success'],
  ]
  return (
    <div className="flex h-full min-h-0 flex-col">
      <PanelHeader eyebrow="Runtime detail" title="Debug events" description="Raw orchestration events for the selected run." />
      <div className="min-h-0 flex-1 space-y-2 overflow-y-auto p-3 font-mono text-[10px] scrollbar-thin">
        {events.map(([name, payload], index) => <div key={`${name}-${index}`} className="rounded-lg border border-border/70 bg-black/20 p-2.5"><p className="text-primary-light">{name}</p><p className="mt-1 break-all text-muted">{payload}</p></div>)}
      </div>
    </div>
  )
}

function ValidationPanel() {
  const checks = [
    ['One entry point', true],
    ['All nodes are reachable', true],
    ['Every route reaches END', true],
    ['Agent release bindings resolve', true],
    ['Technical Support has no fallback model', false],
    ['Latest Draft has no successful run', false],
  ] as const
  return (
    <div className="flex h-full min-h-0 flex-col">
      <PanelHeader eyebrow="Release readiness" title="Validation" description="Blocking rules and warnings before Staging." />
      <div className="grid grid-cols-2 gap-2 border-b border-border/70 p-3">
        <div className="rounded-lg border border-emerald-500/20 bg-emerald-500/[0.05] p-2.5"><p className="text-lg font-semibold text-emerald-300">0</p><p className="text-[10px] text-muted">Blockers</p></div>
        <div className="rounded-lg border border-amber-500/20 bg-amber-500/[0.05] p-2.5"><p className="text-lg font-semibold text-amber-300">2</p><p className="text-[10px] text-muted">Warnings</p></div>
      </div>
      <div className="min-h-0 flex-1 space-y-1.5 overflow-y-auto p-3 scrollbar-thin">
        {checks.map(([label, passed]) => <div key={label} className="flex gap-2 rounded-lg border border-border/65 bg-background/30 p-2.5">{passed ? <CheckCircle2 className="mt-0.5 h-3.5 w-3.5 shrink-0 text-emerald-400" /> : <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0 text-amber-400" />}<div><p className="text-[11px] font-medium text-white">{label}</p><p className="mt-0.5 text-[10px] leading-4 text-muted">{passed ? 'Ready for snapshot resolution.' : 'Review before Production.'}</p></div></div>)}
      </div>
    </div>
  )
}

function OperationsPanel({ tab, run, selectedRunId, onSelectRun }: { tab: PanelTab; run: Run; selectedRunId: string; onSelectRun: (id: string) => void }) {
  if (tab === 'runs') return <RunsPanel selectedRunId={selectedRunId} onSelect={onSelectRun} />
  if (tab === 'trace') return <TracePanel run={run} />
  if (tab === 'debug') return <DebugPanel run={run} />
  return <ValidationPanel />
}

function CanvasNode({ id, label, subtitle, selected, active, error, className, onSelect }: { id: NodeId; label: string; subtitle: string; selected: boolean; active: boolean; error?: boolean; className: string; onSelect: (id: NodeId) => void }) {
  const terminal = id === 'entry' || id === 'end'
  return (
    <button type="button" onClick={() => onSelect(id)} className={cn('absolute z-20 border bg-surface/95 text-left transition', terminal ? 'flex h-14 w-28 items-center justify-center rounded-full' : 'w-52 rounded-2xl p-3.5', selected ? 'border-primary/70 shadow-[0_0_0_3px_rgba(59,130,246,0.12),0_18px_35px_rgba(0,0,0,0.24)]' : active ? error ? 'border-red-500/55 shadow-xl shadow-red-950/10' : 'border-emerald-500/45 shadow-xl shadow-black/15' : 'border-border/90 opacity-65 shadow-xl shadow-black/10 hover:opacity-100', className)}>
      {terminal ? <div className="flex items-center gap-2"><CircleDot className={cn('h-4 w-4', id === 'entry' ? 'text-primary-light' : 'text-emerald-400')} /><span className="text-[11px] font-semibold uppercase tracking-[0.16em] text-white">{label}</span></div> : <><div className="flex items-start gap-3"><div className={cn('flex h-9 w-9 shrink-0 items-center justify-center rounded-xl border', error ? 'border-red-500/30 bg-red-500/10 text-red-300' : 'border-primary/25 bg-primary/10 text-primary-light')}><Bot className="h-4 w-4" /></div><div className="min-w-0 flex-1"><div className="flex items-start justify-between gap-2"><p className="truncate text-xs font-semibold text-white">{label}</p><span className={cn('mt-0.5 h-2 w-2 rounded-full', error ? 'bg-red-400' : 'bg-emerald-400')} /></div><p className="mt-1 truncate text-[10px] text-muted">{subtitle}</p></div></div><div className="mt-3 flex items-center justify-between border-t border-border/70 pt-2.5 text-[9px] text-muted"><span>Release pinned</span><span className="font-mono text-slate-300">v0.{id === 'coordinator' ? '4' : id === 'billing' ? '3' : '1'}</span></div></>}
    </button>
  )
}

function Connection({ d, active, error }: { d: string; active: boolean; error?: boolean }) {
  return <><path d={d} fill="none" stroke="rgba(71,85,105,0.45)" strokeWidth="2" />{active && <path d={d} fill="none" stroke={error ? 'rgba(248,113,113,0.95)' : 'rgba(96,165,250,0.95)'} strokeWidth="2.5" strokeLinecap="round" strokeDasharray="8 8" />}</>
}

function EmptyNetwork({ onCreateAgent }: { onCreateAgent: () => void }) {
  return (
    <div className="flex min-h-0 flex-1 items-center justify-center bg-background p-8">
      <div className="w-full max-w-2xl rounded-3xl border border-border/90 bg-surface/70 p-8 text-center shadow-2xl shadow-black/20">
        <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl border border-primary/25 bg-primary/10 text-primary-light"><Workflow className="h-6 w-6" /></div>
        <p className="mt-5 text-[10px] font-semibold uppercase tracking-[0.2em] text-primary-light">First Network</p>
        <h2 className="mt-2 text-2xl font-semibold text-white">Build your first Agent Network</h2>
        <p className="mx-auto mt-3 max-w-lg text-sm leading-6 text-muted">Choose the Agent that receives requests. Woobe creates a valid ENTRY → Agent → END flow automatically.</p>
        <button type="button" onClick={onCreateAgent} className="mt-6 inline-flex items-center gap-2 rounded-xl bg-primary px-4 py-2.5 text-sm font-semibold text-white"><Plus className="h-4 w-4" />Create first Agent</button>
        <div className="mt-8 grid grid-cols-[1fr_auto_1fr_auto_1fr] items-center gap-3 rounded-2xl border border-border/70 bg-background/35 p-4 text-[11px] text-muted"><span className="rounded-full border border-border px-3 py-2">ENTRY</span><ArrowRight className="h-4 w-4" /><span className="rounded-xl border border-dashed border-primary/40 px-3 py-3 text-primary-light">Your Agent</span><ArrowRight className="h-4 w-4" /><span className="rounded-full border border-border px-3 py-2">END</span></div>
      </div>
    </div>
  )
}

function NetworkCanvas({ agents, selectedNode, onSelectNode, run, environment }: { agents: Agent[]; selectedNode: NodeId; onSelectNode: (id: NodeId) => void; run: Run; environment: Environment }) {
  const active = new Set(run.path)
  const technicalFailed = run.status === 'error' && run.path.includes('technical')
  return (
    <div className="relative min-h-0 flex-1 overflow-auto bg-background scrollbar-thin">
      <div className="relative mx-auto h-[640px] w-[1000px]" style={{ backgroundImage: 'radial-gradient(circle, rgba(100,116,139,0.16) 1px, transparent 1px)', backgroundSize: '22px 22px' }}>
        <div className="absolute left-4 top-4 z-30 flex items-center gap-2 rounded-xl border border-border/80 bg-surface/85 px-3 py-2 shadow-lg backdrop-blur"><Workflow className="h-3.5 w-3.5 text-primary-light" /><span className="text-[11px] font-medium text-white">Network canvas</span><span className="h-3 w-px bg-border" /><span className="text-[10px] text-muted">3 Agents · 5 connections</span></div>
        <div className="absolute right-4 top-4 z-30 flex items-center gap-1 rounded-xl border border-border/80 bg-surface/85 p-1.5 shadow-lg backdrop-blur">{[ZoomOut, ZoomIn, Maximize2].map((Icon, index) => <button key={index} type="button" className="rounded-lg p-1.5 text-muted hover:bg-background/60 hover:text-white"><Icon className="h-3.5 w-3.5" /></button>)}</div>
        {environment !== 'draft' && <div className="absolute left-1/2 top-5 z-30 -translate-x-1/2 rounded-lg border border-border/80 bg-surface/90 px-3 py-1.5 text-[10px] text-muted">Read-only {environment} snapshot</div>}
        <svg className="absolute inset-0 z-10" width="1000" height="640" viewBox="0 0 1000 640"><Connection d="M188 306 C220 306 225 306 254 306" active={active.has('entry') && active.has('coordinator')} /><Connection d="M462 286 C500 286 480 192 520 192" active={active.has('billing')} /><Connection d="M462 328 C500 328 480 432 520 432" active={active.has('technical')} error={technicalFailed} /><Connection d="M728 192 C790 192 760 306 822 306" active={active.has('billing') && active.has('end')} /><Connection d="M728 432 C790 432 760 306 822 306" active={active.has('technical') && active.has('end')} error={technicalFailed} /></svg>
        <CanvasNode id="entry" label="ENTRY" subtitle="Runtime input" selected={selectedNode === 'entry'} active={active.has('entry')} className="left-[60px] top-[278px]" onSelect={onSelectNode} />
        <CanvasNode id="coordinator" label={agents[0].name} subtitle={`${agents[0].provider}/${agents[0].model}`} selected={selectedNode === 'coordinator'} active={active.has('coordinator')} className="left-[254px] top-[250px]" onSelect={onSelectNode} />
        <CanvasNode id="billing" label={agents[1].name} subtitle={`${agents[1].provider}/${agents[1].model}`} selected={selectedNode === 'billing'} active={active.has('billing')} className="left-[520px] top-[136px]" onSelect={onSelectNode} />
        <CanvasNode id="technical" label={agents[2].name} subtitle={`${agents[2].provider}/${agents[2].model}`} selected={selectedNode === 'technical'} active={active.has('technical')} error={technicalFailed} className="left-[520px] top-[376px]" onSelect={onSelectNode} />
        <CanvasNode id="end" label="END" subtitle="Runtime output" selected={selectedNode === 'end'} active={active.has('end')} className="left-[822px] top-[278px]" onSelect={onSelectNode} />
        <div className="absolute bottom-4 left-4 z-30 w-72 rounded-2xl border border-primary/20 bg-surface/90 p-4 shadow-2xl backdrop-blur"><div className="flex items-center justify-between"><div><p className="text-[9px] font-semibold uppercase tracking-[0.18em] text-primary-light">Network setup</p><p className="mt-1 text-xs font-semibold text-white">3 of 4 steps complete</p></div><ShieldCheck className="h-4 w-4 text-primary-light" /></div><div className="mt-3 space-y-2 text-[10px]">{[['Add entry Agent', true], ['Connect specialist Agents', true], ['Validate Network', true], ['Run first Draft test', false]].map(([label, complete]) => <div key={String(label)} className="flex items-center gap-2 text-muted"><span className={cn('flex h-4 w-4 items-center justify-center rounded-full border', complete ? 'border-emerald-500/35 bg-emerald-500/10 text-emerald-400' : 'border-border')} >{complete && <Check className="h-2.5 w-2.5" />}</span><span>{String(label)}</span></div>)}</div></div>
      </div>
    </div>
  )
}

function DetailRow({ label, value }: { label: string; value: ReactNode }) {
  return <div className="flex items-start justify-between gap-4 border-b border-border/60 py-2.5 last:border-0"><span className="text-[10px] text-muted">{label}</span><span className="max-w-[190px] text-right text-[10px] font-medium text-slate-200">{value}</span></div>
}

function Inspector({ node, agents, organizationId, projectId }: { node: NodeId; agents: Agent[]; organizationId?: string; projectId: string }) {
  const navigate = useNavigate()
  const agent = node === 'coordinator' ? agents[0] : node === 'billing' ? agents[1] : node === 'technical' ? agents[2] : null
  if (!agent) return <div className="space-y-4 p-4"><div className="rounded-xl border border-border/75 bg-background/35 p-3.5"><div className="flex items-center gap-3"><div className="flex h-9 w-9 items-center justify-center rounded-xl border border-primary/25 bg-primary/10 text-primary-light"><CircleDot className="h-4 w-4" /></div><div><p className="text-xs font-semibold text-white">{node === 'entry' ? 'Network entry' : 'Network output'}</p><p className="mt-0.5 text-[10px] text-muted">{node === 'entry' ? 'Receives every runtime request.' : 'Returns the final response.'}</p></div></div></div><div className="rounded-xl border border-border/70 bg-background/25 px-3"><DetailRow label="Schema" value={node === 'entry' ? 'NetworkInput v1' : 'NetworkOutput v1'} /><DetailRow label="Validation" value="Strict" /><DetailRow label="Streaming" value="Enabled" /></div></div>
  const version = node === 'coordinator' ? 'v0.4.20260713.00' : node === 'billing' ? 'v0.3.20260713.01' : 'v0.1.20260712.00'
  return <div className="space-y-4 p-4"><div className="rounded-xl border border-primary/20 bg-primary/[0.05] p-3.5"><div className="flex items-start gap-3"><div className="flex h-10 w-10 items-center justify-center rounded-xl border border-primary/25 bg-primary/10 text-primary-light"><Bot className="h-4 w-4" /></div><div className="min-w-0 flex-1"><p className="truncate text-xs font-semibold text-white">{agent.name}</p><p className="mt-1 text-[10px] leading-4 text-muted">{agent.description}</p></div><span className="mt-1 h-2 w-2 rounded-full bg-emerald-400" /></div></div><section><p className="mb-2 text-[9px] font-semibold uppercase tracking-[0.18em] text-muted/80">Network binding</p><div className="rounded-xl border border-border/70 bg-background/25 px-3"><DetailRow label="Draft policy" value="Use current Staging" /><DetailRow label="Pinned release" value={<span className="font-mono">{version}</span>} /><DetailRow label="Model" value={`${agent.provider}/${agent.model}`} /></div></section><section><p className="mb-2 text-[9px] font-semibold uppercase tracking-[0.18em] text-muted/80">Runtime</p><div className="rounded-xl border border-border/70 bg-background/25 px-3"><DetailRow label="Timeout" value="30 seconds" /><DetailRow label="On failure" value="Stop execution" /><DetailRow label="Handoffs" value={node === 'coordinator' ? '2 destinations' : 'END'} /></div></section><button type="button" onClick={() => { if (!organizationId || agent.id.startsWith('mock-')) return toast.info('Preview Agent is not persisted yet'); navigate(`/organizations/${organizationId}/projects/${projectId}/agents/${agent.id}/playground`) }} className="flex w-full items-center justify-center gap-2 rounded-xl border border-border bg-background/45 px-3 py-2.5 text-[11px] font-medium text-slate-200 hover:border-primary/30 hover:text-white">Open Agent Playground<ArrowRight className="h-3.5 w-3.5" /></button></div>
}

function Versions({ onAction }: { onAction: (action: Exclude<ReleaseAction, null>) => void }) {
  return <div className="space-y-4 p-4"><div><p className="text-sm font-semibold text-white">Network versions</p><p className="mt-1 text-[10px] leading-4 text-muted">Draft is editable. Staging and Production are immutable.</p></div><div className="space-y-2.5">{[
    { title: 'Current Draft', version: 'Revision 18', tone: 'default' as const, description: 'Autosaved 14s ago · 3 Agents · 5 connections', action: <button type="button" onClick={() => onAction('stage')} className="rounded-lg bg-primary px-2.5 py-1.5 text-[10px] font-semibold text-white">Stage</button> },
    { title: 'Staging', version: 'v0.3.20260713.00', tone: 'staging' as const, description: 'Validated snapshot with exact Agent bindings.', action: <button type="button" onClick={() => onAction('publish')} className="rounded-lg border border-indigo-500/35 bg-indigo-500/10 px-2.5 py-1.5 text-[10px] font-semibold text-indigo-200">Publish</button> },
    { title: 'Production', version: 'v0.2.20260710.00', tone: 'production' as const, description: 'Active runtime release · deployed 3 days ago.', action: <Eye className="h-3.5 w-3.5 text-muted" /> },
  ].map((item) => <div key={item.title} className={cn('rounded-xl border p-3.5', item.tone === 'staging' ? 'border-indigo-500/30 bg-indigo-500/[0.045]' : item.tone === 'production' ? 'border-emerald-500/30 bg-emerald-500/[0.04]' : 'border-border/80 bg-background/30')}><div className="flex items-start justify-between gap-3"><div className="min-w-0"><p className="text-[9px] font-semibold uppercase tracking-[0.16em] text-muted/80">{item.title}</p><p className="mt-1.5 truncate font-mono text-[11px] font-medium text-white">{item.version}</p><p className="mt-1.5 text-[10px] leading-4 text-muted">{item.description}</p></div>{item.action}</div></div>)}</div><section><div className="mb-2 flex items-center justify-between"><p className="text-[9px] font-semibold uppercase tracking-[0.18em] text-muted/80">History</p><History className="h-3.5 w-3.5 text-muted" /></div><div className="rounded-lg border border-border/70 bg-background/25 p-3"><div className="flex items-start justify-between"><div><p className="font-mono text-[10px] font-medium text-white">v0.1.20260708.01</p><p className="mt-1 text-[9px] text-muted">08 Jul, 18:13 · 2 Agents</p></div><Badge>Archived</Badge></div><button type="button" onClick={() => onAction('rollback')} className="mt-2.5 inline-flex items-center gap-1.5 text-[9px] font-medium text-emerald-400"><RotateCcw className="h-3 w-3" />Rollback Production</button></div></section></div>
}

function RightPanel({ tab, onTab, node, agents, organizationId, projectId, onAction }: { tab: InspectorTab; onTab: (tab: InspectorTab) => void; node: NodeId; agents: Agent[]; organizationId?: string; projectId: string; onAction: (action: Exclude<ReleaseAction, null>) => void }) {
  return <aside className="hidden w-[380px] shrink-0 flex-col border-l border-border/90 bg-surface/75 2xl:flex"><div className="grid grid-cols-2 gap-1 border-b border-border/80 bg-background/20 p-1.5">{([['inspector', 'Inspector', Settings2], ['versions', 'Versions', Rocket]] as const).map(([id, label, Icon]) => <button key={id} type="button" onClick={() => onTab(id)} className={cn('flex items-center justify-center gap-2 rounded-lg border px-3 py-2 text-[11px] font-medium', tab === id ? 'border-primary/30 bg-primary/10 text-primary-light' : 'border-transparent text-muted hover:border-border/70 hover:text-white')}><Icon className="h-3.5 w-3.5" />{label}</button>)}</div><div className="min-h-0 flex-1 overflow-y-auto scrollbar-thin">{tab === 'inspector' ? <Inspector node={node} agents={agents} organizationId={organizationId} projectId={projectId} /> : <Versions onAction={onAction} />}</div></aside>
}

function ReleaseModal({ action, agents, onClose, onConfirm }: { action: Exclude<ReleaseAction, null>; agents: Agent[]; onClose: () => void; onConfirm: () => void }) {
  const content = action === 'stage' ? { eyebrow: 'Draft → Staging', title: 'Stage Network Draft?', description: 'Create an immutable snapshot and resolve every Agent binding.', confirm: 'Stage snapshot', icon: ShieldCheck } : action === 'publish' ? { eyebrow: 'Staging → Production', title: 'Publish Network Release?', description: 'The exact Staging snapshot becomes active in Production.', confirm: 'Publish to Production', icon: Rocket } : { eyebrow: 'Production rollback', title: 'Rollback Production?', description: 'Replace Production with the selected historical snapshot.', confirm: 'Rollback Production', icon: RotateCcw }
  const Icon = content.icon
  return <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 p-4 backdrop-blur-md"><div className="w-full max-w-2xl overflow-hidden rounded-2xl border border-border/90 bg-surface shadow-2xl"><div className="flex items-start gap-4 border-b border-border/80 bg-background/20 p-5"><div className="flex h-10 w-10 items-center justify-center rounded-xl border border-primary/25 bg-primary/10 text-primary-light"><Icon className="h-5 w-5" /></div><div className="min-w-0 flex-1"><p className="text-[9px] font-semibold uppercase tracking-[0.18em] text-primary-light">{content.eyebrow}</p><h2 className="mt-1.5 text-lg font-semibold text-white">{content.title}</h2><p className="mt-1.5 text-xs leading-5 text-muted">{content.description}</p></div><button type="button" onClick={onClose} className="rounded-lg p-1.5 text-muted hover:text-white"><X className="h-4 w-4" /></button></div><div className="space-y-4 p-5">{action === 'stage' && <div className="rounded-xl border border-border/75 bg-background/30 p-3.5"><p className="text-[10px] font-semibold text-white">Resolved Agent Releases</p><div className="mt-3 space-y-2">{agents.map((agent, index) => <div key={agent.id} className="flex justify-between gap-3 text-[10px]"><span className="truncate text-muted">{agent.name}</span><span className="font-mono text-slate-200">v0.{index + 1}.20260713.00</span></div>)}</div></div>}{action === 'publish' && <><div className="rounded-xl border border-indigo-500/25 bg-indigo-500/[0.05] p-4"><p className="text-[9px] uppercase tracking-[0.16em] text-indigo-300">Staging snapshot</p><p className="mt-1.5 font-mono text-sm text-white">v0.3.20260713.00</p><p className="mt-2 text-[10px] text-muted">3 Agents · 5 connections · 0 blockers</p></div><textarea className="min-h-24 w-full resize-none rounded-xl border border-border bg-background/45 px-3 py-2.5 text-xs text-white outline-none focus:border-primary/45" defaultValue="Add Technical Support routing and pin latest specialist releases." /></>}{action === 'rollback' && <div className="rounded-xl border border-amber-500/25 bg-amber-500/[0.055] p-4"><div className="flex gap-3"><AlertTriangle className="h-4 w-4 shrink-0 text-amber-400" /><p className="text-[10px] leading-4 text-amber-100/80">Current Production v0.3 will be replaced by v0.2. Historical snapshots remain immutable.</p></div></div>}<p className="rounded-lg border border-border/65 bg-background/20 px-3 py-2 text-[9px] text-muted">Prototype only. No Network release is persisted yet.</p></div><div className="flex justify-end gap-2 border-t border-border/80 bg-background/20 p-4"><button type="button" onClick={onClose} className="rounded-xl border border-border px-3.5 py-2 text-[11px] text-muted">Cancel</button><button type="button" onClick={onConfirm} className={cn('rounded-xl px-3.5 py-2 text-[11px] font-semibold text-white', action === 'rollback' ? 'bg-red-600' : 'bg-primary')}>{content.confirm}</button></div></div></div>
}

export default function NetworkPage() {
  const { organizationId, projectId } = useParams<{ organizationId: string; projectId: string }>()
  const navigate = useNavigate()
  const { currentProject } = useWorkspace()
  const agentsQuery = useAgents(projectId)
  const [environment, setEnvironment] = useState<Environment>('draft')
  const [panelTab, setPanelTab] = useState<PanelTab>('runs')
  const [selectedRunId, setSelectedRunId] = useState('run-1')
  const [selectedNode, setSelectedNode] = useState<NodeId>('coordinator')
  const [inspectorTab, setInspectorTab] = useState<InspectorTab>('inspector')
  const [releaseAction, setReleaseAction] = useState<ReleaseAction>(null)
  const hasAgents = Boolean(agentsQuery.data?.length)
  const agents = useMemo(() => { const source = agentsQuery.data?.length ? agentsQuery.data : fallbackAgents; return [source[0] ?? fallbackAgents[0], source[1] ?? fallbackAgents[1], source[2] ?? fallbackAgents[2]] }, [agentsQuery.data])
  const run = runs.find((item) => item.id === selectedRunId) ?? runs[0]
  const headerAction = environment === 'draft' ? ['Stage draft', ShieldCheck, 'stage'] as const : environment === 'staging' ? ['Publish release', Rocket, 'publish'] as const : ['Rollback', RotateCcw, 'rollback'] as const
  const HeaderActionIcon = headerAction[1]

  const confirmAction = () => {
    if (releaseAction === 'stage') { setEnvironment('staging'); toast.success('Draft snapshot staged in the prototype') }
    if (releaseAction === 'publish') { setEnvironment('production'); toast.success('Staging release published in the prototype') }
    if (releaseAction === 'rollback') toast.success('Production rollback simulated')
    setReleaseAction(null)
  }

  return <div className="flex h-screen min-w-[1100px] flex-col overflow-hidden bg-background"><header className="flex h-14 shrink-0 items-center gap-3 border-b border-border/90 bg-surface/80 px-3"><button type="button" onClick={() => navigate(`/organizations/${organizationId}/projects/${projectId}`)} className="flex h-8 w-8 items-center justify-center rounded-lg border border-border/80 bg-background/35 text-muted hover:text-white"><ChevronLeft className="h-4 w-4" /></button><div className="h-6 w-px bg-border" /><div className="min-w-0"><div className="flex items-center gap-2"><h1 className="truncate text-sm font-semibold text-white">{currentProject?.name || 'Project'} Network</h1><Badge>Prototype</Badge></div><p className="mt-0.5 text-[9px] text-muted">One operational Agent Network for this Project</p></div><div className="ml-auto flex items-center gap-2"><div className="hidden items-center gap-1.5 rounded-lg border border-border/75 bg-background/30 px-2.5 py-1.5 text-[9px] text-muted xl:flex"><span className="h-1.5 w-1.5 rounded-full bg-emerald-400" />Draft saved 14s ago</div><div className="flex rounded-xl border border-border/80 bg-background/35 p-1">{(['draft', 'staging', 'production'] as Environment[]).map((item) => <button key={item} type="button" onClick={() => setEnvironment(item)} className={cn('rounded-lg px-3 py-1.5 text-[10px] font-medium capitalize', environment === item ? item === 'production' ? 'bg-emerald-500/12 text-emerald-300' : item === 'staging' ? 'bg-indigo-500/12 text-indigo-300' : 'bg-primary/12 text-primary-light' : 'text-muted hover:text-white')}>{item}</button>)}</div><button type="button" onClick={() => setPanelTab('validation')} className="hidden items-center gap-2 rounded-xl border border-border/80 bg-background/35 px-3 py-2 text-[10px] text-slate-200 xl:flex"><ListChecks className="h-3.5 w-3.5" />Validate</button><button type="button" onClick={() => { setEnvironment('draft'); setPanelTab('runs'); setSelectedRunId('run-4'); toast.success('Draft test started in the prototype') }} className="flex items-center gap-2 rounded-xl border border-primary/30 bg-primary/10 px-3 py-2 text-[10px] font-semibold text-primary-light"><Play className="h-3.5 w-3.5 fill-current" />Run test</button><button type="button" onClick={() => setReleaseAction(headerAction[2])} className="flex items-center gap-2 rounded-xl bg-primary px-3 py-2 text-[10px] font-semibold text-white"><HeaderActionIcon className="h-3.5 w-3.5" />{headerAction[0]}</button></div></header><div className="flex h-7 shrink-0 items-center border-b border-border/80 bg-surface/35 px-3 text-[9px] text-muted"><span className="font-medium text-slate-300">Using: {environment === 'draft' ? 'Current Draft · Revision 18' : environment === 'staging' ? 'v0.3.20260713.00' : 'v0.2.20260710.00'}</span><span className="mx-2 text-border">·</span><span>{environment === 'draft' ? 'Editable autosaved workspace' : 'Immutable release snapshot'}</span><span className="ml-auto">Max hops 8 · Timeout 90s · Sequential handoffs</span></div><div className="flex min-h-0 flex-1 overflow-hidden"><nav className="flex w-14 shrink-0 flex-col items-center gap-2 border-r border-border/90 bg-surface/75 p-2">{panelItems.map((item) => { const Icon = item.icon; return <button key={item.id} type="button" onClick={() => setPanelTab(item.id)} className={cn('relative flex h-10 w-10 items-center justify-center rounded-xl border', panelTab === item.id ? 'border-primary/35 bg-primary/10 text-primary-light' : 'border-transparent text-muted hover:border-border/80 hover:text-white')} title={item.label}><Icon className="h-4 w-4" />{item.count != null && <span className="absolute -right-1 -top-1 min-w-4 rounded-full border border-surface bg-primary px-1 text-[8px] leading-4 text-white">{item.count}</span>}</button> })}<div className="mt-auto flex flex-col gap-2"><button type="button" onClick={() => toast.info('Agent picker opened in the prototype')} className="flex h-10 w-10 items-center justify-center rounded-xl border border-border/80 bg-background/35 text-muted"><Plus className="h-4 w-4" /></button><button type="button" onClick={() => toast.info('Network settings opened in the prototype')} className="flex h-10 w-10 items-center justify-center rounded-xl text-muted"><Settings2 className="h-4 w-4" /></button></div></nav><aside className="hidden w-[330px] shrink-0 border-r border-border/90 bg-surface/65 xl:block"><OperationsPanel tab={panelTab} run={run} selectedRunId={selectedRunId} onSelectRun={setSelectedRunId} /></aside>{agentsQuery.isLoading ? <div className="flex flex-1 items-center justify-center text-xs text-muted">Loading Network inventory</div> : hasAgents ? <NetworkCanvas agents={agents} selectedNode={selectedNode} onSelectNode={(node) => { setSelectedNode(node); setInspectorTab('inspector') }} run={run} environment={environment} /> : <EmptyNetwork onCreateAgent={() => navigate(`/organizations/${organizationId}/projects/${projectId}/agents`)} />}<RightPanel tab={inspectorTab} onTab={setInspectorTab} node={selectedNode} agents={agents} organizationId={organizationId} projectId={projectId || ''} onAction={setReleaseAction} /></div>{releaseAction && <ReleaseModal action={releaseAction} agents={agents} onClose={() => setReleaseAction(null)} onConfirm={confirmAction} />}</div>
}
