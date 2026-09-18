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

  it('keeps External Context fields as dense collapsed rows', () => {
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

    expect(markup).toContain('grid-cols-[minmax(88px,1fr)_72px_72px_34px_38px_28px_28px]')
    expect(markup).toContain('Req.')
    expect(markup).toContain('Model')
    expect(markup).toContain('1 field')
    expect(markup).toContain('aria-expanded="false"')
    expect(markup).not.toContain('<textarea')
    expect(markup).not.toContain('Customer identity for the current conversation')
    expect(markup).not.toContain('overflow-x')
  })

  it('does not multiply vertical detail panels when the contract has many fields', () => {
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

    expect(markup).toContain('10 fields')
    expect(markup.match(/aria-expanded="false"/g)).toHaveLength(10)
    expect(markup).not.toContain('<textarea')
    expect(markup).not.toContain('Description 10')
  })
})
