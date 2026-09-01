import { renderToStaticMarkup } from 'react-dom/server'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { resetAgentStreamStopState, setAgentStreamStopState } from '@/features/playground/stream-stop-state'
import { SessionsPanel } from './SessionsPanel'

const session = {
  id: '12345678-0000-0000-0000-000000000000',
  project_id: 'project-1',
  agent_id: 'agent-1',
  runtime_environment: 'draft' as const,
  opened_release_id: null,
  opened_release_version: null,
  status: 'active',
  mode: 'chat',
  data: { source: 'playground' },
  last_message_at: null,
  created_at: null,
  message_count: 1,
}

afterEach(() => resetAgentStreamStopState())

describe('SessionsPanel active Run isolation', () => {
  it('keeps Session actions enabled while runtime is idle', () => {
    resetAgentStreamStopState()
    const html = renderToStaticMarkup(
      <SessionsPanel
        sessions={[session]}
        currentSessionId={session.id}
        sessionMode="stateful"
        onNewSession={vi.fn()}
        onSelectSession={vi.fn()}
      />,
    )

    expect(html).not.toContain('Wait for the active Agent Run')
  })

  it('disables Session creation and selection while an Agent Run is running', () => {
    setAgentStreamStopState('running')
    const html = renderToStaticMarkup(
      <SessionsPanel
        sessions={[session]}
        currentSessionId={session.id}
        sessionMode="stateful"
        onNewSession={vi.fn()}
        onSelectSession={vi.fn()}
      />,
    )

    expect(html).toContain('Wait for the active Agent Run to finish or stop it before changing Sessions')
    expect((html.match(/disabled=""/g) ?? []).length).toBeGreaterThanOrEqual(2)
  })

  it('keeps Session actions disabled while cancellation is being finalized', () => {
    setAgentStreamStopState('stopping')
    const html = renderToStaticMarkup(
      <SessionsPanel
        sessions={[session]}
        currentSessionId={session.id}
        sessionMode="stateful"
        onNewSession={vi.fn()}
        onSelectSession={vi.fn()}
      />,
    )

    expect(html).toContain('Wait for the active Agent Run cancellation to finish before changing Sessions')
    expect((html.match(/disabled=""/g) ?? []).length).toBeGreaterThanOrEqual(2)
  })
})