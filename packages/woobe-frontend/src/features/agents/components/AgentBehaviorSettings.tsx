import { useId } from 'react'
import { Plus, X } from 'lucide-react'
import { Input } from '@/components/ui/Input'
import { Textarea } from '@/components/ui/Textarea'
import { Button } from '@/components/ui/Button'
import { useAgentEditor } from '@/features/playground/AgentEditorContext'
import { behaviorFields, type AgentBehavior } from '../behavior'

export function AgentBehaviorFields({ behavior, onChange }: { behavior: AgentBehavior; onChange: (behavior: AgentBehavior) => void }) {
  const id = useId()
  const field = (definition: typeof behaviorFields[number]) => {
    const { key, label, help } = definition
    const value = behavior[key]
    const fieldId = `${id}-${key}`
    return <div key={key} className="space-y-2">
      <div className="flex items-center gap-1.5">
        <label id={`${fieldId}-label`} htmlFor={Array.isArray(value) ? undefined : fieldId} className="text-xs font-medium text-muted">{label}</label>
        <span tabIndex={0} title={help} aria-label={`${label}: ${help}`} className="cursor-help text-[10px] text-muted hover:text-primary-light focus:text-primary-light">(?)</span>
      </div>
      {Array.isArray(value) ? <div role="group" aria-labelledby={`${fieldId}-label`} className="space-y-2">
        {value.map((item, index) => <div key={index} className="flex items-start gap-1.5">
          <Textarea aria-label={`${label} ${index + 1}`} rows={2} className="min-h-0 resize-y text-xs leading-5" value={item} onChange={event => onChange({ ...behavior, [key]: value.map((current, itemIndex) => itemIndex === index ? event.target.value : current) })} />
          <Button type="button" size="sm" variant="ghost" className="h-8 w-8 shrink-0 p-0" aria-label={`Remove ${label.toLowerCase()} ${index + 1}`} onClick={() => onChange({ ...behavior, [key]: value.filter((_, itemIndex) => itemIndex !== index) })}><X className="h-3.5 w-3.5" /></Button>
        </div>)}
        <Button type="button" size="sm" variant="ghost" className="h-7 px-2 text-[11px]" aria-label={`Add ${label.toLowerCase()}`} onClick={() => onChange({ ...behavior, [key]: [...value, ''] })}><Plus className="mr-1 h-3 w-3" />{key === 'responsibilities' ? 'Add responsibility' : 'Add behavior'}</Button>
      </div> : <Textarea id={fieldId} value={value} onChange={event => onChange({ ...behavior, [key]: event.target.value })} rows={key === 'operatingInstructions' || key === 'additionalInstructions' ? 5 : 3} className="min-h-0 resize-y text-xs leading-5" />}
    </div>
  }
  return <section aria-label="Behavior" className="rounded-xl border border-border bg-surface p-4">
    <h3 className="text-xs font-semibold uppercase tracking-wider text-muted">Behavior</h3>
    <p className="mt-1 text-xs leading-5 text-muted">Define how this Agent should act.</p>
    <div className="mt-4 divide-y divide-border/70">
      {behaviorFields.slice(0, 6).map(definition => <div key={definition.key} className="py-4 first:pt-0">{field(definition)}</div>)}
      <details className="pt-4">
        <summary className="cursor-pointer text-xs font-medium text-muted hover:text-white">Advanced{behavior.additionalInstructions ? ' · Additional instructions configured' : ''}</summary>
        <div className="mt-4">{field(behaviorFields[6])}</div>
      </details>
    </div>
  </section>
}

export function AgentBehaviorSettings() {
  const { state, setField } = useAgentEditor()
  const id = useId()
  return <div className="space-y-4 p-4">
    <section aria-label="Agent Details" className="space-y-3 rounded-xl border border-border bg-surface p-4">
      <h3 className="text-xs font-semibold uppercase tracking-wider text-muted">Agent Details</h3>
      <label className="block text-xs font-medium text-muted" htmlFor={`${id}-name`}>Name</label>
      <Input id={`${id}-name`} value={state.name} onChange={event => setField('name', event.target.value)} />
      <label className="block text-xs font-medium text-muted" htmlFor={`${id}-description`}>Description</label>
      <Textarea id={`${id}-description`} rows={2} className="min-h-0 resize-y text-xs" value={state.description} onChange={event => setField('description', event.target.value)} placeholder="Role and specialization" />
    </section>
    <AgentBehaviorFields behavior={state.behavior} onChange={value => setField('behavior', value)} />
  </div>
}
