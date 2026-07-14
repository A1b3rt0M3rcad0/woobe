import { describe, expect, it } from 'vitest'

import { initialNetworkWorkspaceState, networkWorkspaceReducer } from './networkWorkspaceReducer'

describe('networkWorkspaceReducer', () => {
  it('keeps the selected Agent and inspector tab when switching between Canvas and Chat', () => {
    const agentContext = networkWorkspaceReducer(initialNetworkWorkspaceState, {
      type: 'context',
      context: 'agent',
    })
    const selected = networkWorkspaceReducer(agentContext, {
      type: 'select',
      selection: { type: 'node', id: 'agent-node-1' },
    })
    const chat = networkWorkspaceReducer(selected, { type: 'center', mode: 'chat' })

    expect(chat.selection).toEqual({ type: 'node', id: 'agent-node-1' })
    expect(chat.inspectorContext).toBe('agent')
    expect(chat.centerMode).toBe('chat')
  })

  it('changes the inspected Agent without forcing the Network tab to Agent', () => {
    const next = networkWorkspaceReducer(initialNetworkWorkspaceState, {
      type: 'select',
      selection: { type: 'node', id: 'agent-node-1' },
    })

    expect(next.inspectorContext).toBe('network')
    expect(next.selection).toEqual({ type: 'node', id: 'agent-node-1' })
  })

  it('keeps Agent context for delegations without changing the center mode', () => {
    const agentChat = {
      ...initialNetworkWorkspaceState,
      centerMode: 'chat' as const,
      inspectorContext: 'agent' as const,
    }
    const next = networkWorkspaceReducer(agentChat, {
      type: 'select',
      selection: { type: 'edge', id: 'edge-1' },
    })

    expect(next.centerMode).toBe('chat')
    expect(next.inspectorContext).toBe('agent')
    expect(next.selection).toEqual({ type: 'edge', id: 'edge-1' })
  })

  it('marks Run inspection as read-only context without replacing selection', () => {
    const selected = networkWorkspaceReducer(initialNetworkWorkspaceState, {
      type: 'select',
      selection: { type: 'node', id: 'agent-node-1' },
    })
    const inspected = networkWorkspaceReducer(selected, { type: 'inspect-run', runId: 'run-1' })

    expect(inspected.inspectionScope).toEqual({ type: 'run', runId: 'run-1' })
    expect(inspected.selection).toEqual({ type: 'node', id: 'agent-node-1' })
  })

  it('clears historical Run inspection when changing environment', () => {
    const inspected = networkWorkspaceReducer(initialNetworkWorkspaceState, { type: 'inspect-run', runId: 'run-1' })
    const staging = networkWorkspaceReducer(inspected, {
      type: 'environment',
      environment: 'staging',
      selection: { type: 'network' },
    })

    expect(staging.environment).toBe('staging')
    expect(staging.inspectionScope).toEqual({ type: 'current' })
    expect(staging.selection).toEqual({ type: 'network' })
  })
})
