import { Activity, Database } from 'lucide-react'

import { useAgentEditor, type AgentSessionMode } from '@/features/playground/AgentEditorContext'
import { cn } from '@/lib/utils'

export function AgentSessionModeField({
  readOnly = false,
  definedBy,
}: {
  readOnly?: boolean
  definedBy?: string | null
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
      description: 'Receives explicit input, responds and keeps no Agent Session.',
      icon: Activity,
    },
  ]

  return (
    <section className="rounded-xl border border-border bg-surface p-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wider text-muted">Runtime behavior</p>
          <p className="mt-1 text-xs text-muted">Session mode is part of the Agent snapshot and changes through the release flow.</p>
        </div>
        {definedBy ? <span className="shrink-0 rounded border border-border bg-background/50 px-2 py-1 font-mono text-[9px] text-muted">{definedBy}</span> : null}
      </div>

      <div className="mt-3 grid grid-cols-2 gap-2">
        {options.map(({ value, title, description, icon: Icon }) => {
          const selected = state.sessionMode === value
          return (
            <button
              key={value}
              type="button"
              disabled={readOnly}
              onClick={() => setField('sessionMode', value)}
              className={cn(
                'rounded-xl border p-3 text-left transition-colors disabled:cursor-default',
                selected
                  ? 'border-primary/35 bg-primary/10 text-white'
                  : 'border-border/80 bg-background/35 text-muted hover:border-primary/25 hover:text-white',
                readOnly && !selected && 'opacity-45',
              )}
              aria-pressed={selected}
            >
              <div className="flex items-center gap-2">
                <Icon className={cn('h-3.5 w-3.5', selected ? 'text-primary-light' : 'text-muted')} />
                <span className="text-xs font-semibold">{title}</span>
              </div>
              <p className="mt-1.5 text-[10px] leading-4 text-muted">{description}</p>
            </button>
          )
        })}
      </div>
    </section>
  )
}
