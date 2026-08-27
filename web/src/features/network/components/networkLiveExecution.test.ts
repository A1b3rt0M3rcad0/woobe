import { describe, expect, it } from 'vitest'

import type { NetworkRuntimeEvent } from '@/features/network/types'

import { applyNetworkRuntimeEvent, emptyLiveNetworkExecution } from './networkLiveExecution'

function event(
  data: Record<string, unknown>,
  overrides: Partial<NetworkRuntimeEvent> = {},
): NetworkRuntimeEvent {
  return {
    protocol_version: 1,
    execution_id: 'execution-1',
    data,
    created_at: '2026-07-16T12:00:00.000Z',
    ...overrides,
  }
}

describe('networkLiveExecution', () => {
  it('tracks specialist Agents, delegation Tools and Sources while a Run is active', () => {
    let state = emptyLiveNetworkExecution()

    state = applyNetworkRuntimeEvent(state, 'agent_invocation_started', event(
      { label: 'AGI Network' },
      { invocation_id: 'root', node_id: 'node-root', depth: 0 },
    ))
    state = applyNetworkRuntimeEvent(state, 'tool_call_started', event(
      {
        tool_call_id: 'tool-1',
        tool_name: 'delegate_to_agente_triste',
        input: { task: 'Answer with a sad tone' },
        status: 'running',
      },
      { invocation_id: 'root' },
    ))
    state = applyNetworkRuntimeEvent(state, 'delegation_started', event(
      { target: 'Agente Triste' },
      { invocation_id: 'root' },
    ))
    state = applyNetworkRuntimeEvent(state, 'agent_invocation_started', event(
      { label: 'Agente Triste' },
      { invocation_id: 'specialist', parent_invocation_id: 'root', node_id: 'node-specialist', depth: 1 },
    ))
    state = applyNetworkRuntimeEvent(state, 'sources', event({
      sources: [{ document_id: 'doc-1', chunk_id: 'chunk-1', document_title: 'Tone guide' }],
    }, { invocation_id: 'specialist' }))
    state = applyNetworkRuntimeEvent(state, 'tool_call_completed', event(
      {
        tool_call_id: 'tool-1',
        tool_name: 'delegate_to_agente_triste',
        input: { task: 'Answer with a sad tone' },
        output: { success: true },
        duration_ms: 120,
        success: true,
        status: 'success',
      },
      { invocation_id: 'root' },
    ))
    state = applyNetworkRuntimeEvent(state, 'agent_invocation_completed', event(
      { sources: [{ document_id: 'doc-1', chunk_id: 'chunk-1', document_title: 'Tone guide' }] },
      {
        invocation_id: 'specialist',
        parent_invocation_id: 'root',
        node_id: 'node-specialist',
        depth: 1,
        created_at: '2026-07-16T12:00:01.000Z',
      },
    ))

    expect(state.agents).toEqual(expect.arrayContaining([
      expect.objectContaining({ invocationId: 'specialist', name: 'Agente Triste', depth: 1, status: 'success' }),
    ]))
    expect(state.tools).toEqual([
      expect.objectContaining({
        tool_call_id: 'tool-1',
        tool_name: 'Delegate to Agente Triste',
        success: true,
        status: 'success',
      }),
    ])
    expect(state.sources).toHaveLength(1)
  })

  it('keeps semantic Tool error codes while a Run is active', () => {
    let state = applyNetworkRuntimeEvent(
      emptyLiveNetworkExecution(),
      'tool_call_started',
      event({
        tool_call_id: 'tool-1',
        tool_name: 'mcp_deepwiki_ask_question',
      }, { invocation_id: 'root' }),
    )

    state = applyNetworkRuntimeEvent(state, 'tool_call_completed', event({
      tool_call_id: 'tool-1',
      tool_name: 'mcp_deepwiki_ask_question',
      success: false,
      status: 'error',
      error_code: 'repository_not_found',
      error: 'Repository not found',
    }, { invocation_id: 'root' }))

    expect(state.tools[0]).toEqual(expect.objectContaining({
      success: false,
      status: 'error',
      error_code: 'repository_not_found',
    }))
  })

  it('marks active execution details as failed when the Run fails', () => {
    let state = applyNetworkRuntimeEvent(
      emptyLiveNetworkExecution(),
      'agent_invocation_started',
      event({ label: 'Specialist' }, { invocation_id: 'specialist', depth: 1 }),
    )
    state = applyNetworkRuntimeEvent(state, 'tool_call_started', event({
      tool_call_id: 'tool-running',
      tool_name: 'lookup',
    }, { invocation_id: 'specialist' }))
    state = applyNetworkRuntimeEvent(state, 'execution_failed', event({ message: 'failed' }))

    expect(state.agents[0].status).toBe('error')
    expect(state.tools[0]).toEqual(expect.objectContaining({
      status: 'error',
      success: false,
      error_code: 'execution_stopped',
    }))
  })

  it('keeps active execution details cancelled instead of failed', () => {
    let state = applyNetworkRuntimeEvent(
      emptyLiveNetworkExecution(),
      'agent_invocation_started',
      event({ label: 'Specialist' }, { invocation_id: 'specialist', depth: 1 }),
    )
    state = applyNetworkRuntimeEvent(state, 'tool_call_started', event({
      tool_call_id: 'tool-running',
      tool_name: 'lookup',
    }, { invocation_id: 'specialist' }))
    state = applyNetworkRuntimeEvent(state, 'execution_cancelled', event({ reason: 'cancel_requested' }))

    expect(state.agents[0].status).toBe('cancelled')
    expect(state.tools[0]).toEqual(expect.objectContaining({
      status: 'cancelled',
      success: false,
      error_code: null,
      error: null,
    }))
  })
})
