export type ToolTemplateNamespace = 'external_context' | 'project_env'

export interface ToolTemplateSymbol {
  namespace: ToolTemplateNamespace
  name: string
  detail?: string
  description?: string
}

export interface ToolTemplateAutocompleteContext {
  openIndex: number
  replaceStart: number
  replaceEnd: number
  namespace?: ToolTemplateNamespace
  query: string
  hasClosingBraces: boolean
}

export interface ToolTemplateSuggestion {
  kind: 'namespace' | 'symbol'
  namespace: ToolTemplateNamespace
  label: string
  insertText: string
  detail?: string
  description?: string
}

const NAMESPACES: Array<{
  namespace: ToolTemplateNamespace
  label: string
  description: string
  search: string
}> = [
  {
    namespace: 'external_context',
    label: 'External Context',
    description: 'Values supplied by the execution External Context contract.',
    search: 'external context external_context context',
  },
  {
    namespace: 'project_env',
    label: 'Project Environment',
    description: 'Project-scoped values resolved from draft, staging or production.',
    search: 'project environment project_env env environment',
  },
]

function matches(query: string, ...values: string[]): boolean {
  const normalized = query.trim().toLowerCase()
  if (!normalized) return true
  return values.some((value) => value.toLowerCase().includes(normalized))
}

export function getToolTemplateAutocompleteContext(
  value: string,
  cursor: number,
): ToolTemplateAutocompleteContext | null {
  const safeCursor = Math.max(0, Math.min(cursor, value.length))
  const before = value.slice(0, safeCursor)
  const openIndex = before.lastIndexOf('{{')
  if (openIndex < 0) return null

  const innerBeforeCursor = before.slice(openIndex + 2)
  if (innerBeforeCursor.includes('}}')) return null

  const closeIndex = value.indexOf('}}', safeCursor)
  const hasClosingBraces = closeIndex >= 0
  const replaceStart = openIndex + 2
  const replaceEnd = hasClosingBraces ? closeIndex : safeCursor
  const trimmed = innerBeforeCursor.trimStart()
  const dotIndex = trimmed.indexOf('.')

  if (dotIndex < 0) {
    return {
      openIndex,
      replaceStart,
      replaceEnd,
      query: trimmed,
      hasClosingBraces,
    }
  }

  const rawNamespace = trimmed.slice(0, dotIndex).trim()
  const namespace = rawNamespace === 'external_context' || rawNamespace === 'project_env'
    ? rawNamespace
    : undefined

  if (!namespace) {
    return {
      openIndex,
      replaceStart,
      replaceEnd,
      query: rawNamespace,
      hasClosingBraces,
    }
  }

  return {
    openIndex,
    replaceStart,
    replaceEnd,
    namespace,
    query: trimmed.slice(dotIndex + 1),
    hasClosingBraces,
  }
}

export function buildToolTemplateSuggestions(
  context: ToolTemplateAutocompleteContext | null,
  symbols: ToolTemplateSymbol[],
): ToolTemplateSuggestion[] {
  if (!context) return []

  if (!context.namespace) {
    return NAMESPACES
      .filter((item) => matches(context.query, item.namespace, item.label, item.search))
      .sort((left, right) => {
        const query = context.query.toLowerCase()
        const leftPrefix = left.namespace.startsWith(query) ? 0 : 1
        const rightPrefix = right.namespace.startsWith(query) ? 0 : 1
        return leftPrefix - rightPrefix || left.label.localeCompare(right.label)
      })
      .map((item) => ({
        kind: 'namespace' as const,
        namespace: item.namespace,
        label: item.label,
        insertText: `${item.namespace}.`,
        detail: item.namespace,
        description: item.description,
      }))
  }

  return symbols
    .filter((symbol) => (
      symbol.namespace === context.namespace
      && matches(context.query, symbol.name, symbol.detail || '', symbol.description || '')
    ))
    .sort((left, right) => {
      const query = context.query.toLowerCase()
      const leftPrefix = left.name.toLowerCase().startsWith(query) ? 0 : 1
      const rightPrefix = right.name.toLowerCase().startsWith(query) ? 0 : 1
      return leftPrefix - rightPrefix || left.name.localeCompare(right.name)
    })
    .map((symbol) => ({
      kind: 'symbol' as const,
      namespace: symbol.namespace,
      label: symbol.name,
      insertText: `${symbol.namespace}.${symbol.name}`,
      detail: symbol.detail,
      description: symbol.description,
    }))
}

export function applyToolTemplateSuggestion(
  value: string,
  context: ToolTemplateAutocompleteContext,
  suggestion: ToolTemplateSuggestion,
): { value: string; cursor: number } {
  const complete = suggestion.kind === 'symbol' && !context.hasClosingBraces
  const inserted = suggestion.insertText + (complete ? '}}' : '')
  const next = (
    value.slice(0, context.replaceStart)
    + inserted
    + value.slice(context.replaceEnd)
  )
  return {
    value: next,
    cursor: context.replaceStart + suggestion.insertText.length,
  }
}
