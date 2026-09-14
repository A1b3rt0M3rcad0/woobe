import { Route } from 'lucide-react'
import { Select } from '@woobe/ui'

import {
  executionStrategyDescriptor,
  executionStrategyFromRuntimeConfig,
  executionStrategySelectOptions,
  withExecutionStrategy,
} from '@/features/agents/executionStrategy'
import { useExecutionStrategies } from '@/features/agents/hooks'
import { useAgentEditor } from '@/features/playground/AgentEditorContext'
import { cn } from '@/lib/utils'

export function AgentExecutionStrategyField({
  readOnly = false,
  compact = false,
}: {
  readOnly?: boolean
  compact?: boolean
}) {
  const { state, setField } = useAgentEditor()
  const { data: strategies = [], isLoading, isError } = useExecutionStrategies()
  const selected = executionStrategyFromRuntimeConfig(state.runtimeConfig)
  const selectedDescriptor = executionStrategyDescriptor(strategies, selected)
  const options = executionStrategySelectOptions(strategies, selected)
  const catalogReady = !isLoading && !isError && strategies.length > 0
  const disabled = readOnly || !catalogReady

  const description = selectedDescriptor?.description
    ?? (isLoading
      ? 'Loading registered execution strategies…'
      : isError
        ? 'The current snapshot selection remains visible, but the strategy catalog is unavailable.'
        : 'The current snapshot selection is not present in the active strategy catalog.')

  return (
    <section className={cn(!compact && 'rounded-container border border-border bg-surface p-ui-lg')} aria-label="Execution Strategy">
      <div>
        <p className="font-mono text-system-meta font-semibold uppercase tracking-[0.1em] text-muted-foreground">Execution Strategy</p>
        <p className="mt-ui-xs font-sans text-product-caption text-muted-foreground">Controls how this Agent conducts model and capability execution.</p>
      </div>

      <div className="mt-ui-md rounded-container border border-border bg-background/35 p-ui-md">
        <div className="flex items-center gap-ui-sm">
          <span className="flex h-control-segment w-control-segment shrink-0 items-center justify-center rounded-control border border-primary/20 bg-primary/10 text-primary-light">
            <Route className="h-3.5 w-3.5" />
          </span>
          <div className="min-w-0 flex-1">
            <Select
              aria-label="Execution Strategy"
              value={selected}
              disabled={disabled}
              options={options}
              onChange={(event) => {
                setField(
                  'runtimeConfig',
                  withExecutionStrategy(state.runtimeConfig, event.target.value),
                )
              }}
            />
          </div>
        </div>

        <p className="mt-ui-sm font-sans text-product-small text-muted-foreground">{description}</p>
        {selectedDescriptor?.behavior ? (
          <p className="mt-ui-xs font-sans text-product-caption text-muted-foreground/80">{selectedDescriptor.behavior}</p>
        ) : null}
        {readOnly ? (
          <p className="mt-ui-sm font-mono text-system-meta uppercase tracking-[0.08em] text-muted-foreground">Locked by snapshot</p>
        ) : null}
      </div>
    </section>
  )
}
