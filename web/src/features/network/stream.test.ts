import { describe, expect, it } from 'vitest'

import { parseSseBlock } from './stream'

describe('parseSseBlock', () => {
  it('parses typed events and sequence ids', () => {
    expect(parseSseBlock('id: 4\nevent: agent_activity\ndata: {"sequence":4}')).toEqual({
      id: '4',
      event: 'agent_activity',
      data: '{"sequence":4}',
    })
  })

  it('joins multiple data lines', () => {
    expect(parseSseBlock('event: token\ndata: first\ndata: second')?.data).toBe('first\nsecond')
  })
})
