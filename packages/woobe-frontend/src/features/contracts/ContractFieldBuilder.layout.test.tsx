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

  it('uses the same compact row grammar for External Context with its own contract controls', () => {
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

    expect(markup).toContain('grid-cols-[minmax(88px,1fr)_78px_78px_42px_46px_28px_28px]')
    expect(markup).toContain('Name')
    expect(markup).toContain('Type')
    expect(markup).toContain('Scope')
    expect(markup).toContain('Req.')
    expect(markup).toContain('Model')
    expect(markup).toContain('aria-label="Edit customer_id description"')
    expect(markup).not.toContain('<textarea')
    expect(markup).not.toContain('Customer identity for the current conversation')
    expect(markup).not.toContain('overflow-x')
  })

  it('keeps ten External Context fields at one compact row per field', () => {
    const rows = Array.from({ length: 10 }, (_, index) => ({
      name: `field_${index + 1}`,
      type: 'string' as const,
      required: index % 2 === 0,
      scope: index % 2 === 0 ? 'run' as const : 'session' as const,
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
