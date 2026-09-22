import { describe, expect, it } from 'vitest'

import type { Tool } from './types'
import {
  collectToolRuntimeDependencies,
  getToolRuntimeCompatibility,
} from './toolRuntimeDependencies'


function tool(config: Record<string, unknown>): Tool {
  return {
    id: 'tool-1',
    project_id: 'project-1',
    name: 'Customer Tool',
    type: 'http',
    config,
    risk_level: 'low',
    status: 'active',
  }
}

describe('toolRuntimeDependencies', () => {
  it('collects every external context field and project environment key', () => {
    const dependencies = collectToolRuntimeDependencies(tool({
      url: 'https://api.example.com/{{external_context.age}}',
      headers: [
        { key: 'X-Title', value: '{{external_context.title}}' },
        { key: 'Authorization', value: 'Bearer {{project_env.API_KEY}}' },
      ],
      routes: [
        {
          id: 'lookup',
          bindings: {
            tenant: {
              source: {
                kind: 'context',
                field: 'tenant_id',
              },
            },
            token: {
              source: {
                kind: 'project_environment',
                field: 'CRM_TOKEN',
              },
            },
          },
        },
      ],
    }))

    expect([...dependencies.externalContextFields].sort()).toEqual([
      'age',
      'tenant_id',
      'title',
    ])
    expect([...dependencies.projectEnvironmentKeys].sort()).toEqual([
      'API_KEY',
      'CRM_TOKEN',
    ])
  })

  it('requires the agent to contain every external context field', () => {
    const candidate = tool({
      body: {
        age: '{{external_context.age}}',
        title: '{{external_context.title}}',
      },
    })

    const result = getToolRuntimeCompatibility(
      candidate,
      new Set(['age']),
      new Set(),
    )

    expect(result.compatible).toBe(false)
    expect(result.missingExternalContext).toEqual(['title'])
  })

  it('accepts a tool only when all agent fields and project keys exist', () => {
    const candidate = tool({
      url: 'https://api.example.com/{{external_context.age}}',
      headers: [
        { key: 'X-Title', value: '{{external_context.title}}' },
        { key: 'Authorization', value: 'Bearer {{project_env.CRM_TOKEN}}' },
      ],
    })

    const result = getToolRuntimeCompatibility(
      candidate,
      new Set(['age', 'title', 'customer_id']),
      new Set(['CRM_TOKEN', 'OTHER_KEY']),
    )

    expect(result).toEqual({
      compatible: true,
      missingExternalContext: [],
      missingProjectEnvironment: [],
      projectEnvironmentUnavailable: false,
    })
  })
})
