import { useMemo, useState, type ReactNode } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { toast } from 'sonner'
import {
  Activity,
  AlertTriangle,
  ArrowRight,
  Bot,
  BookOpen,
  Bug,
  Check,
  CheckCircle2,
  ChevronLeft,
  CircleDot,
  Clock3,
  Code2,
  Coins,
  Copy,
  Cpu,
  Eye,
  FileJson,
  GitBranch,
  History,
  KeyRound,
  ListChecks,
  Maximize2,
  MessageSquare,
  Minimize2,
  Play,
  Plus,
  Rocket,
  RotateCcw,
  Save,
  Search,
  Send,
  Settings2,
  ShieldCheck,
  SlidersHorizontal,
  Workflow,
  Wrench,
  X,
  ZoomIn,
  ZoomOut,
  type LucideIcon,
} from 'lucide-react'

import { useAgents } from '@/features/agents/hooks'
import type { Agent } from '@/features/agents/types'
import { useWorkspace } from '@/features/workspace/WorkspaceProvider'
import { API_BASE_URL } from '@/lib/api/client'
import { cn } from '@/lib/utils'

type Environment = 'draft' | 'staging' | 'production'
type PanelTab = 'runs' | 'trace' | 'debug' | 'validation'
type NodeId = 'entry' | 'coordinator' | 'billing' | 'technical' | 'end'
type AgentNodeId = Exclude<NodeId, 'entry' | 'end'>
type ReleaseAction = 'stage' | 'publish' | 'rollback' | null
type RightPanelMode = 'agent' | 'network'
type AgentWorkspaceTab = 'configure' | 'test' | 'binding' | 'releases'
type ConfigureTab = 'agent' | 'output' | 'model' | 'knowledge' | 'tools'
type AgentSource = 'draft' | 'staging' | 'release'
type BindingMode = 'follow_draft' | 'follow_staging' | 'pin_release'
type ApiSection = 'http' | 'stream' | 'jobs' | 'openai'

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

type ResolvedAgentBinding = {
  nodeId: AgentNodeId
  agent: Agent
  source: AgentSource
  version: string
  binding: BindingMode
  editingVersion: string
  dirty?: boolean
  nextAction: string
}

type AgentEditorDraft = {
  name: string
  role: string
  prompt: string
  model: string
  temperature: string
  outputMode: 'text' | 'json'
  outputSchema: string
  knowledge: string
  tools: string[]
}

const fallbackAgents: [Agent, Agent, Agent] = [
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

const sourceStyles: Record<AgentSource, string> = {
  draft: 'border-blue-500/30 bg-blue-500/10 text-blue-300',
  staging: 'border-indigo-500/30 bg-indigo-500/10 text-indigo-300',
  release: 'border-emerald-500/30 bg-emerald-500/10 text-emerald-300',
}

function Badge({ children, tone = 'default' }: { children: ReactNode; tone?: 'default' | 'staging' | 'production' | 'warning' | 'danger' }) {
  const tones = {
    default: 'border-border/80 bg-background/45 text-muted',
    staging: 'border-indigo-500/30 bg-indigo-500/10 text-indigo-300',
    production: 'border-emerald-500/30 bg-emerald-500/10 text-emerald-300',
    warning: 'border-amber-500/30 bg-amber-500/10 text-amber-300',
    danger: 'border-red-500/30 bg-red-500/10 text-red-300',
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
      <PanelHeader eyebrow="Network operations" title="Executions" description="Inspect path, cost and exact releases used by each run." />
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
                <p className="mt-1 text-[10px] text-muted">+{index * 420}ms · exact Agent Release recorded</p>
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
    ['network.started', `environment=${run.environment} network_release=v0.4.20260713.00`],
    ['node.entered', 'node=coordinator agent_release=v0.5.20260713.00'],
    ['handoff.selected', run.path.includes('billing') ? 'key=billing_support' : 'key=technical_support'],
    [run.status === 'error' ? 'node.failed' : 'network.completed', run.status === 'error' ? 'timeout_after_ms=700' : 'status=success'],
  ]
  return (
    <div className="flex h-full min-h-0 flex-col">
      <PanelHeader eyebrow="Runtime detail" title="Debug events" description="Raw orchestration events with Network and Agent versions." />
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
    ['All Draft Agent bindings can be promoted to Staging', true],
    ['Technical Support has no fallback model', false],
    ['Latest Network Draft has no successful run', false],
  ] as const
  return (
    <div className="flex h-full min-h-0 flex-col">
      <PanelHeader eyebrow="Release readiness" title="Validation" description="Blocking rules and warnings before coordinated promotion." />
      <div className="grid grid-cols-2 gap-2 border-b border-border/70 p-3">
        <div className="rounded-lg border border-emerald-500/20 bg-emerald-500/[0.05] p-2.5"><p className="text-lg font-semibold text-emerald-300">0</p><p className="text-[10px] text-muted">Blockers</p></div>
        <div className="rounded-lg border border-amber-500/20 bg-amber-500/[0.05] p-2.5"><p className="text-lg font-semibold text-amber-300">2</p><p className="text-[10px] text-muted">Warnings</p></div>
      </div>
      <div className="min-h-0 flex-1 space-y-1.5 overflow-y-auto p-3 scrollbar-thin">
        {checks.map(([label, passed]) => <div key={label} className="flex gap-2 rounded-lg border border-border/65 bg-background/30 p-2.5">{passed ? <CheckCircle2 className="mt-0.5 h-3.5 w-3.5 shrink-0 text-emerald-400" /> : <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0 text-amber-400" />}<div><p className="text-[11px] font-medium text-white">{label}</p><p className="mt-0.5 text-[10px] leading-4 text-muted">{passed ? 'Ready for coordinated snapshot resolution.' : 'Review before Production.'}</p></div></div>)}
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

function resolvedBindings(agents: [Agent, Agent, Agent], environment: Environment): Record<AgentNodeId, ResolvedAgentBinding> {
  const draft: Record<AgentNodeId, ResolvedAgentBinding> = {
    coordinator: { nodeId: 'coordinator', agent: agents[0], source: 'draft', version: 'Revision 14', binding: 'follow_draft', editingVersion: 'Revision 14', dirty: true, nextAction: 'Create Agent Staging' },
    billing: { nodeId: 'billing', agent: agents[1], source: 'staging', version: 'v0.3.20260713.01', binding: 'follow_staging', editingVersion: 'Revision 9', nextAction: 'Reuse Agent Staging' },
    technical: { nodeId: 'technical', agent: agents[2], source: 'release', version: 'v0.1.20260712.00', binding: 'pin_release', editingVersion: 'Revision 7', nextAction: 'Reuse immutable Agent Release' },
  }
  if (environment === 'draft') return draft
  if (environment === 'staging') {
    return {
      coordinator: { ...draft.coordinator, source: 'staging', version: 'v0.4.20260713.02', binding: 'follow_staging', dirty: false, nextAction: 'Create Agent Release on publish' },
      billing: { ...draft.billing, nextAction: 'Create Agent Release on publish' },
      technical: draft.technical,
    }
  }
  return {
    coordinator: { ...draft.coordinator, source: 'release', version: 'v0.5.20260713.00', binding: 'pin_release', dirty: false, nextAction: 'Pinned in Network Release' },
    billing: { ...draft.billing, source: 'release', version: 'v0.4.20260713.00', binding: 'pin_release', nextAction: 'Pinned in Network Release' },
    technical: draft.technical,
  }
}

function CanvasNode({ id, label, subtitle, selected, active, error, className, binding, onSelect }: { id: NodeId; label: string; subtitle: string; selected: boolean; active: boolean; error?: boolean; className: string; binding?: ResolvedAgentBinding; onSelect: (id: NodeId) => void }) {
  const terminal = id === 'entry' || id === 'end'
  return (
    <button type="button" onClick={() => onSelect(id)} className={cn('absolute z-20 border bg-surface/95 text-left transition', terminal ? 'flex h-14 w-28 items-center justify-center rounded-full' : 'w-56 rounded-2xl p-3.5', selected ? 'border-primary/70 shadow-[0_0_0_3px_rgba(59,130,246,0.12),0_18px_35px_rgba(0,0,0,0.24)]' : active ? error ? 'border-red-500/55 shadow-xl shadow-red-950/10' : 'border-emerald-500/45 shadow-xl shadow-black/15' : 'border-border/90 opacity-80 shadow-xl shadow-black/10 hover:opacity-100', className)}>
      {terminal ? (
        <div className="flex items-center gap-2"><CircleDot className={cn('h-4 w-4', id === 'entry' ? 'text-primary-light' : 'text-emerald-400')} /><span className="text-[11px] font-semibold uppercase tracking-[0.16em] text-white">{label}</span></div>
      ) : binding ? (
        <>
          <div className="flex items-start gap-3">
            <div className={cn('flex h-9 w-9 shrink-0 items-center justify-center rounded-xl border', error ? 'border-red-500/30 bg-red-500/10 text-red-300' : 'border-primary/25 bg-primary/10 text-primary-light')}><Bot className="h-4 w-4" /></div>
            <div className="min-w-0 flex-1">
              <div className="flex items-start justify-between gap-2"><p className="truncate text-xs font-semibold text-white">{label}</p><span className={cn('mt-0.5 h-2 w-2 rounded-full', error ? 'bg-red-400' : binding.dirty ? 'bg-amber-400' : 'bg-emerald-400')} /></div>
              <p className="mt-1 truncate text-[10px] text-muted">{subtitle}</p>
            </div>
          </div>
          <div className="mt-3 flex items-center justify-between border-t border-border/70 pt-2.5">
            <span className={cn('rounded-md border px-1.5 py-0.5 text-[8px] font-semibold uppercase tracking-wide', sourceStyles[binding.source])}>{binding.source}</span>
            <span className="font-mono text-[9px] text-slate-300">{binding.version}</span>
          </div>
          <p className="mt-2 truncate text-[9px] text-muted">{binding.binding === 'follow_draft' ? 'Binding: Follow Draft' : binding.binding === 'follow_staging' ? 'Binding: Follow Staging' : 'Binding: Pinned Release'}</p>
        </>
      ) : null}
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

function NetworkCanvas({ agents, bindings, selectedNode, onSelectNode, run, environment }: { agents: [Agent, Agent, Agent]; bindings: Record<AgentNodeId, ResolvedAgentBinding>; selectedNode: NodeId; onSelectNode: (id: NodeId) => void; run: Run; environment: Environment }) {
  const active = new Set(run.path)
  const technicalFailed = run.status === 'error' && run.path.includes('technical')
  const sourceCounts = Object.values(bindings).reduce<Record<AgentSource, number>>((acc, binding) => ({ ...acc, [binding.source]: acc[binding.source] + 1 }), { draft: 0, staging: 0, release: 0 })
  return (
    <div className="relative min-h-0 flex-1 overflow-auto bg-background scrollbar-thin">
      <div className="relative mx-auto h-[660px] w-[1040px]" style={{ backgroundImage: 'radial-gradient(circle, rgba(100,116,139,0.16) 1px, transparent 1px)', backgroundSize: '22px 22px' }}>
        <div className="absolute left-4 top-4 z-30 flex items-center gap-2 rounded-xl border border-border/80 bg-surface/85 px-3 py-2 shadow-lg backdrop-blur"><Workflow className="h-3.5 w-3.5 text-primary-light" /><span className="text-[11px] font-medium text-white">Network canvas</span><span className="h-3 w-px bg-border" /><span className="text-[10px] text-muted">3 Agents · {sourceCounts.draft} Draft · {sourceCounts.staging} Staging · {sourceCounts.release} Release</span></div>
        <div className="absolute right-4 top-4 z-30 flex items-center gap-1 rounded-xl border border-border/80 bg-surface/85 p-1.5 shadow-lg backdrop-blur">{[ZoomOut, ZoomIn, Maximize2].map((Icon, index) => <button key={index} type="button" className="rounded-lg p-1.5 text-muted hover:bg-background/60 hover:text-white"><Icon className="h-3.5 w-3.5" /></button>)}</div>
        {environment !== 'draft' && <div className="absolute left-1/2 top-5 z-30 -translate-x-1/2 rounded-lg border border-border/80 bg-surface/90 px-3 py-1.5 text-[10px] text-muted">Read-only {environment} snapshot with exact Agent versions</div>}
        <svg className="absolute inset-0 z-10" width="1040" height="660" viewBox="0 0 1040 660"><Connection d="M188 326 C220 326 225 326 254 326" active={active.has('entry') && active.has('coordinator')} /><Connection d="M478 306 C515 306 500 202 540 202" active={active.has('billing')} /><Connection d="M478 348 C515 348 500 452 540 452" active={active.has('technical')} error={technicalFailed} /><Connection d="M764 202 C820 202 790 326 852 326" active={active.has('billing') && active.has('end')} /><Connection d="M764 452 C820 452 790 326 852 326" active={active.has('technical') && active.has('end')} error={technicalFailed} /></svg>
        <CanvasNode id="entry" label="ENTRY" subtitle="Runtime input" selected={selectedNode === 'entry'} active={active.has('entry')} className="left-[60px] top-[298px]" onSelect={onSelectNode} />
        <CanvasNode id="coordinator" label={agents[0].name} subtitle={`${agents[0].provider}/${agents[0].model}`} selected={selectedNode === 'coordinator'} active={active.has('coordinator')} binding={bindings.coordinator} className="left-[254px] top-[268px]" onSelect={onSelectNode} />
        <CanvasNode id="billing" label={agents[1].name} subtitle={`${agents[1].provider}/${agents[1].model}`} selected={selectedNode === 'billing'} active={active.has('billing')} binding={bindings.billing} className="left-[540px] top-[142px]" onSelect={onSelectNode} />
        <CanvasNode id="technical" label={agents[2].name} subtitle={`${agents[2].provider}/${agents[2].model}`} selected={selectedNode === 'technical'} active={active.has('technical')} error={technicalFailed} binding={bindings.technical} className="left-[540px] top-[392px]" onSelect={onSelectNode} />
        <CanvasNode id="end" label="END" subtitle="Runtime output" selected={selectedNode === 'end'} active={active.has('end')} className="left-[852px] top-[298px]" onSelect={onSelectNode} />
        <div className="absolute bottom-4 left-4 z-30 w-72 rounded-2xl border border-primary/20 bg-surface/90 p-4 shadow-2xl backdrop-blur"><div className="flex items-center justify-between"><div><p className="text-[9px] font-semibold uppercase tracking-[0.18em] text-primary-light">Network setup</p><p className="mt-1 text-xs font-semibold text-white">3 of 4 steps complete</p></div><ShieldCheck className="h-4 w-4 text-primary-light" /></div><div className="mt-3 space-y-2 text-[10px]">{[['Add entry Agent', true], ['Connect specialist Agents', true], ['Validate Network', true], ['Run first Draft test', false]].map(([label, complete]) => <div key={String(label)} className="flex items-center gap-2 text-muted"><span className={cn('flex h-4 w-4 items-center justify-center rounded-full border', complete ? 'border-emerald-500/35 bg-emerald-500/10 text-emerald-400' : 'border-border')}>{complete && <Check className="h-2.5 w-2.5" />}</span><span>{String(label)}</span></div>)}</div></div>
      </div>
    </div>
  )
}

function DetailRow({ label, value }: { label: string; value: ReactNode }) {
  return <div className="flex items-start justify-between gap-4 border-b border-border/60 py-2.5 last:border-0"><span className="text-[10px] text-muted">{label}</span><span className="max-w-[240px] text-right text-[10px] font-medium text-slate-200">{value}</span></div>
}

function WorkspaceTabs({ active, onChange }: { active: AgentWorkspaceTab; onChange: (tab: AgentWorkspaceTab) => void }) {
  const tabs: Array<[AgentWorkspaceTab, string, LucideIcon]> = [
    ['configure', 'Configure', SlidersHorizontal],
    ['test', 'Test', MessageSquare],
    ['binding', 'Binding', GitBranch],
    ['releases', 'Releases', Rocket],
  ]
  return <div className="grid grid-cols-4 gap-1 border-b border-border/80 bg-background/20 p-1.5">{tabs.map(([id, label, Icon]) => <button key={id} type="button" onClick={() => onChange(id)} className={cn('flex items-center justify-center gap-1.5 rounded-lg border px-2 py-2 text-[10px] font-medium', active === id ? 'border-primary/30 bg-primary/10 text-primary-light' : 'border-transparent text-muted hover:border-border/70 hover:text-white')}><Icon className="h-3.5 w-3.5" />{label}</button>)}</div>
}

function ConfigureWorkspace({ draft, onChange, onSave, activeTab, onTabChange }: { draft: AgentEditorDraft; onChange: (patch: Partial<AgentEditorDraft>) => void; onSave: () => void; activeTab: ConfigureTab; onTabChange: (tab: ConfigureTab) => void }) {
  const tabs: Array<[ConfigureTab, string, LucideIcon]> = [
    ['agent', 'Agent', Bot],
    ['output', 'Output', FileJson],
    ['model', 'Model', Cpu],
    ['knowledge', 'Knowledge', BookOpen],
    ['tools', 'Tools', Wrench],
  ]
  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="flex gap-1 overflow-x-auto border-b border-border/80 p-1.5 scrollbar-thin">{tabs.map(([id, label, Icon]) => <button key={id} type="button" onClick={() => onTabChange(id)} className={cn('flex shrink-0 items-center gap-1.5 rounded-lg border px-2.5 py-2 text-[10px] font-medium', activeTab === id ? 'border-primary/30 bg-primary/10 text-primary-light' : 'border-transparent text-muted hover:border-border/70 hover:text-white')}><Icon className="h-3.5 w-3.5" />{label}</button>)}</div>
      <div className="min-h-0 flex-1 overflow-y-auto p-4 scrollbar-thin">
        {activeTab === 'agent' && <div className="space-y-4"><label className="block"><span className="text-[10px] font-medium text-muted">Name</span><input value={draft.name} onChange={(event) => onChange({ name: event.target.value })} className="mt-1.5 w-full rounded-xl border border-border bg-background/45 px-3 py-2.5 text-xs text-white outline-none focus:border-primary/45" /></label><label className="block"><span className="text-[10px] font-medium text-muted">Role in Network</span><input value={draft.role} onChange={(event) => onChange({ role: event.target.value })} className="mt-1.5 w-full rounded-xl border border-border bg-background/45 px-3 py-2.5 text-xs text-white outline-none focus:border-primary/45" /></label><label className="block"><span className="text-[10px] font-medium text-muted">System prompt</span><textarea value={draft.prompt} onChange={(event) => onChange({ prompt: event.target.value })} className="mt-1.5 min-h-56 w-full resize-none rounded-xl border border-border bg-background/45 px-3 py-2.5 text-xs leading-5 text-white outline-none focus:border-primary/45" /></label></div>}
        {activeTab === 'output' && <div className="space-y-4"><div className="grid grid-cols-2 gap-2">{(['text', 'json'] as const).map((mode) => <button key={mode} type="button" onClick={() => onChange({ outputMode: mode })} className={cn('rounded-xl border p-3 text-left', draft.outputMode === mode ? 'border-primary/35 bg-primary/10' : 'border-border bg-background/35')}><p className="text-xs font-medium capitalize text-white">{mode}</p><p className="mt-1 text-[10px] text-muted">{mode === 'json' ? 'Strict structured output' : 'Natural language response'}</p></button>)}</div><label className="block"><span className="text-[10px] font-medium text-muted">Output schema</span><textarea value={draft.outputSchema} onChange={(event) => onChange({ outputSchema: event.target.value })} disabled={draft.outputMode !== 'json'} className="mt-1.5 min-h-64 w-full resize-none rounded-xl border border-border bg-background/45 px-3 py-2.5 font-mono text-[11px] leading-5 text-white outline-none disabled:opacity-45" /></label></div>}
        {activeTab === 'model' && <div className="space-y-4"><label className="block"><span className="text-[10px] font-medium text-muted">Provider / model</span><input value={draft.model} onChange={(event) => onChange({ model: event.target.value })} className="mt-1.5 w-full rounded-xl border border-border bg-background/45 px-3 py-2.5 text-xs text-white outline-none focus:border-primary/45" /></label><label className="block"><span className="text-[10px] font-medium text-muted">Temperature</span><input value={draft.temperature} onChange={(event) => onChange({ temperature: event.target.value })} className="mt-1.5 w-full rounded-xl border border-border bg-background/45 px-3 py-2.5 text-xs text-white outline-none focus:border-primary/45" /></label><div className="rounded-xl border border-border/70 bg-background/30 p-3"><p className="text-[10px] font-medium text-white">Fallback model</p><p className="mt-1 text-[10px] text-muted">Not configured for this mockup.</p></div></div>}
        {activeTab === 'knowledge' && <div className="space-y-3"><p className="text-xs font-medium text-white">Attached Knowledge</p><div className="rounded-xl border border-primary/20 bg-primary/[0.05] p-3"><p className="text-[11px] font-medium text-white">{draft.knowledge}</p><p className="mt-1 text-[10px] text-muted">Vector snapshot resolved at Agent release time.</p></div><button type="button" onClick={() => toast.info('Knowledge picker opened in the mockup')} className="w-full rounded-xl border border-dashed border-border px-3 py-3 text-[11px] text-muted hover:border-primary/30 hover:text-white">Change Collection binding</button></div>}
        {activeTab === 'tools' && <div className="space-y-3"><p className="text-xs font-medium text-white">Allowed Tools</p>{draft.tools.map((tool) => <div key={tool} className="flex items-center justify-between rounded-xl border border-border/70 bg-background/30 p-3"><div className="flex items-center gap-2"><Wrench className="h-3.5 w-3.5 text-primary-light" /><span className="text-[11px] text-white">{tool}</span></div><Badge>Allowed</Badge></div>)}<button type="button" onClick={() => toast.info('Tool picker opened in the mockup')} className="w-full rounded-xl border border-dashed border-border px-3 py-3 text-[11px] text-muted hover:border-primary/30 hover:text-white">Add Tool</button></div>}
      </div>
      <div className="flex items-center gap-2 border-t border-border/80 bg-background/20 p-3"><button type="button" onClick={() => toast.info('Draft reset simulated')} className="rounded-xl border border-border px-3 py-2 text-[10px] text-muted"><RotateCcw className="h-3.5 w-3.5" /></button><button type="button" onClick={onSave} className="flex flex-1 items-center justify-center gap-2 rounded-xl bg-primary px-3 py-2 text-[10px] font-semibold text-white"><Save className="h-3.5 w-3.5" />Save Agent Draft</button></div>
    </div>
  )
}

function TestWorkspace({ binding }: { binding: ResolvedAgentBinding }) {
  const [message, setMessage] = useState('I need help with an invoice that was charged twice.')
  return <div className="flex min-h-0 flex-1 flex-col"><div className="border-b border-border/80 p-3"><div className="rounded-xl border border-primary/20 bg-primary/[0.05] p-3"><p className="text-[10px] font-medium text-white">Testing {binding.agent.name}</p><p className="mt-1 text-[10px] text-muted">Uses saved Agent Draft {binding.editingVersion}. Network bindings remain unchanged.</p></div></div><div className="min-h-0 flex-1 space-y-3 overflow-y-auto p-4 scrollbar-thin"><div className="ml-auto max-w-[85%] rounded-2xl rounded-br-md bg-primary px-3 py-2.5 text-[11px] leading-5 text-white">I need help with an invoice that was charged twice.</div><div className="max-w-[88%] rounded-2xl rounded-bl-md border border-border/70 bg-background/35 px-3 py-2.5 text-[11px] leading-5 text-slate-200">I can help investigate the duplicate charge. Please provide the invoice ID and the last four digits of the payment method.</div><div className="rounded-xl border border-border/70 bg-background/25 p-3"><p className="text-[9px] uppercase tracking-[0.16em] text-muted">Test metadata</p><div className="mt-2 grid grid-cols-2 gap-2 text-[10px] text-muted"><span>Agent Draft {binding.editingVersion}</span><span>842 ms</span><span>324 tokens</span><span>$0.004</span></div></div></div><div className="flex items-end gap-2 border-t border-border/80 p-3"><textarea value={message} onChange={(event) => setMessage(event.target.value)} className="min-h-20 flex-1 resize-none rounded-xl border border-border bg-background/45 px-3 py-2.5 text-xs text-white outline-none focus:border-primary/45" /><button type="button" onClick={() => toast.success('Agent test executed in the mockup')} className="flex h-10 w-10 items-center justify-center rounded-xl bg-primary text-white"><Send className="h-4 w-4" /></button></div></div>
}

function BindingWorkspace({ binding, onBindingChange }: { binding: ResolvedAgentBinding; onBindingChange: (mode: BindingMode) => void }) {
  const options: Array<{ id: BindingMode; title: string; description: string }> = [
    { id: 'follow_draft', title: 'Follow Agent Draft', description: 'Network Draft uses the latest saved Agent Draft. Must be promoted before Network Staging.' },
    { id: 'follow_staging', title: 'Follow Agent Staging', description: 'Network Draft follows Agent Staging. Network Staging pins the exact snapshot.' },
    { id: 'pin_release', title: 'Pin specific Release', description: 'All Network environments use one immutable Agent Release.' },
  ]
  return <div className="min-h-0 flex-1 overflow-y-auto p-4 scrollbar-thin"><div className="rounded-xl border border-border/75 bg-background/30 p-3.5"><p className="text-[9px] font-semibold uppercase tracking-[0.16em] text-muted">Editing</p><div className="mt-2 flex items-center justify-between"><span className="text-[11px] font-medium text-white">Agent Draft</span><span className="font-mono text-[10px] text-amber-300">{binding.editingVersion}{binding.dirty ? ' · Unsaved' : ''}</span></div></div><div className="mt-3 rounded-xl border border-primary/25 bg-primary/[0.05] p-3.5"><p className="text-[9px] font-semibold uppercase tracking-[0.16em] text-primary-light">Used by Network</p><div className="mt-2 flex items-center justify-between"><span className="text-[11px] font-medium capitalize text-white">Agent {binding.source}</span><span className="font-mono text-[10px] text-slate-200">{binding.version}</span></div></div>{binding.source !== 'draft' && <div className="mt-3 flex gap-2 rounded-xl border border-amber-500/25 bg-amber-500/[0.05] p-3"><AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-amber-400" /><p className="text-[10px] leading-4 text-amber-100/80">Your Agent Draft changes are not being used by this Network binding.</p></div>}<div className="mt-5"><p className="text-[9px] font-semibold uppercase tracking-[0.16em] text-muted">Binding source</p><div className="mt-2 space-y-2">{options.map((option) => <button key={option.id} type="button" onClick={() => onBindingChange(option.id)} className={cn('w-full rounded-xl border p-3 text-left', binding.binding === option.id ? 'border-primary/35 bg-primary/10' : 'border-border/75 bg-background/30 hover:border-primary/25')}><div className="flex items-center justify-between"><p className="text-[11px] font-medium text-white">{option.title}</p>{binding.binding === option.id && <CheckCircle2 className="h-4 w-4 text-primary-light" />}</div><p className="mt-1 text-[10px] leading-4 text-muted">{option.description}</p></button>)}</div></div><div className="mt-5 rounded-xl border border-border/70 bg-background/25 px-3"><DetailRow label="Current resolution" value={`${binding.source} · ${binding.version}`} /><DetailRow label="Network Staging" value={binding.source === 'draft' ? 'Create Agent Staging' : 'Pin exact snapshot'} /><DetailRow label="Network Production" value={binding.source === 'release' ? 'Reuse Agent Release' : 'Create or reuse Release'} /></div></div>
}

function AgentReleasesWorkspace({ binding }: { binding: ResolvedAgentBinding }) {
  const releases = [
    { label: 'Current Draft', value: binding.editingVersion, tone: 'default' as const },
    { label: 'Staging', value: binding.nodeId === 'technical' ? 'Not active' : binding.nodeId === 'coordinator' ? 'v0.4.20260713.02' : 'v0.3.20260713.01', tone: 'staging' as const },
    { label: 'Latest Release', value: binding.nodeId === 'coordinator' ? 'v0.5.20260713.00' : binding.nodeId === 'billing' ? 'v0.4.20260713.00' : 'v0.1.20260712.00', tone: 'production' as const },
  ]
  return <div className="min-h-0 flex-1 overflow-y-auto p-4 scrollbar-thin"><div><p className="text-sm font-semibold text-white">Agent lifecycle</p><p className="mt-1 text-[10px] leading-4 text-muted">Review the Agent versions available to this Network node.</p></div><div className="mt-4 space-y-2">{releases.map((release) => <div key={release.label} className="rounded-xl border border-border/75 bg-background/30 p-3.5"><div className="flex items-start justify-between gap-3"><div><p className="text-[9px] uppercase tracking-[0.16em] text-muted">{release.label}</p><p className="mt-1.5 font-mono text-[11px] text-white">{release.value}</p></div><Badge tone={release.tone}>{release.label === 'Latest Release' ? 'Release' : release.label}</Badge></div></div>)}</div><div className="mt-4 rounded-xl border border-primary/20 bg-primary/[0.05] p-3"><p className="text-[10px] font-medium text-white">Network publish behavior</p><p className="mt-1 text-[10px] leading-4 text-muted">Staging snapshots create or reuse immutable Agent Releases. Standalone Agent Production is not changed.</p></div></div>
}

function AgentWorkspace({ binding, expanded, onExpandedChange }: { binding: ResolvedAgentBinding; expanded: boolean; onExpandedChange: (expanded: boolean) => void }) {
  const [activeTab, setActiveTab] = useState<AgentWorkspaceTab>('configure')
  const [configureTab, setConfigureTab] = useState<ConfigureTab>('agent')
  const [bindingMode, setBindingMode] = useState<BindingMode>(binding.binding)
  const [draft, setDraft] = useState<AgentEditorDraft>({
    name: binding.agent.name,
    role: binding.nodeId === 'coordinator' ? 'Routes requests to the correct specialist.' : binding.nodeId === 'billing' ? 'Handles billing and subscription questions.' : 'Resolves technical support requests.',
    prompt: `You are ${binding.agent.name}. Operate only within your assigned role and return control to the Network when another Agent is required.`,
    model: `${binding.agent.provider}/${binding.agent.model}`,
    temperature: '0.3',
    outputMode: 'json',
    outputSchema: '{\n  "answer": "string",\n  "confidence": "number",\n  "handoff": "string | null"\n}',
    knowledge: 'Customer Support Knowledge',
    tools: binding.nodeId === 'billing' ? ['stripe.lookup_invoice', 'billing.create_refund_request'] : binding.nodeId === 'technical' ? ['status.lookup_incident', 'support.create_ticket'] : ['customer.lookup_account'],
  })
  const effectiveBinding = { ...binding, binding: bindingMode }
  return <div className="flex min-h-0 flex-1 flex-col"><div className="border-b border-border/80 p-3"><div className="flex items-start gap-3"><div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-primary/25 bg-primary/10 text-primary-light"><Bot className="h-4 w-4" /></div><div className="min-w-0 flex-1"><div className="flex items-center gap-2"><p className="truncate text-xs font-semibold text-white">{binding.agent.name}</p><span className={cn('rounded-md border px-1.5 py-0.5 text-[8px] font-semibold uppercase', sourceStyles[binding.source])}>{binding.source}</span></div><p className="mt-1 text-[10px] text-muted">Network uses <span className="font-mono text-slate-200">{binding.version}</span></p></div><button type="button" onClick={() => onExpandedChange(!expanded)} className="rounded-lg border border-border/80 bg-background/35 p-1.5 text-muted hover:text-white">{expanded ? <Minimize2 className="h-3.5 w-3.5" /> : <Maximize2 className="h-3.5 w-3.5" />}</button></div></div><WorkspaceTabs active={activeTab} onChange={setActiveTab} />{activeTab === 'configure' && <ConfigureWorkspace draft={draft} onChange={(patch) => setDraft((current) => ({ ...current, ...patch }))} onSave={() => toast.success('Agent Draft saved in the mockup')} activeTab={configureTab} onTabChange={setConfigureTab} />}{activeTab === 'test' && <TestWorkspace binding={binding} />}{activeTab === 'binding' && <BindingWorkspace binding={effectiveBinding} onBindingChange={setBindingMode} />}{activeTab === 'releases' && <AgentReleasesWorkspace binding={binding} />}</div>
}

function TerminalInspector({ node }: { node: 'entry' | 'end' }) {
  return <div className="space-y-4 p-4"><div className="rounded-xl border border-border/75 bg-background/35 p-3.5"><div className="flex items-center gap-3"><div className="flex h-9 w-9 items-center justify-center rounded-xl border border-primary/25 bg-primary/10 text-primary-light"><CircleDot className="h-4 w-4" /></div><div><p className="text-xs font-semibold text-white">{node === 'entry' ? 'Network entry' : 'Network output'}</p><p className="mt-0.5 text-[10px] text-muted">{node === 'entry' ? 'Receives every runtime request.' : 'Returns the final response.'}</p></div></div></div><div className="rounded-xl border border-border/70 bg-background/25 px-3"><DetailRow label="Schema" value={node === 'entry' ? 'NetworkInput v1' : 'NetworkOutput v1'} /><DetailRow label="Validation" value="Strict" /><DetailRow label="Streaming" value="Enabled" /></div></div>
}

function NetworkVersions({ onAction }: { onAction: (action: Exclude<ReleaseAction, null>) => void }) {
  return <div className="min-h-0 flex-1 overflow-y-auto p-4 scrollbar-thin"><div><p className="text-sm font-semibold text-white">Network versions</p><p className="mt-1 text-[10px] leading-4 text-muted">Draft is mutable. Staging and Production preserve exact composition snapshots.</p></div><div className="mt-4 space-y-2.5"><div className="rounded-xl border border-border/80 bg-background/30 p-3.5"><div className="flex items-start justify-between gap-3"><div><p className="text-[9px] uppercase tracking-[0.16em] text-muted">Current Draft</p><p className="mt-1.5 font-mono text-[11px] text-white">Revision 18</p><p className="mt-1.5 text-[10px] leading-4 text-muted">1 Draft · 1 Staging · 1 Release · 2 readiness actions</p></div><button type="button" onClick={() => onAction('stage')} className="rounded-lg bg-primary px-2.5 py-1.5 text-[10px] font-semibold text-white">Stage</button></div></div><div className="rounded-xl border border-indigo-500/30 bg-indigo-500/[0.045] p-3.5"><div className="flex items-start justify-between gap-3"><div><p className="text-[9px] uppercase tracking-[0.16em] text-indigo-300">Staging</p><p className="mt-1.5 font-mono text-[11px] text-white">v0.3.20260713.00</p><p className="mt-1.5 text-[10px] leading-4 text-muted">3 exact Agent snapshots · 0 blockers</p></div><button type="button" onClick={() => onAction('publish')} className="rounded-lg border border-indigo-500/35 bg-indigo-500/10 px-2.5 py-1.5 text-[10px] font-semibold text-indigo-200">Publish</button></div></div><div className="rounded-xl border border-emerald-500/30 bg-emerald-500/[0.04] p-3.5"><div className="flex items-start justify-between gap-3"><div><p className="text-[9px] uppercase tracking-[0.16em] text-emerald-300">Production</p><p className="mt-1.5 font-mono text-[11px] text-white">v0.2.20260710.00</p><p className="mt-1.5 text-[10px] leading-4 text-muted">3 immutable Agent Releases · active runtime</p></div><Eye className="h-3.5 w-3.5 text-muted" /></div></div></div><section className="mt-5"><div className="mb-2 flex items-center justify-between"><p className="text-[9px] font-semibold uppercase tracking-[0.18em] text-muted/80">History</p><History className="h-3.5 w-3.5 text-muted" /></div><div className="rounded-lg border border-border/70 bg-background/25 p-3"><div className="flex items-start justify-between"><div><p className="font-mono text-[10px] font-medium text-white">v0.1.20260708.01</p><p className="mt-1 text-[9px] text-muted">2 Agents · exact composition preserved</p></div><Badge>Archived</Badge></div><div className="mt-3 flex gap-3"><button type="button" className="text-[9px] text-primary-light">View composition</button><button type="button" onClick={() => onAction('rollback')} className="inline-flex items-center gap-1.5 text-[9px] font-medium text-emerald-400"><RotateCcw className="h-3 w-3" />Rollback Production</button></div></div></section></div>
}

function RightPanel({ mode, onMode, node, binding, expanded, onExpandedChange, onAction }: { mode: RightPanelMode; onMode: (mode: RightPanelMode) => void; node: NodeId; binding: ResolvedAgentBinding | null; expanded: boolean; onExpandedChange: (expanded: boolean) => void; onAction: (action: Exclude<ReleaseAction, null>) => void }) {
  return <aside className={cn('hidden shrink-0 flex-col border-l border-border/90 bg-surface/75 2xl:flex', expanded ? 'w-[680px]' : 'w-[480px]')}><div className="grid grid-cols-2 gap-1 border-b border-border/80 bg-background/20 p-1.5"><button type="button" onClick={() => onMode('agent')} className={cn('flex items-center justify-center gap-2 rounded-lg border px-3 py-2 text-[11px] font-medium', mode === 'agent' ? 'border-primary/30 bg-primary/10 text-primary-light' : 'border-transparent text-muted hover:border-border/70 hover:text-white')}><Bot className="h-3.5 w-3.5" />Agent workspace</button><button type="button" onClick={() => onMode('network')} className={cn('flex items-center justify-center gap-2 rounded-lg border px-3 py-2 text-[11px] font-medium', mode === 'network' ? 'border-primary/30 bg-primary/10 text-primary-light' : 'border-transparent text-muted hover:border-border/70 hover:text-white')}><Rocket className="h-3.5 w-3.5" />Network versions</button></div>{mode === 'network' ? <NetworkVersions onAction={onAction} /> : binding ? <AgentWorkspace key={binding.nodeId} binding={binding} expanded={expanded} onExpandedChange={onExpandedChange} /> : <TerminalInspector node={node === 'entry' ? 'entry' : 'end'} />}</aside>
}

function CopyButton({ value }: { value: string }) {
  return <button type="button" onClick={() => { void navigator.clipboard?.writeText(value); toast.success('Copied') }} className="rounded-lg border border-border/80 bg-background/35 p-1.5 text-muted hover:text-white"><Copy className="h-3.5 w-3.5" /></button>
}

function ApiReferenceModal({ open, onClose, agents }: { open: boolean; onClose: () => void; agents: [Agent, Agent, Agent] }) {
  const [environment, setEnvironment] = useState<'staging' | 'production'>('production')
  const [section, setSection] = useState<ApiSection>('http')
  if (!open) return null
  const version = environment === 'production' ? 'v0.2.20260710.00' : 'v0.3.20260713.00'
  const endpoint = section === 'http' ? '/v1/run' : section === 'stream' ? '/v1/run/stream' : section === 'jobs' ? '/v1/jobs' : '/v1/chat/completions'
  const curl = `curl ${section === 'stream' ? '-N ' : ''}-X POST ${API_BASE_URL}${endpoint} \\
  -H "Authorization: Bearer $WOOBE_API_KEY" \\
  -H "Content-Type: application/json" \\
  -d '${JSON.stringify(section === 'openai' ? { model: 'woobe-network', messages: [{ role: 'user', content: 'Hello!' }], stream: false } : { message: 'Hello!', session_id: '<optional-uuid>' }, null, 2)}'`
  return <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 p-4 backdrop-blur-md"><div className="flex h-[86vh] w-full max-w-[1180px] flex-col overflow-hidden rounded-2xl border border-border/90 bg-surface shadow-2xl"><div className="flex items-start justify-between gap-4 border-b border-border/80 bg-background/20 px-5 py-4"><div><p className="text-[9px] font-semibold uppercase tracking-[0.18em] text-primary-light">Network runtime</p><h2 className="mt-1.5 text-base font-semibold text-white">API Reference</h2><p className="mt-1 text-[11px] text-muted">Integrate with the active immutable Network Release through a Runtime Key.</p></div><button type="button" onClick={onClose} className="rounded-lg p-1.5 text-muted hover:text-white"><X className="h-4 w-4" /></button></div><div className="grid min-h-0 flex-1 grid-cols-[330px_1fr]"><aside className="min-h-0 overflow-y-auto border-r border-border/90 bg-background/20 p-4 scrollbar-thin"><div className="space-y-4"><div><p className="text-[9px] font-semibold uppercase tracking-[0.16em] text-muted">Network</p><div className="mt-2 rounded-xl border border-border/80 bg-background/45 p-3"><p className="text-sm font-medium text-white">Customer Support Network</p><div className="mt-2 flex items-center gap-2"><code className="min-w-0 flex-1 truncate text-[10px] text-muted">network_01JZPRAI8FC</code><CopyButton value="network_01JZPRAI8FC" /></div></div></div><div><p className="text-[9px] font-semibold uppercase tracking-[0.16em] text-muted">Environment</p><div className="mt-2 grid grid-cols-2 gap-2">{(['production', 'staging'] as const).map((slot) => <button key={slot} type="button" onClick={() => setEnvironment(slot)} className={cn('rounded-xl border p-3 text-left', environment === slot ? 'border-primary/35 bg-primary/10' : 'border-border/80 bg-background/45')}><p className="text-xs font-semibold capitalize text-white">{slot}</p><p className="mt-1 font-mono text-[9px] text-muted">{slot === 'production' ? 'v0.2.20260710.00' : 'v0.3.20260713.00'}</p></button>)}</div></div><div className="rounded-xl border border-border/80 bg-background/45 p-3"><div className="flex items-start justify-between"><div><p className="text-[9px] uppercase tracking-[0.16em] text-muted">Active Network Release</p><p className="mt-1.5 font-mono text-xs text-white">{version}</p></div><Badge tone={environment === 'production' ? 'production' : 'staging'}>{environment}</Badge></div><div className="mt-3 space-y-1 text-[10px] text-muted"><p>3 Agent Releases</p><p>5 connections</p><p>Max hops: 8</p><p>Sequential handoffs</p></div></div><div><p className="text-[9px] font-semibold uppercase tracking-[0.16em] text-muted">Composition</p><div className="mt-2 space-y-2">{agents.map((agent, index) => <div key={agent.id} className="rounded-lg border border-border/70 bg-background/35 p-2.5"><div className="flex items-center justify-between gap-2"><span className="truncate text-[10px] text-white">{agent.name}</span><span className="font-mono text-[9px] text-emerald-300">v0.{index + 3}.20260713.00</span></div></div>)}</div></div><div><p className="text-[9px] font-semibold uppercase tracking-[0.16em] text-muted">Runtime Key</p><div className="mt-2 rounded-xl border border-primary/20 bg-primary/[0.05] p-3"><div className="flex items-center gap-2"><KeyRound className="h-4 w-4 text-primary-light" /><div><p className="text-[11px] font-medium text-white">{environment === 'production' ? 'Production Network Key' : 'Staging Network Key'}</p><p className="mt-0.5 font-mono text-[9px] text-muted">rk_{environment === 'production' ? 'live' : 'stg'}_••••••••</p></div></div><p className="mt-2 text-[9px] leading-4 text-muted">The key resolves target_type=network, target_id and environment. Deploys do not require client changes.</p></div></div></div></aside><section className="flex min-h-0 flex-col"><div className="flex gap-1 border-b border-border/90 bg-surface/70 p-1.5">{([['http', 'HTTP'], ['stream', 'Streaming'], ['jobs', 'Jobs'], ['openai', 'OpenAI Compatible']] as Array<[ApiSection, string]>).map(([id, label]) => <button key={id} type="button" onClick={() => setSection(id)} className={cn('rounded-lg border px-3 py-2 text-xs font-medium', section === id ? 'border-primary/35 bg-primary/10 text-primary-light' : 'border-transparent text-muted hover:border-border/80 hover:text-white')}>{label}</button>)}</div><div className="min-h-0 flex-1 overflow-y-auto p-5 scrollbar-thin"><div className="space-y-5"><div><p className="mb-2 text-xs font-medium text-muted">Endpoint</p><div className="flex items-center gap-2 rounded-xl border border-border/80 bg-background/45 p-3"><span className="text-[10px] font-semibold text-primary-light">POST</span><code className="min-w-0 flex-1 truncate text-[11px] text-white">{endpoint}</code><CopyButton value={`POST ${endpoint}`} /></div></div><div className="grid gap-4 xl:grid-cols-2"><div><p className="mb-2 text-xs font-medium text-muted">Request</p><pre className="min-h-48 overflow-auto rounded-xl border border-border/80 bg-black/20 p-4 text-[11px] leading-5 text-slate-300">{JSON.stringify(section === 'openai' ? { model: 'woobe-network', messages: [{ role: 'user', content: 'Hello!' }], stream: false } : { message: 'Hello!', session_id: '<optional-uuid>' }, null, 2)}</pre></div><div><p className="mb-2 text-xs font-medium text-muted">Response</p><pre className="min-h-48 overflow-auto rounded-xl border border-border/80 bg-black/20 p-4 text-[11px] leading-5 text-slate-300">{JSON.stringify({ success: true, data: { answer: 'How can I help?', session_id: '<uuid>', trace_id: '<uuid>', network_release_version: version, hops: 2, usage: { input_tokens: 820, output_tokens: 180, cost_usd: 0.014 } } }, null, 2)}</pre></div></div><div><p className="mb-2 text-xs font-medium text-muted">cURL</p><div className="relative"><pre className="overflow-auto rounded-xl border border-border/80 bg-black/20 p-4 pr-12 text-[11px] leading-5 text-slate-300">{curl}</pre><div className="absolute right-3 top-3"><CopyButton value={curl} /></div></div></div><div className="rounded-xl border border-primary/20 bg-primary/[0.05] p-4"><p className="text-[10px] font-medium text-white">Trace composition</p><p className="mt-1 text-[10px] leading-4 text-muted">Public responses expose the Network Release and trace ID. Exact Agent Release IDs remain available in Traces, keeping the API stable while preserving operational evidence.</p></div></div></div></section></div></div></div>
}

function ReleasePlanRow({ name, current, action, status }: { name: string; current: string; action: string; status: 'required' | 'ready' | 'reuse' }) {
  return <div className="rounded-xl border border-border/75 bg-background/30 p-3"><div className="flex items-start justify-between gap-3"><div><p className="text-[11px] font-medium text-white">{name}</p><p className="mt-1 font-mono text-[9px] text-muted">{current}</p><p className="mt-2 text-[10px] text-slate-300">{action}</p></div><Badge tone={status === 'required' ? 'warning' : status === 'reuse' ? 'production' : 'staging'}>{status}</Badge></div></div>
}

function ReleaseModal({ action, agents, onClose, onConfirm }: { action: Exclude<ReleaseAction, null>; agents: [Agent, Agent, Agent]; onClose: () => void; onConfirm: () => void }) {
  const content = action === 'stage'
    ? { eyebrow: 'Draft → Staging', title: 'Stage Network and required Agents?', description: 'Promote every Agent Draft required by the Network, then create one exact Network Staging snapshot.', confirm: 'Stage Network and 1 Agent', icon: ShieldCheck }
    : action === 'publish'
      ? { eyebrow: 'Staging → Release', title: 'Publish Network Release?', description: 'Create or reuse immutable Agent Releases, then pin them inside a new Network Release.', confirm: 'Publish Network and 2 Agent Releases', icon: Rocket }
      : { eyebrow: 'Production rollback', title: 'Rollback Network Production?', description: 'Reactivate one historical Network Release and all Agent Release IDs already pinned inside it.', confirm: 'Rollback Network', icon: RotateCcw }
  const Icon = content.icon
  return <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 p-4 backdrop-blur-md"><div className="w-full max-w-3xl overflow-hidden rounded-2xl border border-border/90 bg-surface shadow-2xl"><div className="flex items-start gap-4 border-b border-border/80 bg-background/20 p-5"><div className="flex h-10 w-10 items-center justify-center rounded-xl border border-primary/25 bg-primary/10 text-primary-light"><Icon className="h-5 w-5" /></div><div className="min-w-0 flex-1"><p className="text-[9px] font-semibold uppercase tracking-[0.18em] text-primary-light">{content.eyebrow}</p><h2 className="mt-1.5 text-lg font-semibold text-white">{content.title}</h2><p className="mt-1.5 text-xs leading-5 text-muted">{content.description}</p></div><button type="button" onClick={onClose} className="rounded-lg p-1.5 text-muted hover:text-white"><X className="h-4 w-4" /></button></div><div className="max-h-[62vh] space-y-4 overflow-y-auto p-5 scrollbar-thin">{action === 'stage' && <><div className="grid gap-2"><ReleasePlanRow name={agents[0].name} current="Agent Draft · Revision 14" action="Create Agent Staging" status="required" /><ReleasePlanRow name={agents[1].name} current="Agent Staging · v0.3.20260713.01" action="Reuse exact Staging snapshot" status="ready" /><ReleasePlanRow name={agents[2].name} current="Agent Release · v0.1.20260712.00" action="Reuse immutable Release" status="reuse" /></div><div className="rounded-xl border border-primary/20 bg-primary/[0.05] p-4"><p className="text-[10px] font-medium text-white">Atomic operation</p><ol className="mt-2 space-y-1 text-[10px] leading-4 text-muted"><li>1. Save pending Agent Draft changes.</li><li>2. Create Staging for 1 Agent.</li><li>3. Resolve exact Agent snapshot IDs.</li><li>4. Create immutable Network Staging.</li></ol></div></>}{action === 'publish' && <><div className="grid gap-2"><ReleasePlanRow name={agents[0].name} current="Agent Staging · v0.4.20260713.02" action="Create or reuse identical Agent Release" status="required" /><ReleasePlanRow name={agents[1].name} current="Agent Staging · v0.3.20260713.01" action="Create or reuse identical Agent Release" status="required" /><ReleasePlanRow name={agents[2].name} current="Agent Release · v0.1.20260712.00" action="Reuse existing Agent Release" status="reuse" /></div><label className="block"><span className="text-[10px] font-medium text-muted">Release description *</span><textarea className="mt-1.5 min-h-24 w-full resize-none rounded-xl border border-border bg-background/45 px-3 py-2.5 text-xs text-white outline-none focus:border-primary/45" defaultValue="Add technical routing and update billing behavior." /></label><div className="rounded-xl border border-emerald-500/20 bg-emerald-500/[0.05] p-4"><p className="text-[10px] font-medium text-white">No standalone Agent deploys</p><p className="mt-1 text-[10px] leading-4 text-muted">This operation creates or reuses immutable Agent Releases for the Network. It does not change each Agent's standalone Production slot.</p></div></>}{action === 'rollback' && <><div className="rounded-xl border border-amber-500/25 bg-amber-500/[0.055] p-4"><div className="flex gap-3"><AlertTriangle className="h-4 w-4 shrink-0 text-amber-400" /><div><p className="text-[10px] font-medium text-amber-100">Production v0.2 will be replaced by Network Release v0.1.</p><p className="mt-1 text-[10px] leading-4 text-amber-100/70">The rollback reuses the exact Agent Release IDs already stored in that historical Network snapshot. Agent Draft and Staging remain unchanged.</p></div></div></div><label className="block"><span className="text-[10px] font-medium text-muted">Rollback reason *</span><textarea className="mt-1.5 min-h-20 w-full resize-none rounded-xl border border-border bg-background/45 px-3 py-2.5 text-xs text-white outline-none" defaultValue="Restore previous stable routing composition." /></label></>}<p className="rounded-lg border border-border/65 bg-background/20 px-3 py-2 text-[9px] text-muted">Prototype only. No Network or Agent release is persisted by this mockup.</p></div><div className="flex justify-end gap-2 border-t border-border/80 bg-background/20 p-4"><button type="button" onClick={onClose} className="rounded-xl border border-border px-3.5 py-2 text-[11px] text-muted">Cancel</button><button type="button" onClick={onConfirm} className={cn('rounded-xl px-3.5 py-2 text-[11px] font-semibold text-white', action === 'rollback' ? 'bg-red-600' : 'bg-primary')}>{content.confirm}</button></div></div></div>
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
  const [rightMode, setRightMode] = useState<RightPanelMode>('agent')
  const [expandedInspector, setExpandedInspector] = useState(false)
  const [releaseAction, setReleaseAction] = useState<ReleaseAction>(null)
  const [apiOpen, setApiOpen] = useState(false)
  const hasAgents = Boolean(agentsQuery.data?.length)
  const agents = useMemo<[Agent, Agent, Agent]>(() => {
    const source = agentsQuery.data?.length ? agentsQuery.data : fallbackAgents
    return [source[0] ?? fallbackAgents[0], source[1] ?? fallbackAgents[1], source[2] ?? fallbackAgents[2]]
  }, [agentsQuery.data])
  const bindings = useMemo(() => resolvedBindings(agents, environment), [agents, environment])
  const run = runs.find((item) => item.id === selectedRunId) ?? runs[0]
  const selectedBinding = selectedNode === 'coordinator' || selectedNode === 'billing' || selectedNode === 'technical' ? bindings[selectedNode] : null
  const headerAction = environment === 'draft' ? ['Stage Network', ShieldCheck, 'stage'] as const : environment === 'staging' ? ['Publish Release', Rocket, 'publish'] as const : ['Rollback', RotateCcw, 'rollback'] as const
  const HeaderActionIcon = headerAction[1]

  const confirmAction = () => {
    if (releaseAction === 'stage') { setEnvironment('staging'); toast.success('Network and required Agent staged in the prototype') }
    if (releaseAction === 'publish') { setEnvironment('production'); toast.success('Network Release and Agent Releases published in the prototype') }
    if (releaseAction === 'rollback') toast.success('Network Production rollback simulated')
    setReleaseAction(null)
  }

  const handleNodeSelection = (node: NodeId) => {
    setSelectedNode(node)
    setRightMode('agent')
  }

  return <div className="flex h-screen min-w-[1180px] flex-col overflow-hidden bg-background"><header className="flex h-14 shrink-0 items-center gap-3 border-b border-border/90 bg-surface/80 px-3"><button type="button" onClick={() => navigate(`/organizations/${organizationId}/projects/${projectId}`)} className="flex h-8 w-8 items-center justify-center rounded-lg border border-border/80 bg-background/35 text-muted hover:text-white"><ChevronLeft className="h-4 w-4" /></button><div className="h-6 w-px bg-border" /><div className="min-w-0"><div className="flex items-center gap-2"><h1 className="truncate text-sm font-semibold text-white">{currentProject?.name || 'Project'} Network</h1><Badge>Prototype</Badge></div><p className="mt-0.5 text-[9px] text-muted">One operational Agent Network for this Project</p></div><div className="ml-auto flex items-center gap-2"><div className="hidden items-center gap-1.5 rounded-lg border border-border/75 bg-background/30 px-2.5 py-1.5 text-[9px] text-muted xl:flex"><span className="h-1.5 w-1.5 rounded-full bg-emerald-400" />Draft saved 14s ago</div><div className="flex rounded-xl border border-border/80 bg-background/35 p-1">{(['draft', 'staging', 'production'] as Environment[]).map((item) => <button key={item} type="button" onClick={() => setEnvironment(item)} className={cn('rounded-lg px-3 py-1.5 text-[10px] font-medium capitalize', environment === item ? item === 'production' ? 'bg-emerald-500/12 text-emerald-300' : item === 'staging' ? 'bg-indigo-500/12 text-indigo-300' : 'bg-primary/12 text-primary-light' : 'text-muted hover:text-white')}>{item}</button>)}</div><button type="button" onClick={() => setPanelTab('validation')} className="hidden items-center gap-2 rounded-xl border border-border/80 bg-background/35 px-3 py-2 text-[10px] text-slate-200 xl:flex"><ListChecks className="h-3.5 w-3.5" />Validate</button><button type="button" onClick={() => { setEnvironment('draft'); setPanelTab('runs'); setSelectedRunId('run-4'); toast.success('Network Draft test started in the prototype') }} className="flex items-center gap-2 rounded-xl border border-primary/30 bg-primary/10 px-3 py-2 text-[10px] font-semibold text-primary-light"><Play className="h-3.5 w-3.5 fill-current" />Run Network</button><button type="button" onClick={() => setApiOpen(true)} className="flex items-center gap-2 rounded-xl border border-border/80 bg-background/35 px-3 py-2 text-[10px] font-semibold text-slate-200"><Code2 className="h-3.5 w-3.5" />API Reference</button><button type="button" onClick={() => setReleaseAction(headerAction[2])} className="flex items-center gap-2 rounded-xl bg-primary px-3 py-2 text-[10px] font-semibold text-white"><HeaderActionIcon className="h-3.5 w-3.5" />{headerAction[0]}</button></div></header><div className="flex h-7 shrink-0 items-center border-b border-border/80 bg-surface/35 px-3 text-[9px] text-muted"><span className="font-medium text-slate-300">Using: {environment === 'draft' ? 'Current Draft · Revision 18' : environment === 'staging' ? 'Network Staging v0.3.20260713.00' : 'Network Release v0.2.20260710.00'}</span><span className="mx-2 text-border">·</span><span>{environment === 'draft' ? 'Editable workspace with mixed Agent sources' : 'Immutable composition snapshot'}</span><span className="ml-auto">Max hops 8 · Timeout 90s · Sequential handoffs</span></div><div className="flex min-h-0 flex-1 overflow-hidden"><nav className="flex w-14 shrink-0 flex-col items-center gap-2 border-r border-border/90 bg-surface/75 p-2">{panelItems.map((item) => { const Icon = item.icon; return <button key={item.id} type="button" onClick={() => setPanelTab(item.id)} className={cn('relative flex h-10 w-10 items-center justify-center rounded-xl border', panelTab === item.id ? 'border-primary/35 bg-primary/10 text-primary-light' : 'border-transparent text-muted hover:border-border/80 hover:text-white')} title={item.label}><Icon className="h-4 w-4" />{item.count != null && <span className="absolute -right-1 -top-1 min-w-4 rounded-full border border-surface bg-primary px-1 text-[8px] leading-4 text-white">{item.count}</span>}</button> })}<div className="mt-auto flex flex-col gap-2"><button type="button" onClick={() => toast.info('Agent picker opened in the prototype')} className="flex h-10 w-10 items-center justify-center rounded-xl border border-border/80 bg-background/35 text-muted"><Plus className="h-4 w-4" /></button><button type="button" onClick={() => toast.info('Network settings opened in the prototype')} className="flex h-10 w-10 items-center justify-center rounded-xl text-muted"><Settings2 className="h-4 w-4" /></button></div></nav><aside className="hidden w-[330px] shrink-0 border-r border-border/90 bg-surface/65 xl:block"><OperationsPanel tab={panelTab} run={run} selectedRunId={selectedRunId} onSelectRun={setSelectedRunId} /></aside>{agentsQuery.isLoading ? <div className="flex flex-1 items-center justify-center text-xs text-muted">Loading Network inventory</div> : hasAgents ? <NetworkCanvas agents={agents} bindings={bindings} selectedNode={selectedNode} onSelectNode={handleNodeSelection} run={run} environment={environment} /> : <EmptyNetwork onCreateAgent={() => navigate(`/organizations/${organizationId}/projects/${projectId}/agents`)} />}<RightPanel mode={rightMode} onMode={setRightMode} node={selectedNode} binding={selectedBinding} expanded={expandedInspector} onExpandedChange={setExpandedInspector} onAction={setReleaseAction} /></div>{releaseAction && <ReleaseModal action={releaseAction} agents={agents} onClose={() => setReleaseAction(null)} onConfirm={confirmAction} />}<ApiReferenceModal open={apiOpen} onClose={() => setApiOpen(false)} agents={agents} /></div>
}
