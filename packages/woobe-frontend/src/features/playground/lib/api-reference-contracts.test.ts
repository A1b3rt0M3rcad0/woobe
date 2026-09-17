import { describe, expect, it } from 'vitest'
import {
  buildApiReferenceForSlot,
  runtimeCurl,
} from './api-reference-contracts'


describe('public API reference contract', () => {
  it('keeps internal routing fields out of the public request', () => {
    const reference = buildApiReferenceForSlot({
      slot: 'production',
      release: null,
    })

    expect(reference.request).toEqual({ message: 'Hello!' })
    expect(reference.request).not.toHaveProperty('project_id')
    expect(reference.request).not.toHaveProperty('agent_id')
    expect(reference.request).not.toHaveProperty('execution_context')
  })

  it('documents the canonical protocol v2 identity for semantic stream events', () => {
    const reference = buildApiReferenceForSlot({
      slot: 'production',
      release: null,
    })

    expect(reference.stream_events.token.data).toMatchObject({
      protocol_version: 2,
      event_id: '<uuid>',
      run_id: '<uuid>',
      session_id: '<uuid>',
      run_kind: 'AGENT',
      sequence: 1,
      type: 'token',
      payload: expect.objectContaining({ content: '<partial token>' }),
    })
    expect(reference.stream_events.heartbeat.data).toEqual({
      protocol_version: 2,
      type: 'heartbeat',
      occurred_at: '<iso datetime>',
    })
    expect(reference.sync_response_contract.data.session_id).toBe('<uuid>')
  })

  it('generates an authenticated public runtime curl', () => {
    const curl = runtimeCurl('https://api.example.com')

    expect(curl).toContain('https://api.example.com/v1/run')
    expect(curl).toContain('Authorization: Bearer $WOOBE_API_KEY')
    expect(curl).not.toContain('project_id')
    expect(curl).not.toContain('agent_id')
    expect(curl).not.toContain('execution_context')
    expect(curl).not.toContain('localhost')
  })
})