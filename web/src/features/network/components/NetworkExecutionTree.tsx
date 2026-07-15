import { useMemo, useState } from 'react'
import { ChevronDown, ChevronRight, Workflow, XCircle } from 'lucide-react'

import { ChatMessage } from '@/features/playground/components/ChatMessage'
import type { ChatMessage as PlaygroundChatMessage, SourceInfo, ToolCallInfo } from '@/features/playground/types'
import { formatLatency } from '@/lib/formatters/number'
import { cn } from '@/lib/utils'

import type { AgentNodeId } from './networkWorkspaceTypes'
import { invocationCount, type NetworkAgentInvocation, type NetworkExecution, type NetworkTurn } from './networkChatExecution'

function flattenTools(invocation: NetworkAgentInvocation): ToolCallInfo[] {
  return [
    ...invocation.tools,
    ...invocation.children.flatMap(flattenTools),
  ]
}

function flattenSources(invocation: NetworkAgentInvocation): SourceInfo[] {
  return [
    ...invocation.sources,
    ...invocation.children.flatMap(flattenSources),
  ]
}

function invocationNames(invocation: NetworkAgentInvocation): Array<{ id?: AgentNodeId; name: string; depth: number }> {
  const visit = (node: NetworkAgentInvocation, depth: number): Array<{ id?: AgentNodeId; name: string; depth: number }> => [
    { id: node.nodeId, name: node.agentName, depth },
    ...node.children.flatMap((child) => visit(child, depth + 1)),
  ]
  return visit(invocation, 0)
}

function AgentsCalled({ root, onSelectAgent }: { root: NetworkAgentInvocation; onSelectAgent: (nodeId: AgentNodeId) => void }) {
  const [open, setOpen] = useState(false)
  const agents = useMemo(() => invocationNames(root), [root])
  if (agents.length <= 1) return null

  return (
    <div className="pl-8">
      <button type="button" onClick={() => setOpen((value) => !value)} className="flex items-center gap-1 text-[9px] text-primary-light transition-colors hover:text-white">
        {open ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
        Agents called ({agents.length - 1})
      </button>
      {open ? (
        <div className="mt-1.5 space-y-1 border-l border-border/70 pl-2">
          {agents.map((agent, index) => agent.id ? (
            <button key={`${agent.id}-${index}`} type="button" onClick={() => onSelectAgent(agent.id!)} className="block max-w-full truncate text-left text-[9px] text-muted hover:text-white" style={{ paddingLeft: `${Math.min(agent.depth, 3) * 10}px` }}>
              {agent.name}
            </button>
          ) : (
            <p key={`${agent.name}-${index}`} className="truncate text-[9px] text-muted" style={{ paddingLeft: `${Math.min(agent.depth, 3) * 10}px` }}>{agent.name}</p>
          ))}
        </div>
      ) : null}
    </div>
  )
}

export function NetworkAnswer({ networkName, turn, onOpenTrace, onSelectAgent }: {
  networkName: string
  turn: NetworkTurn
  onOpenTrace: (execution: NetworkExecution) => void
  onSelectAgent: (nodeId: AgentNodeId) => void
}) {
  const failed = turn.execution.status === 'error'
  const message: PlaygroundChatMessage = {
    role: 'assistant',
    content: turn.answer || turn.execution.root.failure?.message || 'The Network Run failed before producing a response.',
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
  const agents = invocationCount(turn.execution.root)
  const cost = turn.execution.costUsd == null ? 'cost unknown' : `$${turn.execution.costUsd.toFixed(3)}`

  return (
    <div className={cn('space-y-1.5', failed && 'rounded-xl border border-red-500/25 bg-red-500/[0.03] p-2')}>
      <div className="flex items-center gap-2 pl-8 text-[9px] text-muted">
        {failed ? <XCircle className="h-3 w-3 text-red-400" /> : <Workflow className="h-3 w-3 text-primary-light" />}
        <span className="truncate">{networkName}</span>
      </div>
      <ChatMessage message={message} agentName={networkName} variant="network" />
      <AgentsCalled root={turn.execution.root} onSelectAgent={onSelectAgent} />
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1 pl-8 text-[9px] text-muted">
        <span>{agents} Agent{agents === 1 ? '' : 's'}</span>
        <span>{formatLatency(turn.execution.durationMs)}</span>
        <span>{cost}</span>
        <button type="button" onClick={() => onOpenTrace(turn.execution)} className="font-medium text-primary-light hover:text-white">Open Run</button>
      </div>
    </div>
  )
}
