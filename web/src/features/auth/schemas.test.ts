import { describe, expect, it } from 'vitest'

import { registerSchema } from './schemas'

describe('registerSchema', () => {
  it('accepts registration without a workspace name', () => {
    const result = registerSchema.safeParse({
      email: 'owner@example.com',
      password: 'password',
    })

    expect(result.success).toBe(true)
  })

  it('continues to validate email and password', () => {
    const result = registerSchema.safeParse({
      email: 'invalid',
      password: '123',
    })

    expect(result.success).toBe(false)
  })
})
