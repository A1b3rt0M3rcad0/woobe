import { describe, expect, it } from 'vitest'

import {
  externalContractFromRows,
  externalContractRows,
  filterExternalContextInput,
} from './contractFields'

describe('External Context lifecycle helpers', () => {
  it('preserves session scope and omits locked session fields from Run input', () => {
    const contract = externalContractFromRows([
      { name: 'customer_id', type: 'string', required: true, expose: false, scope: 'session' },
      { name: 'page', type: 'string', required: false, expose: false, scope: 'run' },
    ])

    expect(externalContractRows(contract).map((field) => [field.name, field.scope])).toEqual([
      ['customer_id', 'session'],
      ['page', 'run'],
    ])
    expect(filterExternalContextInput(
      contract,
      { customer_id: 'cus-1', page: '/billing' },
      { customer_id: 'cus-1' },
    )).toEqual({ page: '/billing' })
  })
})
