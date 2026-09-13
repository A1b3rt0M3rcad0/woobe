import { operationEventLabel } from '@/features/skills/operations'
import { useEffect, useMemo, useState, type ReactNode } from 'react'
import {
  Activity,
  AlertTriangle,
  ArrowLeft,
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
import { AgentResultViewer } from '@/features/playground/components/AgentResultViewer'
import { AgentRunEvidencePanel } from '@/features/playground/components/AgentRunEvidencePanel'
import { AgentRunOperationalView } from '@/features/playground/components/AgentRunOperationalView'
import { ToolCallsCollapsible } from '@/features/playground/components/ToolCallsCollapsible'
import { formatCurrency, formatLatency, formatTokens } from '@/lib/formatters/number'
import { cn } from '@/lib/utils'

import {
  delegationCount,
  invocationCount,
  sourceCount,
  toolCount,
  skillCount,
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

interface DelegationEvidence {
  id: string
  parent: string
  child: string
  childSpanId: string
  status: NetworkAgentInvocation['status']
  source: string
  version: string
}

function CollapsibleSection({ title, badge, children }: { title: string; badge?: string; children: ReactNode }) {
  const [open, setOpen] = useState(false)
  return (
    <section className="border-t border-border/70 first:border-t-0">
      <button type="button" onClick={() => setOpen((value) => !value)} className="flex w-full items-center gap-ui-sm py-ui-sm text-left font-mono text-system-label font-medium text-muted-foreground transition-colors hover:text-white" aria-expanded={open}>
        {open ? <ChevronDown className="h-3.5 w-3.5" /> : <ChevronRight className="h-3.5 w-3.5" />}
        <span>{title}</span>
        {badge ? <span className="ml-auto text-system-meta text-muted-foreground">{badge}</span> : null}
      </button>
      {open ? <div className="pb-ui-md">{children}</div> : null}
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
    <div className="grid grid-cols-[86px_minmax(0,1fr)_24px] items-center gap-ui-sm py-ui-xs">
      <span className="font-mono text-system-nano uppercase tracking-ui-label text-muted-foreground">{label}</span>
      <code className="truncate font-mono text-system-meta text-slate-300">{value}</code>
      <button type="button" onClick={copy} className="text-muted-foreground transition-colors hover:text-white" aria-label={`Copy ${label}`} title={copied ? 'Copied' : 'Copy'}><Copy className="h-3 w-3" /></button>
    </div>
  )
}

function MetaItem({ label, value }: { label: string; value: string }) {
  return <div className="min-w-0"><p className="font-mono text-system-meta uppercase tracking-ui-label text-muted-foreground">{label}</p><p className="mt-ui-hairline truncate font-sans text-product-caption font-medium text-slate-200">{value}</p></div>
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

function compactStatusIcon(status: NetworkAgentInvocation['status']) {
  if (status === 'error') return <XCircle className="h-3.5 w-3.5 shrink-0 text-red-400" />
  if (status === 'cancelled') return <XCircle className="h-3.5 w-3.5 shrink-0 text-slate-400" />
  if (status === 'running' || status === 'pending') return <CircleDot className="h-3.5 w-3.5 shrink-0 animate-pulse text-blue-400" />
  return <CheckCircle2 className="h-3.5 w-3.5 shrink-0 text-emerald-400" />
}

function delegationEvidence(root: NetworkAgentInvocation): DelegationEvidence[] {
  const rows: DelegationEvidence[] = []
  const visit = (parent: NetworkAgentInvocation) => {
    parent.children.forEach((child) => {
      rows.push({
        id: `${parent.spanId}:${child.spanId}`,
        parent: parent.agentName,
        child: child.agentName,
        childSpanId: child.spanId,
        status: child.status,
        source: child.source,
        version: child.version,
      })
      visit(child)
    })
  }
  visit(root)
  return rows
}

function sessionContinuityLabel(invocation: NetworkAgentInvocation) {
  if (invocation.contextState === 'stateless') return 'Stateless invocation'
  if (invocation.contextState === 'created') return 'Stateful session continuity created for this Agent Run'
  if (invocation.previousInvocationCount <= 0) return 'Stateful session continuity reused'
  return `Stateful session continuity reused after ${invocation.previousInvocationCount} invocation${invocation.previousInvocationCount === 1 ? '' : 's'}`
}

function AgentRunDetail({ invocation, root, onBack, onOpenAgent, onNetworkEvidence }: {
  invocation: NetworkAgentInvocation
  root: NetworkAgentInvocation
  onBack: () => void
  onOpenAgent: (nodeId: AgentNodeId) => void
  onNetworkEvidence: () => void
}) {
  const [detailView, setDetailView] = useState<AgentDetailView>('run')
  const role = invocation.spanId === root.spanId ? 'Entry Agent' : 'Delegated Agent'
  const tools = summarizeInvocationTools(invocation)
  const finalizing = invocation.status === 'running' || invocation.status === 'pending'

  useEffect(() => setDetailView('run'), [invocation.spanId])

  return (
    <div className="space-y-ui-md">
      <button type="button" onClick={onBack} className="inline-flex items-center gap-ui-xs font-mono text-system-micro font-medium text-muted-foreground transition-colors hover:text-white"><ArrowLeft className="h-3.5 w-3.5" />Execution Path</button>

      <section className="rounded-container border border-border/75 bg-background/30 p-ui-md">
        <div className="flex items-start gap-ui-md">
          <div className="mt-ui-hairline flex h-control-sm w-control-sm shrink-0 items-center justify-center rounded-control border border-border bg-surface">{statusIcon(invocation.status)}</div>
          <div className="min-w-0 flex-1">
            <p className="font-mono text-system-meta uppercase tracking-ui-label text-primary-light">{role}</p>
            <h4 className="mt-ui-xs truncate font-sans text-product-small font-semibold text-white">{invocation.agentName}</h4>
            <p className="mt-ui-xs truncate font-mono text-system-meta text-muted-foreground">{invocation.source} · {invocation.version}</p>
          </div>
          {invocation.nodeId ? <button type="button" onClick={() => onOpenAgent(invocation.nodeId!)} className="inline-flex h-control-segment shrink-0 items-center gap-ui-xs rounded-control border border-border px-ui-sm font-mono text-system-micro text-muted-foreground transition-colors hover:border-primary/30 hover:text-white"><ExternalLink className="h-3 w-3" />Open Agent</button> : null}
        </div>
        <div className="mt-ui-md grid grid-cols-3 gap-ui-md border-t border-border/70 pt-ui-md">
          <MetaItem label="Duration" value={invocation.durationMs == null ? 'Running' : formatLatency(invocation.durationMs)} />
          <MetaItem label="Tokens" value={invocation.usage ? `${formatTokens(invocation.usage.input_tokens)} / ${formatTokens(invocation.usage.output_tokens)}` : 'Unknown'} />
          <MetaItem label="Cost" value={invocation.costUsd == null ? 'Unknown' : formatCurrency(invocation.costUsd)} />
        </div>
      </section>

      <nav className="grid grid-cols-2 rounded-control border border-border/75 bg-background/25 p-ui-hairline" aria-label="Agent Run detail views">
        <button type="button" onClick={() => setDetailView('run')} className={cn('rounded-technical px-ui-sm py-ui-xs font-mono text-system-micro font-medium', detailView === 'run' ? 'bg-primary/10 text-primary-light' : 'text-muted-foreground hover:text-white')}>Run</button>
        <button type="button" onClick={() => setDetailView('evidence')} className={cn('rounded-technical px-ui-sm py-ui-xs font-mono text-system-micro font-medium', detailView === 'evidence' ? 'bg-primary/10 text-primary-light' : 'text-muted-foreground hover:text-white')}>Evidence</button>
      </nav>

      {detailView === 'run' ? (
        <div className="overflow-hidden rounded-container border border-border/75 bg-background/20">
          <AgentRunOperationalView
            traceId={invocation.childTraceId}
            runId={invocation.runId}
            finalizing={finalizing}
            resultTitle={`${invocation.agentName} result`}
            resultSubtitle={`${role} · ${invocation.source} ${invocation.version}`}
          >
            <section>
              <p className="font-mono text-system-meta uppercase tracking-ui-label text-muted-foreground">Model</p>
              <p className="mt-ui-xs truncate font-mono text-system-meta text-slate-300">{invocation.provider || '—'}/{invocation.model || '—'}</p>
            </section>

            <section className="border-t border-border/70 pt-ui-md">
              <div className="flex items-center gap-ui-sm"><p className="font-mono text-system-meta font-semibold uppercase tracking-ui-label text-muted-foreground">Session continuity</p><Info className="h-3 w-3 text-muted-foreground" aria-label="Session continuity used by this Agent Run" /></div>
              <p className="mt-ui-xs font-sans text-product-caption text-slate-300">{sessionContinuityLabel(invocation)}</p>
            </section>

            {invocation.failure ? (
              <section className="rounded-container border border-red-500/25 bg-red-500/5 p-ui-md">
                <p className="font-sans text-product-caption font-medium text-red-300">{invocation.failure.message}</p>
                <p className="mt-ui-xs font-mono text-system-meta text-muted-foreground">{invocation.failure.code} · {invocation.failure.stage}</p>
                <button type="button" onClick={() => setDetailView('evidence')} className="mt-ui-sm font-mono text-system-micro font-medium text-red-200 transition-colors hover:text-white">Review Agent Run evidence</button>
              </section>
            ) : null}

            {tools.total ? <ToolCallsCollapsible toolCalls={invocation.tools} variant="network" /> : null}

            {invocation.sources.length ? (
              <CollapsibleSection title="Sources" badge={String(invocation.sources.length)}>
                <div className="space-y-ui-sm">
                  {invocation.sources.map((source, index) => <div key={source.chunk_id || `${source.document_id || 'source'}-${index}`} className="flex items-start gap-ui-sm rounded-control bg-background/40 px-ui-sm py-ui-sm"><Database className="mt-ui-hairline h-3.5 w-3.5 shrink-0 text-violet-300" /><div className="min-w-0"><p className="truncate font-sans text-product-caption text-white">{source.document_title || 'Untitled source'}</p>{source.content_preview ? <p className="mt-ui-xs line-clamp-2 font-sans text-product-caption leading-4 text-muted-foreground">{source.content_preview}</p> : null}</div></div>)}
                </div>
              </CollapsibleSection>
            ) : null}
          </AgentRunOperationalView>
        </div>
      ) : null}

      {detailView === 'evidence' ? <AgentRunEvidencePanel runId={invocation.runId} traceId={invocation.childTraceId} /> : null}

      <button type="button" onClick={onNetworkEvidence} className="inline-flex items-center gap-ui-xs font-mono text-system-micro font-medium text-muted-foreground transition-colors hover:text-white"><SquareTerminal className="h-3.5 w-3.5" />View Network evidence</button>
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
  const skills = skillCount(trace.execution.root)
  const sources = sourceCount(trace.execution.root)
  const delegations = delegationCount(trace.execution.root)
  const delegationRows = useMemo(() => delegationEvidence(trace.execution.root), [trace.execution.root])
  const routeEvents = trace.events.filter((event) => event.type.startsWith('network.route.'))
  const outcome = networkRunOutcome(trace.status, trace.execution.root)
  const meta = outcomeMeta(outcome)
  const OutcomeIcon = meta.icon
  const selectedInvocation = selectedSpanId ? findNetworkInvocation(trace.execution.root, selectedSpanId) : null
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
      <header className="border-b border-border/80 p-ui-md">
        <div className="flex items-start gap-ui-md">
          <div className={cn('flex h-control w-control shrink-0 items-center justify-center rounded-control border', meta.surface)}><OutcomeIcon className={cn('h-4 w-4', meta.text, outcome === 'running' && 'animate-pulse')} /></div>
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-ui-sm"><h3 className="truncate font-sans text-product-small font-semibold text-white">{trace.execution.root.agentName}</h3><span className={cn('rounded-technical border px-ui-sm py-ui-hairline font-mono text-system-meta font-medium', meta.surface, meta.text)}>{meta.label}</span></div>
            <p className="mt-ui-xs truncate font-mono text-system-meta text-muted-foreground">Network Run · {trace.environment} · {trace.networkVersion}</p>
          </div>
          <button type="button" onClick={() => onViewCanvas(trace)} className="inline-flex h-control-segment shrink-0 items-center gap-ui-xs rounded-control border border-primary/25 bg-primary/10 px-ui-sm font-mono text-system-micro text-primary-light transition-colors hover:text-white"><Play className="h-3 w-3" />Canvas</button>
        </div>
      </header>

      <nav className="grid grid-cols-3 border-b border-border/80 bg-background/20 p-ui-xs" aria-label="Network Run inspector views">
        {([
          ['execution', Activity, 'Execution'],
          ['path', GitBranch, 'Path'],
          ['evidence', SquareTerminal, 'Evidence'],
        ] as const).map(([target, Icon, label]) => {
          const active = view === target || (view === 'agent' && target === 'path')
          return <button key={target} type="button" onClick={() => setView(target)} className={cn('flex items-center justify-center gap-ui-xs rounded-control px-ui-sm py-ui-xs font-mono text-system-micro font-medium', active ? 'bg-primary/10 text-primary-light' : 'text-muted-foreground hover:text-white')}><Icon className="h-3.5 w-3.5" />{label}</button>
        })}
      </nav>

      <div className="space-y-ui-md p-ui-md">
        {view === 'execution' ? (
          <>
            <NetworkRunDiagnosticsPanel
              executionId={trace.id}
              projectId={session.projectId}
              running={trace.status === 'running'}
              root={trace.execution.root}
              onOpenAgentRun={openInvocation}
            />

            {trace.execution.root.failure ? (
              <section className="rounded-container border border-red-500/25 bg-red-500/5 p-ui-md">
                <p className="font-sans text-product-caption font-medium text-red-300">{trace.execution.root.failure.message}</p>
                {trace.execution.root.failure.partialResultAvailable || Boolean(trace.answer?.trim()) ? <p className="mt-ui-xs font-sans text-product-caption text-muted-foreground">A partial result and completed Agent/Tool evidence remain available.</p> : null}
                <div className="mt-ui-sm flex gap-ui-md"><button type="button" onClick={() => setView('path')} className="font-mono text-system-micro font-medium text-red-200 transition-colors hover:text-white">Review execution path</button><button type="button" onClick={() => setView('evidence')} className="font-mono text-system-micro font-medium text-red-200 transition-colors hover:text-white">Review failure evidence</button></div>
              </section>
            ) : outcome === 'cancelled' ? (
              <section className="rounded-container border border-slate-500/25 bg-slate-500/5 p-ui-md"><p className="font-sans text-product-caption font-medium text-slate-200">The Network Run was cancelled. Partial output and completed execution evidence remain available.</p></section>
            ) : outcome === 'completed_with_issues' ? (
              <section className="rounded-container border border-amber-500/25 bg-amber-500/5 p-ui-md"><p className="font-sans text-product-caption font-medium text-amber-200">The Network completed with a usable result, but at least one delegated Agent Run reported an issue.</p><button type="button" onClick={() => setView('path')} className="mt-ui-sm font-mono text-system-micro font-medium text-amber-100 transition-colors hover:text-white">Review execution path</button></section>
            ) : null}

            <section><p className="font-mono text-system-meta font-semibold uppercase tracking-ui-label text-muted-foreground">Request</p><p className="mt-ui-xs line-clamp-2 font-sans text-product-caption leading-5 text-slate-300">{trace.userMessage}</p></section>

            <section className="rounded-container border border-border/75 bg-background/30 p-ui-md">
              <p className="font-mono text-system-label font-semibold uppercase tracking-ui-label text-muted-foreground">Result</p>
              <div className="mt-ui-sm"><AgentResultViewer value={trace.answer} title="Network result" subtitle={`${trace.environment} · ${trace.networkVersion}`} compact emptyLabel={outcome === 'running' ? 'The final response is still being generated.' : outcome === 'cancelled' ? 'The Run was cancelled before a final response was produced.' : 'The Run ended without a final response.'} /></div>
            </section>
          </>
        ) : null}

        {view === 'path' ? (
          <>
            <div><div className="flex items-center gap-ui-sm"><p className="font-mono text-system-label font-semibold uppercase tracking-ui-label text-muted-foreground">Execution Path</p><Info className="h-3 w-3 text-muted-foreground" aria-label="Select an Agent Run to inspect it without leaving the Network Run" /></div><p className="mt-ui-xs font-sans text-product-caption leading-4 text-muted-foreground">{agentRuns} Agent Run{agentRuns === 1 ? '' : 's'} across {agents} Agent{agents === 1 ? '' : 's'} · {delegations} delegation{delegations === 1 ? '' : 's'}. Select any invocation to drill into its Run and Evidence.</p></div>
            <section className="rounded-container border border-border/75 bg-background/30 p-ui-md"><NetworkExecutionPath root={trace.execution.root} selectedSpanId={selectedSpanId} onSelect={openInvocation} /></section>
          </>
        ) : null}

        {view === 'agent' && selectedInvocation ? <AgentRunDetail invocation={selectedInvocation} root={trace.execution.root} onBack={() => setView('path')} onOpenAgent={onOpenAgent} onNetworkEvidence={() => setView('evidence')} /> : null}

        {view === 'evidence' ? (
          <>
            <div><div className="flex items-center gap-ui-sm"><p className="font-mono text-system-label font-semibold uppercase tracking-ui-label text-muted-foreground">Evidence</p><Info className="h-3 w-3 text-muted-foreground" aria-label="Trace events, Session continuity and raw runtime data" /></div><p className="mt-ui-xs font-sans text-product-caption leading-4 text-muted-foreground">Technical and causal evidence is preserved here and stays out of the operational Execution view until needed.</p></div>
            {trace.execution.root.failure ? <section className="rounded-container border border-red-500/25 bg-red-500/5 p-ui-md"><p className="font-sans text-product-caption font-medium text-red-300">{trace.execution.root.failure.message}</p><p className="mt-ui-xs font-mono text-system-meta text-muted-foreground">{trace.execution.root.failure.code} · {trace.execution.root.failure.stage}{trace.execution.root.failure.phase ? ` · ${trace.execution.root.failure.phase}` : ''}</p></section> : null}

            <div className="rounded-container border border-border/75 bg-background/30 px-ui-md">
              <CollapsibleSection title="Execution evidence" badge={`${agentRuns} Agent Runs`}><NetworkTraceInvocation invocation={trace.execution.root} trace={trace} depth={0} onOpenAgent={onOpenAgent} /></CollapsibleSection>
              <CollapsibleSection title="Delegations" badge={String(delegationRows.length)}>
                <div className="space-y-ui-sm">
                  {delegationRows.length ? delegationRows.map((delegation) => (
                    <button key={delegation.id} type="button" onClick={() => { setSelectedSpanId(delegation.childSpanId); setView('agent') }} className="flex w-full items-center gap-ui-sm rounded-control bg-background/45 px-ui-sm py-ui-sm text-left transition-colors hover:bg-background/70">
                      {compactStatusIcon(delegation.status)}
                      <div className="min-w-0 flex-1">
                        <p className="truncate font-sans text-product-caption text-slate-200"><span className="text-muted-foreground">{delegation.parent}</span> → {delegation.child}</p>
                        <p className="mt-ui-hairline truncate font-mono text-system-meta text-muted-foreground">{delegation.source} · {delegation.version}</p>
                      </div>
                    </button>
                  )) : <p className="font-sans text-product-caption text-muted-foreground">No Agent delegations were executed.</p>}
                </div>
              </CollapsibleSection>
              {routeEvents.length ? <CollapsibleSection title="Routing decisions" badge={String(routeEvents.length)}><div className="space-y-ui-sm">{routeEvents.map((event) => <div key={event.id} className="rounded-control bg-background/45 p-ui-sm"><div className="flex items-center gap-ui-xs"><GitBranch className="h-3.5 w-3.5 text-primary-light" /><code className="font-mono text-system-meta text-white">{operationEventLabel(event.type, event.payload)}</code></div><p className="mt-ui-xs font-sans text-product-caption text-muted-foreground">{event.label}</p><JsonCodeBlock value={event.payload} maxHeight={128} className="mt-ui-sm" /></div>)}</div></CollapsibleSection> : null}
              {trace.parsedOutput ? <CollapsibleSection title="Structured output"><JsonCodeBlock value={trace.parsedOutput} maxHeight={180} /></CollapsibleSection> : null}
              <CollapsibleSection title="Session composition" badge={`${trace.agentContexts.length} contexts`}><NetworkSessionComposition contexts={trace.agentContexts} /></CollapsibleSection>
              <CollapsibleSection title="Composition snapshot"><JsonCodeBlock value={{ environment: trace.environment, network_version: trace.networkVersion, composition_hash: trace.compositionHash, agents: trace.agentContexts.map((context) => ({ node_id: context.nodeId, agent_id: context.agentId, source: context.source, version: context.version, session_mode: context.sessionMode })) }} maxHeight={220} /></CollapsibleSection>
              <CollapsibleSection title="Events" badge={String(trace.events.length)}><div className="space-y-ui-sm">{trace.events.map((event) => <div key={event.id} className="rounded-control bg-background/45 px-ui-md py-ui-sm"><div className="flex items-center justify-between gap-ui-sm"><code className="truncate font-mono text-system-meta text-white">{operationEventLabel(event.type, event.payload)}</code><span className="font-mono text-system-nano text-muted-foreground">#{event.sequence}</span></div><p className="mt-ui-xs font-sans text-product-caption text-muted-foreground">{event.label}</p><JsonCodeBlock value={event.payload} maxHeight={112} className="mt-ui-sm" /></div>)}</div></CollapsibleSection>
              <CollapsibleSection title="Raw"><JsonCodeBlock value={trace} maxHeight={300} /></CollapsibleSection>
              <CollapsibleSection title="Technical identifiers" badge={`${technicalIds.length} IDs`}><div className="divide-y divide-border/60">{technicalIds.map(([label, value]) => <CopyableIdRow key={label} label={label} value={value} />)}</div><button type="button" onClick={() => void navigator.clipboard.writeText(technicalIds.map(([label, value]) => `${label}: ${value}`).join('\n'))} className="mt-ui-sm inline-flex items-center gap-ui-xs font-mono text-system-micro font-medium text-muted-foreground transition-colors hover:text-white"><Copy className="h-3 w-3" />Copy all identifiers</button></CollapsibleSection>
            </div>

            <div className="grid grid-cols-4 gap-ui-sm font-mono text-system-meta text-muted-foreground"><span className="inline-flex items-center gap-ui-xs"><GitBranch className="h-3 w-3" />{delegations} Delegations</span><span className="inline-flex items-center gap-ui-xs"><Wrench className="h-3 w-3" />{tools} Tools · {skills} Skill operations</span><span className="inline-flex items-center gap-ui-xs"><Database className="h-3 w-3" />{sources} Sources</span><span className="inline-flex items-center gap-ui-xs"><Activity className="h-3 w-3" />{trace.events.length} Events</span></div>
          </>
        ) : null}
      </div>
    </div>
  )
}
