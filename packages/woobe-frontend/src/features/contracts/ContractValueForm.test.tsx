import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it, vi } from 'vitest'

import { ContractValueForm } from './ContractValueForm'

describe('ContractValueForm Session scope', () => {
  it('renders a fixed Session value from the backend snapshot and disables editing', () => {
    const markup = renderToStaticMarkup(
      <ContractValueForm
        contract={{
          client_id: {
            schema: { type: 'string' },
            required: true,
            scope: 'session',
            model: { expose: false },
          },
          current_page: {
            schema: { type: 'string' },
            required: false,
            scope: 'run',
            model: { expose: false },
          },
        }}
        values={{ client_id: 'client-changed', current_page: '/billing' }}
        lockedValues={{ client_id: 'client-123' }}
        onChange={vi.fn()}
      />,
    )

    expect(markup).toContain('SESSION · fixed')
    expect(markup).toContain('RUN')
    expect(markup).toContain('value="client-123"')
    expect(markup).not.toContain('value="client-changed"')
    expect(markup).toMatch(/<input[^>]*disabled=""[^>]*value="client-123"|<input[^>]*value="client-123"[^>]*disabled=""/)
  })
})
