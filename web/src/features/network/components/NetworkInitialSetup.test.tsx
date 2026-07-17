import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it, vi } from 'vitest'

import { NetworkInitialSetup, NetworkInitialSetupInspector, NetworkReadyToTest } from './NetworkInitialSetup'

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
    expect(markup).not.toContain('Choose Agent')
    expect(markup).toContain('One Agent is enough')
    expect(markup).toContain('Saved automatically')
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

    expect(markup).toContain('Choose the entry Agent')
    expect(markup).toContain('Choose Agent')
    expect(markup).toContain('Create new Agent')
    expect(markup).toContain('after validating the first test')
  })

  it('does not reserve a separate inspector during the initial setup', () => {
    expect(renderToStaticMarkup(<NetworkInitialSetupInspector />)).toBe('')
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
