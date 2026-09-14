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
    expect(markup).toContain('The first node and entry point are persisted together.')
    expect(markup).toContain('A single entry Agent already creates a valid Network for testing.')
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

  it('does not render a duplicate ready-to-test banner over the Canvas', () => {
    expect(renderToStaticMarkup(
      <NetworkReadyToTest
        pending={false}
        onTest={vi.fn()}
        onAddSpecialist={vi.fn()}
      />,
    )).toBe('')
  })
})
