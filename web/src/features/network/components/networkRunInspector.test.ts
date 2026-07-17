import { describe, expect, it } from 'vitest'
import type { NetworkAgentInvocation } from './networkChatExecution'
import { findNetworkInvocation, flattenNetworkInvocationPath, networkRunOutcome, summarizeInvocationTools } from './networkRunInspector'

function invocation(spanId: string, overrides: Partial<NetworkAgentInvocation> = {}): NetworkAgentInvocation {
  return {
    spanId,
    parentSpanId: null,
    sequence: 1,
    agentId: `agent-${spanId}`,
    agentName: spanId,
    agentSessionId: null,
    contextState: 'stateless',
    previousInvocationCount: 0,
    childTraceId: null,
    source: 'draft',
    version: 'Draft r1',
    status: 'success',
    tools: [],
    sources: [],
    children: [],
    ...overrides,
  }
}

describe('networkRunInspector', () => {
  it('flattens the causal Agent Run path with roles and depth', () => {
    const child = invocation('specialist', { parentSpanId: 'root' })
    const root = invocation('root', { children: [child] })
    expect(flattenNetworkInvocationPath(root).map((item) => ({ spanId: item.invocation.spanId, depth: item.depth, role: item.role }))).toEqual([
      { spanId: 'root', depth: 0, role: 'entry' },
      { spanId: 'specialist', depth: 1, role: 'delegated' },
    ])
    expect(findNetworkInvocation(root, 'specialist')).toBe(child)
  })

  it('summarizes Tool Calls without expanding their payloads', () => {
    const root = invocation('root', { tools: [
      { tool_name: 'running', status: 'running' },
      { tool_name: 'completed', success: true },
      { tool_name: 'failed', success: false, error: 'failed' },
    ] })
    expect(summarizeInvocationTools(root)).toEqual({ total: 3, running: 1, completed: 1, failed: 1 })
  })

  it('distinguishes completed Runs with handled child failures', () => {
    const root = invocation('root', { children: [invocation('specialist', { status: 'error' })] })
    expect(networkRunOutcome('success', root)).toBe('completed_with_issues')
    expect(networkRunOutcome('error', root)).toBe('failed')
    expect(networkRunOutcome('running', root)).toBe('running')
  })

  it('marks a final response with a failed Tool Call as completed with issues', () => {
    const root = invocation('root', { tools: [{ tool_name: 'http_lookup', success: false, status: 'error', error: 'HTTP request failed' }] })
    expect(networkRunOutcome('success', root)).toBe('completed_with_issues')
  })
})
