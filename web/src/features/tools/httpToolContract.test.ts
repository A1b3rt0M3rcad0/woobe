import { describe, expect, it } from 'vitest'

import { inspectHttpToolContract } from './httpToolContract'


describe('inspectHttpToolContract', () => {
  it('discovers parameters in URL, headers and Body', () => {
    const result = inspectHttpToolContract({
      protocol: 'http',
      method: 'POST',
      url: 'https://api.example.com/{{resourceId}}',
      headers: [
        { key: 'Content-Type', value: 'application/json' },
        { key: 'X-Tenant', value: '{{tenantId}}' },
      ],
      body: '{"expr":"{{a}} + {{b}}"}',
    })

    expect(result.errors).toEqual([])
    expect(result.parameterNames).toEqual(['resourceId', 'a', 'b', 'tenantId'])
    expect(result.inputSchema).toMatchObject({
      type: 'object',
      required: ['resourceId', 'a', 'b', 'tenantId'],
    })
  })

  it('reports malformed placeholders and invalid JSON Body', () => {
    const result = inspectHttpToolContract({
      protocol: 'http',
      method: 'POST',
      url: 'https://api.example.com',
      headers: [{ key: 'Content-Type', value: 'application/json' }],
      body: '{"expr":"{a} + {{b}}"',
    })

    expect(result.errors).toContain('Invalid placeholder {a}. Use {{a}}.')
    expect(result.errors).toContain('Body must be valid JSON when Content-Type is application/json.')
  })

  it('keeps declared parameter types while repairing an empty legacy schema', () => {
    const result = inspectHttpToolContract(
      {
        protocol: 'http',
        method: 'POST',
        url: 'https://api.example.com',
        headers: [{ key: 'Content-Type', value: 'application/json' }],
        body: '{"limit":"{{limit}}"}',
      },
      {
        type: 'object',
        properties: { limit: { type: 'integer' } },
        required: [],
      },
    )

    expect(result.inputSchema).toMatchObject({
      properties: { limit: { type: 'integer' } },
      required: ['limit'],
    })
  })
})
