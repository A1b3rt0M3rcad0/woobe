import { describe, expect, it } from 'vitest'

import {
  inspectHttpRouteContract,
  inspectHttpRouteDependencies,
  inspectHttpToolContract,
} from './httpToolContract'


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

  it('drops stale schema inputs after a placeholder becomes runtime-resolved', () => {
    const config = {
      protocol: 'http' as const,
      mode: 'group' as const,
      base_url: 'https://api.example.com',
      headers: [],
      routes: [],
    }
    const route = {
      id: 'route-1',
      name: 'Calculate',
      description: 'Calculate',
      method: 'GET',
      path: '/v4/?expr={{external_context.age}}%2B{{b}}',
      headers: [],
      input_schema: {
        type: 'object',
        properties: {
          a: { type: 'integer' },
          b: { type: 'integer' },
        },
        required: ['a', 'b'],
      },
    }

    const result = inspectHttpRouteContract(config, route)

    expect(result.parameterNames).toEqual(['b'])
    expect(result.inputSchema).toMatchObject({
      properties: { b: { type: 'integer' } },
      required: ['b'],
    })
  })

  it('lists every request dependency with its source and usage', () => {
    const config = {
      protocol: 'http' as const,
      mode: 'group' as const,
      base_url: '{{project_env.API_URL}}',
      headers: [
        { key: 'Authorization', value: 'Bearer {{project_env.API_KEY}}' },
      ],
      routes: [],
    }
    const route = {
      id: 'route-1',
      name: 'Calculate',
      description: 'Calculate',
      method: 'POST',
      path: '/v4/{{external_context.customer_id}}?expr={{external_context.age}}%2B{{b}}',
      headers: [{ key: 'X-Customer', value: '{{external_context.customer_id}}' }],
      body: '{"query":"{{b}}","tenant":"{{external_context.tenant_id}}"}',
    }
    const preview = inspectHttpRouteContract(config, route)
    const dependencies = inspectHttpRouteDependencies(config, route, preview.inputSchema)

    expect(dependencies).toEqual([
      {
        field: 'API_URL',
        source: 'project_env',
        usages: ['Base URL'],
        required: true,
      },
      {
        field: 'customer_id',
        source: 'external_context',
        usages: ['Path', 'Header · X-Customer'],
        required: true,
      },
      {
        field: 'age',
        source: 'external_context',
        usages: ['Query'],
        required: true,
      },
      {
        field: 'b',
        source: 'agent',
        usages: ['Query', 'Body'],
        required: true,
        type: 'string',
      },
      {
        field: 'API_KEY',
        source: 'project_env',
        usages: ['Header · Authorization'],
        required: true,
      },
      {
        field: 'tenant_id',
        source: 'external_context',
        usages: ['Body'],
        required: true,
      },
    ])
  })

  it('shows legacy HTTP bindings as runtime dependencies without exposing a source editor', () => {
    const config = {
      protocol: 'http' as const,
      mode: 'group' as const,
      base_url: 'https://api.example.com',
      headers: [],
      routes: [],
    }
    const route = {
      id: 'route-1',
      name: 'Legacy',
      description: 'Legacy binding',
      method: 'GET',
      path: '/customers/{{customer}}',
      headers: [],
      bindings: {
        customer: { source: { kind: 'context' as const, field: 'customer_id' } },
      },
    }
    const preview = inspectHttpRouteContract(config, route)

    expect(inspectHttpRouteDependencies(config, route, preview.inputSchema)).toEqual([
      {
        field: 'customer_id',
        source: 'external_context',
        usages: ['Path'],
        required: true,
        legacyBinding: true,
      },
    ])
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
