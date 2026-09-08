import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it, vi } from 'vitest'

import type { NetworkSession } from './networkSessionTypes'
import { NetworkSessionsPanel } from './NetworkSessionsPanel'

const session: NetworkSession = {
  id: 'network-session-1',
  projectId: 'project-1',
  networkId: 'network-1',
  title: 'Production investigation',
  environment: 'production',
  networkVersion: 'version-old',
  versionLabel: 'Production · v3',
  draftRevision: null,
  compositionHash: 'hash-1',
  status: 'active',
  createdAt: '2026-09-08T10:00:00Z',
  lastMessageAt: '2026-09-08T10:05:00Z',
  messageCount: 6,
  traceCount: 3,
  agentContexts: [],
}

const currentSession: NetworkSession = {
  ...session,
  id: 'network-session-current',
  title: 'Current production session',
  networkVersion: 'version-current',
}

describe('NetworkSessionsPanel', () => {
  it('renders Session continuity without a nested New Session action', () => {
    const html = renderToStaticMarkup(
      <NetworkSessionsPanel
        sessions={[session]}
        activeSessionId={session.id}
        currentVersionId="version-current"
        onSelectSession={vi.fn()}
      />,
    )

    expect(html).toContain('Production investigation')
    expect(html).toContain('6 msgs')
    expect(html).toContain('3 Runs')
    expect(html).toContain('Earlier snapshot')
    expect(html).not.toContain('Reset context')
    expect(html).not.toContain('aria-label="New Session"')
  })

  it('moves Reset context to the selected current Session instead of Chat', () => {
    const html = renderToStaticMarkup(
      <NetworkSessionsPanel
        sessions={[currentSession]}
        activeSessionId={currentSession.id}
        currentVersionId="version-current"
        onSelectSession={vi.fn()}
      />,
    )

    expect(html).toContain('Reset context')
  })

  it('does not expose Session context actions when no Session is selected', () => {
    const html = renderToStaticMarkup(
      <NetworkSessionsPanel
        sessions={[currentSession]}
        activeSessionId={null}
        currentVersionId="version-current"
        onSelectSession={vi.fn()}
      />,
    )

    expect(html).not.toContain('Reset context')
  })

  it('points an empty Network to the primary rail action', () => {
    const html = renderToStaticMarkup(
      <NetworkSessionsPanel
        sessions={[]}
        activeSessionId={null}
        currentVersionId={null}
        onSelectSession={vi.fn()}
      />,
    )

    expect(html).toContain('Use New Session in the left rail to start a Network conversation.')
  })
})
