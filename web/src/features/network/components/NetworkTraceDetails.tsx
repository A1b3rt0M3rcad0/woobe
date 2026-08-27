import { useEffect, useMemo, useState, type ReactNode } from 'react'
import {
  Activity,
  AlertTriangle,
  ArrowLeft,
  Brain,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  CircleDot,
  Copy,
  Database,
  ExternalLink,
  GitBranch,
  Info,
  Play,
  SquareTerminal,
  Wrench,
  XCircle,
} from 'lucide-react'

import { JsonCodeBlock } from '@/components/ui/JsonCodeBlock'
import { AgentRunOperationalView } from '@/features/playground/components/AgentRunOperationalView'
import { ToolCallsCollapsible } from '@/features/playground/components/ToolCallsCollapsible'
import { TraceDetails } from '@/features/playground/components/TraceDetails'
import '@/features/playground/components/trace-details-embedded.css'
import type { TraceItem } from '@/features/playground/types'
import { formatCurrency, formatLatency, formatTokens } from '@/lib/formatters/number'
import { cn } from '@/lib/utils'

import {
  delegationCount,
  invocationCount,
  sourceCount,
  toolCount,
  uniqueAgentCount,
  type NetworkAgentInvocation,
} from './networkChatExecution'
import { NetworkExecutionPath } from './NetworkExecutionPath'
import { NetworkRunDiagnosticsPanel } from './NetworkRunDiagnosticsPanel'
import { NetworkSessionComposition } from './NetworkSessionComposition'
import { NetworkTraceInvocation } from './NetworkTraceTree'
import type { AgentNodeId } from './networkWorkspaceTypes'
import type { NetworkTraceRecord } from './networkObservabilityTypes'
import type { NetworkSession } from './networkSessionTypes'
import {
  findNetworkInvocation,
  networkRunOutcome,
  summarizeInvocationTools,
} from './networkRunInspector'

type InspectorView = 'execution' | 'path' | 'agent' | 'evidence'
type AgentDetailView = 'run' | 'evidence'

function CollapsibleSection({ title, badge, children }: { title: string; badge?: string; children: ReactNode }) {
  const [open, setOpen] = useState(false)
  return (
    <section className="border-t border-border/70 first:border-t-0">
      <button type="button" onClick={() => setOpen((value) => !value)} className="flex w-full items-center gap-2 py-2.5 text-left text-[10px] font-medium text-muted transition-colors hover:text-white" aria-expanded={open}>
        {open ? <ChevronDown className="h-3.5 w-3.5" /> : <ChevronRight className="h-3.5 w-3.5" />}
        <span>{title}</span>
        {badge ? <span className="ml-auto text-[9px] text-muted">{badge}</span> : null}
      </button>
      {open ? <div className="pb-3">{children}</div> : null}
    </section>
  )
}

function CopyableIdRow({ label, value }: { label: string; value: string }) {
  const [copied, setCopied] = useState(false)
  const copy = () => {
    void navigator.clipboard.writeText(value)
    setCopied(true)
    setTimeout(() => setCopied(false), 1200)
  }
  return (
    <div className="grid grid-cols-[86px_minmax(0,1fr)_24px] items-center gap-2 py-1.5">
      <span className="text-[8px] uppercase tracking-wide text-muted">{label}</span>
      <code className="truncate text-[9px] text-slate-300">{value}</code>
      <button type="button" onClick={copy} className="text-muted hover:text-white" aria-label={`Copy ${label}`} title={copied ? 'Copied' : 'Copy'}><Copy className="h-3 w-3" /></button>
    </div>
  )
}

function MetaItem({ label, value }: { label: string; value: string }) {
  return <div className="min-w-0"><p className="text-[8px] uppercase tracking-wide text-muted">{label}</p><p className="mt-0.5 truncate text-[10px] font-medium text-slate-200">{value}</p></div>
}

function OutputPreview({ value, emptyLabel = 'No output was produced.' }: { value: string | null | undefined; emptyLabel?: string }) {
  const [expanded, setExpanded] = useState(false)
  if (!value?.trim()) return <p className="text-[10px] text-muted">{emptyLabel}</p>
  return (
    <div>
      <p className={cn('whitespace-pre-wrap text-[10px] leading-5 text-slate-200', !expanded && 'line-clamp-4')}>{value}</p>
      <button type="button" onClick={() => setExpanded((current) => !current)} className="mt-2 text-[9px] font-medium text-primary-light hover:text-white">
        {expanded ? 'Show less' : 'View full result'}
      </button>
    </div>
  )
}

function outcomeMeta(outcome: ReturnType<typeof networkRunOutcome>) {
  if (outcome === 'running') return { label: 'Running', icon: CircleDot, surface: 'border-blue-500/25 bg-blue-500/10', text: 'text-blue-300' }
  if (outcome === 'failed') return { label: 'Failed', icon: XCircle, surface: 'border-red-500/25 bg-red-500/10', text: 'text-red-300' }
  if (outcome === 'cancelled') return { label: 'Cancelled', icon: XCircle, surface: 'border-slate-500/25 bg-slate-500/10', text: 'text-slate-300' }
  if (outcome === 'completed_with_issues') return { label: 'Completed with issues', icon: AlertTriangle, surface: 'border-amber-500/25 bg-amber-500/10', text: 'text-amber-300' }
  return { label: 'Completed', icon: CheckCircle2, surface: 'border-emerald-500/25 bg-emerald-500/10', text: 'text-emerald-300' }
}

function statusIcon(status: NetworkAgentInvocation['status']) {
  if (status === 'error') return <XCircle className="h-4 w-4 text-red-400" />
  if (status === 'cancelled') return <XCircle className="h-4 w-4 text-slate-400" />
  if (status === 'running' || status === 'pending') return <CircleDot className="h-4 w-4 animate-pulse text-blue-400" />
  return <CheckCircle2 className="h-4 w-4 text-emerald-400" />
}

function traceStatus(status: NetworkAgentInvocation['status']): TraceItem['status'] {
  if (status === 'success') return 'success'
  if (status === 'error') return 'error'
  if (status === 'cancelled') return 'cancelled'
  if (status === 'running') return 'running'
  if (status === 'pending') return 'pending'
  return 'warning'
}

function invocationTraceItem(invocation: NetworkAgentInvocation, projectId: string): TraceItem | null {
  if (!invocation.childTraceId) return null
  return {
    id: invocation.childTraceId,
    title: `${invocation.agentName} Agent Run`,
    timestamp: invocation.startedAt ?? new Date().toISOString(),
    status: traceStatus(invocation.status),
    latency_ms: invocation.durationMs ?? null,
    model: invocation.model ?? null,
    provider: invocation.provider ?? null,
    input_tokens: invocation.usage?.input_tokens ?? null,
    output_tokens: invocation.usage?.output_tokens ?? null,
    total_tokens: invocation.usage?.total_tokens ?? null,
    cost_usd: invocation.costUsd ?? null,
    trace_id: invocation.childTraceId,
    response: null,
    project_id: projectId,
    agent_id: invocation.agentId,
  }
}

function sessionContinuityLabel(invocation: NetworkAgentInvocation) {
  if (invocation.contextState === 'stateless') return 'Stateless invocation'
  if (invocation.contextState === 'created') return 'Stateful session continuity created for this Agent Run'
  if (invocation.previousInvocationCount <= 0) return 'Stateful session continuity reused'
  return `Stateful session continuity reused after ${invocation.previousInvocationCount} invocation${invocation.previousInvocationCount === 1 ? '' : 's'}`
}

function AgentRunDetail({ invocation, root, projectId, onBack, onOpenAgent, onNetworkEvidence }: {
  invocation: NetworkAgentInvocation
  root: NetworkAgentInvocation
  projectId: string
  onBack: () => void
  onOpenAgent: (nodeId: AgentNodeId) => void
  onNetworkEvidence: () => void
}) {
  const [detailView, setDetailView] = useState<AgentDetailView>('run')
  const role = invocation.spanId === root.spanId ? 'Entry Agent' : 'Delegated Agent'
  const tools = summarizeInvocationTools(invocation)
  const evidenceTrace = invocationTraceItem(invocation, projectId)
  const finalizing = invocation.status === 'running' || invocation.status === 'pending'

  useEffect(() => {
    setDetailView('run')
  }, [invocation.spanId])

  return (
    <div className="space-y-4">
      <button type="button" onClick={onBack} className="inline-flex items-center gap-1 text-[9px] font-medium text-muted hover:text-white"><ArrowLeft className="h-3.5 w-3.5" />Execution Path</button>

      <section className="rounded-xl border border-border/75 bg-background/30 p-3">
        <div className="flex items-start gap-3">
          <div className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border border-border bg-surface">{statusIcon(invocation.status)}</div>
          <div className="min-w-0 flex-1">
            <p className="text-[8px] uppercase tracking-wide text-primary-light">{role}</p>
            <h4 className="mt-1 truncate text-[12px] font-semibold text-white">{invocation.agentName}</h4>
            <p className="mt-1 truncate text-[9px] text-muted">{invocation.source} · {invocation.version}</p>
          </div>
          {invocation.nodeId ? <button type="button" onClick={() => onOpenAgent(invocation.nodeId!)} className="inline-flex shrink-0 items-center gap-1 rounded-lg border border-border px-2 py-1.5 text-[9px] text-muted hover:border-primary/30 hover:text-white"><ExternalLink className="h-3 w-3" />Open Agent</button> : null}
        </div>
        <div className="mt-3 grid grid-cols-3 gap-3 border-t border-border/70 pt-3">
          <MetaItem label="Duration" value={invocation.durationMs == null ? 'Running' : formatLatency(invocation.durationMs)} />
          <MetaItem label="Tokens" value={invocation.usage ? `${formatTokens(invocation.usage.input_tokens)} / ${formatTokens(invocation.usage.output_tokens)}` : 'Unknown'} />
          <MetaItem label="Cost" value={invocation.costUsd == null ? 'Unknown' : formatCurrency(invocation.costUsd)} />
        </div>
      </section>

      <nav className="grid grid-cols-2 rounded-lg border border-border/75 bg-background/25 p-1" aria-label="Agent Run detail views">
        <button type="button" onClick={() => setDetailView('run')} className={cn('rounded-md px-2 py-1.5 text-[9px] font-medium', detailView === 'run' ? 'bg-primary/10 text-primary-light' : 'text-muted hover:text-white')}>Run</button>
        <button type="button" onClick={() => setDetailView('evidence')} className={cn('rounded-md px-2 py-1.5 text-[9px] font-medium', detailView === 'evidence' ? 'bg-primary/10 text-primary-light' : 'text-muted hover:text-white')}>Evidence</button>
      </nav>

      {detailView === 'run' ? (
        <div className="overflow-hidden rounded-xl border border-border/75 bg-background/20">
          <AgentRunOperationalView traceId={invocation.childTraceId} runId={invocation.spanId} finalizing={finalizing}>
            <section>
              <p className="text-[8px] uppercase tracking-wide text-muted">Model</p>
              <p className="mt-1 truncate font-mono text-[9px] text-slate-300">{invocation.provider || '—'}/{invocation.model || '—'}</p>
            </section>

            <section className="border-t border-border/70 pt-3">
              <div className="flex items-center gap-2"><p className="text-[9px] font-semibold uppercase tracking-wide text-muted">Session continuity</p><Info className="h-3 w-3 text-muted" aria-label="Session continuity used by this Agent Run" /></div>
              <p className="mt-1 text-[10px] text-slate-300">{sessionContinuityLabel(invocation)}</p>
            </section>

            {invocation.failure ? (
              <section className="rounded-xl border border-red-500/25 bg-red-500/5 p-3">
                <p className="text-[10px] font-medium text-red-300">{invocation.failure.message}</p>
                <p className="mt-1 font-mono text-[9px] text-muted">{invocation.failure.code} · {invocation.failure.stage}</p>
                <button type="button" onClick={() => setDetailView('evidence')} className="mt-2 text-[9px] font-medium text-red-200 hover:text-white">Review Agent Run evidence</button>
              </section>
            ) : null}

            <section className="rounded-xl border border-border/75 bg-background/30 p-3">
              <p className="text-[9px] font-semibold uppercase tracking-wide text-muted">Result</p>
              <div className="mt-2"><OutputPreview value={invocation.output} /></div>
            </section>

            {tools.total ? <ToolCallsCollapsible toolCalls={invocation.tools} variant="network" /> : null}

            {invocation.sources.length ? (
              <CollapsibleSection title="Sources" badge={String(invocation.sources.length)}>
                <div className="space-y-1.5">
                  {invocation.sources.map((source, index) => <div key={source.chunk_id || `${source.document_id || 'source'}-${index}`} className="flex items-start gap-2 rounded-lg bg-background/40 px-2.5 py-2"><Database className="mt-0.5 h-3.5 w-3.5 shrink-0 text-violet-300" /><div className="min-w-0"><p className="truncate text-[10px] text-white">{source.document_title || 'Untitled source'}</p>{source.content_preview ? <p className="mt-1 line-clamp-2 text-[9px] leading-4 text-muted">{source.content_preview}</p> : null}</div></div>)}
                </div>
              </CollapsibleSection>
            ) : null}
          </AgentRunOperationalView>
        </div>
      ) : null}

      {detailView === 'evidence' ? (
        evidenceTrace ? (
          <div className="trace-details-embedded overflow-hidden rounded-xl border border-border/75 bg-background/20">
            <TraceDetails trace={evidenceTrace} onBack={() => setDetailView('run')} />
          </div>
        ) : (
          <section className="rounded-xl border border-dashed border-border/80 px-3 py-3 text-[9px] text-muted">
            Agent Run evidence is unavailable until this invocation has a child Trace.
          </section>
        )
      ) : null}

      <button type="button" onClick={onNetworkEvidence} className="inline-flex items-center gap-1.5 text-[9px] font-medium text-muted hover:text-white"><SquareTerminal className="h-3.5 w-3.5" />View Network evidence</button>
    </div>
  )
}

export function NetworkTraceDetails({ trace, session, onViewCanvas, onOpenAgent }: {
  trace: NetworkTraceRecord
  session: NetworkSession
  onViewCanvas: (trace: NetworkTraceRecord) => void
  onOpenAgent: (nodeId: AgentNodeId) => void
}) {
  const [view, setView] = useState<InspectorView>('execution')
  const [selectedSpanId, setSelectedSpanId] = useState<string | null>(null)
  const agentRuns = invocationCount(trace.execution.root)
  const agents = uniqueAgentCount(trace.execution.root)
  const tools = toolCount(trace.execution.root)
  const sources = sourceCount(trace.execution.root)
  const delegations = delegationCount(trace.execution.root)
  const routeEvents = trace.events.filter((event) => event.type.startsWith('network.route.'))
  const outcome = networkRunOutcome(trace.status, trace.execution.root)
  const meta = outcomeMeta(outcome)
  const OutcomeIcon = meta.icon
  const selectedInvocation = selectedSpanId ? findNetworkInvocation(trace.execution.root, selectedSpanId) : null
  const totalTokens = trace.usage ? trace.usage.total_tokens ?? ((trace.usage.input_tokens ?? 0) + (trace.usage.output_tokens ?? 0)) : null
  const technicalIds = useMemo<Array<readonly [string, string]>>(() => {
    const ids: Array<readonly [string, string]> = [
      ['network session', trace.networkSessionId],
      ['network', session.networkId],
      ['project', session.projectId],
    ]
    if (trace.traceId) ids.unshift(['trace', trace.traceId])
    return ids
  }, [session.networkId, session.projectId, trace.networkSessionId, trace.traceId])

  useEffect(() => {
    setView('execution')
    setSelectedSpanId(null)
  }, [trace.id])

  const openInvocation = (invocation: NetworkAgentInvocation) => {
    setSelectedSpanId(invocation.spanId)
    setView('agent')
  }

  return (
    <div className="min-h-full">
      <header className="border-b border-border/80 p-4">
        <div className="flex items-start gap-3">
          <div className={cn('flex h-9 w-9 shrink-0 items-center justify-center rounded-xl border', meta.surface)}><OutcomeIcon className={cn('h-4 w-4', meta.text, outcome === 'running' && 'animate-pulse')} /></div>
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-2"><h3 className="truncate text-[12px] font-semibold text-white">{trace.execution.root.agentName}</h3><span className={cn('rounded-full border px-2 py-0.5 text-[8px] font-medium', meta.surface, meta.text)}>{meta.label}</span></div>
            <p className="mt-1 truncate text-[9px] text-muted">Network Run · {trace.environment} · {trace.networkVersion}</p>
          </div>
          <button type="button" onClick={() => onViewCanvas(trace)} className="inline-flex shrink-0 items-center gap-1 rounded-lg border border-primary/25 bg-primary/10 px-2 py-1.5 text-[9px] text-primary-light hover:text-white"><Play className="h-3 w-3" />Canvas</button>
        </div>
        <div className="mt-3 grid grid-cols-6 gap-2 border-t border-border/70 pt-3">
          <MetaItem label="Duration" value={formatLatency(trace.durationMs)} />
          <MetaItem label="Agent Runs" value={String(agentRuns)} />
          <MetaItem label="Agents" value={String(agents)} />
          <MetaItem label="Tools" value={String(tools)} />
          <MetaItem label="Tokens" value={totalTokens == null ? 'Unknown' : formatTokens(totalTokens)} />
          <MetaItem label="Cost" value={trace.costUsd == null ? 'Unknown' : formatCurrency(trace.costUsd)} />
        </div>
      </header>

      <nav className="grid grid-cols-3 border-b border-border/80 bg-background/20 p-1.5" aria-label="Network Run inspector views">
        {([
          ['execution', Activity, 'Execution'],
          ['path', GitBranch, 'Path'],
          ['evidence', SquareTerminal, 'Evidence'],
        ] as const).map(([target, Icon, label]) => {
          const active = view === target || (view === 'agent' && target === 'path')
          return <button key={target} type="button" onClick={() => setView(target)} className={cn('flex items-center justify-center gap-1.5 rounded-lg px-2 py-1.5 text-[9px] font-medium', active ? 'bg-primary/10 text-primary-light' : 'text-muted hover:text-white')}><Icon className="h-3.5 w-3.5" />{label}</button>
        })}
      </nav>

      <div className="space-y-4 p-4">
        {view === 'execution' ? (
          <>
            <NetworkRunDiagnosticsPanel executionId={trace.id} projectId={session.projectId} running={trace.status === 'running'} mode="execution" />

            {trace.execution.root.failure ? (
              <section className="rounded-xl border border-red-500/25 bg-red-500/5 p-3">
                <p className="text-[10px] font-medium text-red-300">{trace.execution.root.failure.message}</p>
                {trace.execution.root.failure.partialResultAvailable || Boolean(trace.answer?.trim()) ? <p className="mt-1 text-[9px] text-muted">A partial result and completed Agent/Tool evidence remain available.</p> : null}
                <div className="mt-2 flex gap-3">
                  <button type="button" onClick={() => setView('path')} className="text-[9px] font-medium text-red-200 hover:text-white">Review execution path</button>
                  <button type="button" onClick={() => setView('evidence')} className="text-[9px] font-medium text-red-200 hover:text-white">Review failure evidence</button>
                </div>
              </section>
            ) : outcome === 'cancelled' ? (
              <section className="rounded-xl border border-slate-500/25 bg-slate-500/5 p-3">
                <p className="text-[10px] font-medium text-slate-200">The Network Run was cancelled. Partial output and completed execution evidence remain available.</p>
              </section>
            ) : outcome === 'completed_with_issues' ? (
              <section className="rounded-xl border border-amber-500/25 bg-amber-500/5 p-3">
                <p className="text-[10px] font-medium text-amber-200">The Network completed with a usable result, but at least one delegated Agent Run reported an issue.</p>
                <button type="button" onClick={() => setView('path')} className="mt-2 text-[9px] font-medium text-amber-100 hover:text-white">Review execution path</button>
              </section>
            ) : null}

            <section>
              <p className="text-[8px] font-semibold uppercase tracking-wide text-muted">Request</p>
              <p className="mt-1 line-clamp-2 text-[10px] leading-5 text-slate-300">{trace.userMessage}</p>
            </section>

            <section className="rounded-xl border border-border/75 bg-background/30 p-3">
              <p className="text-[9px] font-semibold uppercase tracking-wide text-muted">Result</p>
              <div className="mt-2"><OutputPreview value={trace.answer} emptyLabel={outcome === 'running' ? 'The final response is still being generated.' : outcome === 'cancelled' ? 'The Run was cancelled before a final response was produced.' : 'The Run ended without a final response.'} /></div>
            </section>

            <section className="rounded-xl border border-border/75 bg-background/30 p-3">
              <p className="text-[9px] font-semibold uppercase tracking-wide text-muted">Activity</p>
              <div className="mt-2 grid grid-cols-4 gap-3"><MetaItem label="Agent Runs" value={String(agentRuns)} /><MetaItem label="Delegations" value={String(delegations)} /><MetaItem label="Tools" value={`${tools} calls`} /><MetaItem label="Events" value={String(trace.events.length)} /></div>
            </section>

            <section className="space-y-3 border-t border-border/70 pt-4">
              <div className="flex items-start gap-2">
                <Brain className="mt-0.5 h-3.5 w-3.5 text-muted" />
                <div>
                  <p className="text-[9px] font-semibold uppercase tracking-wide text-muted">Network Context</p>
                  <p className="mt-1 text-[9px] leading-4 text-muted">Aggregated from the actual Model Invocations executed by child Agent Runs.</p>
                </div>
              </div>
              <NetworkRunDiagnosticsPanel executionId={trace.id} projectId={session.projectId} running={trace.status === 'running'} mode="context" />
              <p className="rounded-lg border border-border/75 bg-background/25 px-3 py-2 text-[9px] leading-4 text-muted">Open Path to inspect an individual Agent Run, then return directly to the Network execution path without losing this Run context.</p>
            </section>
          </>
        ) : null}

        {view === 'path' ? (
          <>
            <div>
              <div className="flex items-center gap-2"><p className="text-[9px] font-semibold uppercase tracking-wide text-muted">Execution Path</p><Info className="h-3 w-3 text-muted" aria-label="Select an Agent Run to inspect it without leaving the Network Run" /></div>
              <p className="mt-1 text-[9px] leading-4 text-muted">{agentRuns} Agent Run{agentRuns === 1 ? '' : 's'} across {agents} Agent{agents === 1 ? '' : 's'} · {delegations} delegation{delegations === 1 ? '' : 's'}. Select any invocation to drill into its Run and Evidence.</p>
            </div>
            <section className="rounded-xl border border-border/75 bg-background/30 p-3">
              <NetworkExecutionPath root={trace.execution.root} selectedSpanId={selectedSpanId} onSelect={openInvocation} />
            </section>
          </>
        ) : null}

        {view === 'agent' && selectedInvocation ? <AgentRunDetail invocation={selectedInvocation} root={trace.execution.root} projectId={session.projectId} onBack={() => setView('path')} onOpenAgent={onOpenAgent} onNetworkEvidence={() => setView('evidence')} /> : null}

        {view === 'evidence' ? (
          <>
            <div><div className="flex items-center gap-2"><p className="text-[9px] font-semibold uppercase tracking-wide text-muted">Evidence</p><Info className="h-3 w-3 text-muted" aria-label="Trace events, Session continuity and raw runtime data" /></div><p className="mt-1 text-[9px] leading-4 text-muted">Technical and causal evidence is preserved here and stays out of the operational Execution view until needed.</p></div>

            {trace.execution.root.failure ? <section className="rounded-xl border border-red-500/25 bg-red-500/5 p-3"><p className="text-[10px] font-medium text-red-300">{trace.execution.root.failure.message}</p><p className="mt-1 font-mono text-[9px] text-muted">{trace.execution.root.failure.code} · {trace.execution.root.failure.stage}{trace.execution.root.failure.phase ? ` · ${trace.execution.root.failure.phase}` : ''}</p></section> : null}

            <div className="rounded-xl border border-border/75 bg-background/30 px-3">
              <CollapsibleSection title="Execution evidence" badge={`${agentRuns} Agent Runs`}><NetworkTraceInvocation invocation={trace.execution.root} trace={trace} depth={0} onOpenAgent={onOpenAgent} /></CollapsibleSection>
              <CollapsibleSection title="Routing" badge={String(routeEvents.length)}><div className="space-y-2">{routeEvents.length ? routeEvents.map((event) => <div key={event.id} className="rounded-lg bg-background/45 p-2.5"><div className="flex items-center gap-1.5"><GitBranch className="h-3.5 w-3.5 text-primary-light" /><code className="text-[9px] text-white">{event.type}</code></div><p className="mt-1 text-[9px] text-muted">{event.label}</p><JsonCodeBlock value={event.payload} maxHeight={128} className="mt-2" /></div>) : <p className="text-[9px] text-muted">No routing decisions were recorded.</p>}</div></CollapsibleSection>
              {trace.parsedOutput ? <CollapsibleSection title="Structured output"><JsonCodeBlock value={trace.parsedOutput} maxHeight={180} /></CollapsibleSection> : null}
              <CollapsibleSection title="Session composition" badge={`${trace.agentContexts.length} contexts`}><NetworkSessionComposition contexts={trace.agentContexts} /></CollapsibleSection>
              <CollapsibleSection title="Composition snapshot"><JsonCodeBlock value={{ environment: trace.environment, network_version: trace.networkVersion, composition_hash: trace.compositionHash, agents: trace.agentContexts.map((context) => ({ node_id: context.nodeId, agent_id: context.agentId, source: context.source, version: context.version, session_mode: context.sessionMode })) }} maxHeight={220} /></CollapsibleSection>
              <CollapsibleSection title="Events" badge={String(trace.events.length)}><div className="space-y-1.5">{trace.events.map((event) => <div key={event.id} className="rounded-lg bg-background/45 px-3 py-2"><div className="flex items-center justify-between gap-2"><code className="truncate text-[9px] text-white">{event.type}</code><span className="text-[8px] text-muted">#{event.sequence}</span></div><p className="mt-1 text-[9px] text-muted">{event.label}</p><JsonCodeBlock value={event.payload} maxHeight={112} className="mt-2" /></div>)}</div></CollapsibleSection>
              <CollapsibleSection title="Raw"><JsonCodeBlock value={trace} maxHeight={300} /></CollapsibleSection>
              <CollapsibleSection title="Technical identifiers" badge={`${technicalIds.length} IDs`}>
                <div className="divide-y divide-border/60">{technicalIds.map(([label, value]) => <CopyableIdRow key={label} label={label} value={value} />)}</div>
                <button type="button" onClick={() => void navigator.clipboard.writeText(technicalIds.map(([label, value]) => `${label}: ${value}`).join('\n'))} className="mt-2 inline-flex items-center gap-1.5 text-[9px] font-medium text-muted hover:text-white"><Copy className="h-3 w-3" />Copy all identifiers</button>
              </CollapsibleSection>
            </div>

            <div className="flex items-center justify-between text-[9px] text-muted"><span className="inline-flex items-center gap-1"><Wrench className="h-3 w-3" />{tools} Tool Calls</span><span className="inline-flex items-center gap-1"><Database className="h-3 w-3" />{sources} Sources</span><span className="inline-flex items-center gap-1"><Activity className="h-3 w-3" />{trace.events.length} Events</span></div>
          </>
        ) : null}
      </div>
    </div>
  )
}
