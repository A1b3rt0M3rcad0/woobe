import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it, vi } from 'vitest'

import { ContractFieldBuilder } from './ContractFieldBuilder'

describe('ContractFieldBuilder responsive layout', () => {
  it('keeps Output fields in a compact single-row grid', () => {
    const markup = renderToStaticMarkup(
      <ContractFieldBuilder
        kind="output"
        rows={[{
          name: 'answer',
          type: 'string',
          required: true,
          scope: 'run',
          expose: true,
        }]}
        onChange={vi.fn()}
      />,
    )

    expect(markup).toContain('grid-cols-[minmax(100px,1fr)_90px_54px_24px]')
    expect(markup).not.toContain('overflow-x')
  })

  it('renders External Context as readable field cards instead of a compressed table', () => {
    const markup = renderToStaticMarkup(
      <ContractFieldBuilder
        kind="external"
        rows={[{
          name: 'customer_id',
          type: 'string',
          required: true,
          scope: 'session',
          expose: false,
          description: 'Customer identity for the current conversation',
        }]}
        onChange={vi.fn()}
      />,
    )

    expect(markup).toContain('Field 1')
    expect(markup).toContain('Description')
    expect(markup).toContain('Required at runtime')
    expect(markup).toContain('Expose to model')
    expect(markup).toContain('Session values persist across Runs')
    expect(markup).not.toContain('grid-cols-[minmax(56px,1fr)_66px_66px_38px_66px_24px]')
    expect(markup).not.toContain('overflow-x')
  })
})
