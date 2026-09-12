import { SectionBlock } from '@woobe/ui'
import type { BehaviorSpecification } from '../types'
import { behaviorFields } from '../behavior'

export function AgentBehaviorDetails({ behavior, legacyPrompt }: { behavior?: BehaviorSpecification | null; legacyPrompt?: string }) {
  return (
    <SectionBlock
      density="compact"
      eyebrow="Behavior"
      title={behavior ? 'Behavior contract' : 'Legacy Agent Instructions'}
      className="bg-background/25"
    >
      {behavior ? (
        <dl className="divide-y divide-border/50 border-t border-border/60">
          {behaviorFields.map(({ specKey, label }) => {
            const value = behavior[specKey]
            const empty = Array.isArray(value) ? value.length === 0 : !value
            return (
              <div key={specKey} className="grid gap-1 py-2 sm:grid-cols-[132px_minmax(0,1fr)] sm:gap-3">
                <dt className="font-mono text-[8px] text-muted-foreground">{label}</dt>
                <dd className={`min-w-0 whitespace-pre-wrap break-words font-sans text-[9px] leading-4 ${empty ? 'text-muted-foreground' : 'text-slate-200'}`}>
                  {Array.isArray(value)
                    ? value.length
                      ? <ul className="space-y-1">{value.map((item, index) => <li key={index} className="flex gap-2"><span className="mt-[7px] h-1 w-1 shrink-0 rounded-full bg-muted-foreground" /><span>{item}</span></li>)}</ul>
                      : 'Not configured'
                    : value || 'Not configured'}
                </dd>
              </div>
            )
          })}
        </dl>
      ) : (
        <p className="scrollbar-thin max-h-56 overflow-y-auto whitespace-pre-wrap break-words border-t border-border/60 pt-2.5 font-sans text-[9px] leading-4 text-slate-200">{legacyPrompt || 'No instructions stored.'}</p>
      )}
    </SectionBlock>
  )
}
