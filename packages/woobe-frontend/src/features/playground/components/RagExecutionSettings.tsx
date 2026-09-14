import { Select } from '@woobe/ui'

import type { RagStrategyDescriptor } from '@/features/knowledge/ragStrategies'

function formatStrategyName(name: string): string {
  const words = name.replace(/[-_]+/g, ' ').trim().split(/\s+/).filter(Boolean)
  const label = words
    .map((word) => word.toLowerCase() === 'rag'
      ? 'RAG'
      : `${word.charAt(0).toUpperCase()}${word.slice(1).toLowerCase()}`)
    .join(' ')
  if (!label) return 'RAG'
  return /\bRAG$/i.test(label) ? label : `${label} RAG`
}

export interface RagExecutionSettingsProps {
  value: string
  strategies: RagStrategyDescriptor[]
  isLoading?: boolean
  onChange: (strategy: string) => void
}

export function RagExecutionSettings({
  value,
  strategies,
  isLoading = false,
  onChange,
}: RagExecutionSettingsProps) {
  const registered = strategies.find((strategy) => strategy.name === value)
  const fallback: RagStrategyDescriptor = {
    name: value,
    display_name: formatStrategyName(value),
    description: strategies.length > 0
      ? 'This strategy is configured in the Draft but is not registered by the current runtime.'
      : 'RAG execution strategy configured for this Agent Draft.',
    is_default: value === 'classic',
  }
  const current = registered ?? fallback
  const catalog = registered || strategies.length === 0
    ? strategies.length > 0 ? strategies : [fallback]
    : [fallback, ...strategies]

  return (
    <div className="grid gap-ui-md">
      <label className="block">
        <span className="mb-ui-xs block font-mono text-chrome-label text-muted-foreground">
          RAG Strategy
        </span>
        <Select
          aria-label="RAG Strategy"
          value={value}
          disabled={isLoading && strategies.length === 0}
          onChange={(event) => onChange(event.target.value)}
          options={catalog.map((strategy) => ({
            value: strategy.name,
            label: strategy.display_name,
          }))}
        />
      </label>

      <div className="rounded-container border border-border bg-background/25 p-ui-md">
        <div className="flex items-center justify-between gap-ui-md">
          <p className="font-mono text-chrome-label font-semibold text-slate-100">
            {current.display_name}
          </p>
          {current.is_default ? (
            <span className="font-mono text-chrome-meta uppercase tracking-wide text-primary-light">
              Default
            </span>
          ) : null}
        </div>
        <p className="mt-ui-xs font-sans text-product-caption leading-relaxed text-muted-foreground">
          {current.description}
        </p>
        {!registered && strategies.length > 0 ? (
          <p className="mt-ui-sm border-l-2 border-l-amber-400/70 pl-ui-sm font-sans text-product-caption text-amber-200/90">
            Select a registered strategy before saving this Draft.
          </p>
        ) : null}
      </div>
    </div>
  )
}
