import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it, vi } from 'vitest'

import { AgentCreationLoadError, AgentCreationPreparing } from './AgentCreationBootstrap'

describe('Agent creation bootstrap', () => {
  it('keeps a stable preparation surface while inventory loads', () => {
    const markup = renderToStaticMarkup(<AgentCreationPreparing />)

    expect(markup).toContain('Preparing Agent setup')
    expect(markup).toContain('Loading Provider connections and generation models')
    expect(markup).toContain('min-h-[520px]')
  })

  it('offers retry and cancel when the inventory cannot be loaded', () => {
    const markup = renderToStaticMarkup(
      <AgentCreationLoadError onRetry={vi.fn()} onCancel={vi.fn()} />,
    )

    expect(markup).toContain('Could not prepare Agent setup')
    expect(markup).toContain('Retry')
    expect(markup).toContain('Cancel')
  })
})
