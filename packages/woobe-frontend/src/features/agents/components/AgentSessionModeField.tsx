import { Activity, Database } from 'lucide-react'
import { SegmentedControl } from '@woobe/ui'

import { useAgentEditor, type AgentSessionMode } from '@/features/playground/AgentEditorContext'
import { cn } from '@/lib/utils'

export function AgentSessionModeField({
  readOnly = false,
  definedBy,
  compact = false,
}: {
  readOnly?: boolean
  definedBy?: string | null
  compact?: boolean
}) {
  const { state, setField } = useAgentEditor()

  const options: Array<{
    value: AgentSessionMode
    title: string
    description: string
    icon: typeof Database
  }> = [
    {
      value: 'stateful',
      title: 'Stateful',
      description: 'Persists Agent history between Runs in the same Session.',
      icon: Database,
    },
    {
      value: 'stateless',
      title: 'Stateless',
      description: 'Receives explicit input for each Run and does not preserve Agent Session history.',
      icon: Activity,
    },
  ]

  const selectedOption = options.find(option => option.value === state.sessionMode) ?? options[0]

  return (
    <section className={cn(!compact && 'rounded-container border border-border bg-surface p-ui-lg')} aria-label="Session Mode">
      <div className="flex items-start justify-between gap-ui-md">
        <div>
          <p className="font-mono text-system-meta font-semibold uppercase tracking-[0.1em] text-muted-foreground">Session Mode</p>
          <p className="mt-ui-xs font-sans text-product-caption text-muted-foreground">Controls continuity between Runs.</p>
        </div>
        {definedBy ? <span className="shrink-0 rounded-technical border border-border bg-background/50 px-ui-sm py-ui-xs font-mono text-system-meta text-muted-foreground">{definedBy}</span> : null}
      </div>

      <div className="mt-ui-md">
        <SegmentedControl
          ariaLabel="Session mode options"
          value={state.sessionMode}
          onValueChange={(value) => setField('sessionMode', value as AgentSessionMode)}
          stretch
          size="compact"
          items={options.map(({ value, title, icon: Icon }) => ({
            value,
            label: title,
            icon: <Icon className="h-3.5 w-3.5" />,
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
