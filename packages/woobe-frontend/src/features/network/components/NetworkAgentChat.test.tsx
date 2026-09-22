// @vitest-environment jsdom
import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import type { Agent } from '@/features/agents/types'

const fixture = vi.hoisted(() => ({
  reattach: vi.fn(),
  stream: vi.fn(),
  cancel: vi.fn(),
  refetchSessions: vi.fn(),
  getActiveAgentRun: vi.fn(),
  completeReattach: null as null | (() => void),
}))

vi.mock('@/features/playground/AgentEditorContext', () => ({
  useAgentEditor: () => ({
    toSnapshot: () => ({ name: 'Billing Agent' }),
    isDirty: false,
  }),
}))

vi.mock('@/features/playground/components/ChatMessage', () => ({
  ChatMessage: ({ message }: { message: { content?: string; activity?: { message?: string } | null } }) => (
    <div data-testid="chat-message">{message.content || message.activity?.message || ''}</div>
  ),
}))

vi.mock('@/features/playground/hooks', () => ({
  useAskStream: () => ({
    stream: fixture.stream,
    reattach: fixture.reattach,
    cancel: fixture.cancel,
  }),
  useAgentSessions: () => ({
    data: { pages: [] },
    isLoading: false,
    isFetching: false,
    hasNextPage: false,
    isFetchingNextPage: false,
    fetchNextPage: vi.fn(),
    refetch: fixture.refetchSessions,
  }),
  useSessionMessages: (sessionId?: string) => ({
    data: sessionId
      ? [{
          id: 'message-user',
          role: 'user',
          content: 'Tell me a long story',
          data: {},
          input_tokens: null,
          output_tokens: null,
          cost_usd: null,
          created_at: '2026-09-11T00:00:00Z',
        }]
      : undefined,
    isFetching: false,
  }),
}))

vi.mock('@/features/playground/reattach-api', () => ({
  getActiveAgentRun: fixture.getActiveAgentRun,
}))

import { NetworkAgentChat } from './NetworkAgentChat'

const agent: Agent = {
  id: 'agent-1',
  project_id: 'project-1',
  name: 'Billing Agent',
  description: 'Billing specialist',
  provider: 'openai',
  model: 'test-model',
  status: 'active',
  session_mode: 'stateful',
  system_prompt: '',
}

let root: Root
let container: HTMLDivElement

async function flush() {
  await act(async () => {
    await Promise.resolve()
    await Promise.resolve()
  })
}

beforeEach(() => {
  Object.assign(globalThis, { IS_REACT_ACT_ENVIRONMENT: true })
  localStorage.clear()
  fixture.reattach.mockReset()
  fixture.stream.mockReset()
  fixture.cancel.mockReset()
  fixture.refetchSessions.mockReset()
  fixture.getActiveAgentRun.mockReset()
  fixture.completeReattach = null
  container = document.createElement('div')
  document.body.appendChild(container)
  root = createRoot(container)
})

afterEach(async () => {
  await act(async () => root.unmount())
  container.remove()
  localStorage.clear()
})

describe('Network Agent Chat active Run reattach', () => {
  it('restores the persisted session, reattaches the same Run and shows partial output before terminal persistence', async () => {
    localStorage.setItem(
      'woobe:network-agent-chat:project-1:agent-1:session',
      'session-1',
    )
    localStorage.setItem(
      'woobe:network-agent-chat:project-1:agent-1:run',
      'run-1',
    )

    fixture.reattach.mockImplementation(async (runId, callbacks) => {
      expect(runId).toBe('run-1')
      callbacks.onMeta({ run_id: 'run-1', session_id: 'session-1', trace_id: 'trace-1' })
      callbacks.onAssistantMessageCompleted?.({
        message_id: 'message-progress',
        content: 'Vou procurar.',
        phase: 'capability_response_generation',
        output_mode: 'intermediate',
      })
      callbacks.onToken({
        content: 'partial recovered',
        visibility: 'assistant',
        channel: 'final',
        phase: 'final_response_generation',
        provider: 'test-provider',
        model: 'test-model',
        redacted: null,
      })
      await new Promise<void>((resolve) => {
        fixture.completeReattach = () => {
          callbacks.onDone({
            answer: 'partial recovered done',
            session_id: 'session-1',
            trace_id: 'trace-1',
          })
          resolve()
        }
      })
    })

    const onChatCompleted = vi.fn()
    await act(async () => {
      root.render(
        <NetworkAgentChat
          agent={agent}
          projectId="project-1"
          onChatCompleted={onChatCompleted}
        />,
      )
    })
    await flush()
    await flush()

    expect(fixture.reattach).toHaveBeenCalledTimes(1)
    expect(container.textContent).toContain('Tell me a long story')
    expect(container.textContent).toContain('Vou procurar.')
    expect(container.textContent).toContain('partial recovered')
    expect(container.textContent).not.toContain('partial recovered done')

    await act(async () => fixture.completeReattach?.())
    await flush()

    expect(container.textContent).toContain('Vou procurar.')
    expect(container.textContent).toContain('partial recovered done')
    expect(onChatCompleted).toHaveBeenCalledTimes(1)
    expect(localStorage.getItem(
      'woobe:network-agent-chat:project-1:agent-1:run',
    )).toBeNull()
  })

  it('discovers the active Run by stored Session when the local Run pointer is missing', async () => {
    localStorage.setItem(
      'woobe:network-agent-chat:project-1:agent-1:session',
      'session-1',
    )
    fixture.getActiveAgentRun.mockResolvedValue({
      run_id: 'run-discovered',
      status: 'running',
      session_id: 'session-1',
      agent_id: 'agent-1',
      environment: 'draft',
    })
    fixture.reattach.mockImplementation(async (_runId, callbacks) => {
      callbacks.onDone({ answer: 'done', session_id: 'session-1' })
    })

    await act(async () => {
      root.render(
        <NetworkAgentChat
          agent={agent}
          projectId="project-1"
          onChatCompleted={vi.fn()}
        />,
      )
    })
    await flush()
    await flush()

    expect(fixture.getActiveAgentRun).toHaveBeenCalledWith('session-1')
    expect(fixture.reattach).toHaveBeenCalledWith(
      'run-discovered',
      expect.any(Object),
    )
  })
})
