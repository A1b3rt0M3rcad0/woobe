import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it, vi } from 'vitest'

import { NetworkInitialSetup, NetworkReadyToTest } from './NetworkInitialSetup'

describe('Network initial setup', () => {
  it('prioritizes creating the first Agent when the Project has no Agents', () => {
    const markup = renderToStaticMarkup(
      <NetworkInitialSetup
        hasAgents={false}
        pending={false}
        onChooseAgent={vi.fn()}
        onCreateAgent={vi.fn()}
      />,
    )

    expect(markup).toContain('Create first Agent')
    expect(markup).not.toContain('Choose existing Agent')
    expect(markup).toContain('Specialists and delegations can be added after the first test')
  })

  it('offers existing Agent selection without making specialists mandatory', () => {
    const markup = renderToStaticMarkup(
      <NetworkInitialSetup
        hasAgents
        pending={false}
        onChooseAgent={vi.fn()}
        onCreateAgent={vi.fn()}
      />,
    )

    expect(markup).toContain('Choose existing Agent')
    expect(markup).toContain('Create new Agent')
    expect(markup).toContain('automatically defined as the entry point')
  })

  it('makes the first test the primary next action', () => {
    const markup = renderToStaticMarkup(
      <NetworkReadyToTest
        pending={false}
        onTest={vi.fn()}
        onAddSpecialist={vi.fn()}
      />,
    )

    expect(markup).toContain('Network ready for the first test')
    expect(markup).toContain('Test Network')
    expect(markup).toContain('Add specialist')
  })
})
