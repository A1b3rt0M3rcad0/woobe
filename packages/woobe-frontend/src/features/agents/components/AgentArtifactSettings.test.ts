import { describe, expect, it } from 'vitest'
import { availableBindingField, synchronizeBindingContract } from './AgentArtifactSettings'

describe('Artifact binding authoring', () => {
  it('chooses an unused External Context field without replacing user data', () => {
    const contract = {
      fields: {
        artifact_workspace: { schema: { type: 'string' }, description: 'Application-owned field' },
        artifact_workspace_2: { schema: { type: 'integer' }, required: false },
      },
      additionalProperties: false,
    }

    expect(availableBindingField(contract)).toBe('artifact_workspace_3')
    expect(synchronizeBindingContract(contract, null, 'artifact_workspace', 'session')).toBeNull()
    expect(contract.fields.artifact_workspace).toEqual({ schema: { type: 'string' }, description: 'Application-owned field' })
  })

  it('preserves the External Context wrapper while adding the private selector', () => {
    const contract = {
      fields: { account_id: { schema: { type: 'string' }, required: true } },
      additionalProperties: false,
    }

    const result = synchronizeBindingContract(contract, null, 'artifact_workspace', 'session')

    expect(result).toMatchObject({ additionalProperties: false, fields: {
      account_id: { schema: { type: 'string' }, required: true },
      artifact_workspace: { schema: { type: 'string', minLength: 1, maxLength: 128 }, required: true, scope: 'session', model: { expose: false } },
    } })
  })
})
