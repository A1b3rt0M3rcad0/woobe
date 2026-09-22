import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it, vi } from 'vitest'

import { RuntimeContextPanel } from './RuntimeContextPanel'

describe('RuntimeContextPanel External Context', () => {
  it('renders all declared Run input fields in the runtime form', () => {
    const html = renderToStaticMarkup(
      <RuntimeContextPanel
        environment="draft"
        contract={{
          current_page: {
            schema: { type: 'string' },
            required: false,
            model: { expose: true },
          },
          customer_id: {
            schema: { type: 'string' },
            required: true,
            model: { expose: false },
          },
        }}
        savedValues={{
          current_page: '/checkout',
          customer_id: 'cus-1',
        }}
        onSave={vi.fn()}
      />,
    )

    expect(html).toContain('External Context')
    expect(html).toContain('current_page')
    expect(html).toContain('customer_id')
  })
})
