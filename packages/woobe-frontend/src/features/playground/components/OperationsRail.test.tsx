import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it, vi } from 'vitest'

import { OperationsRail } from './OperationsRail'

describe('OperationsRail Session actions', () => {
  it('renders New Session as the primary action before Runs and Sessions', () => {
    const html = renderToStaticMarkup(
      <OperationsRail
        activeTab="traces"
        environment="draft"
        onTabChange={vi.fn()}
        onNewSession={vi.fn()}
      />,
    )

    const newSession = html.indexOf('aria-label="New Session"')
    const runs = html.indexOf('>Runs<')
    const sessions = html.indexOf('>Sessions<')

    expect(newSession).toBeGreaterThanOrEqual(0)
    expect(newSession).toBeLessThan(runs)
    expect(runs).toBeLessThan(sessions)
    expect(html).not.toContain('>Debug<')
    expect(html).toContain('border-primary/35 bg-primary/[0.10]')
  })

  it('disables New Session without turning it into a navigation tab', () => {
    const html = renderToStaticMarkup(
      <OperationsRail
        activeTab="sessions"
        environment="production"
        onTabChange={vi.fn()}
        onNewSession={vi.fn()}
        newSessionDisabled
        newSessionDisabledReason="Runtime unavailable"
      />,
    )

    expect(html).toContain('aria-label="New Session"')
    expect(html).toContain('title="Runtime unavailable"')
    expect(html).toContain('disabled=""')
  })
})
