import type { ToolCallInfo } from '@/features/playground/types'

import {
  operationalTools,
  type NetworkAgentInvocation,
  type NetworkExecution,
} from './networkChatExecution'

export interface NetworkInvocationPathItem {
  invocation: NetworkAgentInvocation
  depth: number
  role: 'entry' | 'delegated'
}

export interface NetworkToolSummary {
  total: number
  running: number
  completed: number
  failed: number
}

export function flattenNetworkInvocationPath(root: NetworkAgentInvocation): NetworkInvocationPathItem[] {
  const items: NetworkInvocationPathItem[] = []
  const visit = (invocation: NetworkAgentInvocation, depth: number) => {
    items.push({ invocation, depth, role: depth === 0 ? 'entry' : 'delegated' })
    invocation.children.forEach((child) => visit(child, depth + 1))
  }
  visit(root, 0)
  return items
}

export function findNetworkInvocation(root: NetworkAgentInvocation, spanId: string): NetworkAgentInvocation | null {
  if (root.spanId === spanId) return root
  for (const child of root.children) {
    const match = findNetworkInvocation(child, spanId)
    if (match) return match
  }
  return null
}

function toolState(tool: ToolCallInfo): 'running' | 'completed' | 'failed' {
  if (tool.status === 'running' || tool.status === 'pending') return 'running'
  if (tool.success === false || tool.status === 'error' || tool.status === 'failed') return 'failed'
  return 'completed'
}

export function summarizeInvocationTools(invocation: NetworkAgentInvocation, recursive = false): NetworkToolSummary {
  const tools = recursive
    ? flattenNetworkInvocationPath(invocation)
      .flatMap((item) => operationalTools(item.invocation.tools))
    : operationalTools(invocation.tools)
  return tools.reduce<NetworkToolSummary>((summary, tool) => {
    const state = toolState(tool)
    summary.total += 1
    summary[state] += 1
    return summary
  }, { total: 0, running: 0, completed: 0, failed: 0 })
}

export function invocationHasFailure(root: NetworkAgentInvocation): boolean {
  if (root.status === 'error' || root.failure) return true
  if (operationalTools(root.tools).some((tool) => toolState(tool) === 'failed')) return true
  return root.children.some(invocationHasFailure)
}

export function networkRunOutcome(
  status: NetworkExecution['status'],
  root: NetworkAgentInvocation,
): 'running' | 'completed' | 'completed_with_issues' | 'failed' | 'cancelled' {
  if (status === 'running') return 'running'
  if (status === 'error') return 'failed'
  if (status === 'cancelled') return 'cancelled'
  return invocationHasFailure(root) ? 'completed_with_issues' : 'completed'
}
