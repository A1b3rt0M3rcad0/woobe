import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'

import { NetworkWorkspaceBootstrap } from './NetworkWorkspaceBootstrap'

describe('Network workspace bootstrap', () => {
  it('covers the full workspace without operational controls', () => {
    const markup = renderToStaticMarkup(
      <NetworkWorkspaceBootstrap networkName="Support Network" />,
    )

    expect(markup).toContain('Support Network')
    expect(markup).toContain('Preparing Network')
    expect(markup).toContain('fixed inset-0')
    expect(markup).not.toContain('Stage Network')
    expect(markup).not.toContain('API Reference')
    expect(markup).not.toContain('Runs')
  })
})
