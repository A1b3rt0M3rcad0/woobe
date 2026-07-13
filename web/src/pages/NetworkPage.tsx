import { useMemo, useRef, useState, type ReactNode } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { toast } from 'sonner'
import {
  Activity,
  AlertTriangle,
  Bot,
  Bug,
  CheckCircle2,
  ChevronLeft,
  CircleDot,
  Code2,
  Copy,
  GitBranch,
  KeyRound,
  ListChecks,
  Maximize2,
  MessageSquare,
  Minimize2,
  Plus,
  Rocket,
  Search,
  Send,
  Settings2,
  SlidersHorizontal,
  Workflow,
  X,
  type LucideIcon,
} from 'lucide-react'

import { useAgents } from '@/features/agents/hooks'
import type { Agent } from '@/features/agents/types'
import {
  NetworkAgentWorkspace,
  type AgentNetworkBindingSummary,
} from '@/features/network/components/NetworkAgentWorkspace'
import { useWorkspace } from '@/features/workspace/WorkspaceProvider'
import { API_BASE_URL } from '@/lib/api/client'
import { cn } from '@/lib/utils'

type Environment = 'draft' | 'staging' | 'production'
type ChatTarget = Environment | 'history'
type Source = 'draft' | 'staging' | 'release'
type NodeId = 'entry' | 'coordinator' | 'billing' | 'technical' | 'end'
type AgentNodeId = Exclude<NodeId, 'entry' | 'end'>
type PanelTab = 'runs' | 'trace' | 'debug' | 'validation'
type CenterMode = 'canvas' | 'chat'
type InspectorContext = 'agent' | 'network'
type NetworkSection = 'configuration' | 'versions'
type NetworkConfigSection = 'general' | 'composition' | 'routing' | 'runtime'
type ReleaseAction = 'stage' | 'publish' | 'rollback' | null

type Selection = {
  source: Source
  ref: string
  version: string
  draftVersion: string
  draftBase?: string
  dirty: boolean
}

type Binding = Selection & {
  nodeId: AgentNodeId
  agent: Agent
}

type VersionOption = {
  source: Source
  ref: string
  version: string
  note: string
  created: string
}

type Run = {
  id: string
  title: string
  environment: Environment
  status: 'success' | 'error' | 'running'
  duration: string
  cost: string
  path: NodeId[]
}

type Message = {
  role: 'user' | 'assistant'
  content: string
  path?: string
  meta?: string
}

const surface = 'rounded-xl border border-border/75 bg-background/35'
const smallButton = 'rounded-lg border border-border/80 bg-background/40 px-2.5 py-1.5 text-[10px] font-medium text-muted hover:border-primary/30 hover:text-white disabled:cursor-not-allowed disabled:opacity-45'

const sourceClass: Record<Source, string> = {
  draft: 'border-blue-500/30 bg-blue-500/10 text-blue-300',
  staging: 'border-indigo-500/30 bg-indigo-500/10 text-indigo-300',
  release: 'border-emerald-500/30 bg-emerald-500/10 text-emerald-300',
}

const fallbackAgents: [Agent, Agent, Agent] = [
  { id: 'mock-coordinator', project_id: 'mock', name: 'Coordinator', description: 'Routes requests to the correct specialist.', provider: 'openai', model: 'gpt-5.2', status: 'active' },
  { id: 'mock-billing', project_id: 'mock', name: 'Billing Specialist', description: 'Handles invoices, payments and subscriptions.', provider: 'openai', model: 'gpt-5.2-mini', status: 'active' },
  { id: 'mock-technical', project_id: 'mock', name: 'Technical Support', description: 'Investigates incidents and technical questions.', provider: 'anthropic', model: 'claude-sonnet-4.5', status: 'active' },
]

const DRAFT: Record<AgentNodeId, Selection> = {
  coordinator: { source: 'draft', ref: 'draft-coordinator', version: 'Revision 14', draftVersion: 'Revision 14', dirty: false },
  billing: { source: 'staging', ref: 'staging-billing-v3', version: 'v0.3.20260713.01', draftVersion: 'Revision 9', dirty: false },
  technical: { source: 'release', ref: 'release-technical-v1', version: 'v0.1.20260712.00', draftVersion: 'Revision 7', dirty: false },
}

const STAGING: Record<AgentNodeId, Selection> = {
  coordinator: { source: 'staging', ref: 'staging-coordinator-v4', version: 'v0.4.20260713.02', draftVersion: 'Revision 14', dirty: false },
  billing: { source: 'staging', ref: 'staging-billing-v3', version: 'v0.3.20260713.01', draftVersion: 'Revision 9', dirty: false },
  technical: { source: 'release', ref: 'release-technical-v1', version: 'v0.1.20260712.00', draftVersion: 'Revision 7', dirty: false },
}

const PRODUCTION: Record<AgentNodeId, Selection> = {
  coordinator: { source: 'release', ref: 'release-coordinator-v5', version: 'v0.5.20260713.00', draftVersion: 'Revision 14', dirty: false },
  billing: { source: 'release', ref: 'release-billing-v4', version: 'v0.4.20260713.00', draftVersion: 'Revision 9', dirty: false },
  technical: { source: 'release', ref: 'release-technical-v1', version: 'v0.1.20260712.00', draftVersion: 'Revision 7', dirty: false },
}

const HISTORY: Record<AgentNodeId, Selection> = {
  coordinator: { source: 'release', ref: 'release-coordinator-v3', version: 'v0.3.20260701.00', draftVersion: 'Revision 14', dirty: false },
  billing: { source: 'release', ref: 'release-billing-v2', version: 'v0.2.20260629.01', draftVersion: 'Revision 9', dirty: false },
  technical: { source: 'release', ref: 'release-technical-v1', version: 'v0.1.20260712.00', draftVersion: 'Revision 7', dirty: false },
}

const runHistory: Run[] = [
  { id: 'run-1', title: 'Invoice status request', environment: 'production', status: 'success', duration: '1.84s', cost: '$0.012', path: ['entry', 'coordinator', 'billing', 'end'] },
  { id: 'run-2', title: 'Password reset guidance', environment: 'staging', status: 'success', duration: '2.21s', cost: '$0.017', path: ['entry', 'coordinator', 'technical', 'end'] },
  { id: 'run-3', title: 'API timeout investigation', environment: 'staging', status: 'error', duration: '0.73s', cost: '$0.004', path: ['entry', 'coordinator', 'technical'] },
]

function clone(value: Record<AgentNodeId, Selection>): Record<AgentNodeId, Selection> {
  return {
    coordinator: { ...value.coordinator },
    billing: { ...value.billing },
    technical: { ...value.technical },
  }
}

function bind(agents: [Agent, Agent, Agent], value: Record<AgentNodeId, Selection>): Record<AgentNodeId, Binding> {
  return {
    coordinator: { nodeId: 'coordinator', agent: agents[0], ...value.coordinator },
    billing: { nodeId: 'billing', agent: agents[1], ...value.billing },
    technical: { nodeId: 'technical', agent: agents[2], ...value.technical },
  }
}

function signature(target: ChatTarget, bindings: Record<AgentNodeId, Binding>) {
  return `${target}|${(['coordinator', 'billing', 'technical'] as AgentNodeId[])
    .map((id) => `${id}:${bindings[id].ref}:${bindings[id].dirty ? 'preview' : 'saved'}`)
    .join('|')}`
}

function sourceLabel(source: Source) {
  if (source === 'draft') return 'Agent Draft'
  if (source === 'staging') return 'Agent Staging'
  return 'Agent Release'
}

function networkLabel(target: ChatTarget) {
  if (target === 'draft') return 'Network Draft · Revision 29'
  if (target === 'staging') return 'Network Staging · v0.12.20260713.00'
  if (target === 'production') return 'Network Production · v0.10.20260710.00'
  return 'Historical Network Release · v0.8.20260701.00'
}

function catalog(binding: Binding): Record<Source, VersionOption[]> {
  const prefix = binding.nodeId
  const staging = binding.nodeId === 'coordinator'
    ? 'v0.4.20260713.02'
    : binding.nodeId === 'billing'
      ? 'v0.3.20260713.01'
      : 'v0.2.20260713.00'

  const releases = binding.nodeId === 'coordinator'
    ? [['v0.5.20260713.00', 'Current orchestration behavior'], ['v0.4.20260708.01', 'Previous routing policy'], ['v0.3.20260701.00', 'Stable June composition']]
    : binding.nodeId === 'billing'
      ? [['v0.4.20260713.00', 'Refund tool validation'], ['v0.3.20260706.02', 'Invoice lookup improvements'], ['v0.2.20260629.01', 'Previous billing behavior']]
      : [['v0.3.20260713.00', 'Incident routing update'], ['v0.2.20260705.00', 'Status page integration'], ['v0.1.20260712.00', 'Initial technical support release']]

  return {
    draft: [{ source: 'draft', ref: `draft-${prefix}`, version: binding.draftVersion, note: binding.draftBase ? `Based on ${binding.draftBase}` : 'Current mutable Agent Draft', created: 'Updated moments ago' }],
    staging: [{ source: 'staging', ref: `staging-${prefix}`, version: staging, note: 'Exact read-only validation snapshot', created: '13 Jul 2026, 14:42' }],
    release: releases.map(([version, note], index) => ({ source: 'release', ref: `release-${prefix}-${index}`, version, note, created: `${13 - index * 4} Jul 2026` })),
  }
}

function Badge({ children, tone = 'default' }: { children: ReactNode; tone?: 'default' | 'staging' | 'production' | 'warning' | 'danger' }) {
  const styles = {
    default: 'border-border bg-background/50 text-muted',
    staging: sourceClass.staging,
    production: sourceClass.release,
    warning: 'border-amber-500/30 bg-amber-500/10 text-amber-300',
    danger: 'border-red-500/30 bg-red-500/10 text-red-300',
  }
  return <span className={cn('rounded-md border px-1.5 py-0.5 text-[9px] font-semibold uppercase tracking-wide', styles[tone])}>{children}</span>
}

function PanelTitle({ title, description }: { title: string; description: string }) {
  return <div className="border-b border-border/80 p-4"><h2 className="text-sm font-semibold text-white">{title}</h2><p className="mt-1 text-[10px] leading-4 text-muted">{description}</p></div>
}

function Operations({ tab, run, draftBindings }: { tab: PanelTab; run: Run; draftBindings: Record<AgentNodeId, Binding> }) {
  if (tab === 'runs') {
    return (
      <div className="flex h-full flex-col">
        <PanelTitle title="Executions" description="Inspect Network path, composition and cost." />
        <div className="flex items-center gap-2 border-b border-border/70 p-3"><button className="rounded-md border border-primary/30 bg-primary/10 px-2 py-1 text-[10px] text-primary-light">All runs</button><Search className="ml-auto h-3.5 w-3.5 text-muted" /></div>
        <div className="space-y-2 overflow-y-auto p-3">
          {runHistory.map((item) => (
            <div key={item.id} className={cn(surface, 'p-3')}>
              <div className="flex items-start gap-2">
                <span className={cn('mt-1 h-2 w-2 rounded-full', item.status === 'success' ? 'bg-emerald-400' : 'bg-red-400')} />
                <div className="min-w-0 flex-1"><p className="truncate text-[11px] font-medium text-white">{item.title}</p><div className="mt-2 flex items-center gap-2"><Badge tone={item.environment === 'production' ? 'production' : 'staging'}>{item.environment}</Badge><span className="text-[9px] text-muted">{item.duration} · {item.cost}</span></div></div>
              </div>
            </div>
          ))}
        </div>
      </div>
    )
  }

  if (tab === 'trace') {
    return (
      <div className="flex h-full flex-col">
        <PanelTitle title="Trace path" description={`${run.title} · ${run.duration}`} />
        <div className="overflow-y-auto p-4">
          {run.path.map((node, index) => (
            <div key={`${node}-${index}`} className="relative flex gap-3 pb-5">
              <span className="relative z-10 mt-1 h-3 w-3 rounded-full border-2 border-emerald-400 bg-emerald-500/20" />
              {index < run.path.length - 1 && <span className="absolute left-[5px] top-4 h-full w-px bg-border" />}
              <div className={cn(surface, 'flex-1 p-2.5')}><p className="text-[10px] font-medium capitalize text-white">{node}</p><p className="mt-1 text-[9px] text-muted">Exact source and version recorded</p></div>
            </div>
          ))}
        </div>
      </div>
    )
  }

  if (tab === 'debug') {
    return (
      <div className="flex h-full flex-col">
        <PanelTitle title="Debug events" description="Raw Network orchestration events." />
        <div className="space-y-2 overflow-y-auto p-3 font-mono text-[9px]">
          {[
            ['network.started', 'checksum=9c14f3a1'],
            ['node.entered', 'node=coordinator'],
            ['handoff.selected', 'key=billing_support'],
            ['network.completed', 'status=success'],
          ].map(([name, data]) => <div key={name} className={cn(surface, 'p-3')}><p className="text-primary-light">{name}</p><p className="mt-1 text-muted">{data}</p></div>)}
        </div>
      </div>
    )
  }

  const drafts = Object.values(draftBindings).filter((item) => item.source === 'draft').length
  return (
    <div className="flex h-full flex-col">
      <PanelTitle title="Validation" description="Readiness before coordinated promotion." />
      <div className="grid grid-cols-2 gap-2 border-b border-border p-3"><div className="rounded-lg border border-emerald-500/20 bg-emerald-500/5 p-3"><p className="text-lg text-emerald-300">0</p><p className="text-[9px] text-muted">Blockers</p></div><div className="rounded-lg border border-amber-500/20 bg-amber-500/5 p-3"><p className="text-lg text-amber-300">2</p><p className="text-[9px] text-muted">Warnings</p></div></div>
      <div className="space-y-2 p-3">
        {['One entry point', 'Every route reaches END', `${drafts} Draft binding${drafts === 1 ? '' : 's'} can be promoted`, 'All exact versions are available'].map((text) => <div key={text} className={cn(surface, 'flex gap-2 p-3')}><CheckCircle2 className="h-4 w-4 text-emerald-400" /><p className="text-[10px] text-white">{text}</p></div>)}
      </div>
    </div>
  )
}

function NodeCard({ id, binding, active, selected, dirty, className, onSelect }: { id: NodeId; binding?: Binding; active: boolean; selected: boolean; dirty?: boolean; className: string; onSelect: () => void }) {
  const terminal = id === 'entry' || id === 'end'
  return (
    <button onClick={onSelect} className={cn('absolute z-20 border bg-surface/95 text-left shadow-xl transition', terminal ? 'flex h-14 w-28 items-center justify-center rounded-full' : 'w-56 rounded-2xl p-3.5', selected ? 'border-primary/70 ring-4 ring-primary/10' : active ? 'border-emerald-500/45' : 'border-border/90', className)}>
      {terminal ? (
        <div className="flex items-center gap-2"><CircleDot className="h-4 w-4 text-primary-light" /><span className="text-[10px] font-semibold tracking-widest text-white">{id.toUpperCase()}</span></div>
      ) : binding ? (
        <>
          <div className="flex gap-3"><div className="flex h-9 w-9 items-center justify-center rounded-xl border border-primary/25 bg-primary/10 text-primary-light"><Bot className="h-4 w-4" /></div><div className="min-w-0 flex-1"><p className="truncate text-xs font-semibold text-white">{binding.agent.name}</p><p className="mt-1 truncate text-[9px] text-muted">{binding.agent.provider}/{binding.agent.model}</p></div><span className={cn('mt-1 h-2 w-2 rounded-full', dirty ? 'bg-amber-400' : 'bg-emerald-400')} /></div>
          <div className="mt-3 flex items-center justify-between border-t border-border/70 pt-2"><span className={cn('rounded-md border px-1.5 py-0.5 text-[8px] font-semibold uppercase', sourceClass[binding.source])}>{binding.source}</span><span className="font-mono text-[8px] text-slate-300">{binding.source === 'draft' && dirty ? `${binding.draftVersion} preview` : binding.version}</span></div>
        </>
      ) : null}
    </button>
  )
}

function Canvas({ bindings, run, selectedNode, environment, dirtyAgentIds, onSelect }: { bindings: Record<AgentNodeId, Binding>; run: Run; selectedNode: NodeId; environment: Environment; dirtyAgentIds: Set<string>; onSelect: (node: NodeId) => void }) {
  const active = new Set(run.path)
  const counts = Object.values(bindings).reduce<Record<Source, number>>((acc, item) => ({ ...acc, [item.source]: acc[item.source] + 1 }), { draft: 0, staging: 0, release: 0 })
  return (
    <div className="min-h-0 flex-1 overflow-auto bg-background">
      <div className="relative mx-auto h-[660px] w-[1040px]" style={{ backgroundImage: 'radial-gradient(circle, rgba(100,116,139,.16) 1px, transparent 1px)', backgroundSize: '22px 22px' }}>
        <div className="absolute left-4 top-4 z-30 rounded-xl border border-border bg-surface/90 px-3 py-2 text-[10px] text-muted"><span className="font-medium text-white">Working composition</span> · {counts.draft} Draft · {counts.staging} Staging · {counts.release} Release</div>
        {environment !== 'draft' && <div className="absolute left-1/2 top-4 z-30 -translate-x-1/2 rounded-lg border border-border bg-surface/90 px-3 py-2 text-[9px] text-muted">Read-only exact {environment} snapshot</div>}
        <svg className="absolute inset-0 z-10" width="1040" height="660"><path d="M188 326 C220 326 225 326 254 326" fill="none" stroke="#475569" strokeWidth="2" /><path d="M478 306 C515 306 500 202 540 202" fill="none" stroke="#475569" strokeWidth="2" /><path d="M478 348 C515 348 500 452 540 452" fill="none" stroke="#475569" strokeWidth="2" /><path d="M764 202 C820 202 790 326 852 326" fill="none" stroke="#475569" strokeWidth="2" /><path d="M764 452 C820 452 790 326 852 326" fill="none" stroke="#475569" strokeWidth="2" /></svg>
        <NodeCard id="entry" active={active.has('entry')} selected={selectedNode === 'entry'} className="left-[60px] top-[298px]" onSelect={() => onSelect('entry')} />
        <NodeCard id="coordinator" binding={bindings.coordinator} dirty={dirtyAgentIds.has(bindings.coordinator.agent.id)} active={active.has('coordinator')} selected={selectedNode === 'coordinator'} className="left-[254px] top-[268px]" onSelect={() => onSelect('coordinator')} />
        <NodeCard id="billing" binding={bindings.billing} dirty={dirtyAgentIds.has(bindings.billing.agent.id)} active={active.has('billing')} selected={selectedNode === 'billing'} className="left-[540px] top-[142px]" onSelect={() => onSelect('billing')} />
        <NodeCard id="technical" binding={bindings.technical} dirty={dirtyAgentIds.has(bindings.technical.agent.id)} active={active.has('technical')} selected={selectedNode === 'technical'} className="left-[540px] top-[392px]" onSelect={() => onSelect('technical')} />
        <NodeCard id="end" active={active.has('end')} selected={selectedNode === 'end'} className="left-[852px] top-[298px]" onSelect={() => onSelect('end')} />
        <div className="absolute bottom-4 left-4 z-30 w-80 rounded-xl border border-primary/20 bg-surface/90 p-4"><p className="text-[10px] font-medium text-white">Agent workspace inside the Network</p><p className="mt-1 text-[9px] leading-4 text-muted">Select an Agent to edit the same Draft used by Playground, inspect real Versions and run an isolated test. ENTRY and END open Network configuration.</p></div>
      </div>
    </div>
  )
}

function NetworkChat({ target, bindings, sessionSignature, pinned, onTarget, onNewSession, onPin, onRun }: { target: ChatTarget; bindings: Record<AgentNodeId, Binding>; sessionSignature: string; pinned: boolean; onTarget: (target: ChatTarget) => void; onNewSession: (signature: string) => void; onPin: () => void; onRun: (run: Run) => void }) {
  const [text, setText] = useState('I need help with an invoice that was charged twice.')
  const [messages, setMessages] = useState<Message[]>([
    { role: 'user', content: 'I need help with an invoice that was charged twice.' },
    { role: 'assistant', content: 'I found the invoice and routed the request to Billing Specialist.', path: 'ENTRY → Coordinator → Billing Specialist → END', meta: '2 hops · 1.84s · $0.012' },
  ])
  const currentSignature = signature(target, bindings)
  const changed = currentSignature !== sessionSignature
  const counts = Object.values(bindings).reduce<Record<Source, number>>((acc, item) => ({ ...acc, [item.source]: acc[item.source] + 1 }), { draft: 0, staging: 0, release: 0 })

  const send = () => {
    if (!text.trim()) return
    if (changed && !pinned) return toast.warning('Resolve the session composition before sending')
    const technical = /api|password|error|incident/i.test(text)
    const path: NodeId[] = technical ? ['entry', 'coordinator', 'technical', 'end'] : ['entry', 'coordinator', 'billing', 'end']
    setMessages((items) => [...items, { role: 'user', content: text }, { role: 'assistant', content: technical ? 'Technical Support received the handoff and prepared the diagnostic steps.' : 'Billing Specialist found the matching invoice and reviewed the duplicate charge.', path: technical ? 'ENTRY → Coordinator → Technical Support → END' : 'ENTRY → Coordinator → Billing Specialist → END', meta: pinned ? 'Pinned previous composition' : `${networkLabel(target)} · preview execution` }])
    onRun({ id: 'preview', title: text, environment: target === 'history' ? 'production' : target, status: 'success', duration: '1.62s', cost: '$0.011', path })
    setText('')
  }

  return (
    <div className="flex min-h-0 flex-1 flex-col bg-background">
      <div className="border-b border-border bg-surface/45 p-3">
        <div className="flex items-start gap-3"><div className="flex-1"><p className="text-[9px] font-semibold uppercase tracking-widest text-primary-light">Network Playground</p><p className="mt-1 text-xs font-semibold text-white">Every message starts at ENTRY and executes the complete composition.</p></div><select value={target} onChange={(event) => onTarget(event.target.value as ChatTarget)} className="h-9 rounded-lg border border-border bg-background/70 px-3 text-[10px] text-white"><option value="draft">Draft · working composition</option><option value="staging">Staging · v0.12</option><option value="production">Production · v0.10</option><option value="history">Historical Release · v0.8</option></select></div>
        <div className={cn(surface, 'mt-3 flex flex-wrap items-center gap-2 px-3 py-2')}><Badge tone={target === 'production' ? 'production' : target === 'staging' ? 'staging' : 'default'}>{target}</Badge><span className="text-[10px] font-medium text-white">{networkLabel(target)}</span><span className="text-[9px] text-muted">{counts.draft} Draft · {counts.staging} Staging · {counts.release} Release</span><span className="ml-auto font-mono text-[9px] text-muted">checksum {currentSignature.slice(-8)}</span></div>
        {target === 'draft' && counts.draft > 0 && <div className="mt-2 rounded-lg border border-blue-500/20 bg-blue-500/5 px-3 py-2 text-[9px] text-blue-100/80">Draft Chat can include unsaved Agent overrides. It is internal and unavailable through Runtime Keys.</div>}
        {changed && !pinned && <div className="mt-2 flex items-center gap-3 rounded-xl border border-amber-500/25 bg-amber-500/5 p-3"><AlertTriangle className="h-4 w-4 text-amber-400" /><div className="flex-1"><p className="text-[10px] font-medium text-amber-100">Composition changed during this session</p><p className="text-[9px] text-amber-100/65">Keep the old pinned snapshot or start a clean session.</p></div><button onClick={onPin} className={smallButton}>Keep previous</button><button onClick={() => { onNewSession(currentSignature); setMessages([]) }} className="rounded-lg bg-primary px-2.5 py-1.5 text-[9px] font-semibold text-white">Start new session</button></div>}
        {pinned && <div className="mt-2 rounded-lg border border-border bg-background/40 px-3 py-2 text-[9px] text-muted">This session remains pinned to its previous composition.</div>}
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto p-5"><div className="mx-auto max-w-3xl space-y-4">{messages.map((message, index) => <div key={index} className={cn('max-w-[82%]', message.role === 'user' ? 'ml-auto' : 'mr-auto')}><div className={cn('rounded-2xl px-4 py-3 text-[12px] leading-5', message.role === 'user' ? 'rounded-br-md bg-primary text-white' : 'rounded-bl-md border border-border bg-surface/70 text-slate-200')}>{message.content}</div>{message.path && <div className={cn(surface, 'mt-2 p-2.5')}><p className="text-[9px] text-primary-light">{message.path}</p><p className="mt-1 text-[9px] text-muted">{message.meta}</p></div>}</div>)}</div></div>
      <div className="border-t border-border bg-surface/45 p-4"><div className="mx-auto flex max-w-3xl items-end gap-2"><textarea value={text} onChange={(event) => setText(event.target.value)} className="min-h-20 flex-1 resize-none rounded-xl border border-border bg-background/60 px-3 py-2.5 text-xs text-white" placeholder="Send a message to the Network entry point..." /><button onClick={send} className="flex h-11 w-11 items-center justify-center rounded-xl bg-primary text-white"><Send className="h-4 w-4" /></button></div></div>
    </div>
  )
}

function SecondaryTabs<T extends string>({ value, items, onChange }: { value: T; items: Array<{ id: T; label: string; icon: LucideIcon }>; onChange: (value: T) => void }) {
  return <div className="flex gap-1 border-b border-border/80 bg-surface/60 p-1.5">{items.map(({ id, label, icon: Icon }) => <button key={id} onClick={() => onChange(id)} className={cn('flex flex-1 items-center justify-center gap-1.5 rounded-lg border px-2 py-2 text-[10px] font-medium', value === id ? 'border-primary/30 bg-primary/10 text-primary-light' : 'border-transparent text-muted hover:border-border/70 hover:text-white')}><Icon className="h-3.5 w-3.5" />{label}</button>)}</div>
}

function CompositionVersionCard({ option, selected, readOnly, onUse }: { option: VersionOption; selected: boolean; readOnly: boolean; onUse: () => void }) {
  return (
    <div className={cn(surface, 'p-3', selected && 'border-primary/40 bg-primary/5')}>
      <div className="flex items-start gap-2"><div className="min-w-0 flex-1"><div className="flex items-center gap-2"><span className={cn('rounded-md border px-1.5 py-0.5 text-[8px] font-semibold uppercase', sourceClass[option.source])}>{option.source}</span><span className="font-mono text-[10px] text-white">{option.version}</span></div><p className="mt-2 text-[10px] text-slate-200">{option.note}</p><p className="mt-1 text-[9px] text-muted">{option.created}</p></div>{selected && <CheckCircle2 className="h-4 w-4 text-primary-light" />}</div>
      <div className="mt-3 flex items-center gap-3"><button onClick={() => toast.info(`Viewing ${option.version}`)} className="text-[9px] text-muted hover:text-white">View snapshot</button><button disabled={readOnly || selected} onClick={onUse} className={cn(smallButton, 'ml-auto text-primary-light')}>{selected ? 'Used by Network' : 'Use in Network'}</button></div>
    </div>
  )
}

function NetworkConfiguration({ section, environment, bindings, compositionNode, onSection, onCompositionNode, onUse }: { section: NetworkConfigSection; environment: Environment; bindings: Record<AgentNodeId, Binding>; compositionNode: AgentNodeId; onSection: (section: NetworkConfigSection) => void; onCompositionNode: (node: AgentNodeId) => void; onUse: (node: AgentNodeId, option: VersionOption) => void }) {
  const [source, setSource] = useState<Source>(bindings[compositionNode].source)
  const readOnly = environment !== 'draft'
  const active = bindings[compositionNode]
  const versions = catalog(active)
  const sections: Array<{ id: NetworkConfigSection; label: string; icon: LucideIcon }> = [
    { id: 'general', label: 'General', icon: SlidersHorizontal },
    { id: 'composition', label: 'Composition', icon: GitBranch },
    { id: 'routing', label: 'Routing', icon: Workflow },
    { id: 'runtime', label: 'Runtime', icon: Settings2 },
  ]

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="flex gap-1 overflow-x-auto border-b border-border p-1.5">{sections.map(({ id, label, icon: Icon }) => <button key={id} onClick={() => onSection(id)} className={cn('flex shrink-0 items-center gap-1.5 rounded-lg border px-2.5 py-2 text-[10px] font-medium', section === id ? 'border-primary/30 bg-primary/10 text-primary-light' : 'border-transparent text-muted hover:border-border/70 hover:text-white')}><Icon className="h-3.5 w-3.5" />{label}</button>)}</div>
      <div className="min-h-0 flex-1 overflow-y-auto p-4">
        {readOnly && <div className="mb-4 rounded-xl border border-border bg-background/35 p-3 text-[10px] text-muted">Viewing an exact read-only {environment} snapshot. Switch to Draft to change Network configuration or composition.</div>}
        {section === 'general' && <div className="space-y-4"><label className="block text-[10px] text-muted">Network name<input disabled={readOnly} defaultValue="Customer Support Network" className="mt-1.5 w-full rounded-xl border border-border bg-background/50 px-3 py-2.5 text-xs text-white disabled:opacity-50" /></label><label className="block text-[10px] text-muted">Description<textarea disabled={readOnly} defaultValue="Routes customer requests to billing or technical support specialists." className="mt-1.5 min-h-28 w-full resize-none rounded-xl border border-border bg-background/50 px-3 py-2.5 text-xs leading-5 text-white disabled:opacity-50" /></label><div className={cn(surface, 'p-3')}><p className="text-[9px] uppercase tracking-wide text-muted">Entry point</p><p className="mt-1 text-[10px] text-white">Coordinator</p></div></div>}
        {section === 'composition' && <div><div><p className="text-sm font-semibold text-white">Agent composition</p><p className="mt-1 text-[10px] leading-4 text-muted">Choose the exact Agent source used by each Network node. This control does not edit the Agent.</p></div><div className="mt-4 space-y-2">{(Object.keys(bindings) as AgentNodeId[]).map((node) => { const item = bindings[node]; return <button key={node} onClick={() => { onCompositionNode(node); setSource(item.source) }} className={cn('w-full rounded-xl border p-3 text-left', node === compositionNode ? 'border-primary/35 bg-primary/5' : 'border-border/75 bg-background/30 hover:border-primary/20')}><div className="flex items-center gap-3"><div className="flex h-9 w-9 items-center justify-center rounded-xl border border-primary/20 bg-primary/5 text-primary-light"><Bot className="h-4 w-4" /></div><div className="min-w-0 flex-1"><p className="truncate text-[11px] font-medium text-white">{item.agent.name}</p><p className="mt-1 text-[9px] text-muted">{sourceLabel(item.source)} · <span className="font-mono">{item.version}</span></p></div><span className={cn('rounded-md border px-1.5 py-0.5 text-[8px] font-semibold uppercase', sourceClass[item.source])}>{item.source}</span></div></button> })}</div><div className="mt-5 border-t border-border pt-4"><p className="text-[9px] font-semibold uppercase tracking-wide text-muted">Version used by {active.agent.name}</p><div className="mt-2 grid grid-cols-3 gap-2">{(['draft', 'staging', 'release'] as Source[]).map((item) => <button key={item} onClick={() => setSource(item)} className={cn('rounded-xl border p-3 text-left', source === item ? 'border-primary/35 bg-primary/10' : 'border-border bg-background/35')}><p className="text-[10px] font-semibold capitalize text-white">{item}</p><p className="mt-1 text-[9px] text-muted">{item === 'draft' ? 'Mutable preview' : item === 'staging' ? 'Exact snapshot' : 'Immutable history'}</p></button>)}</div><div className="mt-3 space-y-2">{versions[source].map((option) => <CompositionVersionCard key={option.ref} option={option} selected={active.ref === option.ref} readOnly={readOnly} onUse={() => onUse(compositionNode, option)} />)}</div></div></div>}
        {section === 'routing' && <div className="space-y-4"><div className={cn(surface, 'p-3')}><p className="text-[10px] font-medium text-white">Coordinator → Billing Specialist</p><p className="mt-1 text-[9px] text-muted">Condition: billing, invoice, refund or subscription intent.</p></div><div className={cn(surface, 'p-3')}><p className="text-[10px] font-medium text-white">Coordinator → Technical Support</p><p className="mt-1 text-[9px] text-muted">Condition: API, incident, password or technical error intent.</p></div></div>}
        {section === 'runtime' && <div className="space-y-4"><div className="grid grid-cols-2 gap-2"><button disabled={readOnly} className="rounded-xl border border-primary/35 bg-primary/10 p-3 text-left disabled:opacity-50"><p className="text-[10px] font-medium text-white">Stateful</p><p className="mt-1 text-[9px] text-muted">Persistent Network sessions</p></button><button disabled={readOnly} className="rounded-xl border border-border bg-background/35 p-3 text-left disabled:opacity-50"><p className="text-[10px] font-medium text-white">Stateless</p><p className="mt-1 text-[9px] text-muted">Independent requests</p></button></div><label className="block text-[10px] text-muted">Maximum hops<input disabled={readOnly} defaultValue="8" className="mt-1.5 w-full rounded-xl border border-border bg-background/50 px-3 py-2.5 text-xs text-white disabled:opacity-50" /></label></div>}
      </div>
    </div>
  )
}

function NetworkVersions({ draftBindings, stagingBindings, productionBindings, onStage, onPublish, onRollback, onLoadNetwork }: { draftBindings: Record<AgentNodeId, Binding>; stagingBindings: Record<AgentNodeId, Binding>; productionBindings: Record<AgentNodeId, Binding>; onStage: () => void; onPublish: () => void; onRollback: () => void; onLoadNetwork: () => void }) {
  const count = (items: Record<AgentNodeId, Binding>, type: Source) => Object.values(items).filter((item) => item.source === type).length
  return <div className="min-h-0 flex-1 overflow-y-auto p-4"><div><p className="text-sm font-semibold text-white">Network lifecycle</p><p className="mt-1 text-[10px] leading-4 text-muted">Draft is mutable. Staging and Production preserve exact composition snapshots.</p></div><div className="mt-4 space-y-2"><div className={cn(surface, 'p-3')}><div className="flex justify-between gap-3"><div><p className="text-[9px] uppercase text-muted">Draft Revision 29</p><p className="mt-1 text-[10px] text-white">{count(draftBindings, 'draft')} Draft · {count(draftBindings, 'staging')} Staging · {count(draftBindings, 'release')} Release</p></div><button onClick={onStage} className="rounded-lg bg-primary px-2.5 py-1.5 text-[9px] text-white">Stage</button></div></div><div className="rounded-xl border border-indigo-500/30 bg-indigo-500/5 p-3"><div className="flex justify-between gap-3"><div><p className="text-[9px] uppercase text-indigo-300">Staging v0.12</p><p className="mt-1 text-[10px] text-white">{count(stagingBindings, 'staging')} Staging · {count(stagingBindings, 'release')} Release</p></div><button onClick={onPublish} className={smallButton}>Publish</button></div></div><div className="rounded-xl border border-emerald-500/30 bg-emerald-500/5 p-3"><p className="text-[9px] uppercase text-emerald-300">Production v0.10</p><p className="mt-1 text-[10px] text-white">{count(productionBindings, 'release')} immutable Agent Releases</p></div><div className={cn(surface, 'p-3')}><div className="flex justify-between"><div><p className="font-mono text-[10px] text-white">Historical v0.8</p><p className="mt-1 text-[9px] text-muted">Exact composition preserved</p></div><Badge>Archived</Badge></div><div className="mt-3 flex gap-3"><button onClick={onLoadNetwork} className="text-[9px] text-indigo-300">Load to Draft</button><button onClick={onRollback} className="text-[9px] text-emerald-400">Rollback</button></div></div></div></div>
}

function NetworkInspector({ section, configSection, environment, bindings, draftBindings, stagingBindings, productionBindings, compositionNode, onSection, onConfigSection, onCompositionNode, onUse, onStage, onPublish, onRollback, onLoadNetwork }: { section: NetworkSection; configSection: NetworkConfigSection; environment: Environment; bindings: Record<AgentNodeId, Binding>; draftBindings: Record<AgentNodeId, Binding>; stagingBindings: Record<AgentNodeId, Binding>; productionBindings: Record<AgentNodeId, Binding>; compositionNode: AgentNodeId; onSection: (section: NetworkSection) => void; onConfigSection: (section: NetworkConfigSection) => void; onCompositionNode: (node: AgentNodeId) => void; onUse: (node: AgentNodeId, option: VersionOption) => void; onStage: () => void; onPublish: () => void; onRollback: () => void; onLoadNetwork: () => void }) {
  return <div className="flex min-h-0 flex-1 flex-col"><SecondaryTabs value={section} onChange={onSection} items={[{ id: 'configuration', label: 'Configuration', icon: SlidersHorizontal }, { id: 'versions', label: 'Versions', icon: Rocket }]} />{section === 'configuration' ? <NetworkConfiguration key={compositionNode} section={configSection} environment={environment} bindings={bindings} compositionNode={compositionNode} onSection={onConfigSection} onCompositionNode={onCompositionNode} onUse={onUse} /> : <NetworkVersions draftBindings={draftBindings} stagingBindings={stagingBindings} productionBindings={productionBindings} onStage={onStage} onPublish={onPublish} onRollback={onRollback} onLoadNetwork={onLoadNetwork} />}</div>
}

function Inspector({ context, selectedAgentDraft, selectedNetworkBinding, expanded, onContext, onExpand, agentWorkspace, networkWorkspace }: { context: InspectorContext; selectedAgentDraft: Binding | null; selectedNetworkBinding: Binding | null; expanded: boolean; onContext: (context: InspectorContext) => void; onExpand: () => void; agentWorkspace: ReactNode; networkWorkspace: ReactNode }) {
  return (
    <aside className={cn('absolute inset-y-0 right-0 z-40 flex min-h-0 shrink-0 flex-col border-l border-border bg-surface/95 shadow-2xl shadow-black/30 xl:relative xl:z-auto xl:bg-surface/75 xl:shadow-none', expanded ? 'w-[min(96vw,720px)] xl:w-[720px]' : 'w-[min(94vw,520px)] xl:w-[520px]')}>
      <div className="flex items-center gap-1 border-b border-border bg-background/20 p-1.5">
        <button disabled={!selectedAgentDraft} onClick={() => onContext('agent')} className={cn('flex flex-1 items-center justify-center gap-2 rounded-lg border px-3 py-2 text-[11px] font-medium', context === 'agent' ? 'border-primary/30 bg-primary/10 text-primary-light' : 'border-transparent text-muted hover:border-border/70 hover:text-white', !selectedAgentDraft && 'cursor-not-allowed opacity-40')}><Bot className="h-3.5 w-3.5" />Agent</button>
        <button onClick={() => onContext('network')} className={cn('flex flex-1 items-center justify-center gap-2 rounded-lg border px-3 py-2 text-[11px] font-medium', context === 'network' ? 'border-primary/30 bg-primary/10 text-primary-light' : 'border-transparent text-muted hover:border-border/70 hover:text-white')}><Workflow className="h-3.5 w-3.5" />Network</button>
        <button onClick={onExpand} className="rounded-lg border border-border/80 bg-background/35 p-2 text-muted hover:text-white">{expanded ? <Minimize2 className="h-3.5 w-3.5" /> : <Maximize2 className="h-3.5 w-3.5" />}</button>
      </div>
      <div className="min-h-0 flex-1 overflow-hidden">
        {context === 'agent' ? (selectedAgentDraft && selectedNetworkBinding ? agentWorkspace : <div className="flex h-full items-center justify-center p-6 text-center"><div><Bot className="mx-auto h-7 w-7 text-muted" /><p className="mt-3 text-xs font-medium text-white">Configure an Agent</p><p className="mt-1 max-w-xs text-[10px] leading-4 text-muted">Select an Agent node on the canvas to edit its Draft, inspect Versions and run an isolated test without leaving the Network.</p></div></div>) : networkWorkspace}
      </div>
    </aside>
  )
}

function ApiModal({ open, onClose, bindings }: { open: boolean; onClose: () => void; bindings: { staging: Record<AgentNodeId, Binding>; production: Record<AgentNodeId, Binding> } }) {
  const [environment, setEnvironment] = useState<'staging' | 'production'>('staging')
  if (!open) return null
  const active = bindings[environment]
  const version = environment === 'production' ? 'v0.10.20260710.00' : 'v0.12.20260713.00'
  const curl = `curl -X POST "${API_BASE_URL}/v1/run" \\
  -H "Authorization: Bearer $WOOBE_API_KEY" \\
  -H "Content-Type: application/json" \\
  -d '{"message":"Hello!"}'`

  return <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 p-4 backdrop-blur"><div className="flex h-[82vh] w-full max-w-5xl flex-col overflow-hidden rounded-2xl border border-border bg-surface"><div className="flex items-start border-b border-border p-5"><div><p className="text-[9px] uppercase tracking-widest text-primary-light">Network runtime</p><h2 className="mt-1 text-base font-semibold text-white">API Reference</h2><p className="mt-1 text-[10px] text-muted">Runtime API is available only for Staging and Production.</p></div><button onClick={onClose} className="ml-auto text-muted"><X className="h-4 w-4" /></button></div><div className="grid min-h-0 flex-1 grid-cols-[320px_1fr]"><aside className="overflow-y-auto border-r border-border p-4"><p className="text-[9px] uppercase text-muted">Environment</p><div className="mt-2 grid grid-cols-2 gap-2">{(['staging', 'production'] as const).map((item) => <button key={item} onClick={() => setEnvironment(item)} className={cn('rounded-xl border p-3 text-left', item === environment ? 'border-primary/35 bg-primary/10' : 'border-border bg-background/35')}><p className="text-[10px] font-semibold capitalize text-white">{item}</p><p className="mt-1 font-mono text-[9px] text-muted">{item === 'production' ? 'v0.10' : 'v0.12'}</p></button>)}</div><div className={cn(surface, 'mt-4 p-3')}><p className="text-[9px] uppercase text-muted">Active Network snapshot</p><p className="mt-1 font-mono text-xs text-white">{version}</p></div><p className="mt-4 text-[9px] uppercase text-muted">Composition</p><div className="mt-2 space-y-2">{Object.values(active).map((item) => <div key={item.nodeId} className={cn(surface, 'flex justify-between p-2.5')}><span className="truncate text-[9px] text-white">{item.agent.name}</span><span className="font-mono text-[8px] text-emerald-300">{item.version}</span></div>)}</div><div className="mt-4 rounded-xl border border-primary/20 bg-primary/5 p-3"><div className="flex gap-2"><KeyRound className="h-4 w-4 text-primary-light" /><div><p className="text-[10px] text-white">{environment} Network Key</p><p className="font-mono text-[9px] text-muted">rk_{environment === 'production' ? 'live' : 'stg'}_••••••</p></div></div><p className="mt-2 text-[9px] text-muted">target_type=network · target_id · environment</p></div></aside><section className="overflow-y-auto p-5"><div className={cn(surface, 'flex items-center gap-2 p-3')}><span className="text-[10px] font-semibold text-primary-light">POST</span><code className="text-[10px] text-white">/v1/run</code><button onClick={() => void navigator.clipboard?.writeText('/v1/run')} className="ml-auto text-muted"><Copy className="h-3.5 w-3.5" /></button></div><div className="mt-4 grid grid-cols-2 gap-4"><pre className="rounded-xl border border-border bg-black/20 p-4 text-[10px] text-slate-300">{JSON.stringify({ message: 'Hello!', session_id: '<optional-uuid>' }, null, 2)}</pre><pre className="rounded-xl border border-border bg-black/20 p-4 text-[10px] text-slate-300">{JSON.stringify({ success: true, data: { answer: 'How can I help?', network_release_version: version, composition_checksum: '<sha256>', trace_id: '<uuid>', hops: 2 } }, null, 2)}</pre></div><pre className="mt-4 rounded-xl border border-border bg-black/20 p-4 text-[10px] text-slate-300">{curl}</pre><div className="mt-4 rounded-xl border border-primary/20 bg-primary/5 p-4 text-[10px] leading-4 text-muted">Draft is tested only through the internal Network Chat. Exact Agent versions remain available in Traces for every API execution.</div></section></div></div></div>
}

function ReleaseModal({ action, draftBindings, stagingBindings, onClose, onConfirm }: { action: Exclude<ReleaseAction, null>; draftBindings: Record<AgentNodeId, Binding>; stagingBindings: Record<AgentNodeId, Binding>; onClose: () => void; onConfirm: () => void }) {
  const items = action === 'stage' ? Object.values(draftBindings) : Object.values(stagingBindings)
  const required = items.filter((item) => action === 'stage' ? item.source === 'draft' : item.source === 'staging').length
  const title = action === 'stage' ? 'Stage working composition?' : action === 'publish' ? 'Publish Network Release?' : 'Rollback Network Production?'

  return <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 p-4 backdrop-blur"><div className="w-full max-w-2xl rounded-2xl border border-border bg-surface"><div className="flex border-b border-border p-5"><div><p className="text-[9px] uppercase tracking-widest text-primary-light">{action === 'stage' ? 'Draft → Staging' : action === 'publish' ? 'Staging → Release' : 'Production rollback'}</p><h2 className="mt-1 text-base font-semibold text-white">{title}</h2><p className="mt-1 text-[10px] text-muted">The plan resolves every node to a compatible exact version.</p></div><button onClick={onClose} className="ml-auto text-muted"><X className="h-4 w-4" /></button></div><div className="max-h-[60vh] space-y-2 overflow-y-auto p-5">{action !== 'rollback' && items.map((item) => { const promote = action === 'stage' ? item.source === 'draft' : item.source === 'staging'; return <div key={item.nodeId} className={cn(surface, 'flex items-start gap-3 p-3')}><div className="flex-1"><p className="text-[10px] font-medium text-white">{item.agent.name}</p><p className="mt-1 font-mono text-[9px] text-muted">{sourceLabel(item.source)} · {item.version}</p><p className="mt-2 text-[9px] text-slate-300">{promote ? action === 'stage' ? 'Save Draft and create exact Agent Staging' : 'Create or reuse immutable Agent Release' : `Reuse exact ${sourceLabel(item.source)}`}</p></div><Badge tone={promote ? 'warning' : item.source === 'release' ? 'production' : 'staging'}>{promote ? 'required' : 'reuse'}</Badge></div>})}{action === 'stage' && <div className="rounded-xl border border-primary/20 bg-primary/5 p-4 text-[9px] leading-4 text-muted">Atomic operation: save pending Drafts, promote {required} Agent{required === 1 ? '' : 's'} to Staging, resolve exact snapshot IDs and create Network Staging.</div>}{action === 'publish' && <div className="rounded-xl border border-emerald-500/20 bg-emerald-500/5 p-4 text-[9px] leading-4 text-muted">Create or reuse {required} immutable Agent Release{required === 1 ? '' : 's'}, then pin them in the Network Release. Standalone Agent Production is unchanged.</div>}{action === 'rollback' && <div className="rounded-xl border border-emerald-500/20 bg-emerald-500/5 p-4 text-[9px] leading-4 text-muted">Reactivate historical Network Release v0.8 and every exact Agent Release ID stored in its composition.</div>}</div><div className="flex justify-end gap-2 border-t border-border p-4"><button onClick={onClose} className={smallButton}>Cancel</button><button onClick={onConfirm} className="rounded-lg bg-primary px-3 py-2 text-[10px] font-semibold text-white">{action === 'stage' ? `Stage Network and ${required} Agent${required === 1 ? '' : 's'}` : action === 'publish' ? `Publish Network and ${required} Agent Release${required === 1 ? '' : 's'}` : 'Rollback Network'}</button></div></div></div>
}

function UnsavedAgentSwitchDialog({ agentName, onStay, onDiscard, onSave }: { agentName: string; onStay: () => void; onDiscard: () => void; onSave: () => void }) {
  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center bg-black/75 p-4 backdrop-blur-sm">
      <div className="w-full max-w-lg overflow-hidden rounded-2xl border border-border/90 bg-surface shadow-2xl shadow-black/40">
        <div className="border-b border-border/90 p-5"><div className="flex items-start gap-3"><AlertTriangle className="mt-0.5 h-5 w-5 shrink-0 text-amber-400" /><div><h2 className="text-base font-semibold text-white">Unsaved Agent changes</h2><p className="mt-1 text-xs leading-5 text-muted">{agentName} contains unsaved Draft changes. Save them before switching context, discard them, or remain on this Agent.</p></div></div></div>
        <div className="flex flex-wrap justify-end gap-2 p-4"><button onClick={onStay} className={smallButton}>Stay</button><button onClick={onDiscard} className="rounded-lg border border-red-500/25 bg-red-500/5 px-3 py-2 text-[10px] font-medium text-red-300 hover:bg-red-500/10">Discard and switch</button><button onClick={onSave} className="rounded-lg bg-primary px-3 py-2 text-[10px] font-semibold text-white">Save and switch</button></div>
      </div>
    </div>
  )
}

export default function NetworkPage() {
  const { organizationId, projectId } = useParams<{ organizationId: string; projectId: string }>()
  const navigate = useNavigate()
  const { currentProject } = useWorkspace()
  const agentsQuery = useAgents(projectId)
  const agents = useMemo<[Agent, Agent, Agent]>(() => {
    const source = agentsQuery.data?.length ? agentsQuery.data : fallbackAgents
    return [source[0] ?? fallbackAgents[0], source[1] ?? fallbackAgents[1], source[2] ?? fallbackAgents[2]]
  }, [agentsQuery.data])

  const [environment, setEnvironment] = useState<Environment>('draft')
  const [centerMode, setCenterMode] = useState<CenterMode>('canvas')
  const [chatTarget, setChatTarget] = useState<ChatTarget>('draft')
  const [panelTab, setPanelTab] = useState<PanelTab>('runs')
  const [selectedNode, setSelectedNode] = useState<NodeId>('coordinator')
  const [pendingNode, setPendingNode] = useState<NodeId | null>(null)
  const [compositionNode, setCompositionNode] = useState<AgentNodeId>('coordinator')
  const [inspectorContext, setInspectorContext] = useState<InspectorContext>('agent')
  const [networkSection, setNetworkSection] = useState<NetworkSection>('configuration')
  const [networkConfigSection, setNetworkConfigSection] = useState<NetworkConfigSection>('composition')
  const [expanded, setExpanded] = useState(false)
  const [showApi, setShowApi] = useState(false)
  const [releaseAction, setReleaseAction] = useState<ReleaseAction>(null)
  const [draftState, setDraftState] = useState(() => clone(DRAFT))
  const [stagingState, setStagingState] = useState(() => clone(STAGING))
  const [productionState, setProductionState] = useState(() => clone(PRODUCTION))
  const [dirtyAgentIds, setDirtyAgentIds] = useState<Set<string>>(() => new Set())
  const saveAgentActionRef = useRef<(() => Promise<boolean>) | null>(null)

  const draftBindings = useMemo(() => bind(agents, draftState), [agents, draftState])
  const stagingBindings = useMemo(() => bind(agents, stagingState), [agents, stagingState])
  const productionBindings = useMemo(() => bind(agents, productionState), [agents, productionState])
  const historyBindings = useMemo(() => bind(agents, HISTORY), [agents])
  const visibleBindings = environment === 'draft' ? draftBindings : environment === 'staging' ? stagingBindings : productionBindings
  const chatBindings = chatTarget === 'draft' ? draftBindings : chatTarget === 'staging' ? stagingBindings : chatTarget === 'production' ? productionBindings : historyBindings
  const [run, setRun] = useState<Run>(runHistory[0])
  const [sessionSignature, setSessionSignature] = useState(() => signature('draft', bind(fallbackAgents, DRAFT)))
  const [pinned, setPinned] = useState(false)
  const selectedAgentNode = selectedNode === 'entry' || selectedNode === 'end' ? null : selectedNode
  const selectedAgentDraft = selectedAgentNode ? draftBindings[selectedAgentNode] : null
  const selectedNetworkBinding = selectedAgentNode ? visibleBindings[selectedAgentNode] : null
  const action = environment === 'draft' ? 'stage' : environment === 'staging' ? 'publish' : 'rollback'

  const commitNodeSelection = (node: NodeId) => {
    setSelectedNode(node)
    if (node === 'entry' || node === 'end') {
      setInspectorContext('network')
      setNetworkSection('configuration')
      setNetworkConfigSection(node === 'entry' ? 'general' : 'routing')
      return
    }
    setCompositionNode(node)
    setInspectorContext('agent')
  }

  const selectNode = (node: NodeId) => {
    const currentAgentId = selectedAgentDraft?.agent.id
    const changingAgent = node !== selectedNode
    if (changingAgent && currentAgentId && dirtyAgentIds.has(currentAgentId)) {
      setPendingNode(node)
      return
    }
    commitNodeSelection(node)
  }

  const updateSelectedAgentDirty = (dirty: boolean) => {
    const agentId = selectedAgentDraft?.agent.id
    if (!agentId) return
    setDirtyAgentIds((current) => {
      const next = new Set(current)
      if (dirty) next.add(agentId)
      else next.delete(agentId)
      return next
    })
  }

  const discardAndSwitch = () => {
    if (!pendingNode) return
    const currentAgentId = selectedAgentDraft?.agent.id
    if (currentAgentId) setDirtyAgentIds((current) => { const next = new Set(current); next.delete(currentAgentId); return next })
    const target = pendingNode
    setPendingNode(null)
    commitNodeSelection(target)
  }

  const saveAndSwitch = async () => {
    if (!pendingNode || !saveAgentActionRef.current) return
    const succeeded = await saveAgentActionRef.current()
    if (!succeeded) return
    const target = pendingNode
    setPendingNode(null)
    commitNodeSelection(target)
  }

  const useVersion = (node: AgentNodeId, option: VersionOption) => {
    if (environment !== 'draft') return
    setDraftState((current) => ({ ...current, [node]: { ...current[node], source: option.source, ref: option.ref, version: option.version } }))
    toast.success(`${option.version} selected for this Network node`)
  }

  const stage = () => {
    const next = Object.fromEntries((Object.entries(draftState) as Array<[AgentNodeId, Selection]>).map(([node, item]) => [node, item.source === 'draft' ? { ...item, source: 'staging' as const, ref: `staging-${node}-new`, version: node === 'coordinator' ? 'v0.5.20260713.03' : node === 'billing' ? 'v0.4.20260713.02' : 'v0.3.20260713.01', dirty: false } : { ...item, dirty: false }])) as Record<AgentNodeId, Selection>
    setStagingState(next)
    setEnvironment('staging')
    setChatTarget('staging')
    toast.success('Network and required Agent Drafts promoted to Staging')
  }

  const publish = () => {
    const next = Object.fromEntries((Object.entries(stagingState) as Array<[AgentNodeId, Selection]>).map(([node, item]) => [node, item.source === 'release' ? { ...item } : { ...item, source: 'release' as const, ref: `release-${node}-new`, version: node === 'coordinator' ? 'v0.6.20260713.00' : node === 'billing' ? 'v0.5.20260713.00' : 'v0.4.20260713.00' }])) as Record<AgentNodeId, Selection>
    setProductionState(next)
    setEnvironment('production')
    setChatTarget('production')
    toast.success('Immutable Network Release created')
  }

  const confirmRelease = () => {
    if (releaseAction === 'stage') stage()
    else if (releaseAction === 'publish') publish()
    else {
      setProductionState(clone(HISTORY))
      toast.success('Historical Network Release reactivated')
    }
    setReleaseAction(null)
  }

  const networkBindingSummary: AgentNetworkBindingSummary | null = selectedNetworkBinding
    ? { source: selectedNetworkBinding.source, version: selectedNetworkBinding.version }
    : null

  const agentWorkspace = selectedAgentDraft && networkBindingSummary ? (
    <NetworkAgentWorkspace
      key={selectedAgentDraft.agent.id}
      agent={selectedAgentDraft.agent}
      projectId={projectId!}
      networkBinding={networkBindingSummary}
      onOpenComposition={() => {
        setCompositionNode(selectedAgentDraft.nodeId)
        setInspectorContext('network')
        setNetworkSection('configuration')
        setNetworkConfigSection('composition')
      }}
      onDirtyChange={updateSelectedAgentDirty}
      onRegisterSaveAction={(saveAction) => { saveAgentActionRef.current = saveAction }}
    />
  ) : null

  const networkWorkspace = (
    <NetworkInspector
      section={networkSection}
      configSection={networkConfigSection}
      environment={environment}
      bindings={visibleBindings}
      draftBindings={draftBindings}
      stagingBindings={stagingBindings}
      productionBindings={productionBindings}
      compositionNode={compositionNode}
      onSection={setNetworkSection}
      onConfigSection={setNetworkConfigSection}
      onCompositionNode={(node) => { setCompositionNode(node); setSelectedNode(node) }}
      onUse={useVersion}
      onStage={() => setReleaseAction('stage')}
      onPublish={() => setReleaseAction('publish')}
      onRollback={() => setReleaseAction('rollback')}
      onLoadNetwork={() => { setDraftState(clone(HISTORY)); setEnvironment('draft'); setInspectorContext('network'); setNetworkSection('configuration'); setNetworkConfigSection('composition'); toast.success('Historical Network Release loaded into Draft') }}
    />
  )

  return (
    <div className="flex h-screen min-w-[1180px] flex-col overflow-hidden bg-background">
      <header className="flex h-14 items-center gap-3 border-b border-border bg-surface/80 px-3">
        <button onClick={() => navigate(`/organizations/${organizationId}/projects/${projectId}`)} className="flex h-8 w-8 items-center justify-center rounded-lg border border-border text-muted"><ChevronLeft className="h-4 w-4" /></button>
        <div><div className="flex items-center gap-2"><h1 className="text-sm font-semibold text-white">{currentProject?.name || 'Project'} Network</h1><Badge>Prototype</Badge></div><p className="text-[9px] text-muted">One Network per Project</p></div>
        <div className="ml-auto flex items-center gap-2"><div className="flex rounded-xl border border-border bg-background/35 p-1">{(['draft', 'staging', 'production'] as Environment[]).map((item) => <button key={item} onClick={() => setEnvironment(item)} className={cn('rounded-lg px-3 py-1.5 text-[10px] capitalize', item === environment ? item === 'production' ? 'bg-emerald-500/10 text-emerald-300' : item === 'staging' ? 'bg-indigo-500/10 text-indigo-300' : 'bg-primary/10 text-primary-light' : 'text-muted')}>{item}</button>)}</div><button onClick={() => { setCenterMode('chat'); setChatTarget(environment); setPinned(false) }} className={smallButton}><MessageSquare className="mr-1 inline h-3.5 w-3.5" />Network Chat</button><button onClick={() => setShowApi(true)} className={smallButton}><Code2 className="mr-1 inline h-3.5 w-3.5" />API Reference</button><button onClick={() => setReleaseAction(action)} className="rounded-lg bg-primary px-3 py-2 text-[10px] font-semibold text-white">{environment === 'draft' ? 'Stage Network' : environment === 'staging' ? 'Publish Release' : 'Rollback'}</button></div>
      </header>
      <div className="relative flex h-8 items-center border-b border-border bg-surface/35 px-3 text-[9px] text-muted"><span>Viewing: <b className="text-slate-300">{environment === 'draft' ? 'Working Draft Revision 29' : environment === 'staging' ? 'Network Staging v0.12' : 'Network Release v0.10'}</b> · {environment === 'draft' ? 'Network configuration enabled' : 'exact read-only composition'}</span><div className="absolute left-1/2 flex -translate-x-1/2 rounded-lg border border-border bg-background/45 p-0.5">{([['canvas', Workflow], ['chat', MessageSquare]] as Array<[CenterMode, LucideIcon]>).map(([mode, Icon]) => <button key={mode} onClick={() => setCenterMode(mode)} className={cn('flex items-center gap-1 rounded-md px-2.5 py-1 capitalize', centerMode === mode ? 'bg-primary/10 text-primary-light' : 'text-muted')}><Icon className="h-3 w-3" />{mode}</button>)}</div><span className="ml-auto">Max hops 8 · Timeout 90s</span></div>
      <div className="relative flex min-h-0 flex-1">
        <nav className="flex w-14 flex-col items-center gap-2 border-r border-border bg-surface/75 p-2">{([['runs', Activity], ['trace', GitBranch], ['debug', Bug], ['validation', ListChecks]] as Array<[PanelTab, LucideIcon]>).map(([tab, Icon]) => <button key={tab} onClick={() => setPanelTab(tab)} className={cn('flex h-10 w-10 items-center justify-center rounded-xl border', panelTab === tab ? 'border-primary/35 bg-primary/10 text-primary-light' : 'border-transparent text-muted')}><Icon className="h-4 w-4" /></button>)}<button className="mt-auto flex h-10 w-10 items-center justify-center rounded-xl border border-border text-muted"><Plus className="h-4 w-4" /></button><button className="flex h-10 w-10 items-center justify-center text-muted"><Settings2 className="h-4 w-4" /></button></nav>
        <aside className="hidden w-[330px] border-r border-border bg-surface/65 2xl:block"><Operations tab={panelTab} run={run} draftBindings={draftBindings} /></aside>
        {agentsQuery.isLoading ? <div className="flex flex-1 items-center justify-center text-xs text-muted">Loading Network inventory</div> : centerMode === 'canvas' ? <Canvas bindings={visibleBindings} run={run} selectedNode={selectedNode} environment={environment} dirtyAgentIds={dirtyAgentIds} onSelect={selectNode} /> : <NetworkChat target={chatTarget} bindings={chatBindings} sessionSignature={sessionSignature} pinned={pinned} onTarget={(target) => { setChatTarget(target); setPinned(false) }} onNewSession={(next) => { setSessionSignature(next); setPinned(false); toast.success('New Network session started') }} onPin={() => { setPinned(true); toast.info('Session kept on previous composition') }} onRun={(next) => { setRun(next); setPanelTab('trace') }} />}
        <Inspector context={inspectorContext} selectedAgentDraft={selectedAgentDraft} selectedNetworkBinding={selectedNetworkBinding} expanded={expanded} onContext={setInspectorContext} onExpand={() => setExpanded((value) => !value)} agentWorkspace={agentWorkspace} networkWorkspace={networkWorkspace} />
      </div>
      {showApi && <ApiModal open={showApi} onClose={() => setShowApi(false)} bindings={{ staging: stagingBindings, production: productionBindings }} />}
      {releaseAction && <ReleaseModal action={releaseAction} draftBindings={draftBindings} stagingBindings={stagingBindings} onClose={() => setReleaseAction(null)} onConfirm={confirmRelease} />}
      {pendingNode && selectedAgentDraft && <UnsavedAgentSwitchDialog agentName={selectedAgentDraft.agent.name} onStay={() => setPendingNode(null)} onDiscard={discardAndSwitch} onSave={() => void saveAndSwitch()} />}
    </div>
  )
}
