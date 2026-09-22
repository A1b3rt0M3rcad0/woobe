import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it, vi } from 'vitest'

import {
  invalidToolInputBindingTargets,
  normalizeToolInputBindings,
  toolInputBindingsForSchema,
  ToolInputBindingsEditor,
  toolInputDescriptors,
} from './ToolInputBindingsEditor'

describe('ToolInputBindingsEditor', () => {
  const schema = {
    type: 'object',
    properties: {
      customer_id: { type: 'string' },
      limit: { type: 'integer' },
    },
    required: ['customer_id'],
  }

  it('renders Agent, External Context and Project Environment sources in one compact input contract', () => {
    const html = renderToStaticMarkup(
      <ToolInputBindingsEditor
        schema={schema}
        bindings={{
          customer_id: {
            source: { kind: 'context', field: 'customer_id' },
          },
        }}
        onChange={vi.fn()}
      />,
    )

    expect(html).toContain('customer_id')
    expect(html).toContain('limit')
    expect(html).toContain('External Context')
    expect(html).toContain('Project Environment')
    expect(html).toContain('Model-provided')
    expect(html).toContain('customer_id External Context field')
  })

  it('derives required/type metadata from the input schema', () => {
    expect(toolInputDescriptors(schema)).toEqual([
      { name: 'customer_id', type: 'string', required: true },
      { name: 'limit', type: 'integer', required: false },
    ])
  })

  it('drops stale bindings when an input no longer exists in the schema', () => {
    expect(toolInputBindingsForSchema(schema, {
      customer_id: { source: { kind: 'context', field: 'customer_id' } },
      removed_input: { source: { kind: 'context', field: 'old_value' } },
    })).toEqual({
      customer_id: { source: { kind: 'context', field: 'customer_id' } },
    })
  })

  it('normalizes fields for persistence and detects incomplete bindings', () => {
    expect(normalizeToolInputBindings({
      customer_id: { source: { kind: 'context', field: ' customer_id ' } },
      limit: { source: { kind: 'project_environment', field: ' API_LIMIT ' } },
    })).toEqual({
      customer_id: { source: { kind: 'context', field: 'customer_id' } },
      limit: { source: { kind: 'project_environment', field: 'API_LIMIT' } },
    })

    expect(invalidToolInputBindingTargets({
      customer_id: { source: { kind: 'context', field: '   ' } },
    })).toEqual(['customer_id'])
  })
})
