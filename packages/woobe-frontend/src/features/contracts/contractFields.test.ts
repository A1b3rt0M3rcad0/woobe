import { describe, expect, it } from 'vitest'

import {
  externalContractFromRows,
  externalContractRows,
  filterContractValues,
  outputSchemaFromRows,
} from './contractFields'

describe('contract field builders', () => {
  it('compiles External Context fields directly at the contract root', () => {
    expect(externalContractFromRows([
      { name: 'customer_id', type: 'string', required: true, scope: 'session', expose: false },
      { name: 'current_page', type: 'string', required: false, scope: 'run', expose: true },
    ])).toEqual({
      customer_id: {
        schema: { type: 'string' },
        required: true,
        scope: 'session',
        model: { expose: false },
      },
      current_page: {
        schema: { type: 'string' },
        required: false,
        scope: 'run',
        model: { expose: true },
      },
    })
  })

  it('reads the old fields wrapper without keeping it in the visual model', () => {
    expect(externalContractRows({
      fields: {
        customer_id: {
          schema: { type: 'string' },
          required: true,
          scope: 'session',
          model: { expose: false },
        },
      },
    })).toEqual([
      { name: 'customer_id', type: 'string', required: true, scope: 'session', expose: false },
    ])
  })

  it('compiles Output rows into a strict object schema', () => {
    expect(outputSchemaFromRows([
      { name: 'answer', type: 'string', required: true, scope: 'run', expose: true },
      { name: 'confidence', type: 'number', required: false, scope: 'run', expose: true },
    ])).toEqual({
      type: 'object',
      properties: {
        answer: { type: 'string' },
        confidence: { type: 'number' },
      },
      required: ['answer'],
      additionalProperties: false,
    })
  })

  it('drops persisted values that are no longer declared by the selected environment contract', () => {
    const contract = externalContractFromRows([
      { name: 'customer_id', type: 'string', required: true, scope: 'session', expose: false },
    ])
    expect(filterContractValues(contract, {
      customer_id: 'cus-123',
      removed_field: 'stale',
    })).toEqual({ customer_id: 'cus-123' })
  })

  it('preserves semantic descriptions through the visual builder round-trip', () => {
    const contract = {
      name: {
        schema: { type: 'string' },
        required: true,
        scope: 'run',
        model: { expose: true },
        description: 'Preferred name of the current user',
      },
    }

    const rows = externalContractRows(contract)

    expect(rows).toHaveLength(1)
    expect(rows[0].description).toBe('Preferred name of the current user')
    expect(externalContractFromRows(rows)).toEqual(contract)
  })

  it('omits blank descriptions instead of persisting visual-editor noise', () => {
    const contract = externalContractFromRows([
      {
        name: 'name',
        type: 'string',
        required: true,
        scope: 'run',
        expose: true,
        description: '   ',
      },
    ])

    expect(contract.name.description).toBeUndefined()
  })
})
