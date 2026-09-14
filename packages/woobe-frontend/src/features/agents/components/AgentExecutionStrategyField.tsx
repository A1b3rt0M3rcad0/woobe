import { Route } from 'lucide-react'
import { SegmentedControl } from '@woobe/ui'

import {
  executionStrategyFromRuntimeConfig,
  withExecutionStrategy,
  type AgentExecutionStrategy,
} from '@/features/agents/executionStrategy'
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
  const selected = executionStrategyFromRuntimeConfig(state.runtimeConfig)

  const options: Array<{
    value: AgentExecutionStrategy
    title: string
    description: string
  }> = [
    {
      value: 'standard',
      title: 'Standard',
      description: 'Uses the current Woobe model and capability loop while preserving the same Runtime lifecycle, persistence, policies, recovery, streaming, and observability guarantees.',
    },
  ]

  const selectedOption = options.find(option => option.value === selected) ?? options[0]

  return (
    <section className={cn(!compact && 'rounded-container border border-border bg-surface p-ui-lg')} aria-label="Execution Strategy">
      <div>
        <p className="font-mono text-system-meta font-semibold uppercase tracking-[0.1em] text-muted-foreground">Execution Strategy</p>
        <p className="mt-ui-xs font-sans text-product-caption text-muted-foreground">Controls how this Agent conducts model and capability execution.</p>
      </div>

      <div className="mt-ui-md">
        <SegmentedControl
          ariaLabel="Execution strategy options"
          value={selected}
          onValueChange={(value) => {
            setField(
              'runtimeConfig',
              withExecutionStrategy(
                state.runtimeConfig,
                value as AgentExecutionStrategy,
              ),
            )
          }}
          stretch
          size="compact"
          items={options.map(({ value, title }) => ({
            value,
            label: title,
            icon: <Route className="h-3.5 w-3.5" />,
            disabled: readOnly,
          }))}
          className="w-full"
        />
      </div>

      <div className="mt-ui-md rounded-container border border-border/70 bg-background/25 px-ui-md py-ui-sm">
        <p className="font-sans text-product-small text-muted-foreground">{selectedOption.description}</p>
      </div>
    </section>
  )
}
