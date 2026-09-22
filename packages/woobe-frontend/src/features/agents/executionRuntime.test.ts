import { describe, expect, it } from 'vitest'

import {
  DEFAULT_INTERMEDIATE_MESSAGES_ENABLED,
  intermediateMessagesEnabledFromRuntimeConfig,
  withIntermediateMessagesEnabled,
} from './executionRuntime'

describe('Agent execution runtime config', () => {
  it('keeps historical Agents final-only', () => {
    expect(DEFAULT_INTERMEDIATE_MESSAGES_ENABLED).toBe(false)
    expect(intermediateMessagesEnabledFromRuntimeConfig({})).toBe(false)
    expect(intermediateMessagesEnabledFromRuntimeConfig({
      execution_strategy: 'standard',
    })).toBe(false)
  })

  it('reads the explicit execution policy', () => {
    expect(intermediateMessagesEnabledFromRuntimeConfig({
      execution: { intermediate_messages: true },
    })).toBe(true)
    expect(intermediateMessagesEnabledFromRuntimeConfig({
      execution: { intermediate_messages: false },
    })).toBe(false)
  })

  it('updates only the intermediate message setting', () => {
    expect(withIntermediateMessagesEnabled({
      execution_strategy: 'standard',
      execution: { future_setting: 'keep-me' },
      tools: { tool_ids: ['tool-1'] },
    }, true)).toEqual({
      execution_strategy: 'standard',
      execution: {
        future_setting: 'keep-me',
        intermediate_messages: true,
      },
      tools: { tool_ids: ['tool-1'] },
    })
  })
})
