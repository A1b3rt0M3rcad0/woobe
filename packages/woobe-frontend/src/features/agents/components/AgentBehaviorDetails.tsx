import type { BehaviorSpecification } from '../types'
import { behaviorFields } from '../behavior'

export function AgentBehaviorDetails({ behavior, legacyPrompt }: { behavior?: BehaviorSpecification | null; legacyPrompt?: string }) {
  return <section className="rounded-xl border border-border/80 bg-background/35 p-4">
    <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-300">{behavior ? 'Behavior' : 'Legacy Agent Instructions'}</h3>
    {behavior ? <dl className="mt-3 space-y-4">
      {behaviorFields.map(({ specKey, label }) => {
        const value = behavior[specKey]
        return <div key={specKey}>
          <dt className="text-xs font-medium text-muted">{label}</dt>
          <dd className="mt-1 break-words whitespace-pre-wrap text-xs leading-5 text-slate-200">{Array.isArray(value)
            ? value.length ? <ul className="list-disc space-y-1 pl-4">{value.map((item, index) => <li key={index}>{item}</li>)}</ul> : 'Not configured'
            : value || 'Not configured'}</dd>
        </div>
      })}
    </dl> : <p className="mt-3 max-h-64 overflow-y-auto whitespace-pre-wrap break-words text-xs leading-5 text-slate-200">{legacyPrompt || 'No instructions stored.'}</p>}
  </section>
}
