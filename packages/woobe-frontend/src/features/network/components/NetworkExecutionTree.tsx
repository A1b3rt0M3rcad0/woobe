import { useMemo, useState } from 'react'
import { CheckCircle2, ChevronDown, ChevronRight, Loader2, XCircle } from 'lucide-react'

import type { ChatMessage as PlaygroundChatMessage, SourceInfo, ToolCallInfo } from '@/features/playground/types'
import { formatCurrency } from '@/lib/formatters/number'

import type { LiveNetworkAgent, LiveNetworkDelegation } from './networkLiveExecution'
import type { AgentNodeId } from './networkWorkspaceTypes'
import {
  delegationCount,
  invocationCount,
  operationalTools,
  type NetworkAgentInvocation,
  type NetworkExecution,
  type NetworkTurn,
} from './networkChatExecution'

function flattenTools(invocation: NetworkAgentInvocation): ToolCallInfo[] {
  return [
    ...operationalTools(invocation.tools),
    ...invocation.children.flatMap(flattenTools),
  ]
}

function flattenSources(invocation: NetworkAgentInvocation): SourceInfo[] {
  return [
    ...invocation.sources,
    ...invocation.children.flatMap(flattenSources),
  ]
}

function invocationNames(invocation: NetworkAgentInvocation): Array<{
  id?: AgentNodeId
  name: string
  depth: number
  status: NetworkAgentInvocation['status']
}> {
  const visit = (node: NetworkAgentInvocation, depth: number): Array<{
    id?: AgentNodeId
    name: string
    depth: number
    status: NetworkAgentInvocation['status']
  }> => [
    { id: node.nodeId, name: node.agentName, depth, status: node.status },
    ...node.children.flatMap((child) => visit(child, depth + 1)),
  ]
  return visit(invocation, 0)
}

function AgentStatusIcon({ status }: { status: NetworkAgentInvocation['status'] | LiveNetworkAgent['status'] }) {
  if (status === 'running' || status === 'pending') {
    return <Loader2 className="h-3.5 w-3.5 shrink-0 animate-spin text-primary-light" />
  }
  if (status === 'error') return <XCircle className="h-3.5 w-3.5 shrink-0 text-red-400" />
  return <CheckCircle2 className="h-3.5 w-3.5 shrink-0 text-emerald-400" />
}

function DelegationStatusIcon({ status }: { status: LiveNetworkDelegation['status'] }) {
  if (status === 'running') return <Loader2 className="h-3.5 w-3.5 shrink-0 animate-spin text-primary-light" />
  if (status === 'error') return <XCircle className="h-3.5 w-3.5 shrink-0 text-red-400" />
  if (status === 'cancelled' || status === 'skipped') return <XCircle className="h-3.5 w-3.5 shrink-0 text-slate-400" />
  return <CheckCircle2 className="h-3.5 w-3.5 shrink-0 text-emerald-400" />
}

function agentSummary(agents: Array<{ name: string; status: NetworkAgentInvocation['status'] | LiveNetworkAgent['status'] }>) {
  const running = agents.filter((agent) => agent.status === 'running' || agent.status === 'pending').length
  const failed = agents.filter((agent) => agent.status === 'error').length
  const completed = agents.length - running - failed
  const singleAgent = agents.length === 1 ? agents[0].name : null
  const parts = [`Agents called (${agents.length})${singleAgent ? ` · ${singleAgent}` : ''}`]
  if (running) parts.push(`${running} running`)
  if (completed) parts.push(`${completed} completed`)
  if (failed) parts.push(`${failed} failed`)
  return parts.join(' · ')
}

function delegationSummary(delegations: LiveNetworkDelegation[]) {
  const running = delegations.filter((item) => item.status === 'running').length
  const completed = delegations.filter((item) => item.status === 'success').length
  const failed = delegations.filter((item) => item.status === 'error').length
  const skipped = delegations.filter((item) => item.status === 'skipped' || item.status === 'cancelled').length
  const parts = [`Delegations (${delegations.length})`]
  if (running) parts.push(`${running} running`)
  if (completed) parts.push(`${completed} completed`)
  if (failed) parts.push(`${failed} failed`)
  if (skipped) parts.push(`${skipped} skipped`)
  return parts.join(' · ')
}

function AgentsCalled({ root, onSelectAgent }: { root: NetworkAgentInvocation; onSelectAgent: (nodeId: AgentNodeId) => void }) {
  const [open, setOpen] = useState(false)
  const agents = useMemo(() => invocationNames(root).filter((agent) => agent.depth > 0), [root])
  if (!agents.length) return null

  return (
    <div className="pl-16">
      <button type="button" onClick={() => setOpen((value) => !value)} className="flex max-w-full items-center gap-ui-xs font-mono text-system-micro text-primary-light transition-colors hover:text-white">
        {open ? <ChevronDown className="h-3.5 w-3.5 shrink-0" /> : <ChevronRight className="h-3.5 w-3.5 shrink-0" />}
        <span className="truncate">{agentSummary(agents)}</span>
      </button>
      {open ? (
        <div className="mt-ui-xs space-y-ui-xs border-l border-border/70 pl-ui-sm">
          {agents.map((agent, index) => agent.id ? (
            <button key={`${agent.id}-${index}`} type="button" onClick={() => onSelectAgent(agent.id!)} className="flex max-w-full items-center gap-ui-xs text-left font-mono text-system-micro text-muted-foreground hover:text-white" style={{ paddingLeft: `${Math.max(0, Math.min(agent.depth - 1, 3)) * 10}px` }}>
              <AgentStatusIcon status={agent.status} />
              <span className="truncate">{agent.name}</span>
            </button>
          ) : (
            <div key={`${agent.name}-${index}`} className="flex max-w-full items-center gap-ui-xs font-mono text-system-micro text-muted-foreground" style={{ paddingLeft: `${Math.max(0, Math.min(agent.depth - 1, 3)) * 10}px` }}>
              <AgentStatusIcon status={agent.status} />
              <span className="truncate">{agent.name}</span>
            </div>
          ))}
        </div>
      ) : null}
    </div>
  )
}

export function NetworkLiveAgents({ agents, onSelectAgent }: {
  agents: LiveNetworkAgent[]
  onSelectAgent: (nodeId: AgentNodeId) => void
}) {
  const [open, setOpen] = useState(false)
  const calledAgents = useMemo(() => agents.filter((agent) => agent.depth > 0), [agents])
  if (!calledAgents.length) return null

  return (
    <div className="pl-16">
      <button type="button" onClick={() => setOpen((value) => !value)} className="flex max-w-full items-center gap-ui-xs font-mono text-system-micro text-primary-light transition-colors hover:text-white">
        {open ? <ChevronDown className="h-3.5 w-3.5 shrink-0" /> : <ChevronRight className="h-3.5 w-3.5 shrink-0" />}
        <span className="truncate">{agentSummary(calledAgents)}</span>
      </button>
      {open ? (
        <div className="mt-ui-xs space-y-ui-xs border-l border-border/70 pl-ui-sm">
          {calledAgents.map((agent) => agent.nodeId ? (
            <button key={agent.invocationId} type="button" onClick={() => onSelectAgent(agent.nodeId!)} className="flex max-w-full items-center gap-ui-xs text-left font-mono text-system-micro text-muted-foreground hover:text-white" style={{ paddingLeft: `${Math.max(0, Math.min(agent.depth - 1, 3)) * 10}px` }}>
              <AgentStatusIcon status={agent.status} />
              <span className="truncate">{agent.name}</span>
            </button>
          ) : (
            <div key={agent.invocationId} className="flex max-w-full items-center gap-ui-xs font-mono text-system-micro text-muted-foreground" style={{ paddingLeft: `${Math.max(0, Math.min(agent.depth - 1, 3)) * 10}px` }}>
              <AgentStatusIcon status={agent.status} />
              <span className="truncate">{agent.name}</span>
            </div>
          ))}
        </div>
      ) : null}
    </div>
  )
}

export function NetworkLiveDelegations({ delegations }: { delegations: LiveNetworkDelegation[] }) {
  const [open, setOpen] = useState(false)
  if (!delegations.length) return null

  return (
    <div className="pl-16">
      <button type="button" onClick={() => setOpen((value) => !value)} className="flex max-w-full items-center gap-ui-xs font-mono text-system-micro text-primary-light transition-colors hover:text-white">
        {open ? <ChevronDown className="h-3.5 w-3.5 shrink-0" /> : <ChevronRight className="h-3.5 w-3.5 shrink-0" />}
        <span className="truncate">{delegationSummary(delegations)}</span>
      </button>
      {open ? (
        <div className="mt-ui-xs space-y-ui-xs border-l border-border/70 pl-ui-sm">
          {delegations.map((delegation) => (
            <div key={delegation.id} className="flex max-w-full items-center gap-ui-xs font-mono text-system-micro text-muted-foreground">
              <DelegationStatusIcon status={delegation.status} />
              <span className="truncate">{delegation.target}</span>
            </div>
          ))}
        </div>
      ) : null}
    </div>
  )
}

export function networkTurnChatMessage(turn: NetworkTurn): PlaygroundChatMessage {
  const failure = turn.execution.root.failure
  const fallback = failure?.partialResultAvailable
    ? `${failure.message}\n\nCompleted Tool and Agent results remain available below.`
    : failure?.message || 'The Network Run failed before producing a response.'

  return {
    role: 'assistant',
    content: turn.answer || fallback,
    usage: turn.usage,
    sources: flattenSources(turn.execution.root),
    tool_calls: flattenTools(turn.execution.root),
    model: turn.model || null,
    provider: turn.provider || null,
    latency_ms: turn.execution.durationMs,
    trace_id: turn.execution.traceId,
    parsed_output: turn.parsedOutput ?? null,
    output_parse_error: turn.outputParseError ?? null,
  }
}

export function NetworkTurnDetails({ turn, onSelectAgent }: {
  turn: NetworkTurn
  onSelectAgent: (nodeId: AgentNodeId) => void
}) {
  const delegations = delegationCount(turn.execution.root)
  return (
    <div className="space-y-ui-xs">
      {delegations > 0 ? <div className="pl-16 font-mono text-system-micro text-primary-light">Delegations ({delegations}) · completed in this Run</div> : null}
      <AgentsCalled root={turn.execution.root} onSelectAgent={onSelectAgent} />
    </div>
  )
}

export function NetworkLiveDetails({ delegations, agents, onSelectAgent }: {
  delegations: LiveNetworkDelegation[]
  agents: LiveNetworkAgent[]
  onSelectAgent: (nodeId: AgentNodeId) => void
}) {
  return (
    <div className="space-y-ui-xs">
      <NetworkLiveDelegations delegations={delegations} />
      <NetworkLiveAgents agents={agents} onSelectAgent={onSelectAgent} />
    </div>
  )
}

export function NetworkTurnFooterMeta({ turn }: { turn: NetworkTurn }) {
  const agents = invocationCount(turn.execution.root)
  const delegations = delegationCount(turn.execution.root)
  const cost = turn.execution.costUsd == null ? 'cost unknown' : formatCurrency(turn.execution.costUsd)
  return (
    <>
      <span>{agents} Agent Run{agents === 1 ? '' : 's'}</span>
      <span>{delegations} delegation{delegations === 1 ? '' : 's'}</span>
      <span>{cost}</span>
    </>
  )
}

export function NetworkOpenRunAction({ execution, onOpenTrace }: {
  execution: NetworkExecution
  onOpenTrace: (execution: NetworkExecution) => void
}) {
  return (
    <button type="button" onClick={() => onOpenTrace(execution)} className="h-control-segment rounded-control px-ui-sm font-mono text-system-micro font-medium text-primary-light transition-colors hover:bg-background/70 hover:text-white">
      Open Run
    </button>
  )
}
