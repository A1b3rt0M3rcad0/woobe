import { describe, expect, it } from 'vitest'

import { externalContractFromRows, externalContractRows } from './contractFields'

describe('External Context contract fields', () => {
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
