import {
  createContext,
  useContext,
  useMemo,
  useRef,
  useState,
} from 'react'
import type { ComponentProps, KeyboardEvent, ReactNode } from 'react'

import { Input } from '@/components/ui/Input'
import { Textarea } from '@/components/ui/Textarea'
import { useAgent, useAgents } from '@/features/agents/hooks'
import type { Agent, ExternalContextContract } from '@/features/agents/types'
import { useProjectEnvironmentKeys } from '@/features/projects/hooks'
import {
  applyToolTemplateSuggestion,
  buildToolTemplateSuggestions,
  getToolTemplateAutocompleteContext,
} from '@/features/tools/toolTemplateAutocomplete'
import type {
  ToolTemplateAutocompleteContext,
  ToolTemplateSuggestion,
  ToolTemplateSymbol,
} from '@/features/tools/toolTemplateAutocomplete'

const TemplateSymbolsContext = createContext<ToolTemplateSymbol[]>([])

function agentContract(agent: Agent | undefined): ExternalContextContract {
  const raw = agent?.settings?.external_context_contract
  return raw && typeof raw === 'object' && !Array.isArray(raw)
    ? raw as ExternalContextContract
    : {}
}

function schemaType(field: ExternalContextContract[string]): string {
  const raw = field.schema?.type
  if (Array.isArray(raw)) return raw.map(String).join(' | ')
  return typeof raw === 'string' && raw ? raw : 'Any'
}

export function ToolTemplateAutocompleteProvider({
  projectId,
  agentId,
  children,
}: {
  projectId?: string
  agentId?: string | null
  children: ReactNode
}) {
  const environmentQuery = useProjectEnvironmentKeys(projectId)
  const agentQuery = useAgent(agentId || undefined)
  const agentsQuery = useAgents(agentId ? undefined : projectId)

  const symbols = useMemo<ToolTemplateSymbol[]>(() => {
    const environmentSymbols: ToolTemplateSymbol[] = (environmentQuery.data || []).map((item) => {
      const configured = (['draft', 'staging', 'production'] as const)
        .filter((environment) => item.values[environment]?.configured)
        .map((environment) => environment[0].toUpperCase())
        .join(' · ')
      return {
        namespace: 'project_env',
        name: item.key,
        detail: `${item.kind === 'secret' ? 'Secret' : 'Value'}${configured ? ` · ${configured}` : ' · Not configured'}`,
        description: item.kind === 'secret'
          ? 'Project Environment secret. The stored value is never exposed to the Agent.'
          : 'Project Environment value resolved from the Tool execution environment.',
      }
    })

    const sourceAgents = agentId
      ? (agentQuery.data ? [agentQuery.data] : [])
      : (agentsQuery.data || [])
    const fields = new Map<string, ExternalContextContract[string]>()
    for (const agent of sourceAgents) {
      for (const [name, field] of Object.entries(agentContract(agent))) {
        if (!fields.has(name)) fields.set(name, field)
      }
    }

    const externalSymbols: ToolTemplateSymbol[] = [...fields.entries()].map(([name, field]) => ({
      namespace: 'external_context',
      name,
      detail: `${schemaType(field)}${field.required ? ' · required' : ''}`,
      description: field.description || 'External Context field supplied by the execution contract.',
    }))

    return [...externalSymbols, ...environmentSymbols]
  }, [
    agentId,
    agentQuery.data,
    agentsQuery.data,
    environmentQuery.data,
  ])

  return (
    <TemplateSymbolsContext.Provider value={symbols}>
      {children}
    </TemplateSymbolsContext.Provider>
  )
}

function SuggestionMenu({
  suggestions,
  activeIndex,
  onSelect,
}: {
  suggestions: ToolTemplateSuggestion[]
  activeIndex: number
  onSelect: (suggestion: ToolTemplateSuggestion) => void
}) {
  if (!suggestions.length) return null
  return (
    <div className="absolute left-0 right-0 top-full z-[80] mt-1 max-h-64 overflow-auto rounded-lg border border-border bg-surface p-1 shadow-xl">
      {suggestions.map((suggestion, index) => (
        <button
          key={`${suggestion.namespace}:${suggestion.label}`}
          type="button"
          className={`flex w-full items-start gap-3 rounded-md px-3 py-2 text-left transition-colors ${
            index === activeIndex ? 'bg-primary/10' : 'hover:bg-background/70'
          }`}
          onMouseDown={(event) => {
            event.preventDefault()
            onSelect(suggestion)
          }}
        >
          <span className="min-w-0 flex-1">
            <span className="block truncate font-mono text-xs text-white">
              {suggestion.kind === 'namespace' ? suggestion.detail : suggestion.label}
            </span>
            {suggestion.detail && suggestion.kind === 'symbol' ? (
              <span className="mt-0.5 block truncate text-[10px] text-primary-light">
                {suggestion.detail}
              </span>
            ) : null}
            {suggestion.description ? (
              <span className="mt-0.5 block text-[10px] leading-4 text-muted">
                {suggestion.description}
              </span>
            ) : null}
          </span>
        </button>
      ))}
    </div>
  )
}

function useTemplateAutocomplete(
  value: string,
  onValueChange: (value: string) => void,
) {
  const symbols = useContext(TemplateSymbolsContext)
  const [context, setContext] = useState<ToolTemplateAutocompleteContext | null>(null)
  const [suggestions, setSuggestions] = useState<ToolTemplateSuggestion[]>([])
  const [activeIndex, setActiveIndex] = useState(0)

  const refresh = (nextValue: string, cursor: number | null) => {
    if (cursor == null) {
      setContext(null)
      setSuggestions([])
      return
    }
    const nextContext = getToolTemplateAutocompleteContext(nextValue, cursor)
    const nextSuggestions = buildToolTemplateSuggestions(nextContext, symbols)
    setContext(nextContext)
    setSuggestions(nextSuggestions)
    setActiveIndex(0)
  }

  const apply = (
    suggestion: ToolTemplateSuggestion,
    setCursor: (cursor: number) => void,
  ) => {
    if (!context) return
    const next = applyToolTemplateSuggestion(value, context, suggestion)
    onValueChange(next.value)
    setSuggestions([])
    setContext(null)
    setTimeout(() => {
      setCursor(next.cursor)
      if (suggestion.kind === 'namespace') {
        refresh(next.value, next.cursor)
      }
    }, 0)
  }

  const keyDown = (
    event: KeyboardEvent<HTMLInputElement | HTMLTextAreaElement>,
    setCursor: (cursor: number) => void,
  ) => {
    if (!suggestions.length) return
    if (event.key === 'ArrowDown') {
      event.preventDefault()
      setActiveIndex((current) => (current + 1) % suggestions.length)
      return
    }
    if (event.key === 'ArrowUp') {
      event.preventDefault()
      setActiveIndex((current) => (current - 1 + suggestions.length) % suggestions.length)
      return
    }
    if (event.key === 'Enter' || event.key === 'Tab') {
      event.preventDefault()
      apply(suggestions[activeIndex], setCursor)
      return
    }
    if (event.key === 'Escape') {
      event.preventDefault()
      setSuggestions([])
      setContext(null)
    }
  }

  return {
    suggestions,
    activeIndex,
    refresh,
    apply,
    keyDown,
    close: () => {
      setSuggestions([])
      setContext(null)
    },
  }
}

type TemplateInputProps = Omit<ComponentProps<typeof Input>, 'value' | 'onChange'> & {
  value: string
  onValueChange: (value: string) => void
}

export function ToolTemplateInput({
  value,
  onValueChange,
  ...props
}: TemplateInputProps) {
  const ref = useRef<HTMLInputElement | null>(null)
  const autocomplete = useTemplateAutocomplete(value, onValueChange)
  const setCursor = (cursor: number) => {
    ref.current?.focus()
    ref.current?.setSelectionRange(cursor, cursor)
  }

  return (
    <div className="relative">
      <Input
        {...props}
        ref={ref}
        value={value}
        onChange={(event) => {
          const cursor = event.currentTarget.selectionStart
          onValueChange(event.target.value)
          autocomplete.refresh(event.target.value, cursor)
        }}
        onFocus={(event) => autocomplete.refresh(value, event.currentTarget.selectionStart)}
        onClick={(event) => autocomplete.refresh(value, event.currentTarget.selectionStart)}
        onKeyUp={(event) => {
          if (!['ArrowDown', 'ArrowUp', 'Enter', 'Tab', 'Escape'].includes(event.key)) {
            autocomplete.refresh(event.currentTarget.value, event.currentTarget.selectionStart)
          }
        }}
        onKeyDown={(event) => autocomplete.keyDown(event, setCursor)}
        onBlur={() => setTimeout(autocomplete.close, 120)}
      />
      <SuggestionMenu
        suggestions={autocomplete.suggestions}
        activeIndex={autocomplete.activeIndex}
        onSelect={(suggestion) => autocomplete.apply(suggestion, setCursor)}
      />
    </div>
  )
}

type TemplateTextareaProps = Omit<ComponentProps<typeof Textarea>, 'value' | 'onChange'> & {
  value: string
  onValueChange: (value: string) => void
}

export function ToolTemplateTextarea({
  value,
  onValueChange,
  ...props
}: TemplateTextareaProps) {
  const ref = useRef<HTMLTextAreaElement | null>(null)
  const autocomplete = useTemplateAutocomplete(value, onValueChange)
  const setCursor = (cursor: number) => {
    ref.current?.focus()
    ref.current?.setSelectionRange(cursor, cursor)
  }

  return (
    <div className="relative">
      <Textarea
        {...props}
        ref={ref}
        value={value}
        onChange={(event) => {
          const cursor = event.currentTarget.selectionStart
          onValueChange(event.target.value)
          autocomplete.refresh(event.target.value, cursor)
        }}
        onFocus={(event) => autocomplete.refresh(value, event.currentTarget.selectionStart)}
        onClick={(event) => autocomplete.refresh(value, event.currentTarget.selectionStart)}
        onKeyUp={(event) => {
          if (!['ArrowDown', 'ArrowUp', 'Enter', 'Tab', 'Escape'].includes(event.key)) {
            autocomplete.refresh(value, event.currentTarget.selectionStart)
          }
        }}
        onKeyDown={(event) => autocomplete.keyDown(event, setCursor)}
        onBlur={() => setTimeout(autocomplete.close, 120)}
      />
      <SuggestionMenu
        suggestions={autocomplete.suggestions}
        activeIndex={autocomplete.activeIndex}
        onSelect={(suggestion) => autocomplete.apply(suggestion, setCursor)}
      />
    </div>
  )
}
