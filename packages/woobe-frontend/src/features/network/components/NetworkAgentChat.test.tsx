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
  useSessionMessages: vi.fn(),
  sessionPages: [] as Array<Record<string, unknown>>,
  externalContextContract: {} as Record<string, unknown>,
  completeReattach: null as null | (() => void),
}))

vi.mock('@/features/playground/AgentEditorContext', () => ({
  useAgentEditor: () => ({
    toSnapshot: () => ({
      name: 'Billing Agent',
      external_context_contract: fixture.externalContextContract,
    }),
    isDirty: false,
    state: {
      externalContextContract: fixture.externalContextContract,
    },
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
    data: { pages: [{ items: fixture.sessionPages }] },
    isLoading: false,
    isFetching: false,
    hasNextPage: false,
    isFetchingNextPage: false,
    fetchNextPage: vi.fn(),
    refetch: fixture.refetchSessions,
  }),
  useSessionMessages: (sessionId?: string) => {
    fixture.useSessionMessages(sessionId)
    return {
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
    }
  },
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
  fixture.useSessionMessages.mockReset()
  fixture.sessionPages = []
  fixture.externalContextContract = {}
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
    expect(container.textContent).toContain('partial recovered')
    expect(container.textContent).not.toContain('partial recovered done')

    await act(async () => fixture.completeReattach?.())
    await flush()

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


async function setInputValue(element: HTMLInputElement | HTMLTextAreaElement, value: string) {
  await act(async () => {
    const prototype = element instanceof HTMLTextAreaElement
      ? HTMLTextAreaElement.prototype
      : HTMLInputElement.prototype
    const setter = Object.getOwnPropertyDescriptor(prototype, 'value')?.set
    setter?.call(element, value)
    element.dispatchEvent(new Event('input', { bubbles: true }))
  })
}

async function click(element: Element) {
  await act(async () => {
    element.dispatchEvent(new MouseEvent('click', { bubbles: true }))
  })
}

describe('Network Agent Chat External Context lifecycle', () => {
  it('uses the live Agent Draft contract and sends explicit External Context', async () => {
    fixture.externalContextContract = {
      client_id: {
        schema: { type: 'string' },
        required: true,
        scope: 'session',
        model: { expose: false },
      },
      current_page: {
        schema: { type: 'string' },
        required: false,
        model: { expose: false },
      },
    }
    fixture.stream.mockImplementation(async (_request, callbacks) => {
      callbacks.onMeta({ session_id: 'session-created', run_id: 'run-1' })
      callbacks.onDone({ answer: 'ok', session_id: 'session-created' })
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

    const externalContextToggle = [...container.querySelectorAll('button')]
      .find((element) => element.textContent?.includes('External Context'))
    expect(externalContextToggle).toBeTruthy()
    await click(externalContextToggle!)

    const clientId = container.querySelector('input[aria-label="client_id"]') as HTMLInputElement
    const currentPage = container.querySelector('input[aria-label="current_page"]') as HTMLInputElement
    expect(clientId).toBeTruthy()
    expect(currentPage).toBeTruthy()
    await setInputValue(clientId, 'client-123')
    await setInputValue(currentPage, '/billing')

    const textarea = container.querySelector('textarea[placeholder="Message this Agent…"]') as HTMLTextAreaElement
    await setInputValue(textarea, 'hello')
    const send = container.querySelector('button[aria-label="Send message"]')
    expect(send).toBeTruthy()
    await click(send!)
    await flush()

    expect(fixture.stream).toHaveBeenCalledTimes(1)
    expect(fixture.stream.mock.calls[0][0]).toMatchObject({
      external_context: {
        client_id: 'client-123',
        current_page: '/billing',
      },
    })
    expect(fixture.refetchSessions).toHaveBeenCalled()
  })

  it('renders Session snapshot values as fixed and omits them from later Runs', async () => {
    localStorage.setItem(
      'woobe:network-agent-chat:project-1:agent-1:session',
      'session-1',
    )
    fixture.externalContextContract = {
      client_id: {
        schema: { type: 'string' },
        required: true,
        scope: 'session',
        model: { expose: false },
      },
      current_page: {
        schema: { type: 'string' },
        required: false,
        model: { expose: false },
      },
    }
    fixture.sessionPages = [{
      id: 'session-1',
      project_id: 'project-1',
      agent_id: 'agent-1',
      runtime_environment: 'draft',
      status: 'active',
      mode: 'chat',
      external_context_snapshot: { client_id: 'client-fixed' },
      last_message_at: null,
      created_at: '2026-09-11T00:00:00Z',
      message_count: 0,
    }]
    fixture.stream.mockImplementation(async (_request, callbacks) => {
      callbacks.onDone({ answer: 'ok', session_id: 'session-1' })
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

    const externalContextToggle = [...container.querySelectorAll('button')]
      .find((element) => element.textContent?.includes('External Context'))
    await click(externalContextToggle!)

    const clientId = container.querySelector('input[aria-label="client_id"]') as HTMLInputElement
    expect(clientId.value).toBe('client-fixed')
    expect(clientId.disabled).toBe(true)
    expect(container.textContent).toContain('SESSION · fixed')

    const currentPage = container.querySelector('input[aria-label="current_page"]') as HTMLInputElement
    await setInputValue(currentPage, '/orders')
    const textarea = container.querySelector('textarea[placeholder="Message this Agent…"]') as HTMLTextAreaElement
    await setInputValue(textarea, 'next')
    await click(container.querySelector('button[aria-label="Send message"]')!)
    await flush()

    expect(fixture.stream.mock.calls[0][0]).toMatchObject({
      session_id: 'session-1',
      external_context: { current_page: '/orders' },
    })
    expect(fixture.stream.mock.calls[0][0].external_context).not.toHaveProperty('client_id')
  })

  it('reuses a technical Session for stateless Agents without loading its conversation history', async () => {
    localStorage.setItem(
      'woobe:network-agent-chat:project-1:agent-1:session',
      'session-stateless',
    )
    const statelessAgent = { ...agent, session_mode: 'stateless' }
    fixture.stream.mockImplementation(async (_request, callbacks) => {
      callbacks.onDone({ answer: 'ok', session_id: 'session-stateless' })
    })

    await act(async () => {
      root.render(
        <NetworkAgentChat
          agent={statelessAgent}
          projectId="project-1"
          onChatCompleted={vi.fn()}
        />,
      )
    })
    await flush()

    expect(fixture.useSessionMessages).not.toHaveBeenCalledWith('session-stateless')
    const textarea = container.querySelector('textarea[placeholder="Message this Agent…"]') as HTMLTextAreaElement
    await setInputValue(textarea, 'stateless run')
    await click(container.querySelector('button[aria-label="Send message"]')!)
    await flush()

    expect(fixture.stream.mock.calls[0][0].session_id).toBe('session-stateless')
    expect(localStorage.getItem(
      'woobe:network-agent-chat:project-1:agent-1:session',
    )).toBe('session-stateless')
    expect(container.textContent).toContain('Stateless isolated test · Session context preserved')
  })
})
