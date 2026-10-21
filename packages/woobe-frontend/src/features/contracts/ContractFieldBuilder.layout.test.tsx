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
          expose: true,
        }]}
        onChange={vi.fn()}
      />,
    )

    expect(markup).toContain('grid-cols-[minmax(100px,1fr)_90px_54px_24px]')
    expect(markup).not.toContain('overflow-x')
  })

  it('labels every External Context control independently of the wide-screen header', () => {
    const markup = renderToStaticMarkup(
      <ContractFieldBuilder
        kind="external"
        rows={[{
          name: 'customer_id',
          type: 'string',
          required: true,
          expose: false,
          description: 'Customer identity for the current conversation',
        }]}
        onChange={vi.fn()}
      />,
    )

    for (const label of ['Field 1 name', 'Field customer_id type', 'Field customer_id scope', 'Field customer_id required', 'Field customer_id model visibility', 'Remove customer_id']) {
      expect(markup).toContain(`aria-label="${label}"`)
    }
    expect(markup).toContain('aria-label="Edit customer_id description"')
    expect(markup).not.toContain('<textarea')
    expect(markup).not.toContain('Customer identity for the current conversation')
    expect(markup).not.toContain('overflow-x')
  })

  it('keeps descriptions in an on-demand editor when there are ten External Context fields', () => {
    const rows = Array.from({ length: 10 }, (_, index) => ({
      name: `field_${index + 1}`,
      type: 'string' as const,
      required: index % 2 === 0,
      expose: true,
      description: `Description ${index + 1}`,
    }))

    const markup = renderToStaticMarkup(
      <ContractFieldBuilder kind="external" rows={rows} onChange={vi.fn()} />,
    )

    expect(markup.match(/aria-label="Edit field_\d+ description"/g)).toHaveLength(10)
    expect(markup).not.toContain('<textarea')
    expect(markup).not.toContain('Description 10')
    expect(markup).not.toContain('aria-expanded')
  })
})
