import { Activity, Database } from 'lucide-react'

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
    <section className={cn(!compact && 'rounded-xl border border-border bg-surface p-4')} aria-label="Session Mode">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wider text-muted">Session Mode</p>
          <p className="mt-1 text-xs leading-5 text-muted">Controls continuity between Runs.</p>
        </div>
        {definedBy ? <span className="shrink-0 rounded border border-border bg-background/50 px-2 py-1 font-mono text-[9px] text-muted">{definedBy}</span> : null}
      </div>

      <div role="group" aria-label="Session mode options" className="mt-3 grid grid-cols-2 gap-1 rounded-lg border border-border bg-background/35 p-1">
        {options.map(({ value, title, icon: Icon }) => {
          const selected = state.sessionMode === value
          return (
            <button
              key={value}
              type="button"
              disabled={readOnly}
              onClick={() => setField('sessionMode', value)}
              className={cn(
                'flex min-w-0 items-center justify-center gap-2 rounded-md border border-transparent px-3 py-2 text-xs font-semibold transition-colors disabled:cursor-default',
                selected
                  ? 'border-primary/35 bg-primary/10 text-white'
                  : 'text-muted hover:bg-accent/25 hover:text-white',
                readOnly && !selected && 'opacity-45',
              )}
              aria-pressed={selected}
            >
              <Icon className={cn('h-3.5 w-3.5 shrink-0', selected ? 'text-primary-light' : 'text-muted')} />
              <span>{title}</span>
            </button>
          )
        })}
      </div>

      <div className="mt-3 rounded-lg border border-border/70 bg-background/25 px-3 py-2.5">
        <p className="text-[11px] leading-5 text-muted">{selectedOption.description}</p>
      </div>
    </section>
  )
}
