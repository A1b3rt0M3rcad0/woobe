import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it, vi } from 'vitest'

import { NetworkOperationsRail } from './NetworkOperationsRail'

describe('NetworkOperationsRail', () => {
  it('renders New Session first and exposes only Runs and Sessions as tabs', () => {
    const html = renderToStaticMarkup(
      <NetworkOperationsRail
        activeTab="traces"
        onTabChange={vi.fn()}
        onNewSession={vi.fn()}
      />,
    )

    const newSession = html.indexOf('New<br/>Session')
    const runs = html.indexOf('>Runs<')
    const sessions = html.indexOf('>Sessions<')

    expect(newSession).toBeGreaterThanOrEqual(0)
    expect(newSession).toBeLessThan(runs)
    expect(runs).toBeLessThan(sessions)
    expect(html).not.toContain('>Debug<')
    expect(html).toContain('title="Runs"')
    expect(html).toContain('title="Sessions"')
  })

  it('shows pending state and disables New Session while creation is in flight', () => {
    const html = renderToStaticMarkup(
      <NetworkOperationsRail
        activeTab={null}
        onTabChange={vi.fn()}
        onNewSession={vi.fn()}
        newSessionPending
      />,
    )

    expect(html).toContain('aria-label="New Session"')
    expect(html).toContain('disabled=""')
    expect(html).toContain('animate-spin')
  })
})
