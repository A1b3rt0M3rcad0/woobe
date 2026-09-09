import { useId } from 'react'
import { ChevronDown, CircleHelp, Plus, X } from 'lucide-react'
import { Input } from '@/components/ui/Input'
import { Textarea } from '@/components/ui/Textarea'
import { Button } from '@/components/ui/Button'
import { useAgentEditor } from '@/features/playground/AgentEditorContext'
import { behaviorFields, type AgentBehavior } from '../behavior'
import { cn } from '@/lib/utils'

type ListBehaviorKey = 'responsibilities' | 'allowedBehaviors' | 'disallowedBehaviors'
type TextBehaviorKey = 'objective' | 'operatingInstructions' | 'responseGuidelines' | 'additionalInstructions'

function fieldDefinition(key: keyof AgentBehavior) {
  return behaviorFields.find(field => field.key === key)!
}

function HelpHint({ label, help }: { label: string; help: string }) {
  return (
    <span
      tabIndex={0}
      title={help}
      aria-label={`${label}: ${help}`}
      className="inline-flex cursor-help items-center text-muted transition-colors hover:text-primary-light focus:text-primary-light focus:outline-none"
    >
      <CircleHelp className="h-3.5 w-3.5" aria-hidden="true" />
    </span>
  )
}

function SectionHeading({ index, title, description }: { index: string; title: string; description: string }) {
  return (
    <div className="mb-3">
      <div className="flex items-center gap-2">
        <span className="font-mono text-[9px] text-muted/70">{index}</span>
        <h4 className="font-mono text-[10px] font-semibold uppercase tracking-[0.14em] text-muted">{title}</h4>
      </div>
      <p className="mt-1 pl-6 text-[11px] leading-4 text-muted">{description}</p>
    </div>
  )
}

function ListField({
  behavior,
  onChange,
  fieldKey,
  addLabel,
  numbered = false,
  tone = 'neutral',
}: {
  behavior: AgentBehavior
  onChange: (behavior: AgentBehavior) => void
  fieldKey: ListBehaviorKey
  addLabel: string
  numbered?: boolean
  tone?: 'neutral' | 'allowed' | 'disallowed'
}) {
  const definition = fieldDefinition(fieldKey)
  const items = behavior[fieldKey]
  const updateItem = (index: number, value: string) => onChange({
    ...behavior,
    [fieldKey]: items.map((current, itemIndex) => itemIndex === index ? value : current),
  })
  const removeItem = (index: number) => onChange({
    ...behavior,
    [fieldKey]: items.filter((_, itemIndex) => itemIndex !== index),
  })

  return (
    <div className="space-y-2">
      <div className="flex items-center gap-1.5">
        <span className="text-xs font-medium text-muted">{definition.label}</span>
        <HelpHint label={definition.label} help={definition.help} />
      </div>

      {items.length ? (
        <div className="space-y-1.5">
          {items.map((item, index) => (
            <div key={index} className="flex items-center gap-2 rounded-md border border-border/70 bg-background/30 px-2 py-1.5">
              {numbered ? (
                <span className="w-5 shrink-0 font-mono text-[9px] text-muted/70">{String(index + 1).padStart(2, '0')}</span>
              ) : (
                <span
                  aria-hidden="true"
                  className={cn(
                    'h-1.5 w-1.5 shrink-0 rounded-full',
                    tone === 'allowed' && 'bg-emerald-400/80',
                    tone === 'disallowed' && 'bg-red-400/80',
                    tone === 'neutral' && 'bg-muted/70',
                  )}
                />
              )}
              <div className="min-w-0 flex-1">
                <Input
                  aria-label={`${definition.label} ${index + 1}`}
                  value={item}
                  onChange={event => updateItem(index, event.target.value)}
                  className="h-7 rounded-none border-0 bg-transparent px-0 text-xs shadow-none focus-visible:ring-0"
                />
              </div>
              <Button
                type="button"
                size="sm"
                variant="ghost"
                className="h-7 w-7 shrink-0 p-0 text-muted hover:text-white"
                aria-label={`Remove ${definition.label.toLowerCase()} ${index + 1}`}
                onClick={() => removeItem(index)}
              >
                <X className="h-3.5 w-3.5" />
              </Button>
            </div>
          ))}
        </div>
      ) : (
        <p className="text-[11px] leading-4 text-muted/70">No {definition.label.toLowerCase()} configured.</p>
      )}

      <Button
        type="button"
        size="sm"
        variant="ghost"
        className="h-7 px-1.5 text-[11px] text-muted hover:text-white"
        aria-label={`Add ${definition.label.toLowerCase()}`}
        onClick={() => onChange({ ...behavior, [fieldKey]: [...items, ''] })}
      >
        <Plus className="mr-1 h-3 w-3" />
        {addLabel}
      </Button>
    </div>
  )
}

function GuidanceField({
  id,
  behavior,
  onChange,
  fieldKey,
  description,
}: {
  id: string
  behavior: AgentBehavior
  onChange: (behavior: AgentBehavior) => void
  fieldKey: Exclude<TextBehaviorKey, 'objective'>
  description: string
}) {
  const definition = fieldDefinition(fieldKey)
  const value = behavior[fieldKey]
  const configured = value.trim().length > 0

  return (
    <details className="group border-t border-border/70 first:border-t-0">
      <summary className="flex cursor-pointer list-none items-center justify-between gap-3 py-3 [&::-webkit-details-marker]:hidden">
        <div className="min-w-0">
          <div className="flex items-center gap-1.5">
            <span className="text-xs font-medium text-muted">{definition.label}</span>
            <HelpHint label={definition.label} help={definition.help} />
          </div>
          <p className="mt-0.5 text-[11px] leading-4 text-muted/70">{description}</p>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          <span className={cn('font-mono text-[9px]', configured ? 'text-primary-light' : 'text-muted/60')}>
            {configured ? 'Configured' : 'Not configured'}
          </span>
          <ChevronDown className="h-3.5 w-3.5 text-muted transition-transform group-open:rotate-180" />
        </div>
      </summary>
      <div className="pb-4">
        <label className="sr-only" htmlFor={`${id}-${fieldKey}`}>{definition.label}</label>
        <Textarea
          id={`${id}-${fieldKey}`}
          aria-label={definition.label}
          value={value}
          onChange={event => onChange({ ...behavior, [fieldKey]: event.target.value })}
          rows={fieldKey === 'operatingInstructions' || fieldKey === 'additionalInstructions' ? 5 : 4}
          className="min-h-0 resize-y text-xs leading-5"
        />
      </div>
    </details>
  )
}

export function AgentBehaviorFields({ behavior, onChange }: { behavior: AgentBehavior; onChange: (behavior: AgentBehavior) => void }) {
  const id = useId()
  const objective = fieldDefinition('objective')

  return (
    <section aria-label="Behavior" className="space-y-6">
      <div>
        <h3 className="text-sm font-semibold text-white">Behavior</h3>
        <p className="mt-1 text-xs leading-5 text-muted">Define the operating behavior of this Agent.</p>
      </div>

      <section aria-label="Purpose">
        <SectionHeading index="01" title="Purpose" description="Define the primary outcome this Agent should pursue." />
        <div className="space-y-1.5 pl-0 sm:pl-6">
          <div className="flex items-center gap-1.5">
            <label htmlFor={`${id}-objective`} className="text-xs font-medium text-muted">{objective.label}</label>
            <HelpHint label={objective.label} help={objective.help} />
          </div>
          <Textarea
            id={`${id}-objective`}
            value={behavior.objective}
            onChange={event => onChange({ ...behavior, objective: event.target.value })}
            rows={4}
            className="min-h-0 resize-y text-xs leading-5"
          />
        </div>
      </section>

      <section aria-label="Boundaries" className="border-t border-border/70 pt-5">
        <SectionHeading index="02" title="Boundaries" description="Make responsibilities and behavioral limits explicit." />
        <div className="space-y-5 pl-0 sm:pl-6">
          <ListField behavior={behavior} onChange={onChange} fieldKey="responsibilities" addLabel="Add responsibility" numbered />
          <ListField behavior={behavior} onChange={onChange} fieldKey="allowedBehaviors" addLabel="Add behavior" tone="allowed" />
          <ListField behavior={behavior} onChange={onChange} fieldKey="disallowedBehaviors" addLabel="Add behavior" tone="disallowed" />
        </div>
      </section>

      <section aria-label="Guidance" className="border-t border-border/70 pt-5">
        <SectionHeading index="03" title="Guidance" description="Keep detailed execution and response guidance available without dominating the editor." />
        <div className="pl-0 sm:pl-6">
          <GuidanceField id={id} behavior={behavior} onChange={onChange} fieldKey="operatingInstructions" description="Specific guidance used while executing tasks." />
          <GuidanceField id={id} behavior={behavior} onChange={onChange} fieldKey="responseGuidelines" description="Tone, structure and presentation expectations." />
          <GuidanceField id={id} behavior={behavior} onChange={onChange} fieldKey="additionalInstructions" description="Additional guidance, including instructions preserved from legacy Agents." />
        </div>
      </section>
    </section>
  )
}

export function AgentBehaviorSettings() {
  const { state, setField } = useAgentEditor()
  return <div className="p-4"><AgentBehaviorFields behavior={state.behavior} onChange={value => setField('behavior', value)} /></div>
}
