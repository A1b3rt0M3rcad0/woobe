import { describe, expect, it } from 'vitest'

import { credentialDisplayLabel } from './AgentModelStep'
import { firstRunAgentStepCopy } from './FirstRunAgentSetup'

describe('first-run Agent setup', () => {
  it('keeps a stable three-step hierarchy', () => {
    expect(firstRunAgentStepCopy('details')).toEqual({
      title: 'Define the Agent',
      description: 'Set its identity and initial behavior before choosing the model.',
    })
    expect(firstRunAgentStepCopy('model').title).toBe('Choose the Agent model')
    expect(firstRunAgentStepCopy('review').title).toBe('Review and create')
  })

  it('does not promote provider connection to an onboarding step', () => {
    const copy = ['details', 'model', 'review'] as const
    expect(copy).not.toContain('connect-provider')
  })

  it('does not duplicate the provider name in connection labels', () => {
    expect(credentialDisplayLabel({ name: 'OpenRouter', provider: 'openrouter' })).toBe('OpenRouter')
    expect(credentialDisplayLabel({ name: 'Production', provider: 'openrouter' })).toBe('Production · OpenRouter')
  })
})