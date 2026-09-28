// @vitest-environment jsdom
import { act, type ReactNode } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { StreamCallbacks } from '@/features/playground/stream-client'

const fixture = vi.hoisted(() => ({
  reattach: vi.fn(), stream: vi.fn(), disconnect: vi.fn(), active: vi.fn(),
  toast: { error: vi.fn(), warning: vi.fn(), info: vi.fn() },
  queryClient: { invalidateQueries: vi.fn() },
  agent: { id: 'agent-1', name: 'Agent', project_id: 'project-1' },
  state: { externalContextContract: {}, sessionMode: 'stateful' },
  history: [{ role: 'user', content: 'Olá' }],
  sessions: { pages: [{ items: [{ id: 'session-1', runtime_environment: 'draft' }] }] },
  releases: [], traces: [], sending: false,
}))
vi.mock('react-router-dom', () => ({ useParams: () => ({ projectId: 'project-1', agentId: 'agent-1' }), useNavigate: () => vi.fn() }))
vi.mock('@tanstack/react-query', () => ({ useQueryClient: () => fixture.queryClient }))
vi.mock('sonner', () => ({ toast: fixture.toast }))
vi.mock('@/features/agents/hooks', () => ({
  useAgent: () => ({ data: fixture.agent }),
  useReleases: () => ({ data: fixture.releases }),
  useAgentRuntimeEnvironments: () => ({ data: undefined }),
}))
vi.mock('@/features/agents/components/AgentEditorNavigation', () => ({ useAgentEditorSection: () => [null, vi.fn()] }))
vi.mock('@/features/traces/hooks', () => ({ usePlaygroundTraces: () => ({ data: fixture.traces }) }))
vi.mock('@/features/playground/AgentEditorContext', () => ({
  AgentEditorProvider: ({ children }: { children: ReactNode }) => children,
  useAgentEditor: () => ({ state: fixture.state, isDirty: false }),
}))
vi.mock('@/features/playground/hooks', () => ({
  useAskStream: () => ({ stream: fixture.stream, reattach: fixture.reattach, cancel: vi.fn(), disconnect: fixture.disconnect }),
  useAgentSessions: () => ({ data: fixture.sessions }),
  useCreateSession: () => ({ mutateAsync: vi.fn() }),
  useSessionMessages: () => ({ data: fixture.history, isFetching: false }),
}))
vi.mock('@/features/playground/reattach-api', () => ({ getActiveAgentRun: fixture.active }))
vi.mock('@/features/playground/components/PlaygroundHeader', () => ({ PlaygroundHeader: () => null }))
vi.mock('@/features/playground/components/OperationsRail', () => ({ OperationsRail: () => null }))
vi.mock('@/features/playground/components/OperationsPanel', () => ({ OperationsPanel: () => null }))
vi.mock('@/features/playground/components/AgentInspector', () => ({ AgentInspector: () => null }))
vi.mock('@/features/playground/components/ApiModal', () => ({ ApiModal: () => null }))
vi.mock('@/features/playground/components/ChatCanvas', () => ({
  ChatCanvas: ({ isSending }: { isSending: boolean }) => { fixture.sending = isSending; return null },
}))

import AgentPlaygroundPage from './AgentPlaygroundPage'
import { getStoredPlaygroundRunId, setStoredPlaygroundSessionId } from '@/features/playground/lib/playground-session-store'

let root: Root
let container: HTMLDivElement
beforeEach(() => {
  Object.assign(globalThis, { IS_REACT_ACT_ENVIRONMENT: true })
  vi.clearAllMocks()
  localStorage.clear()
  setStoredPlaygroundSessionId('project-1', 'agent-1', 'draft', 'session-1')
  fixture.active.mockResolvedValue({ run_id: 'run-1' })
  container = document.createElement('div')
  root = createRoot(container)
})
afterEach(async () => { await act(async () => root.unmount()); localStorage.clear() })

async function renderAndRefresh() {
  await act(async () => root.render(<AgentPlaygroundPage />))
  for (let i = 0; i < 4; i++) await act(async () => root.render(<AgentPlaygroundPage />))
}

describe('Standalone terminal Run discovery', () => {
  it.each(['failed', 'completed', 'cancelled'])('does not reattach a %s Run rediscovered as active', async (status) => {
    fixture.reattach.mockImplementation(async (runId: string, callbacks: StreamCallbacks) => {
      callbacks.onMeta({ run_id: runId, session_id: 'session-1' })
      if (status === 'failed') callbacks.onError(new Error('prepare_failed'))
      else if (status === 'completed') callbacks.onDone({ answer: 'Hello' })
      else callbacks.onCancelled?.({})
    })
    await renderAndRefresh()
    expect(fixture.reattach).toHaveBeenCalledTimes(1)
    expect(fixture.active.mock.calls.length).toBeLessThanOrEqual(2)
    expect(fixture.stream).not.toHaveBeenCalled()
    expect(fixture.sending).toBe(false)
    expect(getStoredPlaygroundRunId('project-1', 'agent-1', 'draft')).toBeNull()
  })

  it('does not reset the stream client retry budget after transport exhaustion', async () => {
    fixture.reattach.mockRejectedValue(new Error('connection unavailable'))
    await renderAndRefresh()
    expect(fixture.reattach).toHaveBeenCalledTimes(1)
    expect(getStoredPlaygroundRunId('project-1', 'agent-1', 'draft')).toBe('run-1')
    expect(fixture.sending).toBe(false)
    await act(async () => root.unmount())
    root = createRoot(container)
    fixture.reattach.mockImplementation(async (_runId: string, callbacks: StreamCallbacks) => callbacks.onDone({ answer: 'Recovered' }))
    await renderAndRefresh()
    expect(fixture.reattach).toHaveBeenCalledTimes(2)
  })
})
