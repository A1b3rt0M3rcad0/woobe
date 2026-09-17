import { describe, expect, it } from 'vitest'

import {
  buildExecutionFromRuntimeEvents,
  buildTurnFromRuntimeEvents,
  currentSignature,
  networkLabel,
  type RuntimeEventRecord,
} from './networkChatExecution'
import type { NetworkBinding } from './networkWorkspaceTypes'

const binding = {
  nodeId: 'node-root',
  agent: {
    id: 'agent-root',
    name: 'Root Agent',
    provider: 'openai',
    model: 'gpt-test',
  },
  source: 'draft',
  ref: 'agent-root',
  version: 'r7',
  draftVersion: 'r7',
  dirty: false,
} as NetworkBinding

describe('Network runtime event projection', () => {
  it('builds a real invocation tree from SSE events', () => {
    const records: RuntimeEventRecord[] = [
      {
        eventType: 'agent_invocation_started',
        event: {
          protocol_version: 2,
          execution_id: 'execution-1',
          invocation_id: 'invocation-1',
          parent_invocation_id: null,
          node_id: 'node-root',
          agent_id: 'agent-root',
          depth: 0,
          data: { label: 'Root Agent' },
          sequence: 2,
          created_at: '2026-07-14T10:00:00.000Z',
        },
      },
      {
        eventType: 'agent_invocation_completed',
        event: {
          protocol_version: 2,
          execution_id: 'execution-1',
          invocation_id: 'invocation-1',
          parent_invocation_id: null,
          node_id: 'node-root',
          agent_id: 'agent-root',
          depth: 0,
          data: {
            trace_id: 'trace-1',
            output: 'answer',
            provider: 'openai',
            model: 'gpt-test',
            usage: { input_tokens: 5, output_tokens: 3, total_tokens: 8, cost_usd: 0.01 },
          },
          sequence: 3,
          created_at: '2026-07-14T10:00:00.500Z',
        },
      },
    ]

    const turn = buildTurnFromRuntimeEvents({
      records,
      environment: 'draft',
      bindings: { 'node-root': binding },
      executionId: 'execution-1',
      user: 'hello',
      answer: 'answer',
    })

    expect(turn.execution.root.agentName).toBe('Root Agent')
    expect(turn.execution.root.output).toBe('answer')
    expect(turn.execution.path).toEqual(['node-root'])
    expect(turn.usage?.total_tokens).toBe(8)
    expect(turn.execution.traceId).toBe('trace-1')
  })

  it('binds the explicit Agent Run identity without treating the Network span as the Run id', () => {
    const records: RuntimeEventRecord[] = [
      {
        eventType: 'agent_invocation_started',
        event: {
          protocol_version: 2,
          execution_id: 'execution-identity',
          invocation_id: 'span-1',
          parent_invocation_id: null,
          node_id: 'node-root',
          agent_id: 'agent-root',
          depth: 0,
          data: { label: 'Root Agent' },
          sequence: 1,
          created_at: '2026-09-11T03:00:00.000Z',
        },
      },
      {
        eventType: 'agent_run_identity',
        event: {
          protocol_version: 2,
          execution_id: 'execution-identity',
          invocation_id: 'span-1',
          parent_invocation_id: null,
          node_id: 'node-root',
          agent_id: 'agent-root',
          depth: 0,
          data: { agent_run_id: 'agent-run-1' },
          sequence: 2,
          created_at: '2026-09-11T03:00:00.010Z',
        },
      },
      {
        eventType: 'agent_invocation_completed',
        event: {
          protocol_version: 2,
          execution_id: 'execution-identity',
          invocation_id: 'span-1',
          parent_invocation_id: null,
          node_id: 'node-root',
          agent_id: 'agent-root',
          depth: 0,
          data: { output: 'done' },
          sequence: 3,
          created_at: '2026-09-11T03:00:00.500Z',
        },
      },
    ]

    const turn = buildTurnFromRuntimeEvents({
      records,
      environment: 'draft',
      bindings: { 'node-root': binding },
      executionId: 'execution-identity',
      user: 'hello',
      answer: 'done',
    })

    expect(turn.execution.root.spanId).toBe('span-1')
    expect(turn.execution.root.runId).toBe('agent-run-1')
  })

  it('keeps a failed Agent Run causal without inventing telemetry or a Trace', () => {
    const records: RuntimeEventRecord[] = [
      {
        eventType: 'agent_invocation_started',
        event: {
          protocol_version: 2,
          execution_id: 'execution-failed',
          invocation_id: 'invocation-failed',
          parent_invocation_id: null,
          node_id: 'node-root',
          agent_id: 'agent-root',
          depth: 0,
          data: { label: 'Root Agent' },
          sequence: 2,
          created_at: '2026-07-14T10:00:00.000Z',
        },
      },
      {
        eventType: 'agent_invocation_failed',
        event: {
          protocol_version: 2,
          execution_id: 'execution-failed',
          invocation_id: 'invocation-failed',
          parent_invocation_id: null,
          node_id: 'node-root',
          agent_id: 'agent-root',
          depth: 0,
          data: {
            code: 'runtime_configuration_error',
            stage: 'agent_bootstrap',
            message: 'The Agent runtime configuration could not be loaded.',
            retryable: false,
          },
          sequence: 3,
          created_at: '2026-07-14T10:00:00.020Z',
        },
      },
      {
        eventType: 'execution_failed',
        event: {
          protocol_version: 2,
          execution_id: 'execution-failed',
          data: { code: 'runtime_configuration_error' },
          sequence: 4,
          created_at: '2026-07-14T10:00:00.025Z',
        },
      },
    ]

    const turn = buildTurnFromRuntimeEvents({
      records,
      environment: 'draft',
      bindings: { 'node-root': binding },
      executionId: 'execution-failed',
      user: 'hello',
      answer: '',
      terminalStatus: 'error',
    })

    expect(turn.execution.traceId).toBeNull()
    expect(turn.execution.costUsd).toBeNull()
    expect(turn.usage).toBeNull()
    expect(turn.execution.path).toEqual(['node-root'])
    expect(turn.execution.root.failure?.code).toBe('runtime_configuration_error')
    expect(turn.answer).toContain('configuration')
  })

  it('keeps a real Agent Trace when the provider fails after preparation', () => {
    const records: RuntimeEventRecord[] = [
      {
        eventType: 'agent_invocation_started',
        event: {
          protocol_version: 2,
          execution_id: 'execution-provider-failed',
          invocation_id: 'invocation-provider-failed',
          parent_invocation_id: null,
          node_id: 'node-root',
          agent_id: 'agent-root',
          depth: 0,
          data: { label: 'Root Agent' },
          sequence: 2,
          created_at: '2026-07-14T10:00:00.000Z',
        },
      },
      {
        eventType: 'agent_invocation_failed',
        event: {
          protocol_version: 2,
          execution_id: 'execution-provider-failed',
          invocation_id: 'invocation-provider-failed',
          parent_invocation_id: null,
          node_id: 'node-root',
          agent_id: 'agent-root',
          depth: 0,
          data: {
            code: 'provider_request_error',
            stage: 'provider_request',
            message: 'The model provider rejected the Agent request.',
            retryable: false,
            trace_id: 'trace-provider-failed',
          },
          sequence: 3,
          created_at: '2026-07-14T10:00:00.020Z',
        },
      },
      {
        eventType: 'execution_failed',
        event: {
          protocol_version: 2,
          execution_id: 'execution-provider-failed',
          data: {
            code: 'provider_request_error',
            trace_id: 'trace-provider-failed',
          },
          sequence: 4,
          created_at: '2026-07-14T10:00:00.025Z',
        },
      },
    ]

    const turn = buildTurnFromRuntimeEvents({
      records,
      environment: 'draft',
      bindings: { 'node-root': binding },
      executionId: 'execution-provider-failed',
      user: 'hello',
      answer: '',
      terminalStatus: 'error',
    })

    expect(turn.execution.traceId).toBe('trace-provider-failed')
    expect(turn.execution.root.childTraceId).toBe('trace-provider-failed')
    expect(turn.execution.root.failure?.stage).toBe('provider_request')
    expect(turn.usage).toBeNull()
    expect(turn.execution.costUsd).toBeNull()
  })

  it('preserves failed Tools, partial-result metadata and per-Agent duration', () => {
    const records: RuntimeEventRecord[] = [
      {
        eventType: 'agent_invocation_started',
        event: {
          protocol_version: 2,
          execution_id: 'execution-partial',
          invocation_id: 'root',
          node_id: 'node-root',
          agent_id: 'agent-root',
          depth: 0,
          sequence: 1,
          created_at: '2026-07-16T12:00:00.000Z',
          data: { label: 'Root Agent' },
        },
      },
      {
        eventType: 'tool_call_started',
        event: {
          protocol_version: 2,
          execution_id: 'execution-partial',
          invocation_id: 'root',
          sequence: 2,
          created_at: '2026-07-16T12:00:01.000Z',
          data: {
            tool_call_id: 'tool-1',
            tool_name: 'mcp_deepwiki_ask_question',
            input: { repoName: 'openclaude' },
          },
        },
      },
      {
        eventType: 'tool_call_completed',
        event: {
          protocol_version: 2,
          execution_id: 'execution-partial',
          invocation_id: 'root',
          sequence: 3,
          created_at: '2026-07-16T12:00:02.000Z',
          data: {
            tool_call_id: 'tool-1',
            tool_name: 'mcp_deepwiki_ask_question',
            success: false,
            status: 'error',
            error_code: 'invalid_repository_identifier',
            error: 'Invalid repoName format',
            duration_ms: 1000,
          },
        },
      },
      {
        eventType: 'agent_invocation_started',
        event: {
          protocol_version: 2,
          execution_id: 'execution-partial',
          invocation_id: 'child',
          parent_invocation_id: 'root',
          node_id: 'node-child',
          agent_id: 'agent-child',
          depth: 1,
          sequence: 4,
          created_at: '2026-07-16T12:00:02.000Z',
          data: { label: 'Specialist' },
        },
      },
      {
        eventType: 'agent_invocation_completed',
        event: {
          protocol_version: 2,
          execution_id: 'execution-partial',
          invocation_id: 'child',
          parent_invocation_id: 'root',
          node_id: 'node-child',
          agent_id: 'agent-child',
          depth: 1,
          sequence: 5,
          created_at: '2026-07-16T12:00:05.000Z',
          data: { output: 'done', tool_calls: [], sources: [] },
        },
      },
      {
        eventType: 'agent_invocation_failed',
        event: {
          protocol_version: 2,
          execution_id: 'execution-partial',
          invocation_id: 'root',
          node_id: 'node-root',
          agent_id: 'agent-root',
          depth: 0,
          sequence: 6,
          created_at: '2026-07-16T12:00:06.000Z',
          data: {
            code: 'provider_request_error',
            stage: 'provider_request',
            message: 'The model provider rejected the final response request.',
            retryable: false,
            phase: 'final_response_generation',
            partial_result_available: true,
          },
        },
      },
    ]

    const built = buildExecutionFromRuntimeEvents({
      records,
      environment: 'draft',
      bindings: { 'node-root': binding },
      executionId: 'execution-partial',
      answer: '',
      terminalStatus: 'error',
    })

    expect(built.execution.root.tools).toEqual([
      expect.objectContaining({
        tool_call_id: 'tool-1',
        success: false,
        error_code: 'invalid_repository_identifier',
      }),
    ])
    expect(built.execution.root.failure?.partialResultAvailable).toBe(true)
    expect(built.execution.root.durationMs).toBe(6000)
    expect(built.execution.root.children[0].durationMs).toBe(3000)
  })

  it('signs any dynamic node ids without fixed roles', () => {
    expect(currentSignature('draft', { 'node-root': binding })).toContain('node-root')
    expect(currentSignature('draft', { 'node-root': binding })).not.toContain('billing')
    expect(networkLabel('draft', 7)).toBe('Draft r7')
  })
})