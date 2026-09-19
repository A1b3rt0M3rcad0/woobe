import { describe, expect, it } from 'vitest'

import {
  applyToolTemplateSuggestion,
  buildToolTemplateSuggestions,
  getToolTemplateAutocompleteContext,
} from './toolTemplateAutocomplete'
import type { ToolTemplateSymbol } from './toolTemplateAutocomplete'

const symbols: ToolTemplateSymbol[] = [
  {
    namespace: 'external_context',
    name: 'customer_id',
    detail: 'string · required',
  },
  {
    namespace: 'project_env',
    name: 'API_KEY',
    detail: 'Secret · D · S · P',
  },
  {
    namespace: 'project_env',
    name: 'API_URL',
    detail: 'Value · D · S · P',
  },
]

describe('tool template autocomplete', () => {
  it('suggests namespaces after {{', () => {
    const context = getToolTemplateAutocompleteContext('{{', 2)
    expect(buildToolTemplateSuggestions(context, symbols).map((item) => item.namespace)).toEqual([
      'external_context',
      'project_env',
    ])
  })

  it('filters namespace from partial input', () => {
    const context = getToolTemplateAutocompleteContext('{{e', 3)
    expect(buildToolTemplateSuggestions(context, symbols).map((item) => item.namespace)).toEqual([
      'external_context',
    ])
  })

  it('supports fuzzy environment lookup', () => {
    const context = getToolTemplateAutocompleteContext('{{env', 5)
    expect(buildToolTemplateSuggestions(context, symbols).map((item) => item.namespace)).toEqual([
      'project_env',
    ])
  })

  it('suggests symbols for the selected namespace', () => {
    const context = getToolTemplateAutocompleteContext('{{project_env.API', 17)
    expect(buildToolTemplateSuggestions(context, symbols).map((item) => item.label)).toEqual([
      'API_KEY',
      'API_URL',
    ])
  })

  it('works when closing braces already exist', () => {
    const value = '{{project_env.API}}'
    const cursor = value.indexOf('}}')
    const context = getToolTemplateAutocompleteContext(value, cursor)
    expect(context?.hasClosingBraces).toBe(true)

    const suggestion = buildToolTemplateSuggestions(context, symbols)[0]
    expect(applyToolTemplateSuggestion(value, context!, suggestion)).toEqual({
      value: '{{project_env.API_KEY}}',
      cursor: '{{project_env.API_KEY'.length,
    })
  })

  it('adds closing braces only for a completed symbol in an open expression', () => {
    const value = 'Bearer {{project_env.API'
    const context = getToolTemplateAutocompleteContext(value, value.length)!
    const suggestion = buildToolTemplateSuggestions(context, symbols)[0]

    expect(applyToolTemplateSuggestion(value, context, suggestion).value).toBe(
      'Bearer {{project_env.API_KEY}}',
    )
  })

  it('replaces the remainder when cursor is in the middle of a closed expression', () => {
    const value = '{{project_env.API_URL}}'
    const cursor = '{{project_env.API'.length
    const context = getToolTemplateAutocompleteContext(value, cursor)!
    const suggestion = buildToolTemplateSuggestions(context, symbols)[0]

    expect(applyToolTemplateSuggestion(value, context, suggestion).value).toBe(
      '{{project_env.API_KEY}}',
    )
  })
})
