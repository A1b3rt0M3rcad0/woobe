import { MessageSquareMore } from 'lucide-react'
import { SegmentedControl } from '@woobe/ui'

import {
  intermediateMessagesEnabledFromRuntimeConfig,
  withIntermediateMessagesEnabled,
} from '@/features/agents/executionRuntime'
import { useAgentEditor } from '@/features/playground/AgentEditorContext'
import { cn } from '@/lib/utils'

export function AgentIntermediateMessagesField({
  readOnly = false,
  compact = false,
}: {
  readOnly?: boolean
  compact?: boolean
}) {
  const { state, setField } = useAgentEditor()
  const enabled = intermediateMessagesEnabledFromRuntimeConfig(state.runtimeConfig)

  return (
    <section
      className={cn(!compact && 'rounded-container border border-border bg-surface p-ui-lg')}
      aria-label="Intermediate Messages"
    >
      <div className="flex items-start gap-ui-sm">
        <span className="flex h-control-sm w-control-sm shrink-0 items-center justify-center rounded-control border border-primary/20 bg-primary/10 text-primary-light">
          <MessageSquareMore className="h-icon w-icon" />
        </span>
        <div className="min-w-0">
          <p className="font-mono text-system-meta font-semibold uppercase tracking-[0.1em] text-muted-foreground">
            Intermediate Messages
          </p>
          <p className="mt-ui-xs font-sans text-product-caption text-muted-foreground">
            Controls whether this Agent publishes and persists Assistant messages while a Run is still executing.
          </p>
        </div>
      </div>

      <div className="mt-ui-md">
        <SegmentedControl
          ariaLabel="Intermediate Assistant message delivery"
          value={enabled ? 'enabled' : 'final_only'}
          onValueChange={(value) => {
            if (readOnly) return
            setField(
              'runtimeConfig',
              withIntermediateMessagesEnabled(
                state.runtimeConfig,
                value === 'enabled',
              ),
            )
          }}
          stretch
          size="compact"
          items={[
            {
              value: 'final_only',
              label: 'Final only',
              disabled: readOnly,
            },
            {
              value: 'enabled',
              label: 'Intermediate + final',
              disabled: readOnly,
            },
          ]}
          className="w-full"
        />
      </div>

      <div className="mt-ui-md rounded-container border border-border/70 bg-background/25 px-ui-md py-ui-sm">
        <p className="font-sans text-product-small text-muted-foreground">
          {enabled
            ? 'Public bridges may receive durable intermediate Assistant messages before the terminal answer.'
            : 'The Agent keeps in-progress communication internal and only publishes the terminal Assistant answer.'}
        </p>
      </div>
    </section>
  )
}
